# 统计聚合服务（spec P3 仪表盘）：一次查询出首页总览所需全部数据
from datetime import datetime, timedelta

from sqlalchemy import Integer, cast
from sqlmodel import Session, func, select

from api.models import ExamRecord, Mistake, Question, QuestionBank, QuizSession

TREND_DAYS = 14
RECENT_SESSIONS = 5

MODE_LABELS = {"sequential": "顺序", "random": "随机", "mistake": "错题"}


def get_overview(session: Session) -> dict:
    total_banks = session.exec(select(func.count(QuestionBank.id))).one()
    total_questions = session.exec(select(func.count(Question.id))).one()
    pending_mistakes = session.exec(select(func.count(Mistake.id))).one()

    attempts = session.exec(select(func.count(ExamRecord.id))).one()
    correct = session.exec(
        select(func.count(ExamRecord.id)).where(ExamRecord.is_correct == True)  # noqa: E712
    ).one()
    accuracy = round(correct / attempts * 100, 1) if attempts else 0.0

    return {
        "total_banks": total_banks,
        "total_questions": total_questions,
        "total_attempts": attempts,
        "accuracy": accuracy,
        "pending_mistakes": pending_mistakes,
        "trend": _accuracy_trend(session),
        "recent_sessions": _recent_sessions(session),
        "bank_progress": _bank_progress(session),
    }


def _accuracy_trend(session: Session) -> list[dict]:
    """最近 N 天每日作答数与正确数（无数据的日期补零，便于前端画连续趋势）"""
    since = datetime.now() - timedelta(days=TREND_DAYS - 1)
    rows = session.exec(
        select(
            func.date(ExamRecord.created_at),
            func.count(ExamRecord.id),
            func.sum(cast(ExamRecord.is_correct, Integer)),
        )
        .where(ExamRecord.created_at >= since.replace(hour=0, minute=0, second=0, microsecond=0))
        .group_by(func.date(ExamRecord.created_at))
    ).all()
    by_day = {str(day): (total, correct or 0) for day, total, correct in rows}

    trend = []
    for i in range(TREND_DAYS):
        day = (datetime.now() - timedelta(days=TREND_DAYS - 1 - i)).strftime("%Y-%m-%d")
        total, ok = by_day.get(day, (0, 0))
        trend.append({"date": day, "attempts": total, "correct": ok})
    return trend


def _recent_sessions(session: Session) -> list[dict]:
    sessions = session.exec(
        select(QuizSession, QuestionBank)
        .join(QuestionBank, QuizSession.bank_id == QuestionBank.id)
        .order_by(QuizSession.id.desc())
        .limit(RECENT_SESSIONS)
    ).all()

    result = []
    for qs, bank in sessions:
        total = session.exec(
            select(func.count(ExamRecord.id)).where(ExamRecord.session_id == qs.id)
        ).one()
        ok = session.exec(
            select(func.count(ExamRecord.id)).where(
                ExamRecord.session_id == qs.id, ExamRecord.is_correct == True  # noqa: E712
            )
        ).one()
        result.append(
            {
                "session_id": qs.id,
                "bank_name": bank.name,
                "mode": MODE_LABELS.get(qs.mode, qs.mode),
                "answered": total,
                "total": qs.total,
                "correct": ok,
                "accuracy": round(ok / total * 100, 1) if total else 0.0,
                "finished": qs.finished,
                "created_at": qs.created_at,
            }
        )
    return result


def _bank_progress(session: Session) -> list[dict]:
    """各题库：题目数、已作答题目数（去重）、正确率"""
    banks = session.exec(select(QuestionBank).order_by(QuestionBank.id)).all()
    q_counts = dict(
        session.exec(
            select(Question.bank_id, func.count(Question.id)).group_by(Question.bank_id)
        ).all()
    )
    answered = dict(
        session.exec(
            select(Question.bank_id, func.count(func.distinct(ExamRecord.question_id)))
            .join(Question, ExamRecord.question_id == Question.id)
            .group_by(Question.bank_id)
        ).all()
    )
    correct = dict(
        session.exec(
            select(Question.bank_id, func.count(ExamRecord.id))
            .join(Question, ExamRecord.question_id == Question.id)
            .where(ExamRecord.is_correct == True)  # noqa: E712
            .group_by(Question.bank_id)
        ).all()
    )

    result = []
    for bank in banks:
        total = q_counts.get(bank.id, 0)
        done = answered.get(bank.id, 0)
        ok = correct.get(bank.id, 0)
        result.append(
            {
                "bank_id": bank.id,
                "bank_name": bank.name,
                "question_count": total,
                "answered_questions": done,
                "progress": round(done / total * 100, 1) if total else 0.0,
                "accuracy": round(ok / done * 100, 1) if done else 0.0,
            }
        )
    return result
