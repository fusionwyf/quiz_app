from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select, func

from api.constants import QUESTION_TYPES
from api.deps import get_session
from api.models import QuestionBank, Question
from api.schemas import QuestionDTO

router = APIRouter()

MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 20


@router.get("/banks/{bank_id}/questions")
def list_questions(
    bank_id: int,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    session: Session = Depends(get_session),
):
    """题库题目分页列表（题目管理页数据源；空题库返回 total=0 而非 404）"""
    bank = session.get(QuestionBank, bank_id)
    if not bank:
        raise HTTPException(404, f"QuestionBank with id {bank_id} not found")

    page = max(1, page)
    page_size = min(max(1, page_size), MAX_PAGE_SIZE)

    base = select(Question).where(Question.bank_id == bank_id)
    total = session.exec(select(func.count()).select_from(base.subquery())).first()
    rows = session.exec(
        base.order_by(Question.id).offset((page - 1) * page_size).limit(page_size)
    ).all()

    return {
        "bank_id": bank_id,
        "bank_name": bank.name,
        "total": total,
        "page": page,
        "page_size": page_size,
        "questions": [
            {
                "id": q.id,
                "bank_id": q.bank_id,
                "type": q.type,
                "content": q.content,
                "options": q.options,
                "answer": q.answer,
                "blank_answer": q.blank_answer,
                "score": q.score,
                "created_at": q.created_at,
            }
            for q in rows
        ],
    }


class CreateQuestionDTO(BaseModel):
    bank_id: int
    type: str  # single | multi | judge | blank
    content: str
    options: Optional[dict[str, str]] = None
    answer: Optional[List[str]] = None
    blank_answer: Optional[List[str]] = None
    score: float = 1.0


class UpdateQuestionDTO(BaseModel):
    type: Optional[str] = None  # single | multi | judge | blank
    content: Optional[str] = None
    options: Optional[dict[str, str]] = None
    answer: Optional[List[str]] = None
    blank_answer: Optional[List[str]] = None
    score: Optional[float] = None


@router.post("/questions")
def create_question(
    question: CreateQuestionDTO,
    session: Session = Depends(get_session),
):
    # 验证题库存在
    bank = session.get(QuestionBank, question.bank_id)
    if not bank:
        raise HTTPException(404, f"QuestionBank with id {question.bank_id} not found")

    # 验证题目类型
    if question.type not in QUESTION_TYPES:
        raise HTTPException(400, f"Invalid question type: {question.type}")

    # 根据类型验证答案字段
    if question.type == "blank":
        if not question.blank_answer:
            raise HTTPException(
                400, "blank_answer is required for blank type questions"
            )
        # 对于填空题，使用blank_answer作为答案
        answer_to_store = question.blank_answer
    else:
        if not question.answer:
            raise HTTPException(400, "answer is required for non-blank type questions")
        answer_to_store = question.answer

    # 创建题目
    new_question = Question(
        bank_id=question.bank_id,
        type=question.type,
        content=question.content,
        options=question.options,
        answer=answer_to_store,
        blank_answer=question.blank_answer if question.type == "blank" else None,
        score=question.score,
    )

    session.add(new_question)
    session.commit()
    session.refresh(new_question)

    return QuestionDTO(
        id=new_question.id,
        type=new_question.type,
        question=new_question.content,
        options=new_question.options,
        score=new_question.score,
    )


@router.get("/questions/{question_id}", response_model=QuestionDTO)
def get_question(
    question_id: int,
    session: Session = Depends(get_session),
):
    question = session.get(Question, question_id)
    if not question:
        raise HTTPException(404, f"Question with id {question_id} not found")

    return QuestionDTO(
        id=question.id,
        type=question.type,
        question=question.content,
        options=question.options,
        score=question.score,
    )


@router.put("/questions/{question_id}")
def update_question(
    question_id: int,
    update_data: UpdateQuestionDTO,
    session: Session = Depends(get_session),
):
    question = session.get(Question, question_id)
    if not question:
        raise HTTPException(404, f"Question with id {question_id} not found")

    # 更新字段（仅更新提供的字段）
    if update_data.type is not None:
        if update_data.type not in QUESTION_TYPES:
            raise HTTPException(400, f"Invalid question type: {update_data.type}")
        question.type = update_data.type

    if update_data.content is not None:
        question.content = update_data.content

    if update_data.options is not None:
        question.options = update_data.options

    if update_data.answer is not None:
        question.answer = update_data.answer

    if update_data.blank_answer is not None:
        question.blank_answer = update_data.blank_answer

    if update_data.score is not None:
        question.score = update_data.score

    session.commit()
    session.refresh(question)

    return QuestionDTO(
        id=question.id,
        type=question.type,
        question=question.content,
        options=question.options,
        score=question.score,
    )


@router.delete("/questions/{question_id}")
def delete_question(
    question_id: int,
    session: Session = Depends(get_session),
):
    question = session.get(Question, question_id)
    if not question:
        raise HTTPException(404, f"Question with id {question_id} not found")

    session.delete(question)
    session.commit()

    return {"message": f"Question with id {question_id} deleted successfully"}
