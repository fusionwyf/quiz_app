# api.py
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from sqlmodel import Session, select
import random

from models import (
    engine,
    Question,
    ExamRecord,
    QuestionBank,
    QuizSession,
)

app = FastAPI(title="Quiz App API", version="2.0")

# ===== CORS（给 React / Tauri 用）=====
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===== DB Session =====
def get_session():
    with Session(engine) as session:
        yield session


# ======================================================
# DTOs
# ======================================================


class QuestionDTO(BaseModel):
    id: int
    type: str
    question: str
    options: Optional[dict[str, str]]
    score: float


class AnswerSubmission(BaseModel):
    question_id: int
    user_choices: List[str]


class CheckResult(BaseModel):
    question_id: int
    is_correct: bool
    correct_answer: List[str]
    score_obtained: float


class MistakeDTO(BaseModel):
    record_id: int
    question_content: str
    timestamp: datetime


# ======================================================
# 工具函数（统一判题）
# ======================================================


def check_answer(q: Question, user_answer: List[str]) -> bool:
    # 单选 / 多选 / 判断
    if q.type in ("single", "multi", "judge"):
        return set(a.upper() for a in user_answer) == set(q.answer or [])

    # 填空题（预留）
    if q.type == "blank":
        return [a.lower() for a in user_answer] == [a.lower() for a in (q.answer or [])]

    return False


# ======================================================
# 题库管理
# ======================================================


@app.get("/banks")
def list_banks(session: Session = Depends(get_session)):
    return session.exec(select(QuestionBank)).all()


@app.post("/banks/create")
def create_bank(name: str, session: Session = Depends(get_session)):
    bank = QuestionBank(name=name)
    session.add(bank)
    session.commit()
    session.refresh(bank)
    return bank


# ======================================================
# 随机出题（保留你原有接口，升级支持题库）
# ======================================================


@app.get("/quiz/random", response_model=List[QuestionDTO])
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


# ======================================================
# 顺序做题 Session
# ======================================================


@app.post("/session/start")
def start_session(
    bank_id: int,
    mode: str = "sequential",  # sequential / random
    session: Session = Depends(get_session),
):
    q_ids = session.exec(select(Question.id).where(Question.bank_id == bank_id)).all()

    if not q_ids:
        raise HTTPException(404, "No questions in bank")

    ids = [i for i in q_ids]
    if mode == "random":
        random.shuffle(ids)

    qs = QuizSession(
        bank_id=bank_id,
        mode=mode,
        question_ids=ids,
        total=len(ids),
    )
    session.add(qs)
    session.commit()
    session.refresh(qs)
    return qs


@app.get("/session/{session_id}/current", response_model=QuestionDTO)
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


@app.post("/session/{session_id}/answer", response_model=CheckResult)
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


# ======================================================
# 错题本
# ======================================================


@app.get("/records/mistakes", response_model=List[MistakeDTO])
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
