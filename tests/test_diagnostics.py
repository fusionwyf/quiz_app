"""本地日志与诊断包测试"""
import io
import json
import logging
import logging.handlers
import os
import zipfile

import pytest

import api.services.diagnostics as diagnostics


@pytest.fixture(name="tmp_logs")
def tmp_logs_fixture(tmp_path, monkeypatch):
    """把日志目录指到临时目录并重置已挂载标记，避免写真实用户目录"""
    log_dir = tmp_path / "logs"
    monkeypatch.setattr(diagnostics, "LOG_DIR", log_dir)
    monkeypatch.setattr(diagnostics, "BACKEND_LOG", log_dir / "backend.log")
    monkeypatch.setattr(diagnostics, "_attached", False)
    return log_dir


def test_configure_logging_idempotent_writes_file(tmp_logs):
    diagnostics.configure_logging()
    diagnostics.configure_logging()  # 重复调用不叠加 handler

    root = logging.getLogger()
    file_handlers = [
        h for h in root.handlers
        if isinstance(h, logging.handlers.RotatingFileHandler)
        and str(getattr(h, "baseFilename", "")) == str(tmp_logs / "backend.log")
    ]
    assert len(file_handlers) == 1

    logging.getLogger("test.diagnostics").info("诊断测试日志行")
    file_handlers[0].flush()
    content = (tmp_logs / "backend.log").read_text(encoding="utf-8")
    assert "诊断测试日志行" in content
    # 清理本次测试挂的 handler，避免污染其他用例
    root.removeHandler(file_handlers[0])


def test_diagnostics_info_endpoint(client):
    resp = client.get("/diagnostics/info")
    assert resp.status_code == 200
    data = resp.json()
    assert "log_dir" in data
    assert "app_version" in data
    assert "platform" in data


def test_export_diagnostics_zip_contains_logs_and_info(client, tmp_logs):
    tmp_logs.mkdir(parents=True, exist_ok=True)
    (tmp_logs / "backend.log").write_text("backend 日志内容", encoding="utf-8")
    (tmp_logs / "shell.log").write_text("shell 日志内容", encoding="utf-8")

    resp = client.get("/diagnostics/export")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/zip")
    assert "quiz-diagnostics-" in resp.headers["content-disposition"]

    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        names = zf.namelist()
        assert "info.json" in names
        assert "backend.log" in names
        assert "shell.log" in names
        info = json.loads(zf.read("info.json"))
        assert "app_version" in info and "platform" in info


def test_open_log_folder(tmp_logs, monkeypatch):
    tmp_logs.mkdir(parents=True, exist_ok=True)
    called = {}
    # os 在 win32 分支内延迟导入，直接 patch 标准库 os 模块
    monkeypatch.setattr(
        os, "startfile", lambda p: called.setdefault("path", p), raising=False
    )
    if diagnostics.sys.platform == "win32":
        diagnostics.open_log_folder()
        assert called["path"] == tmp_logs
