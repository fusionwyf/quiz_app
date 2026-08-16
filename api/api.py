# api.py
import os
from contextlib import asynccontextmanager
from datetime import datetime, UTC
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Depends, Request, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from sqlmodel import Session, select, func, or_
import random

from api.models import (
    engine,
    Question,
    ExamRecord,
    QuestionBank,
    QuizSession,
    Mistake,
    AppSetting,
    create_db_and_tables,
)
from api.parsers import extract_text, parse_questions, parse_keyvalue_block
from api import llm


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时自动建表（已存在则跳过）
    create_db_and_tables()
    yield


app = FastAPI(title="Quiz App API", version="2.0", lifespan=lifespan)

# ===== CORS（给 React / Tauri 用）=====
def _cors_origins() -> list[str]:
    env = os.environ.get("CORS_ORIGINS")
    if env:
        return [o.strip() for o in env.split(",") if o.strip()]
    return [
        "http://localhost:5173",   # Vite dev
        "http://tauri.localhost",  # Tauri WebView (Windows)
        "tauri://localhost",       # Tauri WebView (macOS/Linux)
    ]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
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
    """返回所有题库，附每个库的题目数（供前端直接同步展示）"""
    banks = session.exec(select(QuestionBank)).all()
    counts = dict(
        session.exec(
            select(Question.bank_id, func.count(Question.id)).group_by(
                Question.bank_id
            )
        ).all()
    )
    return [
        {**bank.model_dump(mode="json"), "question_count": counts.get(bank.id, 0)}
        for bank in banks
    ]


@app.post("/banks/create")
def create_bank(name: str, session: Session = Depends(get_session)):
    name = name.strip()
    if not name:
        raise HTTPException(400, "题库名称不能为空")
    exists = session.exec(
        select(QuestionBank).where(QuestionBank.name == name)
    ).first()
    if exists:
        raise HTTPException(409, f"题库名称已存在：{name}")
    bank = QuestionBank(name=name)
    session.add(bank)
    session.commit()
    session.refresh(bank)
    return bank


@app.delete("/banks/{bank_id}")
def delete_bank(bank_id: int, session: Session = Depends(get_session)):
    """删除题库，并级联清理题目、做题 Session、答题记录与错题"""
    bank = session.get(QuestionBank, bank_id)
    if not bank:
        raise HTTPException(404, f"QuestionBank with id {bank_id} not found")

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

    return {"message": f"Bank {bank_id} and related data deleted"}


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


@app.get("/session/{session_id}/status", response_model=SessionStatus)
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


@app.post("/session/{session_id}/finish", response_model=SessionSummary)
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


# ======================================================
# 题目 CRUD
# ======================================================


@app.post("/questions")
def create_question(
    question: CreateQuestionDTO,
    session: Session = Depends(get_session),
):
    # 验证题库存在
    bank = session.get(QuestionBank, question.bank_id)
    if not bank:
        raise HTTPException(404, f"QuestionBank with id {question.bank_id} not found")

    # 验证题目类型
    if question.type not in ("single", "multi", "judge", "blank"):
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

    # 返回QuestionDTO格式
    return QuestionDTO(
        id=new_question.id,
        type=new_question.type,
        question=new_question.content,
        options=new_question.options,
        score=new_question.score,
    )


@app.get("/questions/{question_id}", response_model=QuestionDTO)
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


@app.put("/questions/{question_id}")
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
        if update_data.type not in ("single", "multi", "judge", "blank"):
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


@app.delete("/questions/{question_id}")
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


# ======================================================
# 导入/导出功能
# ======================================================


