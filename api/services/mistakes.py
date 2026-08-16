# 错题本领域服务：入本/出本/连对出本语义的唯一实现（CONTEXT.md「错题」「已掌握」）。
# 事务由调用方（路由）统一提交。
from datetime import datetime, UTC
from typing import Optional

from sqlmodel import Session, select

from api.models import AppSetting, Mistake, Question

MASTER_THRESHOLD_KEY = "MISTAKE_MASTER_THRESHOLD"
DEFAULT_MASTER_THRESHOLD = 2


def get_master_threshold(session: Session) -> int:
    """连续答对多少次自动移出错题本（应用设置可配，默认 2）"""
    row = session.get(AppSetting, MASTER_THRESHOLD_KEY)
    if not row or not row.value:
        return DEFAULT_MASTER_THRESHOLD
    try:
        return max(1, int(row.value))
    except ValueError:
        return DEFAULT_MASTER_THRESHOLD


def set_master_threshold(session: Session, value: int) -> None:
    row = session.get(AppSetting, MASTER_THRESHOLD_KEY) or AppSetting(
        key=MASTER_THRESHOLD_KEY
    )
    row.value = str(value)
    session.add(row)


def _find_mistake(session: Session, question_id: int) -> Optional[Mistake]:
    return session.exec(
        select(Mistake).where(Mistake.question_id == question_id)
    ).first()


def record_answer_result(session: Session, question: Question, is_correct: bool) -> bool:
    """作答判分后更新错题本。

    - 答错：自动入本（已存在则 wrong_count +1、刷新最近答错时间），连对清零
    - 答对且已在错题本：连对 +1；达到阈值自动出本（已掌握）
    返回该题作答后是否仍在错题本中。事务由调用方提交。
    """
    mistake = _find_mistake(session, question.id)

    if not is_correct:
        now = datetime.now(UTC)
        if mistake:
            mistake.wrong_count += 1
            mistake.last_wrong_at = now
            mistake.consecutive_correct = 0
        else:
            session.add(
                Mistake(
                    bank_id=question.bank_id,
                    question_id=question.id,
                    wrong_count=1,
                    last_wrong_at=now,
                    consecutive_correct=0,
                )
            )
        return True

    if not mistake:
        return False  # 答对且不在错题本，无事发生

    mistake.consecutive_correct += 1
    if mistake.consecutive_correct >= get_master_threshold(session):
        session.delete(mistake)
        return False
    return True


def mark_mastered(session: Session, question_id: int) -> bool:
    """手动已掌握：移出错题本。返回是否确有移除（不存在则 False）。"""
    mistake = _find_mistake(session, question_id)
    if not mistake:
        return False
    session.delete(mistake)
    return True
