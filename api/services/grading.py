from typing import List

from api.models import Question


def check_answer(q: Question, user_answer: List[str]) -> bool:
    # 单选 / 多选 / 判断
    if q.type in ("single", "multi", "judge"):
        return set(a.upper() for a in user_answer) == set(q.answer or [])

    # 填空题（预留，T04 重构为归一化 + 多备选答案）
    if q.type == "blank":
        return [a.lower() for a in user_answer] == [a.lower() for a in (q.answer or [])]

    return False
