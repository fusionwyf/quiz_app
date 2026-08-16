"""备份/恢复测试（HTTP seam + 备份服务的文件操作直测）"""
import json
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

import api.services.backup as backup_service
from api.models import AppSetting, Question, QuestionBank


def _seed_data(client: TestClient, session: Session) -> dict:
    """造一套完整数据：题库 + 题目 + 错题 + 答题记录 + 设置（含 API Key）"""
    resp = client.post("/banks/create?name=备份测试库")
    bank_id = resp.json()["id"]
    client.post(
        "/questions",
        json={
            "bank_id": bank_id,
            "type": "single",
            "content": "备份题",
            "options": {"A": "a", "B": "b"},
            "answer": ["A"],
        },
    )
    sid = client.post(f"/session/start?bank_id={bank_id}").json()["id"]
    qid = client.get(f"/session/{sid}/current").json()["id"]
    client.post(
        f"/session/{sid}/answer",
        json={"question_id": qid, "user_choices": ["B"]},
    )  # 答错 → 错题 + 记录
    client.put("/llm/config", json={"provider": "openai", "api_key": "sk-secret"})
    client.put("/mistakes/master-threshold", json={"value": 3})
    return {"bank_id": bank_id, "question_id": qid}


def test_backup_roundtrip_restores_everything(client, session):
    seeds = _seed_data(client, session)

    payload = client.post("/backup").json()

    # 备份不含 API Key，含其他设置
    setting_keys = [s["key"] for s in payload["data"]["settings"]]
    assert "LLM_API_KEY" not in setting_keys
    assert "MISTAKE_MASTER_THRESHOLD" in setting_keys
    assert payload["format"] == "quiz-helper-backup"

    # 清空（删库级联清掉题目/错题/记录）
    assert client.delete(f"/banks/{seeds['bank_id']}").status_code == 200
    assert client.get("/mistakes").json()["mistakes"] == []

    # 恢复
    resp = client.post("/backup/restore", json=payload)
    assert resp.status_code == 200
    counts = resp.json()["restored"]
    assert counts["banks"] == 1 and counts["questions"] == 1
    assert counts["mistakes"] == 1 and counts["records"] == 1

    # 数据完整：ID 保留、错题连对字段在、阈值恢复、API Key 保留本机值
    bank = session.exec(select(QuestionBank)).one()
    assert bank.id == seeds["bank_id"]
    mistakes = client.get("/mistakes").json()["mistakes"]
    assert mistakes[0]["question_id"] == seeds["question_id"]
    assert mistakes[0]["consecutive_correct"] == 0
    assert client.get("/mistakes/master-threshold").json()["threshold"] == 3
    cfg = client.get("/llm/config").json()
    assert cfg["api_key_set"] is True  # 本机 Key 未被清掉


def test_restore_old_backup_defaults_new_fields(client, session):
    """旧版本备份（mistake 无连对字段）恢复后取默认值"""
    old_payload = {
        "format": "quiz-helper-backup",
        "format_version": 1,
        "data": {
            "banks": [{"id": 1, "name": "旧库", "created_at": "2026-01-01T00:00:00"}],
            "questions": [
                {
                    "id": 99,
                    "bank_id": 1,
                    "type": "single",
                    "content": "旧题",
                    "options": None,
                    "answer": ["A"],
                    "blank_answer": None,
                    "score": 1.0,
                    "created_at": "2026-01-01T00:00:00",
                }
            ],
            "mistakes": [
                {
                    "id": 1,
                    "bank_id": 1,
                    "question_id": 99,
                    "wrong_count": 2,
                    "last_wrong_at": "2026-01-01T00:00:00",
                    # 无 consecutive_correct
                }
            ],
            "records": [],
            "settings": [],
        },
    }
    resp = client.post("/backup/restore", json=old_payload)
    assert resp.status_code == 200
    mistakes = client.get("/mistakes").json()["mistakes"]
    assert len(mistakes) == 1
    assert mistakes[0]["consecutive_correct"] == 0


def test_restore_rejects_invalid_payload(client):
    assert client.post("/backup/restore", json={"foo": 1}).status_code == 400
    assert client.post("/backup/restore", json=[1, 2]).status_code == 400


def test_auto_backup_daily_once_and_rotation(tmp_path, monkeypatch, client, session):
    _seed_data(client, session)
    monkeypatch.setattr(backup_service, "AUTO_BACKUP_DIR", tmp_path)

    # 今日首次：生成；同日再调：跳过
    created = backup_service.maybe_daily_backup(session)
    assert created is not None and created.exists()
    assert backup_service.maybe_daily_backup(session) is None

    # 造 9 天历史 → 只保留最近 7 份
    for i in range(2, 11):
        day = datetime(2026, 1, i)
        path = backup_service.auto_backup_path(day)
        path.write_text("{}", encoding="utf-8")
    backup_service.maybe_daily_backup(session)

    backups = backup_service.list_auto_backups()
    assert len(backups) == 7
    assert backups[0]["date"] > backups[-1]["date"]  # 新的在前

    # 每个条目含文件名与大小
    assert backups[0]["size_bytes"] > 0
    assert "filename" in backups[0]


def test_restore_from_auto_backup(client, session, tmp_path, monkeypatch):
    _seed_data(client, session)
    monkeypatch.setattr(backup_service, "AUTO_BACKUP_DIR", tmp_path)
    backup_service.maybe_daily_backup(session)
    filename = backup_service.list_auto_backups()[0]["filename"]

    # 清空后从自动备份恢复
    for bank in session.exec(select(QuestionBank)).all():
        session.delete(bank)
    session.commit()

    resp = client.post(f"/backup/restore/auto/{filename}")
    assert resp.status_code == 200
    assert len(client.get("/banks").json()) == 1

    # 非法文件名（路径穿越/任意名）拒绝
    assert client.post("/backup/restore/auto/..%2Fevil.json").status_code in (400, 404)
    assert client.post("/backup/restore/auto/auto-99999999.json").status_code == 400


def test_backup_list_endpoint(client, tmp_path, monkeypatch):
    monkeypatch.setattr(backup_service, "AUTO_BACKUP_DIR", tmp_path)
    resp = client.get("/backup/list")
    assert resp.status_code == 200
    assert resp.json() == {"backups": []}
