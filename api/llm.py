# llm.py
"""
LLM 智能整理模块（可选功能）

题库文件导入解析器识别不出题目时，调用 LLM 将原文整理为标准键值格式
（题目：/类型：/选项：JSON/答案：JSON）后重新解析，作为自动兜底。

支持两种 provider（默认关闭）：
- openai：任意 OpenAI 兼容端点（Ollama / 第三方 API / llama.cpp server / LM Studio）
- local：llama-cpp-python 进程内加载 GGUF 模型（可选安装，便于 Tauri 打包）

配置来源两级：环境变量为底，AppSetting 表（前端 /llm/config 写入）覆盖同名键。
不依赖 HTTP 路由，便于单元测试。
"""
import os
import re

import httpx
from sqlmodel import Session

from api.models import AppSetting

# 送入 LLM 的最大字符数（小模型上下文有限，单块超出截断；全文按块拆分）
MAX_LLM_INPUT_CHARS = 8000
# LLM 调用超时（秒）
LLM_TIMEOUT_SECONDS = 120.0
# openai 模式默认端点（Ollama 的 OpenAI 兼容地址）
DEFAULT_OPENAI_BASE_URL = "http://localhost:11434/v1"
DEFAULT_MODEL = "qwen2.5:3b"
# 分块整理的块数上限（防止超大文件产生失控的 API 调用费用）
MAX_LLM_CHUNKS = 40

# AppSetting 表中可覆盖 env 的键（字段名 -> 设置键，与同名环境变量对应）
LLM_SETTING_KEYS = {
    "provider": "LLM_PROVIDER",
    "base_url": "LLM_BASE_URL",
    "api_key": "LLM_API_KEY",
    "model": "LLM_MODEL",
}

