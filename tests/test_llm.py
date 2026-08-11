"""
LLM 智能整理模块（api/llm.py）单元测试

不依赖真实 LLM：配置解析、文本预处理逻辑通过纯函数测试，
LLM 调用路径在端点测试中通过 monkeypatch 覆盖。
"""
import pytest

import api.llm as llm


# ======================================================
# 配置与状态
# ======================================================


def test_config_defaults(monkeypatch):
    """默认配置：provider=none，端点指向 Ollama"""
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    cfg = llm.get_llm_config()
    assert cfg["provider"] == "none"
    assert cfg["base_url"] == "http://localhost:11434/v1"
    assert cfg["model"] == "qwen2.5:3b"


def test_config_from_env(monkeypatch):
    """环境变量覆盖配置"""
    monkeypatch.setenv("LLM_PROVIDER", "OpenAI")
    monkeypatch.setenv("LLM_BASE_URL", "https://api.example.com/v1/")
    monkeypatch.setenv("LLM_MODEL", "gpt-4o-mini")
    cfg = llm.get_llm_config()
    assert cfg["provider"] == "openai"  # 归一化为小写
    assert cfg["base_url"] == "https://api.example.com/v1"  # 去除尾部斜杠
    assert cfg["model"] == "gpt-4o-mini"


def test_status_disabled_by_default(monkeypatch):
    """默认未启用"""
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    status = llm.get_llm_status()
    assert status == {
        "provider": "none",
        "enabled": False,
        "model": "qwen2.5:3b",
    }


def test_status_enabled_openai(monkeypatch):
    """openai provider 启用，model 取 LLM_MODEL"""
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_MODEL", "qwen2.5:7b")
    status = llm.get_llm_status()
    assert status["enabled"] is True
    assert status["model"] == "qwen2.5:7b"


def test_status_enabled_local(monkeypatch):
    """local provider 启用，model 展示 GGUF 路径"""
    monkeypatch.setenv("LLM_PROVIDER", "local")
    monkeypatch.setenv("LOCAL_LLM_MODEL_PATH", "models/qwen2.5-3b.gguf")
    status = llm.get_llm_status()
    assert status["enabled"] is True
    assert status["model"] == "models/qwen2.5-3b.gguf"


# ======================================================
# 文本预处理
# ======================================================


def test_strip_code_fences_with_fence():
    """剥离 markdown 代码围栏"""
    raw = "```txt\n题目：1+1=?\n类型：single\n```"
    assert llm.strip_code_fences(raw) == "题目：1+1=?\n类型：single"


def test_strip_code_fences_without_fence():
    """无围栏时仅去除首尾空白"""
    raw = "\n题目：1+1=?\n类型：single\n"
    assert llm.strip_code_fences(raw) == "题目：1+1=?\n类型：single"


def test_truncate_input():
    """超长输入截断到上限"""
    text = "x" * (llm.MAX_LLM_INPUT_CHARS + 500)
    assert len(llm.truncate_input(text)) == llm.MAX_LLM_INPUT_CHARS


# ======================================================
# normalize 入口
# ======================================================


def test_normalize_raises_when_disabled(monkeypatch):
    """未启用时 normalize 抛出 RuntimeError（调用方捕获后回退）"""
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    with pytest.raises(RuntimeError, match="未启用"):
        llm.normalize_quiz_text("1. 题目 A. 选项")


def test_normalize_openai_strips_fences(monkeypatch):
    """openai 模式：调用 _chat_openai 并剥离围栏"""
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setattr(
        llm, "_chat_openai", lambda cfg, messages: "```\n题目：X\n类型：single\n```"
    )
    result = llm.normalize_quiz_text("任意原文")
    assert result == "题目：X\n类型：single"


def test_normalize_local_missing_dependency(monkeypatch):
    """local 模式未安装 llama-cpp-python 时报清晰错误"""
    monkeypatch.setenv("LLM_PROVIDER", "local")
    monkeypatch.setattr(llm, "_local_model", None)

    class FakeLoader:
        def __call__(self, cfg):
            raise RuntimeError(
                "LLM_PROVIDER=local 需要安装 llama-cpp-python，请执行: uv sync --extra llm"
            )

    monkeypatch.setattr(llm, "_get_local_model", FakeLoader())
    with pytest.raises(RuntimeError, match="llama-cpp-python"):
        llm.normalize_quiz_text("任意原文")
