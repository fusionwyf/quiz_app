from sqlmodel import Session, select, or_

from api.models import Question, ExamRecord, QuestionBank, QuizSession, Mistake


def delete_bank_cascade(session: Session, bank: QuestionBank) -> None:
    """删除题库并级联清理题目、做题会话、答题记录与错题。

    级联清理的唯一实现——新增关联数据时必须同步维护此处。
    """
    bank_id = bank.id

    question_ids = session.exec(
        select(Question.id).where(Question.bank_id == bank_id)
    ).all()
    session_ids = session.exec(
        select(QuizSession.id).where(QuizSession.bank_id == bank_id)
    ).all()

    # 答题记录：按题目关联（无 session 的直接作答）或按 session 关联两条路径都要清
    if question_ids or session_ids:
        conditions = []
        if question_ids:
            conditions.append(ExamRecord.question_id.in_(question_ids))
        if session_ids:
            conditions.append(ExamRecord.session_id.in_(session_ids))
        for record in session.exec(select(ExamRecord).where(or_(*conditions))).all():
            session.delete(record)
    for mistake in session.exec(
        select(Mistake).where(Mistake.bank_id == bank_id)
    ).all():
        session.delete(mistake)
    for question in session.exec(
        select(Question).where(Question.bank_id == bank_id)
    ).all():
        session.delete(question)
    for quiz_session in session.exec(
        select(QuizSession).where(QuizSession.bank_id == bank_id)
    ).all():
        session.delete(quiz_session)
    session.delete(bank)
    session.commit()
