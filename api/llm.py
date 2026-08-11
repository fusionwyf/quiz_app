# llm.py
"""
LLM 智能整理模块（可选功能）

题库文件导入解析器识别不出题目时，调用 LLM 将原文整理为标准键值格式
（题目：/类型：/选项：JSON/答案：JSON）后重新解析，作为自动兜底。

支持两种 provider（环境变量配置，默认关闭）：
- openai：任意 OpenAI 兼容端点（Ollama / 第三方 API / llama.cpp server / LM Studio）
- local：llama-cpp-python 进程内加载 GGUF 模型（可选安装，便于 Tauri 打包）

纯模块，不依赖 DB 与 HTTP 路由，便于单元测试。
"""
import os
import re

import httpx

# 送入 LLM 的最大字符数（小模型上下文有限，超出截断）
MAX_LLM_INPUT_CHARS = 8000
# LLM 调用超时（秒）
LLM_TIMEOUT_SECONDS = 120.0
# openai 模式默认端点（Ollama 的 OpenAI 兼容地址）
DEFAULT_OPENAI_BASE_URL = "http://localhost:11434/v1"
DEFAULT_MODEL = "qwen2.5:3b"

# 归一化输出的目标格式提示词（与 parsers.parse_keyvalue_block 严格对齐）
SYSTEM_PROMPT = """你是题库格式化助手。把用户提供的题目文本整理为标准键值格式，只输出整理后的结果，不要输出任何解释、前后缀或 markdown 代码块。

每道题的格式（题目之间用一个空行分隔）：
题目：题干内容
类型：single
选项：{"A": "选项内容", "B": "选项内容"}
答案：["B"]
分数：1.0

规则：
1. 类型只能是 single（单选）、multi（多选）、judge（判断）、blank（填空）之一
2. 选项为标准 JSON 对象，仅 single / multi 需要；judge / blank 不输出选项行
3. 答案为标准 JSON 数组：single / multi 用大写字母如 ["B"] 或 ["A","C"]；judge 用 ["对"] 或 ["错"]；blank 用答案文本如 ["北京"]
4. 分数可省略（默认 1.0）
5. 不得改动题干与选项的原文内容，只调整格式
6. 无法识别为题目的内容（标题、说明文字等）直接忽略
"""

# local 模式模型单例（懒加载）
_local_model = None


def get_llm_config() -> dict:
    """读取环境变量配置"""
    return {
        "provider": os.environ.get("LLM_PROVIDER", "none").strip().lower(),
        "base_url": os.environ.get("LLM_BASE_URL", DEFAULT_OPENAI_BASE_URL).rstrip("/"),
        "api_key": os.environ.get("LLM_API_KEY", ""),
        "model": os.environ.get("LLM_MODEL", DEFAULT_MODEL),
        "local_model_path": os.environ.get("LOCAL_LLM_MODEL_PATH", ""),
    }


def get_llm_status() -> dict:
    """LLM 可用状态（供 GET /llm/status 与导入兜底判断）"""
    cfg = get_llm_config()
    enabled = cfg["provider"] in ("openai", "local")
    model = cfg["local_model_path"] if cfg["provider"] == "local" else cfg["model"]
    return {"provider": cfg["provider"], "enabled": enabled, "model": model}


def strip_code_fences(text: str) -> str:
    """剥离 LLM 输出中的 markdown 代码围栏"""
    m = re.search(r"```[^\n]*\n(.*?)```", text, flags=re.S)
    if m:
        return m.group(1).strip()
    return text.strip()


def truncate_input(text: str) -> str:
    """限制送入 LLM 的文本长度"""
    return text[:MAX_LLM_INPUT_CHARS]


def _chat_openai(cfg: dict, messages: list[dict]) -> str:
    """调用 OpenAI 兼容的 /chat/completions 端点"""
    headers = {"Content-Type": "application/json"}
    if cfg["api_key"]:
        headers["Authorization"] = f"Bearer {cfg['api_key']}"
    resp = httpx.post(
        f"{cfg['base_url']}/chat/completions",
        json={
            "model": cfg["model"],
            "messages": messages,
            "temperature": 0,
        },
        headers=headers,
        timeout=LLM_TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"] or ""


def _get_local_model(cfg: dict):
    """懒加载 local 模式模型单例"""
    global _local_model
    if _local_model is None:
        try:
            from llama_cpp import Llama
        except ImportError as e:
            raise RuntimeError(
                "LLM_PROVIDER=local 需要安装 llama-cpp-python，请执行: uv sync --extra llm"
            ) from e
        path = cfg["local_model_path"]
        if not path or not os.path.exists(path):
            raise RuntimeError(f"LOCAL_LLM_MODEL_PATH 未设置或文件不存在: {path!r}")
        _local_model = Llama(model_path=path, verbose=False)
    return _local_model


def _chat_local(cfg: dict, messages: list[dict]) -> str:
    """调用进程内 GGUF 模型"""
    model = _get_local_model(cfg)
    result = model.create_chat_completion(messages=messages, temperature=0)
    return result["choices"][0]["message"]["content"] or ""


def normalize_quiz_text(text: str) -> str:
    """
    调用 LLM 将原始题目文本整理为标准键值格式

    未启用 LLM 时抛出 RuntimeError；调用方捕获后回退原解析结果。
    """
    cfg = get_llm_config()
    if cfg["provider"] not in ("openai", "local"):
        raise RuntimeError("LLM 未启用（LLM_PROVIDER 未配置为 openai / local）")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": truncate_input(text)},
    ]

    if cfg["provider"] == "openai":
        content = _chat_openai(cfg, messages)
    else:
        content = _chat_local(cfg, messages)

    return strip_code_fences(content)
