import json

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import PlainTextResponse
from sqlmodel import Session, select, func

from api.deps import get_session
from api.models import QuestionBank, Question
from api.parsers import extract_text, parse_questions, parse_keyvalue_block
from api.services.banks import delete_bank_cascade
from api.services import sample_bank
from api import llm

router = APIRouter()

# 最大导入文件大小（10MB）
MAX_IMPORT_FILE_SIZE = 10 * 1024 * 1024
# 响应中返回的最大错误明细条数
MAX_REPORTED_ERRORS = 50


@router.get("/banks")
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


@router.post("/banks/create")
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


@router.delete("/banks/{bank_id}")
def delete_bank(bank_id: int, session: Session = Depends(get_session)):
    """删除题库，并级联清理题目、做题 Session、答题记录与错题"""
    bank = session.get(QuestionBank, bank_id)
    if not bank:
        raise HTTPException(404, f"QuestionBank with id {bank_id} not found")
    delete_bank_cascade(session, bank)
    return {"message": f"Bank {bank_id} and related data deleted"}


@router.post("/banks/import/sample")
def import_sample_bank_route(session: Session = Depends(get_session)):
    """一键导入内置示例题库（覆盖全部四种题型，含多空与 | 备选答案）"""
    try:
        bank = sample_bank.import_sample_bank(session)
    except ValueError as e:
        raise HTTPException(409, str(e))
    return bank


@router.post("/banks/{bank_id}/import")
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


@router.get("/banks/{bank_id}/export")
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
        questions_list = []
        for q in questions:
            questions_list.append(
                {
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
            )

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
                txt_block += f"选项：{json.dumps(q.options, ensure_ascii=False)}\n"
            if q.answer:
                txt_block += f"答案：{json.dumps(q.answer, ensure_ascii=False)}\n"
            txt_block += f"分数：{q.score}\n"
            txt_output.append(txt_block.strip())

        return PlainTextResponse("\n\n".join(txt_output))

    else:
        raise HTTPException(400, f"Unsupported format: {format}. Use 'json' or 'txt'")


@router.post("/banks/{bank_id}/import/file")
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
