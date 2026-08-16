"""
LLM 智能整理配置测试：
- 分块工具函数（split_into_chunks / normalize_quiz_text_chunked）
- 配置解析（resolve_llm_config：数据库覆盖环境变量）
- /llm/config GET/PUT、/llm/test、/llm/status 路由
- 导入接口 force_llm 强制整理与分块行为
"""
import httpx
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

import api.llm as llm
from api.models import AppSetting, Question, QuestionBank


def create_test_bank(session: Session, name: str = "LLM 配置测试题库") -> QuestionBank:
    bank = QuestionBank(name=name)
    session.add(bank)
    session.commit()
    session.refresh(bank)
    return bank


def upload(
    client: TestClient,
    bank_id: int,
    filename: str,
    data: bytes,
    force_llm: bool = False,
):
    return client.post(
        f"/banks/{bank_id}/import/file",
        params={"force_llm": "true"} if force_llm else None,
        files={"file": (filename, data, "application/octet-stream")},
    )


# ======================================================
# split_into_chunks / normalize_quiz_text_chunked
# ======================================================


def test_split_single_chunk():
    text = "题目：1+1=?\n类型：judge\n答案：[\"对\"]"
    assert llm.split_into_chunks(text) == [text]


def test_split_merges_small_paragraphs():
    para = "x" * 3000
    chunks = llm.split_into_chunks("\n\n".join([para, para, para]))
    # 3000+2+3000=6002 ≤ 8000 可合并，第三段放不下
    assert len(chunks) == 2
    assert all(len(c) <= llm.MAX_LLM_INPUT_CHARS for c in chunks)


def test_split_oversized_paragraph_hard_cut():
    total = llm.MAX_LLM_INPUT_CHARS * 2 + 100
    chunks = llm.split_into_chunks("x" * total)
    assert all(len(c) <= llm.MAX_LLM_INPUT_CHARS for c in chunks)
    assert sum(len(c) for c in chunks) == total


def test_split_empty_text():
    assert llm.split_into_chunks("   \n\n  ") == []


def test_normalize_chunked_joins_results(monkeypatch):
    calls = []

    def fake_normalize(text, cfg=None):
        calls.append(text)
        return f"块{len(calls)}"

    monkeypatch.setattr(llm, "normalize_quiz_text", fake_normalize)
    text = "\n\n".join(["x" * 6000, "y" * 6000])  # 两个块
    assert llm.normalize_quiz_text_chunked(text) == "块1\n\n块2"
    assert len(calls) == 2


def test_normalize_chunked_over_limit_raises(monkeypatch):
    monkeypatch.setattr(llm, "normalize_quiz_text", lambda text, cfg=None: "ok")
    text = "\n\n".join(["x" * llm.MAX_LLM_INPUT_CHARS] * (llm.MAX_LLM_CHUNKS + 1))
    with pytest.raises(RuntimeError, match="上限"):
        llm.normalize_quiz_text_chunked(text)


# ======================================================
# resolve_llm_config / mask_api_key
# ======================================================