# 归一化输出的目标格式提示词（与 parsers.parse_keyvalue_block 严格对齐：
# 键名、JSON 合法性、judge 答案对错归一、题号剥离等都是解析器的硬性要求）
SYSTEM_PROMPT = """你是题库整理助手。把用户提供的原始题目文本（可能格式混乱）改写成下面规定的标准键值格式，供程序自动解析入库。只输出改写结果本身，不要任何解释、前言、总结或 markdown 代码块。

【输出格式】
每道题由若干行"键：值"组成，键名只能用：题目、类型、选项、答案、分数。键名后统一用中文冒号"："。题目与题目之间用一个空行分隔。不要添加题号或序号。

题目：题干文本（必须单行写完）
类型：single|multi|judge|blank 四选一
选项：标准 JSON 对象（仅 single / multi 输出此行）
答案：标准 JSON 数组
分数：纯数字（仅当原文明确给出分值时才输出，否则整行省略）

【字段规则】
1. 类型只能取：single（单选）、multi（多选）、judge（判断）、blank（填空）。
2. "题目"必须是每道题的第一行。去掉题干开头的题号（如"1."、"一、"、"（3）"、"第5题："），其余文字保持原文不变（错别字也保留）；填空题保留题干中的下划线或（ ）空位标记。
3. "选项"仅 single / multi 输出，judge / blank 绝对不输出选项行。选项 JSON 的键必须是大写字母 "A"、"B"、"C"、"D"（最多到 "F"），值为选项原文。
4. "答案"规则：
   - single：形如 ["B"]，一个大写字母。
   - multi：形如 ["A","C"]，大写字母、去重、按字母顺序排列。
   - judge：只能是 ["对"] 或 ["错"]。原文的"是/正确/√/T"统一写成"对"，"否/错误/×/F"统一写成"错"。
   - blank：每个空的答案文本按顺序放入数组，如 ["北京"] 或 ["12","31"]。
5. 不要改动、补全、润色题干与选项的文字；不要合并或拆分题目；不要编造原文没有的选项、答案或分数。
6. 原文中的标题、卷首语、答题说明、页码、解析、知识点标签等非题目内容一律忽略，不要输出。
7. 完全没有答案信息的题目、答案为字母但原文没有选项的单选/多选题：整题跳过，不要输出。

【JSON 硬性要求（违反会导致解析失败）】
- "选项"和"答案"必须是合法 JSON：只用英文双引号 \" ，禁止中文引号""''；键与字符串值都必须加引号；不要尾逗号。
- "选项"和"答案"各自必须写在同一行，中间不能换行。
- 值中出现英文双引号时要转义为 \\\"。

【示例输出】
题目：中国的首都是哪座城市？
类型：single
选项：{"A": "上海", "B": "北京", "C": "广州"}
答案：["B"]

题目：下列哪些属于直辖市？
类型：multi
选项：{"A": "北京", "B": "上海", "C": "杭州", "D": "重庆"}
答案：["A", "B", "D"]

题目：光速比声速快。
类型：judge
答案：["对"]

题目：一年有____个季度。
类型：blank
答案：["4"]
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


def resolve_llm_config(session: Session) -> dict:
    """解析最终生效配置：环境变量为底，AppSetting 表非空值覆盖"""
    cfg = get_llm_config()
    for field, setting_key in LLM_SETTING_KEYS.items():
        row = session.get(AppSetting, setting_key)
        if row is not None and row.value != "":
            cfg[field] = row.value
    cfg["provider"] = cfg["provider"].strip().lower()
    cfg["base_url"] = cfg["base_url"].rstrip("/")
    return cfg


def mask_api_key(key: str) -> str:
    """API Key 脱敏展示"""
    if not key:
        return ""
    if len(key) <= 8:
        return "****"
    return f"{key[:3]}****{key[-4:]}"


def get_llm_status(cfg: dict | None = None) -> dict:
    """LLM 可用状态（供 GET /llm/status 与导入兜底判断）"""
    cfg = cfg or get_llm_config()
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


def split_into_chunks(text: str, max_chars: int = MAX_LLM_INPUT_CHARS) -> list[str]:
    """
    按空行分段聚合成不超过 max_chars 的块（题块之间天然以空行分隔，
    尽量不把一道题切到两个块里）；超长单段按字符硬切
    """
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        while len(para) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            chunks.append(para[:max_chars])
            para = para[max_chars:].lstrip()
        if not para:
            continue
        if not current:
            current = para
        elif len(current) + 2 + len(para) <= max_chars:
            current += "\n\n" + para
        else:
            chunks.append(current)
            current = para
    if current:
        chunks.append(current)
    return chunks


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


def normalize_quiz_text(text: str, cfg: dict | None = None) -> str:
    """
    调用 LLM 将原始题目文本整理为标准键值格式

    cfg 为 None 时使用环境变量配置；未启用 LLM 时抛出 RuntimeError，
    调用方捕获后回退原解析结果。
    """
    cfg = cfg or get_llm_config()
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


def normalize_quiz_text_chunked(text: str, cfg: dict | None = None) -> str:
    """
    分块整理长文本：按空行切块逐块调 LLM，空行拼接结果后整体解析，
    避免单次 8000 字符截断导致大文件丢题。块数超过 MAX_LLM_CHUNKS 时抛错。
    """
    chunks = split_into_chunks(text)
    if len(chunks) > MAX_LLM_CHUNKS:
        raise RuntimeError(
            f"文本过长：AI 整理分块数超过上限 {MAX_LLM_CHUNKS}"
            f"（约 {MAX_LLM_CHUNKS * MAX_LLM_INPUT_CHARS} 字符），请拆分文件后分批导入"
        )
    parts = [normalize_quiz_text(chunk, cfg) for chunk in chunks]
    return "\n\n".join(p for p in parts if p.strip())


def test_llm_connection(cfg: dict) -> str:
    """
    用极简消息测试 LLM 连通性，返回模型回复文本；失败抛异常（含可读原因）
    """
    if cfg["provider"] not in ("openai", "local"):
        raise RuntimeError("LLM 未启用（provider 为 none），请先选择 API 类型并保存")
    messages = [{"role": "user", "content": "连通性测试，请只回复两个字符：OK"}]
    try:
        if cfg["provider"] == "openai":
            return _chat_openai(cfg, messages).strip()
        return _chat_local(cfg, messages).strip()
    except RuntimeError:
        raise
    except httpx.HTTPStatusError as e:
        raise RuntimeError(
            f"API 返回错误 {e.response.status_code}：{e.response.text[:200]}"
        ) from e
    except httpx.HTTPError as e:
        raise RuntimeError(f"无法连接 API（{cfg['base_url']}）：{e}") from e
