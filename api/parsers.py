# parsers.py
"""
题库文件解析模块

支持 txt / md / docx 文件的文本提取与题目解析，兼容两种题目格式：
1. 键值格式（题目：/类型：/选项：JSON/答案：JSON/分数：）
2. 通用试卷格式（1. 题干 / A. 选项 / 答案：B）

纯函数模块，不依赖 DB 与 HTTP，便于单元测试。
"""
import io
import json
import re
from pathlib import Path

import docx2txt

from api.models import Question

# 合法的题目类型
VALID_TYPES = ("single", "multi", "judge", "blank")

# 支持导入的文件扩展名
SUPPORTED_EXTENSIONS = (".txt", ".md", ".markdown", ".docx")

# ===== 试卷格式正则 =====
# 题目行：数字题号开头，如 "1." "2、" "3）"
QUESTION_LINE_RE = re.compile(r"^\s*(\d+)\s*[\.、．)\]】]\s*(.*)$")
# 选项行：A-F 字母开头，如 "A. xxx" "B、xxx"
OPTION_LINE_RE = re.compile(r"^\s*([A-Fa-f])\s*[\.、．)\]】]\s*(.+)$")
# 答案行：如 "答案：B" "【答案】AC"
ANSWER_LINE_RE = re.compile(r"^\s*(?:【答案】|答案)\s*[:：]?\s*(.+?)\s*$")

# 判断题答案词表
JUDGE_TRUE_WORDS = {"对", "√", "正确", "true", "t", "yes"}
JUDGE_FALSE_WORDS = {"错", "×", "错误", "false", "f", "no"}

# 题干中的题型标注关键词（按顺序匹配）
TYPE_KEYWORDS = (
    ("单选", "single"),
    ("多选", "multi"),
    ("判断", "judge"),
    ("填空", "blank"),
)


# ======================================================
# 文本提取
# ======================================================


def extract_text(filename: str, data: bytes) -> str:
    """
    按文件扩展名提取纯文本内容
    - .txt / .md：UTF-8 解码，失败回退 GBK
    - .docx：docx2txt 提取，剥离图片占位符
    - .md 额外清洗 Markdown 标记
    """
    ext = Path(filename or "").suffix.lower()

    if ext == ".docx":
        try:
            text = docx2txt.process(io.BytesIO(data))
        except Exception as e:
            raise ValueError(f"docx 解析失败: {e}")
        if text is None:
            return ""
        # 剥离 docx2txt 的图片占位符
        text = re.sub(r"\[IMAGE:[^\]]*\]", "", text)
        return text.strip()

    if ext in (".txt", ".md", ".markdown"):
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text = data.decode("gbk")
            except UnicodeDecodeError:
                raise ValueError("无法解码文件内容，仅支持 UTF-8 / GBK 编码")
        if ext in (".md", ".markdown"):
            text = clean_markdown(text)
        return text

    raise ValueError(
        f"不支持的文件扩展名: {ext or '(无)'}，支持的格式: txt / md / docx"
    )


def clean_markdown(text: str) -> str:
    """剥离 Markdown 标记，归一化为纯文本"""
    # 移除代码块
    text = re.sub(r"```.*?```", "", text, flags=re.S)

    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        stripped = re.sub(r"^#{1,6}\s*", "", stripped)  # 标题符号
        stripped = re.sub(r"^>\s*", "", stripped)  # 引用前缀
        stripped = re.sub(r"^[-*+]\s+", "", stripped)  # 无序列表前缀
        stripped = re.sub(r"\*\*(.+?)\*\*", r"\1", stripped)  # 加粗
        stripped = re.sub(r"\*(.+?)\*", r"\1", stripped)  # 斜体
        lines.append(stripped)
    return "\n".join(lines)


# ======================================================
# 键值格式解析（由 api.py 的 parse_txt_to_question 迁移）
# ======================================================


def parse_keyvalue_block(block: str, bank_id: int) -> Question:
    """
    解析简单键值格式为Question对象
    格式示例：
    题目：1+1=?
    类型：single
    选项：{"A": "1", "B": "2"}
    答案：["B"]
    分数：1.0
    """
    lines = block.strip().split("\n")
    data = {}

    for line in lines:
        line = line.strip()
        if "：" in line:  # 中文冒号
            key, value = line.split("：", 1)
        elif ":" in line:  # 英文冒号
            key, value = line.split(":", 1)
        else:
            continue

        key = key.strip()
        value = value.strip()

        if key == "题目":
            data["content"] = value
        elif key == "类型":
            data["type"] = value
        elif key == "选项":
            try:
                data["options"] = json.loads(value)
            except json.JSONDecodeError:
                raise ValueError(f"Invalid JSON in options: {value}")
        elif key == "答案":
            try:
                data["answer"] = json.loads(value)
            except json.JSONDecodeError:
                raise ValueError(f"Invalid JSON in answer: {value}")
        elif key == "分数":
            try:
                data["score"] = float(value)
            except ValueError:
                raise ValueError(f"Invalid score: {value}")

    # 必填字段检查
    required_fields = ["content", "type"]
    for field in required_fields:
        if field not in data:
            raise ValueError(f"Missing required field: {field}")

    # 题型合法性校验
    if data["type"] not in VALID_TYPES:
        raise ValueError(f"Invalid question type: {data['type']}")

    return Question(
        bank_id=bank_id,
        type=data["type"],
        content=data["content"],
        options=data.get("options"),
        answer=data.get("answer"),
        score=data.get("score", 1.0),
    )


# ======================================================
# 通用试卷格式解析
# ======================================================


