# 判分规则唯一实现（ADR-0002）。题目类型见 api/constants.py。
from typing import List

from api.models import Question


def _to_halfwidth(s: str) -> str:
    """全角 ASCII（含标点与空格）转半角；中文字符不受影响"""
    out = []
    for ch in s:
        code = ord(ch)
        if code == 0x3000:  # 全角空格
            out.append(" ")
        elif 0xFF01 <= code <= 0xFF5E:  # ！- ～
            out.append(chr(code - 0xFEE0))
        else:
            out.append(ch)
    return "".join(out)


def normalize_blank_text(s: str) -> str:
    """填空比较前的归一化：全角转半角、去首尾空格、忽略大小写"""
    return _to_halfwidth(s).strip().casefold()


def check_blank_answer(expected_blanks: List[str], user_answer: List[str]) -> bool:
    """填空判分：逐空比较，每空支持 | 分隔的多个备选答案（CONTEXT.md「备选答案」），
    任一备选归一化后匹配即判对该空；空数不等或任一空不匹配判错。"""
    if len(user_answer) != len(expected_blanks):
        return False
    for expected, got in zip(expected_blanks, user_answer):
        accepted = [normalize_blank_text(alt) for alt in expected.split("|")]
        if normalize_blank_text(got) not in accepted:
            return False
    return True


def check_answer(q: Question, user_answer: List[str]) -> bool:
    # 单选 / 多选 / 判断：选项字母集合比较
    if q.type in ("single", "multi", "judge"):
        return set(a.upper() for a in user_answer) == set(q.answer or [])

    if q.type == "blank":
        expected = q.blank_answer or q.answer or []
        return check_blank_answer(expected, user_answer)

    return False
