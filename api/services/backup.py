# 全库备份/恢复（spec P1）。备份格式：
# {"format": "quiz-helper-backup", "format_version": 1, "schema_version": N,
#  "created_at": iso, "data": {banks|questions|mistakes|records|settings: [...]}}
# 约定：
# - LLM API Key 不随备份带走（隐私默认），恢复时保留本机已存 Key
# - 练习会话（QuizSession）为临时状态，不入备份；答题记录保留其 session_id 作历史引用
import json
import re
from datetime import datetime, UTC
from pathlib import Path

from sqlmodel import Session, select

from api.migrations import SCHEMA_VERSION
from api.models import (
    DATA_DIR,
    AppSetting,
    ExamRecord,
    Mistake,
    Question,
    QuestionBank,
    QuizSession,
)

BACKUP_FORMAT = "quiz-helper-backup"
BACKUP_FORMAT_VERSION = 1
AUTO_BACKUP_DIR = DATA_DIR / "backups"
AUTO_BACKUP_KEEP = 7
_AUTO_FILENAME_RE = re.compile(r"^auto-\d{8}\.json$")
# 备份排除的设置键（敏感信息不落备份文件）
EXCLUDED_SETTING_KEYS = {"LLM_API_KEY"}


def _dump_all(session: Session) -> dict:
    def rows(model, order_by):
        return [r.model_dump(mode="json") for r in session.exec(select(model).order_by(order_by)).all()]

    return {
        "banks": rows(QuestionBank, QuestionBank.id),
        "questions": rows(Question, Question.id),
        "mistakes": rows(Mistake, Mistake.id),
        "records": rows(ExamRecord, ExamRecord.id),
        "settings": [
            s.model_dump(mode="json")
            for s in session.exec(select(AppSetting).order_by(AppSetting.key)).all()
            if s.key not in EXCLUDED_SETTING_KEYS
        ],
    }


def create_backup(session: Session) -> dict:
    """生成全库备份 payload（调用方负责文件落盘/传输）"""
    return {
        "format": BACKUP_FORMAT,
        "format_version": BACKUP_FORMAT_VERSION,
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "data": _dump_all(session),
    }


def validate_backup(payload: dict) -> dict:
    """校验备份格式，返回 data 部分；非法抛 ValueError（路由转 400）"""
    if (
        not isinstance(payload, dict)
        or payload.get("format") != BACKUP_FORMAT
        or not isinstance(payload.get("data"), dict)
    ):
        raise ValueError("不是有效的刷题助手备份文件")
    return payload["data"]


def _insert_models(session: Session, model, rows: list[dict], keep_fields: tuple):
    dt_fields = {"created_at", "last_wrong_at"}
    for row in rows:
        kwargs = {}
        for k, v in row.items():
            if k not in keep_fields:
                continue
            # model_dump(mode="json") 把时间序列化成了 ISO 字符串，回插前还原
            if k in dt_fields and isinstance(v, str):
                v = datetime.fromisoformat(v)
            kwargs[k] = v
        session.add(model(**kwargs))


def restore_backup(session: Session, payload: dict) -> dict:
    """清空并恢复全部数据（调用方负责事务提交与覆盖确认）。

    旧版本备份缺新字段（如连对计数）时取模型默认值。"""
    data = validate_backup(payload)

    # 本机已存的排除键（如 LLM API Key）先留档，恢复后回填（备份不带走敏感信息）
    kept_settings = [
        s for s in session.exec(select(AppSetting)).all()
        if s.key in EXCLUDED_SETTING_KEYS
    ]

    # 清空现有数据（含练习会话）
    for model in (ExamRecord, Mistake, QuizSession, Question, QuestionBank, AppSetting):
        for row in session.exec(select(model)).all():
            session.delete(row)

    _insert_models(session, QuestionBank, data.get("banks", []),
                   ("id", "name", "created_at"))
    _insert_models(session, Question, data.get("questions", []),
                   ("id", "bank_id", "type", "content", "options", "answer",
                    "blank_answer", "score", "created_at"))
    _insert_models(session, Mistake, data.get("mistakes", []),
                   ("id", "bank_id", "question_id", "wrong_count",
                    "last_wrong_at", "consecutive_correct"))
    _insert_models(session, ExamRecord, data.get("records", []),
                   ("id", "session_id", "question_id", "user_answer",
                    "is_correct", "created_at"))
    # 设置：备份排除的键（如 API Key）保留本机现状
    for row in data.get("settings", []):
        key = row.get("key")
        if key and key not in EXCLUDED_SETTING_KEYS:
            session.add(AppSetting(key=key, value=row.get("value", "")))
    for s in kept_settings:
        session.add(AppSetting(key=s.key, value=s.value))

    session.commit()
    return {name: len(data.get(name, [])) for name in
            ("banks", "questions", "mistakes", "records", "settings")}


# ===== 每日自动备份 =====


def auto_backup_path(day: datetime) -> Path:
    return AUTO_BACKUP_DIR / f"auto-{day:%Y%m%d}.json"


def maybe_daily_backup(session: Session) -> Path | None:
    """每日首次调用生成一份自动备份，滚动保留最近 AUTO_BACKUP_KEEP 份"""
    AUTO_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    today = auto_backup_path(datetime.now())
    created = None
    if not today.exists():
        payload = create_backup(session)
        today.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        created = today

    # 无论本次是否新建，都修剪到保留上限（历史文件可能超量）
    backups = sorted(AUTO_BACKUP_DIR.glob("auto-*.json"))
    for old in backups[:-AUTO_BACKUP_KEEP]:
        old.unlink(missing_ok=True)
    return created


def list_auto_backups() -> list[dict]:
    if not AUTO_BACKUP_DIR.exists():
        return []
    result = []
    for path in sorted(AUTO_BACKUP_DIR.glob("auto-*.json"), reverse=True):
        try:
            day = datetime.strptime(path.stem, "auto-%Y%m%d")
        except ValueError:
            continue
        result.append({
            "filename": path.name,
            "date": f"{day:%Y-%m-%d}",
            "size_bytes": path.stat().st_size,
        })
    return result


def load_auto_backup(filename: str) -> dict:
    """读取自动备份文件内容；文件名非法或不存在抛 ValueError"""
    if not _AUTO_FILENAME_RE.match(filename):
        raise ValueError("非法的备份文件名")
    path = AUTO_BACKUP_DIR / filename
    if not path.exists():
        raise ValueError("备份文件不存在")
    return json.loads(path.read_text(encoding="utf-8"))
