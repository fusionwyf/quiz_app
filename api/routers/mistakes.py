from datetime import datetime, UTC

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from api.deps import get_session
from api.models import Question, ExamRecord, Mistake

router = APIRouter()


class MistakeDTO(BaseModel):
    record_id: int
    question_content: str
    timestamp: datetime


class MarkMistakeRequest(BaseModel):
    question_id: int
    bank_id: int


@router.get("/records/mistakes", response_model=list[MistakeDTO])
def get_mistakes(session: Session = Depends(get_session)):
    stmt = (
        select(ExamRecord, Question)
        .join(Question, ExamRecord.question_id == Question.id)
        .where(ExamRecord.is_correct == False)
        .order_by(ExamRecord.created_at.desc())
    )

    results = session.exec(stmt).all()
    return [
        MistakeDTO(
            record_id=r.id,
            question_content=q.content,
            timestamp=r.created_at,
        )
        for r, q in results
    ]


@router.post("/mistakes/mark")
def mark_mistake(
    request: MarkMistakeRequest,
    session: Session = Depends(get_session),
):
    """
    标记题目为错题（加入错题本）
    """
    # 检查题目是否存在
    question = session.get(Question, request.question_id)
    if not question:
        raise HTTPException(404, f"Question with id {request.question_id} not found")

    # 检查是否已标记
    existing = session.exec(
        select(Mistake).where(Mistake.question_id == request.question_id)
    ).first()

    if existing:
        # 已存在，增加错误计数
        existing.wrong_count += 1
        existing.last_wrong_at = datetime.now(UTC)
        session.add(existing)
    else:
        # 创建新的错题记录
        mistake = Mistake(
            bank_id=request.bank_id,
            question_id=request.question_id,
            wrong_count=1,
            last_wrong_at=datetime.now(UTC),
        )
        session.add(mistake)

    session.commit()
    return {"message": f"Question {request.question_id} marked as mistake"}


@router.delete("/mistakes/{question_id}")
def unmark_mistake(
    question_id: int,
    session: Session = Depends(get_session),
):
    """
    从错题本中移除题目
    """
    mistake = session.exec(
        select(Mistake).where(Mistake.question_id == question_id)
    ).first()

    if not mistake:
        raise HTTPException(404, f"Mistake record for question {question_id} not found")

    session.delete(mistake)
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
                "last_wrong_at": mistake.last_wrong_at,
                "bank_id": mistake.bank_id,
            }
        )

    return {"mistakes": mistakes_list}