def parse_exam_paper(text: str, bank_id: int) -> tuple[list[Question], list[str]]:
    """
    解析通用试卷格式文本，返回 (题目列表, 错误信息列表)
    无法识别的题块跳过并记入错误列表，不入库脏数据
    """
    questions: list[Question] = []
    errors: list[str] = []

    # 按题号行切分题块，题号前的内容（如试卷标题）忽略
    blocks: list[tuple[str, list[str]]] = []
    current: tuple[str, list[str]] | None = None

    for line in text.splitlines():
        m = QUESTION_LINE_RE.match(line)
        if m:
            if current:
                blocks.append(current)
            current = (m.group(1), [m.group(2)])
        elif current is not None:
            current[1].append(line)

    if current:
        blocks.append(current)

    if not blocks:
        errors.append("未识别到任何题目块（题目行应以数字题号开头）")
        return questions, errors

    for number, lines in blocks:
        try:
            questions.append(_build_exam_question(lines, bank_id))
        except ValueError as e:
            errors.append(f"第{number}题: {e}，已跳过")

    return questions, errors


def _build_exam_question(lines: list[str], bank_id: int) -> Question:
    """组装单道试卷格式题目（题干/选项/答案状态机）"""
    stem_parts: list[str] = []
    options: dict[str, str] = {}
    answer_text: str | None = None
    last_option: str | None = None

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue

        # 答案行
        m = ANSWER_LINE_RE.match(line)
        if m and answer_text is None:
            answer_text = m.group(1)
            continue

        # 答案行之后的内容（如解析说明）忽略
        if answer_text is not None:
            continue

        # 选项行
        m = OPTION_LINE_RE.match(line)
        if m:
            key = m.group(1).upper()
            options[key] = m.group(2).strip()
            last_option = key
            continue

        # 续行：未出现选项时拼接到题干，否则拼接到上一个选项
        if last_option is None:
            stem_parts.append(line)
        else:
            options[last_option] += line

    stem = "".join(stem_parts).strip()
    if not stem:
        raise ValueError("题干为空")
    if answer_text is None:
        raise ValueError("未识别到答案")

    qtype = _detect_type(stem, answer_text, options)
    answer, blank_answer = _normalize_answer(answer_text, qtype, options)

    return Question(
        bank_id=bank_id,
        type=qtype,
        content=stem,
        options=options if qtype in ("single", "multi") else None,
        answer=answer,
        blank_answer=blank_answer,
        score=1.0,
    )


def _detect_type(stem: str, answer_text: str, options: dict[str, str]) -> str:
    """题型判定：题干标注 > 答案形态推断 > 默认填空"""
    # 1. 题干中的题型标注优先（如「（单选题）」）
    for keyword, qtype in TYPE_KEYWORDS:
        if keyword in stem:
            return qtype

    # 2. 按答案形态推断
    lowered = answer_text.strip().lower()
    if lowered in JUDGE_TRUE_WORDS or lowered in JUDGE_FALSE_WORDS:
        return "judge"

    letters = re.findall(r"[A-Fa-f]", answer_text)
    if len(letters) > 1:
        return "multi"
    if letters:
        return "single"

    # 3. 有选项但答案不是选项字母，无法判定
    if options:
        raise ValueError("答案不是有效选项字母，无法判定题型")

    # 4. 其余视为填空题（自由文本答案）
    return "blank"


def _normalize_answer(
    answer_text: str, qtype: str, options: dict[str, str]
) -> tuple[list[str], list[str] | None]:
    """按题型归一化答案，返回 (answer, blank_answer)"""
    text = answer_text.strip()

    if qtype == "judge":
        lowered = text.lower()
        if lowered in JUDGE_TRUE_WORDS:
            return ["对"], None
        if lowered in JUDGE_FALSE_WORDS:
            return ["错"], None
        raise ValueError(f"判断题答案无法识别: {text}")

    if qtype in ("single", "multi"):
        if not options:
            raise ValueError("未识别到选项")
        letters = re.findall(r"[A-Fa-f]", text)
        if not letters:
            raise ValueError(f"选择题答案无法识别: {text}")
        # 大写去重，保持顺序
        choices = list(dict.fromkeys(l.upper() for l in letters))
        return choices, None

    # 填空题：答案文本整体作为答案
    return [text], [text]


# ======================================================
# 统一入口
# ======================================================


def parse_questions(text: str, bank_id: int) -> tuple[list[Question], list[str]]:
    """
    解析题库文本，自动探测格式：
    - 含「题目：」行 → 键值格式（按空行分块）
    - 否则 → 通用试卷格式
    返回 (题目列表, 错误信息列表)
    """
    if _is_keyvalue_format(text):
        return _parse_keyvalue_text(text, bank_id)
    return parse_exam_paper(text, bank_id)


def _is_keyvalue_format(text: str) -> bool:
    """探测是否为键值格式（存在以「题目：」开头的行）"""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("题目：") or stripped.startswith("题目:"):
            return True
    return False


def _parse_keyvalue_text(
    text: str, bank_id: int
) -> tuple[list[Question], list[str]]:
    """按空行分块解析键值格式，单块失败记入错误列表继续"""
    questions: list[Question] = []
    errors: list[str] = []

    blocks = re.split(r"\n\s*\n", text.strip())
    for i, block in enumerate(blocks, start=1):
        if not block.strip():
            continue
        try:
            questions.append(parse_keyvalue_block(block, bank_id))
        except ValueError as e:
            errors.append(f"第{i}块: {e}，已跳过")

    return questions, errors