def test_resolve_config_env_fallback(session: Session, monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.setenv("LLM_BASE_URL", "http://env-host:9000/v1/")
    cfg = llm.resolve_llm_config(session)
    assert cfg["provider"] == "none"
    assert cfg["base_url"] == "http://env-host:9000/v1"


def test_resolve_config_db_overrides_env(session: Session, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "none")
    monkeypatch.setenv("LLM_MODEL", "env-model")
    session.add(AppSetting(key="LLM_PROVIDER", value="openai"))
    session.add(AppSetting(key="LLM_BASE_URL", value="https://api.test/v1"))
    session.add(AppSetting(key="LLM_API_KEY", value="sk-test-12345678"))
    session.add(AppSetting(key="LLM_MODEL", value="db-model"))
    session.commit()

    cfg = llm.resolve_llm_config(session)
    assert cfg["provider"] == "openai"
    assert cfg["base_url"] == "https://api.test/v1"
    assert cfg["api_key"] == "sk-test-12345678"
    assert cfg["model"] == "db-model"


def test_resolve_config_empty_db_value_ignored(session: Session, monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "env-model")
    session.add(AppSetting(key="LLM_MODEL", value=""))
    session.commit()
    assert llm.resolve_llm_config(session)["model"] == "env-model"


def test_mask_api_key():
    assert llm.mask_api_key("") == ""
    assert llm.mask_api_key("short") == "****"
    assert llm.mask_api_key("sk-1234567890abcdef") == "sk-****cdef"


# ======================================================
# /llm/config GET/PUT 路由
# ======================================================


def test_get_llm_config_defaults(client: TestClient, monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    data = client.get("/llm/config").json()
    assert data["provider"] == "none"
    assert data["enabled"] is False
    assert data["api_key_set"] is False
    assert data["api_key_masked"] == ""


def test_put_llm_config_persists_and_masks(
    client: TestClient, session: Session, monkeypatch
):
    monkeypatch.setenv("LLM_MODEL", "env-model")
    resp = client.put(
        "/llm/config",
        json={
            "provider": "OpenAI",
            "base_url": "https://api.deepseek.com/v1/",
            "model": "deepseek-chat",
            "api_key": "sk-abcdefghijklmn",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["provider"] == "openai"
    assert data["base_url"] == "https://api.deepseek.com/v1"
    assert data["enabled"] is True
    assert data["api_key_set"] is True
    assert "abcdefghijklmn" not in data["api_key_masked"]

    # Key 明文落库
    assert session.get(AppSetting, "LLM_API_KEY").value == "sk-abcdefghijklmn"

    # /llm/status 反映数据库配置
    status = client.get("/llm/status").json()
    assert status["enabled"] is True
    assert status["model"] == "deepseek-chat"


def test_put_llm_config_empty_key_keeps_stored(
    client: TestClient, session: Session, monkeypatch
):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    client.put("/llm/config", json={"provider": "openai", "api_key": "sk-keepme-123456"})
    resp = client.put("/llm/config", json={"provider": "openai", "api_key": ""})
    assert resp.json()["api_key_set"] is True
    assert session.get(AppSetting, "LLM_API_KEY").value == "sk-keepme-123456"


def test_put_llm_config_empty_model_clears_override(
    client: TestClient, session: Session, monkeypatch
):
    monkeypatch.setenv("LLM_MODEL", "env-model")
    client.put("/llm/config", json={"provider": "openai", "model": "db-model"})
    # 传空 model 清除覆盖 → 回退 env
    resp = client.put("/llm/config", json={"provider": "openai", "model": ""})
    assert resp.json()["model"] == "env-model"
    assert session.get(AppSetting, "LLM_MODEL") is None


def test_put_llm_config_disable_overrides_env(
    client: TestClient, monkeypatch
):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    resp = client.put("/llm/config", json={"provider": "none"})
    assert resp.json()["enabled"] is False
    assert client.get("/llm/status").json()["enabled"] is False


def test_put_llm_config_validation(client: TestClient):
    assert client.put("/llm/config", json={"provider": "local"}).status_code == 400
    resp = client.put("/llm/config", json={"provider": "openai", "base_url": "ftp://x"})
    assert resp.status_code == 400


# ======================================================
# /llm/test 路由
# ======================================================


def test_llm_test_with_saved_config(client: TestClient, monkeypatch):
    client.put(
        "/llm/config",
        json={
            "provider": "openai",
            "base_url": "https://api.test/v1",
            "model": "m1",
            "api_key": "sk-xxxx",
        },
    )
    captured = {}

    def fake_chat(cfg, messages):
        captured["cfg"] = cfg
        return "OK"

    monkeypatch.setattr(llm, "_chat_openai", fake_chat)
    resp = client.post("/llm/test")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["model"] == "m1"
    assert data["reply"] == "OK"
    assert captured["cfg"]["api_key"] == "sk-xxxx"


def test_llm_test_with_body_without_saving(client: TestClient, session: Session, monkeypatch):
    def fake_chat(cfg, messages):
        assert cfg["base_url"] == "https://unsaved/v1"
        assert cfg["model"] == "probe-model"
        return "OK"

    monkeypatch.setattr(llm, "_chat_openai", fake_chat)
    resp = client.post(
        "/llm/test",
        json={"provider": "openai", "base_url": "https://unsaved/v1", "model": "probe-model"},
    )
    assert resp.status_code == 200
    # 测试不落库
    assert session.get(AppSetting, "LLM_BASE_URL") is None


def test_llm_test_connection_error_returns_400(client: TestClient, monkeypatch):
    def fake_chat(cfg, messages):
        raise httpx.ConnectError("boom")

    monkeypatch.setattr(llm, "_chat_openai", fake_chat)
    client.put("/llm/config", json={"provider": "openai"})
    resp = client.post("/llm/test")
    assert resp.status_code == 400
    assert "无法连接" in resp.json()["detail"]


def test_llm_test_disabled_returns_400(client: TestClient, monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    resp = client.post("/llm/test", json={"provider": "none"})
    assert resp.status_code == 400


# ======================================================
# 导入接口：force_llm 与分块
# ======================================================

EXAM_TXT = """1. 直接解析的题目？（单选题）
A. 1
B. 2
答案：A
"""

AI_KEYVALUE = """题目：AI 整理的题目
类型：judge
答案：["对"]
"""

UNPARSEABLE_TXT = "这是一段完全不像题目的文字\n没有任何编号和选项"


def test_import_force_llm_replaces_direct_parse(
    client: TestClient, session: Session, monkeypatch
):
    """文件可直接解析 + force_llm：以 AI 整理结果为准"""
    bank = create_test_bank(session)
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setattr(llm, "normalize_quiz_text", lambda text, cfg=None: AI_KEYVALUE)

    resp = upload(client, bank.id, "exam.txt", EXAM_TXT.encode("utf-8"), force_llm=True)
    assert resp.status_code == 200
    data = resp.json()
    assert data["imported_count"] == 1
    assert data["ai_normalized"] is True
    assert data["ai_error"] is None

    questions = session.exec(select(Question).where(Question.bank_id == bank.id)).all()
    assert len(questions) == 1
    assert questions[0].content == "AI 整理的题目"


def test_import_force_llm_error_falls_back_to_direct(
    client: TestClient, session: Session, monkeypatch
):
    """force 下 LLM 失败：回退直接解析结果并报告 ai_error"""
    bank = create_test_bank(session)
    monkeypatch.setenv("LLM_PROVIDER", "openai")

    def raise_error(text, cfg=None):
        raise RuntimeError("LLM 连接失败")

    monkeypatch.setattr(llm, "normalize_quiz_text", raise_error)

    resp = upload(client, bank.id, "exam.txt", EXAM_TXT.encode("utf-8"), force_llm=True)
    assert resp.status_code == 200
    data = resp.json()
    assert data["imported_count"] == 1
    assert data["ai_normalized"] is False
    assert "LLM 连接失败" in data["ai_error"]
    assert session.exec(select(Question)).all()[0].content.startswith("直接解析的题目")


def test_import_force_llm_disabled_returns_400(
    client: TestClient, session: Session, monkeypatch
):
    """LLM 未启用时 force_llm 返回 400"""
    bank = create_test_bank(session)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)

    resp = upload(client, bank.id, "exam.txt", EXAM_TXT.encode("utf-8"), force_llm=True)
    assert resp.status_code == 400


def test_import_llm_fallback_with_db_config(
    client: TestClient, session: Session, monkeypatch
):
    """仅数据库配置（无环境变量）也能触发兜底：走 resolve_llm_config 路径"""
    bank = create_test_bank(session)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    client.put(
        "/llm/config",
        json={"provider": "openai", "base_url": "https://api.test/v1", "model": "m1"},
    )

    def fake_chat(cfg, messages):
        assert cfg["base_url"] == "https://api.test/v1"
        assert cfg["model"] == "m1"
        return AI_KEYVALUE

    monkeypatch.setattr(llm, "_chat_openai", fake_chat)
    resp = upload(client, bank.id, "messy.txt", UNPARSEABLE_TXT.encode("utf-8"))
    assert resp.status_code == 200
    data = resp.json()
    assert data["imported_count"] == 1
    assert data["ai_normalized"] is True


def test_import_long_text_chunked_normalize(
    client: TestClient, session: Session, monkeypatch
):
    """超过单块上限的文本分块整理：逐块调用且结果合并解析"""
    bank = create_test_bank(session)
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    calls = []

    def fake_normalize(text, cfg=None):
        calls.append(text)
        return f"题目：块{len(calls)}的题目\n类型：judge\n答案：[\"对\"]"

    monkeypatch.setattr(llm, "normalize_quiz_text", fake_normalize)

    # 两个 5000 字符段：5000+2+5000 > 8000，各成一块
    long_text = "乱" * 5000 + "\n\n" + "乱" * 5000
    resp = upload(client, bank.id, "long.txt", long_text.encode("utf-8"))
    assert resp.status_code == 200
    data = resp.json()
    assert len(calls) == 2
    assert data["ai_normalized"] is True
    assert data["imported_count"] == 2

    contents = [q.content for q in session.exec(select(Question)).all()]
    assert "块1的题目" in contents
    assert "块2的题目" in contents


# ======================================================
# 主测试运行
# ======================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
