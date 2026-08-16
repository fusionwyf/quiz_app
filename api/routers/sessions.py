import random
from datetime import datetime, UTC
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from api.deps import get_session
from api.models import Question, ExamRecord, QuizSession, Mistake
from api.schemas import QuestionDTO
from api.services.grading import check_answer
from api.services import mistakes as mistake_service

router = APIRouter()


class AnswerSubmission(BaseModel):
    question_id: int
    user_choices: List[str]


class CheckResult(BaseModel):
    question_id: int
    is_correct: bool
    correct_answer: List[str]
    score_obtained: float


class SessionStatus(BaseModel):
    session_id: int
    bank_id: int
    mode: str
    current_index: int
    total: int
    finished: bool
    progress_percentage: float
    correct_count: int
    total_score: float
    average_score: float


class SessionSummary(BaseModel):
    session_id: int
    bank_id: int
    mode: str
    total_questions: int
    answered_questions: int
    correct_count: int
    total_score_obtained: float
    max_possible_score: float
    accuracy_percentage: float
    finished_at: Optional[datetime] = None


@router.get("/quiz/random", response_model=List[QuestionDTO])
def get_random_quiz(
    bank_id: int,
    count: int = 5,
    qtype: Optional[str] = None,
    session: Session = Depends(get_session),
):
    stmt = select(Question).where(Question.bank_id == bank_id)
    if qtype:
        stmt = stmt.where(Question.type == qtype)

    questions = session.exec(stmt).all()
    if not questions:
        return []

    selected = random.sample(questions, min(count, len(questions)))
    return [
        QuestionDTO(
            id=q.id,
            type=q.type,
            question=q.content,
            options=q.options,
            score=q.score,
        )
        for q in selected
    ]


@router.post("/session/start")
def start_session(
    bank_id: int,
    mode: str = "sequential",  # sequential / random（题序）
    source: str = "normal",  # normal（全部题目）/ mistake（错题本，CONTEXT.md「错题练习」）
    session: Session = Depends(get_session),
):
    if source not in ("normal", "mistake"):
        raise HTTPException(400, "source 仅支持 normal / mistake")
    if mode not in ("sequential", "random"):
        raise HTTPException(400, "mode 仅支持 sequential / random")

    if source == "mistake":
        # 题源快照：开练时刻的错题列表，按最近答错在前；random 时打乱
        ids = session.exec(
            select(Mistake.question_id)
            .where(Mistake.bank_id == bank_id)
            .order_by(Mistake.last_wrong_at.desc())
        ).all()
        if not ids:
            raise HTTPException(404, "该题库暂无错题，先去刷题积累错题吧")
        stored_mode = "mistake"
    else:
        ids = session.exec(
            select(Question.id).where(Question.bank_id == bank_id)
        ).all()
        if not ids:
            raise HTTPException(404, "No questions in bank")
        stored_mode = mode

    if mode == "random":
        random.shuffle(ids)

    qs = QuizSession(
        bank_id=bank_id,
        mode=stored_mode,
        question_ids=ids,
        total=len(ids),
    )
    session.add(qs)
    session.commit()
    session.refresh(qs)
    return qs


@router.get("/session/{session_id}/current", response_model=QuestionDTO)
def get_current_question(
    session_id: int,
    session_db: Session = Depends(get_session),
):
    qs = session_db.get(QuizSession, session_id)
    if not qs or qs.finished:
        raise HTTPException(404, "Session finished or not found")

    qid = qs.question_ids[qs.current_index]
    q = session_db.get(Question, qid)

    return QuestionDTO(
        id=q.id,
        type=q.type,
        question=q.content,
        options=q.options,
        score=q.score,
    )


