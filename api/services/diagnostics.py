# 本地日志与诊断包（spec P1）。
# 约定：
# - 后端与桌面壳各自写滚动日志到应用数据目录 logs/（backend.log / shell.log）
# - 日志不记录请求体（题目内容）与 LLM API Key 明文——只记级别、路径、异常栈
# - 诊断包 = logs/ 全部日志 + 版本/环境信息 的 zip，用户自行附到 Issue
import io
import json
import logging
import platform
import subprocess
import sys
import zipfile
from datetime import datetime, UTC
from logging.handlers import RotatingFileHandler
from pathlib import Path

from api.models import DATA_DIR

LOG_DIR = DATA_DIR / "logs"
BACKEND_LOG = LOG_DIR / "backend.log"
MAX_BYTES = 2 * 1024 * 1024
BACKUP_COUNT = 3

_attached = False


def configure_logging() -> None:
    """给根 logger 挂滚动文件 handler（幂等，重复调用不会叠加 handler）。

    挂根 logger 的目的：路由未捕获异常经 uvicorn 的 error logger 冒泡，
    会落入 backend.log，桌面版用户无控制台也能事后排查。"""
    global _attached
    if _attached:
        return
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        BACKEND_LOG, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT, encoding="utf-8"
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    _attached = True
    root.info(
        "logging ready: python=%s platform=%s db=%s",
        sys.version.split()[0],
        platform.platform(),
        DATA_DIR / "database.db",
    )


def log_startup(version: str) -> None:
    logging.getLogger(__name__).info("app startup: version=%s", version)


def diagnostics_info(app_version: str) -> dict:
    return {
        "log_dir": str(LOG_DIR),
        "backend_log": str(BACKEND_LOG),
        "app_version": app_version,
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
    }


def open_log_folder() -> None:
    """用系统文件管理器打开日志目录"""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        import os

        os.startfile(LOG_DIR)  # noqa: S606 - 打开用户自己的日志目录
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(LOG_DIR)])
    else:
        subprocess.Popen(["xdg-open", str(LOG_DIR)])


def export_diagnostics_zip(app_version: str) -> tuple[bytes, str]:
    """打包诊断包：logs/ 全部日志 + 版本/环境信息。返回 (zip 字节, 文件名)。"""
    info = diagnostics_info(app_version)
    info["exported_at"] = datetime.now(UTC).isoformat()

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("info.json", json.dumps(info, ensure_ascii=False, indent=2))
        if LOG_DIR.exists():
            for path in sorted(LOG_DIR.iterdir()):
                if path.is_file() and path.suffix in (".log", ".log.1", ".log.2", ".log.3"):
                    try:
                        zf.writestr(path.name, path.read_text(encoding="utf-8", errors="replace"))
                    except OSError:
                        continue  # 日志正被写/轮转，跳过该份
    filename = f"quiz-diagnostics-{datetime.now():%Y%m%d-%H%M%S}.zip"
    return buf.getvalue(), filename
