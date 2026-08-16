from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select, func

from api.deps import get_session
from api.models import Question, ExamRecord
from api.services import stats as stats_service

router = APIRouter()


class RecordResponse(BaseModel):
    id: int
    session_id: Optional[int]
    question_id: int
    user_answer: List[str]
    is_correct: bool
    created_at: datetime
    question_content: Optional[str] = None
    question_type: Optional[str] = None


class PaginatedRecords(BaseModel):
    total: int
    page: int
    page_size: int
    records: List[RecordResponse]


class QuestionStats(BaseModel):
    question_id: int
    question_content: str
    total_attempts: int
    correct_attempts: int
    wrong_attempts: int
    correct_rate: float
    average_score: float
    total_score_obtained: float
    total_possible_score: float


@router.get("/records", response_model=PaginatedRecords)
def get_records(
    page: int = 1,
    page_size: int = 20,
    question_id: Optional[int] = None,
    session_id: Optional[int] = None,
    is_correct: Optional[bool] = None,
    session_db: Session = Depends(get_session),
):
    """
    获取答题记录（支持分页和过滤）
    """
    # 计算偏移量
    offset = (page - 1) * page_size

    # 构建查询（联取题目，避免逐条再查）
    stmt = select(ExamRecord, Question).join(
        Question, ExamRecord.question_id == Question.id
    )

    # 应用过滤条件
    if question_id is not None:
        stmt = stmt.where(ExamRecord.question_id == question_id)

    if session_id is not None:
        stmt = stmt.where(ExamRecord.session_id == session_id)

    if is_correct is not None:
        stmt = stmt.where(ExamRecord.is_correct == is_correct)

    # 获取总数
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = session_db.exec(count_stmt).first()

    # 获取分页数据
    stmt = stmt.order_by(ExamRecord.created_at.desc())
    stmt = stmt.offset(offset).limit(page_size)

    results = session_db.exec(stmt).all()

    # 构建响应
    records_list = []
    for record, question in results:
        records_list.append(
            RecordResponse(
                id=record.id,
                session_id=record.session_id,
                question_id=record.question_id,
                user_answer=record.user_answer,
                is_correct=record.is_correct,
                created_at=record.created_at,
                question_content=question.content if question else None,
                question_type=question.type if question else None,
            )
        )

    return PaginatedRecords(
        total=total,
        page=page,
        page_size=page_size,
        records=records_list,
    )


@router.get("/stats/overview")
def get_overview(session_db: Session = Depends(get_session)):
    """首页总览：总量、正确率、待复习错题、近 14 天趋势、最近练习、各题库进度"""
    return stats_service.get_overview(session_db)


@router.get("/stats/questions/{question_id}", response_model=QuestionStats)
def get_question_stats(
    question_id: int,
    session_db: Session = Depends(get_session),
):
    """
    获取题目的统计信息（错误率、平均得分等）
    """
    # 检查题目是否存在
    question = session_db.get(Question, question_id)
    if not question:
        raise HTTPException(404, f"Question with id {question_id} not found")

    # 获取该题目的所有答题记录
    stmt = select(ExamRecord).where(ExamRecord.question_id == question_id)
    records = session_db.exec(stmt).all()

    total_attempts = len(records)
    correct_attempts = sum(1 for r in records if r.is_correct)
    wrong_attempts = total_attempts - correct_attempts

    # 计算正确率
    correct_rate = (
        (correct_attempts / total_attempts * 100) if total_attempts > 0 else 0.0
    )

    # 计算得分统计
    total_score_obtained = correct_attempts * question.score  # 每次答对获得题目分数
    total_possible_score = total_attempts * question.score
    average_score = total_score_obtained / total_attempts if total_attempts > 0 else 0.0

    return QuestionStats(
        question_id=question.id,
        question_content=question.content,
        total_attempts=total_attempts,
        correct_attempts=correct_attempts,
        wrong_attempts=wrong_attempts,
        correct_rate=round(correct_rate, 2),
        average_score=round(average_score, 2),
        total_score_obtained=round(total_score_obtained, 2),
        total_possible_score=round(total_possible_score, 2),
    )