@app.post("/banks/{bank_id}/import")
async def import_questions(
    bank_id: int,
    request: Request,
    format: str = "json",  # json 或 txt
    session: Session = Depends(get_session),
):
    """
    导入题目到指定题库
    - format: "json" 或 "txt"
    - file_content: 文件内容字符串
    """
    # 检查题库是否存在
    bank = session.get(QuestionBank, bank_id)
    if not bank:
        raise HTTPException(404, f"QuestionBank with id {bank_id} not found")
    try:
        body_bytes = await request.body()
        file_content = body_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(400, "Invalid UTF-8 encoding")

    if not file_content:
        raise HTTPException(400, "file_content is required")

    imported_count = 0

    if format.lower() == "json":
        import json

        try:
            questions_data = json.loads(file_content)
            # 支持单个对象或数组
            if isinstance(questions_data, dict):
                questions_data = [questions_data]

            for q_data in questions_data:
                # 验证必填字段
                if "content" not in q_data or "type" not in q_data:
                    continue

                question = Question(
                    bank_id=bank_id,
                    type=q_data.get("type"),
                    content=q_data.get("content"),
                    options=q_data.get("options"),
                    answer=q_data.get("answer"),
                    blank_answer=q_data.get("blank_answer"),
                    score=q_data.get("score", 1.0),
                )
                session.add(question)
                imported_count += 1

        except json.JSONDecodeError as e:
            raise HTTPException(400, f"Invalid JSON: {str(e)}")

    elif format.lower() == "txt":
        # 按空行分割多个题目
        txt_blocks = file_content.strip().split("\n\n")
        for block in txt_blocks:
            if not block.strip():
                continue
            try:
                question = parse_keyvalue_block(block, bank_id)
                session.add(question)
                imported_count += 1
            except ValueError:
                # 跳过解析错误的题目，继续导入其他题目
                continue

    else:
        raise HTTPException(400, f"Unsupported format: {format}. Use 'json' or 'txt'")

    session.commit()

    return {
        "message": f"Successfully imported {imported_count} questions to bank {bank_id}",
        "imported_count": imported_count,
    }


@app.get("/banks/{bank_id}/export")
def export_questions(
    bank_id: int,
    format: str = "json",  # json 或 txt
    session: Session = Depends(get_session),
):
    """
    导出题库中的题目
    """
    # 检查题库是否存在
    bank = session.get(QuestionBank, bank_id)
    if not bank:
        raise HTTPException(404, f"QuestionBank with id {bank_id} not found")

    # 获取题库所有题目
    stmt = select(Question).where(Question.bank_id == bank_id)
    questions = session.exec(stmt).all()

    if not questions:
        raise HTTPException(404, f"No questions in bank {bank_id}")

    if format.lower() == "json":
        import json

        questions_list = []
        for q in questions:
            q_dict = {
                "id": q.id,
                "bank_id": q.bank_id,
                "type": q.type,
                "content": q.content,
                "options": q.options,
                "answer": q.answer,
                "blank_answer": q.blank_answer,
                "score": q.score,
                "created_at": q.created_at.isoformat() if q.created_at else None,
            }
            questions_list.append(q_dict)

        return {
            "bank_id": bank_id,
            "bank_name": bank.name,
            "question_count": len(questions),
            "questions": questions_list,
        }

    elif format.lower() == "txt":
        txt_output = []
        for q in questions:
            txt_block = f"题目：{q.content}\n"
            txt_block += f"类型：{q.type}\n"
            if q.options:
                import json

                txt_block += f"选项：{json.dumps(q.options, ensure_ascii=False)}\n"
            if q.answer:
                import json

                txt_block += f"答案：{json.dumps(q.answer, ensure_ascii=False)}\n"
            txt_block += f"分数：{q.score}\n"
            txt_output.append(txt_block.strip())

        return PlainTextResponse("\n\n".join(txt_output))

    else:
        raise HTTPException(400, f"Unsupported format: {format}. Use 'json' or 'txt'")


# ===== 文件上传导入（txt / md / docx）=====

# 最大导入文件大小（10MB）
MAX_IMPORT_FILE_SIZE = 10 * 1024 * 1024
# 响应中返回的最大错误明细条数
MAX_REPORTED_ERRORS = 50