@router.post("/session/{session_id}/answer", response_model=CheckResult)
def submit_session_answer(
    session_id: int,
    submission: AnswerSubmission,
    session_db: Session = Depends(get_session),
):
    qs = session_db.get(QuizSession, session_id)
    q = session_db.get(Question, submission.question_id)

    if not qs or not q:
        raise HTTPException(404)

    is_right = check_answer(q, submission.user_choices)

    record = ExamRecord(
        session_id=session_id,
        question_id=q.id,
        user_answer=submission.user_choices,
        is_correct=is_right,
    )
    session_db.add(record)

    # 答错自动入本；答错清零连对、连对达阈值自动出本（CONTEXT.md「错题」「已掌握」）
    mistake_service.record_answer_result(session_db, q, is_right)

    qs.current_index += 1
    if qs.current_index >= qs.total:
        qs.finished = True

    session_db.commit()

    return CheckResult(
        question_id=q.id,
        is_correct=is_right,
        correct_answer=q.answer or [],
        score_obtained=q.score if is_right else 0.0,
    )


@router.get("/session/{session_id}/status", response_model=SessionStatus)
def get_session_status(
    session_id: int,
    session_db: Session = Depends(get_session),
):
    """
    获取Session的进度和统计信息
    """
    qs = session_db.get(QuizSession, session_id)
    if not qs:
        raise HTTPException(404, f"Session with id {session_id} not found")

    # 计算答对的题目数量
    stmt = select(ExamRecord).where(
        ExamRecord.session_id == session_id, ExamRecord.is_correct == True
    )
    correct_records = session_db.exec(stmt).all()
    correct_count = len(correct_records)

    # 计算累计得分
    stmt = (
        select(ExamRecord, Question)
        .join(Question, ExamRecord.question_id == Question.id)
        .where(ExamRecord.session_id == session_id)
    )

    total_score = 0.0
    for record, question in session_db.exec(stmt).all():
        if record.is_correct:
            total_score += question.score

    # 计算平均得分（按已回答题目数）
    answered_count = qs.current_index
    average_score = total_score / answered_count if answered_count > 0 else 0.0

    # 计算进度百分比
    progress_percentage = (qs.current_index / qs.total * 100) if qs.total > 0 else 0.0

    return SessionStatus(
        session_id=qs.id,
        bank_id=qs.bank_id,
        mode=qs.mode,
        current_index=qs.current_index,
        total=qs.total,
        finished=qs.finished,
        progress_percentage=round(progress_percentage, 2),
        correct_count=correct_count,
        total_score=round(total_score, 2),
        average_score=round(average_score, 2),
    )


@router.post("/session/{session_id}/finish", response_model=SessionSummary)
def finish_session(
    session_id: int,
    session_db: Session = Depends(get_session),
):
    """
    手动结束Session并返回总结
    """
    qs = session_db.get(QuizSession, session_id)
    if not qs:
        raise HTTPException(404, f"Session with id {session_id} not found")

    if qs.finished:
        raise HTTPException(400, f"Session {session_id} is already finished")

    # 标记为完成
    qs.finished = True
    qs.finished_at = datetime.now(UTC)

    # 计算统计信息
    stmt = select(ExamRecord).where(ExamRecord.session_id == session_id)
    records = session_db.exec(stmt).all()

    correct_count = sum(1 for r in records if r.is_correct)
    answered_count = len(records)

    # 计算得分
    total_score_obtained = 0.0
    max_possible_score = 0.0

    if qs.question_ids:
        questions = session_db.exec(
            select(Question).where(Question.id.in_(qs.question_ids))
        ).all()
        # 构建查找表以优化后续记录匹配
        question_map = {q.id: q for q in questions}
        max_possible_score = sum(q.score for q in questions)
    else:
        question_map = {}

    for record in records:
        # 使用 map 查找题目，避免 N+1 查询问题
        if record.question_id in question_map:
            question = question_map[record.question_id]
            if record.is_correct:
                total_score_obtained += question.score

    accuracy_percentage = (
        (correct_count / answered_count * 100) if answered_count > 0 else 0.0
    )

    session_db.commit()

    return SessionSummary(
        session_id=qs.id,
        bank_id=qs.bank_id,
        mode=qs.mode,
        total_questions=qs.total,
        answered_questions=answered_count,
        correct_count=correct_count,
        total_score_obtained=round(total_score_obtained, 2),
        max_possible_score=round(max_possible_score, 2),
        accuracy_percentage=round(accuracy_percentage, 2),
        finished_at=qs.finished_at,
    )
