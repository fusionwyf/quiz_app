from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from api.deps import get_session
from api.models import Mistake, Question
from api.services import mistakes as mistake_service

router = APIRouter()


@router.delete("/mistakes/{question_id}")
def mark_mastered_route(
    question_id: int,
    session: Session = Depends(get_session),
):
    """
    已掌握：将题目移出错题本（错题由答错自动记录，无需手动加入）
    """
    if not mistake_service.mark_mastered(session, question_id):
        raise HTTPException(404, f"Mistake record for question {question_id} not found")
    session.commit()
    return {"message": f"Question {question_id} removed from mistake book"}


@router.get("/mistakes")
def get_mistake_book(
    bank_id: int | None = None,
    session: Session = Depends(get_session),
):
    """
    获取错题本中的题目（支持按题库过滤）
    """
    stmt = select(Mistake, Question).join(Question, Mistake.question_id == Question.id)

    if bank_id is not None:
        stmt = stmt.where(Mistake.bank_id == bank_id)

    stmt = stmt.order_by(Mistake.last_wrong_at.desc())

    results = session.exec(stmt).all()

    mistakes_list = []
    for mistake, question in results:
        mistakes_list.append(
            {
                "mistake_id": mistake.id,
                "question_id": question.id,
                "question_content": question.content,
                "question_type": question.type,
                "wrong_count": mistake.wrong_count,
                "consecutive_correct": mistake.consecutive_correct,
                "last_wrong_at": mistake.last_wrong_at,
                "bank_id": mistake.bank_id,
            }
        )

    return {"mistakes": mistakes_list}


class MasterThresholdIn(BaseModel):
    value: int


@router.get("/mistakes/master-threshold")
def get_master_threshold_route(session: Session = Depends(get_session)):
    """连对出本阈值（默认 2）"""
    return {"threshold": mistake_service.get_master_threshold(session)}


@router.put("/mistakes/master-threshold")
def set_master_threshold_route(
    body: MasterThresholdIn, session: Session = Depends(get_session)
):
    """设置连对出本阈值（>=1，存应用设置）"""
    if body.value < 1:
        raise HTTPException(400, "阈值必须 >= 1")
    mistake_service.set_master_threshold(session, body.value)
    session.commit()
    return {"threshold": body.value}