@app.post("/banks/{bank_id}/import/file")
async def import_questions_file(
    bank_id: int,
    file: UploadFile = File(...),
    force_llm: bool = False,
    session: Session = Depends(get_session),
):
    """
    通过文件上传导入题目到指定题库
    - 支持 .txt / .md / .docx，按扩展名自动识别格式
    - 文本内容兼容键值格式与通用试卷格式（自动探测）
    - 解析失败的题目跳过，错误明细随响应返回
    - LLM 智能整理：解析出 0 题自动兜底；force_llm=true 时强制整理
      （跳过直接解析结果，全部经 LLM 转为键值格式，长文本自动分块）
    """
    # 检查题库是否存在
    bank = session.get(QuestionBank, bank_id)
    if not bank:
        raise HTTPException(404, f"QuestionBank with id {bank_id} not found")

    data = await file.read()
    if len(data) > MAX_IMPORT_FILE_SIZE:
        raise HTTPException(413, "File too large (max 10MB)")

    try:
        text = extract_text(file.filename or "", data)
    except ValueError as e:
        raise HTTPException(400, str(e))

    if not text.strip():
        raise HTTPException(400, "File content is empty")

    questions, errors = parse_questions(text, bank_id)

    # LLM 智能整理：解析出 0 题自动兜底；force_llm 时无条件整理
    cfg = llm.resolve_llm_config(session)
    ai_normalized = False
    ai_error = None
    if force_llm or not questions:
        if cfg["provider"] not in ("openai", "local"):
            if force_llm:
                raise HTTPException(
                    400, "LLM 未启用，无法强制 AI 整理（请先在设置中配置 API）"
                )
        else:
            try:
                normalized = llm.normalize_quiz_text_chunked(text, cfg)
                ai_questions, ai_errors = parse_questions(normalized, bank_id)
                if ai_questions:
                    questions, errors = ai_questions, ai_errors
                    ai_normalized = True
                else:
                    ai_error = "AI 整理后仍未解析出题目，保留直接解析结果"
            except Exception as e:
                # 整理失败（LLM 不可用 / 超出分块上限等）保留原结果并说明原因
                ai_error = f"AI 整理失败：{e}"

    # 去重：题干与库内已有题目（或本文件内已收录题目）重复的跳过，防止重复导入产生两份
    existing_contents = {
        content.strip()
        for content in session.exec(
            select(Question.content).where(Question.bank_id == bank_id)
        ).all()
    }
    unique_questions = []
    duplicate_count = 0
    for question in questions:
        key = question.content.strip()
        if key in existing_contents:
            duplicate_count += 1
            errors.append(f"重复题目已跳过：{question.content[:30]}")
        else:
            existing_contents.add(key)
            unique_questions.append(question)
    questions = unique_questions

    for question in questions:
        session.add(question)
    session.commit()

    truncated = len(errors) > MAX_REPORTED_ERRORS
    reported_errors = errors[:MAX_REPORTED_ERRORS]

    return {
        "message": f"Successfully imported {len(questions)} questions to bank {bank_id}",
        "imported_count": len(questions),
        "skipped_count": len(errors),
        "errors": reported_errors,
        "truncated": truncated,
        "ai_normalized": ai_normalized,
        "ai_error": ai_error,
        "duplicate_count": duplicate_count,
    }


# ===== LLM 智能整理配置 =====


class LlmConfigIn(BaseModel):
    """LLM 配置写入体：空 base_url/model 表示清除覆盖（回退环境变量/默认值），
    空 api_key 表示保留已存 Key"""

    provider: str = "none"
    base_url: str = ""
    model: str = ""
    api_key: str = ""


def _llm_config_payload(cfg: dict) -> dict:
    return {
        "provider": cfg["provider"],
        "base_url": cfg["base_url"],
        "model": cfg["model"],
        "api_key_masked": llm.mask_api_key(cfg["api_key"]),
        "api_key_set": bool(cfg["api_key"]),
        "enabled": llm.get_llm_status(cfg)["enabled"],
    }


def _resolve_test_config(body: LlmConfigIn | None, session: Session) -> dict:
    """测试连接用的配置：body 提供的字段覆盖已存配置（未保存即可先测）"""
    cfg = llm.resolve_llm_config(session)
    if body is None:
        return cfg
    provider = body.provider.strip().lower()
    if provider not in ("none", "openai"):
        raise HTTPException(400, "provider 仅支持 none / openai")
    cfg["provider"] = provider
    if body.base_url.strip():
        cfg["base_url"] = body.base_url.strip().rstrip("/")
    if body.model.strip():
        cfg["model"] = body.model.strip()
    if body.api_key.strip():
        cfg["api_key"] = body.api_key.strip()
    return cfg


@app.get("/llm/config")
def get_llm_config_route(session: Session = Depends(get_session)):
    """查询当前生效的 LLM 配置（数据库覆盖 > 环境变量），API Key 脱敏"""
    return _llm_config_payload(llm.resolve_llm_config(session))


@app.put("/llm/config")
def update_llm_config(body: LlmConfigIn, session: Session = Depends(get_session)):
    """保存 LLM 配置到数据库（AppSetting 表）"""
    provider = body.provider.strip().lower()
    if provider not in ("none", "openai"):
        raise HTTPException(400, "provider 仅支持 none / openai")
    base_url = body.base_url.strip().rstrip("/")
    if base_url and not base_url.startswith(("http://", "https://")):
        raise HTTPException(400, "base_url 必须以 http:// 或 https:// 开头")

    def _save(key: str, value: str):
        if value:
            row = session.get(AppSetting, key) or AppSetting(key=key)
            row.value = value
            session.add(row)
        else:
            row = session.get(AppSetting, key)
            if row is not None:
                session.delete(row)

    # provider 始终落库（none 也存，用于显式禁用环境变量启用的 LLM）
    _save("LLM_PROVIDER", provider)
    _save("LLM_BASE_URL", base_url)
    _save("LLM_MODEL", body.model.strip())
    # 空 api_key = 保留已存 Key
    if body.api_key.strip():
        _save("LLM_API_KEY", body.api_key.strip())
    session.commit()

    return _llm_config_payload(llm.resolve_llm_config(session))


@app.post("/llm/test")
def test_llm_route(body: LlmConfigIn | None = None, session: Session = Depends(get_session)):
    """
    测试 LLM 连通性：带 body 时用 body 字段（未保存即可先测），
    不带 body 时测已保存配置。失败返回 400 + 可读原因
    """
    cfg = _resolve_test_config(body, session)
    try:
        reply = llm.test_llm_connection(cfg)
    except RuntimeError as e:
        raise HTTPException(400, str(e))
    return {"ok": True, "model": cfg["model"], "reply": reply}


@app.get("/llm/status")
def llm_status(session: Session = Depends(get_session)):
    """
    查询 LLM 智能整理配置状态（数据库覆盖 > 环境变量，供前端导入弹窗展示提示）
    """
    return llm.get_llm_status(llm.resolve_llm_config(session))


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


# 错题本管理（基于Mistake表）
class MarkMistakeRequest(BaseModel):
    question_id: int
    bank_id: int


@app.post("/mistakes/mark")
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


@app.delete("/mistakes/{question_id}")
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


@app.get("/mistakes")
def get_mistake_book(
    bank_id: Optional[int] = None,
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


# ======================================================
# 统计与记录
# ======================================================


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


@app.get("/records", response_model=PaginatedRecords)
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

    # 构建查询
    stmt = select(ExamRecord).join(Question, ExamRecord.question_id == Question.id)

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
    for record in results:
        question = session_db.get(Question, record.question_id)
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


@app.get("/stats/questions/{question_id}", response_model=QuestionStats)
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
