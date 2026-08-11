"""
文件上传导入端点（POST /banks/{bank_id}/import/file）与解析器测试
"""
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

import api.api as api_module
import api.parsers as parsers
from api.models import Question, QuestionBank
from api.parsers import (
    clean_markdown,
    extract_text,
    parse_exam_paper,
    parse_keyvalue_block,
    parse_questions,
)


def create_test_bank(session: Session, name: str = "导入测试题库") -> QuestionBank:
    """创建测试题库"""
    bank = QuestionBank(name=name)
    session.add(bank)
    session.commit()
    session.refresh(bank)
    return bank


# ======================================================
# 测试数据
# ======================================================

KEYVALUE_TXT = """题目：文件导入题目1
类型：single
选项：{"A": "选项A", "B": "选项B"}
答案：["A"]
分数：1.0

题目：文件导入题目2
类型：multi
选项：{"A": "选项A", "B": "选项B", "C": "选项C"}
答案：["A", "B"]
分数：2.0"""

EXAM_TXT = """1. 1+1等于几？（单选题）
A. 1
B. 2
C. 3
D. 4
答案：B

2、下列哪些是偶数？（多选题）
A. 2
B. 3
C. 4
答案：AC

3. 地球是圆的。（判断题）
答案：对

4. 这道题没有答案
A. 选项A
"""

MD_EXAM = """# 测试试卷

**1. 1+1等于？**
A. 1
B. 2
答案：b
"""


# ======================================================
# 解析器单元测试
# ======================================================


def test_parse_keyvalue_block():
    """键值格式单块解析"""
    block = '题目：1+1=?\n类型：single\n选项：{"A": "1", "B": "2"}\n答案：["B"]\n分数：1.5'
    q = parse_keyvalue_block(block, bank_id=1)

    assert q.bank_id == 1
    assert q.type == "single"
    assert q.content == "1+1=?"
    assert q.options == {"A": "1", "B": "2"}
    assert q.answer == ["B"]
    assert q.score == 1.5


def test_parse_keyvalue_block_invalid_type():
    """键值格式非法题型应抛错"""
    block = "题目：x\n类型：unknown"
    with pytest.raises(ValueError, match="Invalid question type"):
        parse_keyvalue_block(block, bank_id=1)


def test_parse_exam_paper():
    """试卷格式解析：单选/多选/判断 + 坏块跳过"""
    questions, errors = parse_exam_paper(EXAM_TXT, bank_id=1)

    assert len(questions) == 3
    assert len(errors) == 1
    assert "第4题" in errors[0]

    single, multi, judge = questions
    assert single.type == "single"
    assert single.answer == ["B"]
    assert single.options == {"A": "1", "B": "2", "C": "3", "D": "4"}

    assert multi.type == "multi"
    assert multi.answer == ["A", "C"]

    assert judge.type == "judge"
    assert judge.answer == ["对"]
    assert judge.options is None


def test_parse_exam_paper_lowercase_answer():
    """小写答案字母应归一化为大写"""
    questions, errors = parse_exam_paper("1. 题目？\nA. x\nB. y\n答案：b", bank_id=1)
    assert len(questions) == 1
    assert questions[0].answer == ["B"]
    assert questions[0].type == "single"


def test_parse_exam_paper_no_blocks():
    """无题号文本应产生错误而非题目"""
    questions, errors = parse_exam_paper("这是一段无关文字", bank_id=1)
    assert questions == []
    assert len(errors) == 1


def test_parse_questions_detects_keyvalue():
    """统一入口自动探测键值格式"""
    questions, errors = parse_questions(KEYVALUE_TXT, bank_id=1)
    assert len(questions) == 2
    assert errors == []
    assert {q.content for q in questions} == {"文件导入题目1", "文件导入题目2"}


def test_parse_questions_detects_exam():
    """统一入口自动探测试卷格式"""
    questions, errors = parse_questions(EXAM_TXT, bank_id=1)
    assert len(questions) == 3
    assert len(errors) == 1


def test_parse_questions_keyvalue_bad_block_collected():
    """键值格式坏块收集到错误列表而非中断"""
    text = KEYVALUE_TXT + "\n\n题目：坏题目\n类型：unknown"
    questions, errors = parse_questions(text, bank_id=1)
    assert len(questions) == 2
    assert len(errors) == 1


def test_extract_text_utf8_and_gbk():
    """UTF-8 与 GBK 编码解码"""
    assert extract_text("a.txt", "题目：你好".encode("utf-8")) == "题目：你好"
    assert extract_text("a.txt", "题目：你好".encode("gbk")) == "题目：你好"


def test_extract_text_unknown_extension():
    """未知扩展名抛 ValueError"""
    with pytest.raises(ValueError, match="不支持的文件扩展名"):
        extract_text("a.xlsx", b"data")


def test_extract_text_undecodable():
    """无法解码的内容抛 ValueError"""
    with pytest.raises(ValueError, match="无法解码"):
        extract_text("a.txt", b"\xff\xfe\x00\x01")


def test_clean_markdown():
    """Markdown 标记清洗"""
    text = "# 标题\n\n**加粗题目**\n\n- 列表项\n\n```\ncode\n```"
    cleaned = clean_markdown(text)
    assert "标题" in cleaned
    assert "加粗题目" in cleaned
    assert "#" not in cleaned.split("\n")[0]
    assert "列表项" in cleaned
    assert "code" not in cleaned


def test_extract_text_markdown():
    """md 文件提取后无 Markdown 标记"""
    text = extract_text("a.md", MD_EXAM.encode("utf-8"))
    assert "**" not in text
    assert not text.startswith("#")


# ======================================================
# 文件上传端点测试
# ======================================================


def upload(client: TestClient, bank_id: int, filename: str, data: bytes):
    """辅助：上传文件"""
    return client.post(
        f"/banks/{bank_id}/import/file",
        files={"file": (filename, data, "application/octet-stream")},
    )


def test_import_file_txt_keyvalue(client: TestClient, session: Session):
    """上传键值格式 txt"""
    bank = create_test_bank(session)

    response = upload(client, bank.id, "questions.txt", KEYVALUE_TXT.encode("utf-8"))
    assert response.status_code == 200
    data = response.json()
    assert data["imported_count"] == 2
    assert data["skipped_count"] == 0

    questions = session.exec(
        select(Question).where(Question.bank_id == bank.id)
    ).all()
    assert len(questions) == 2


def test_import_file_txt_exam(client: TestClient, session: Session):
    """上传试卷格式 txt（含坏块部分导入）"""
    bank = create_test_bank(session)

    response = upload(client, bank.id, "exam.txt", EXAM_TXT.encode("utf-8"))
    assert response.status_code == 200
    data = response.json()
    assert data["imported_count"] == 3
    assert data["skipped_count"] == 1
    assert len(data["errors"]) == 1

    questions = session.exec(
        select(Question).where(Question.bank_id == bank.id)
    ).all()
    assert {q.type for q in questions} == {"single", "multi", "judge"}


def test_import_file_md(client: TestClient, session: Session):
    """上传 Markdown 文件"""
    bank = create_test_bank(session)

    response = upload(client, bank.id, "exam.md", MD_EXAM.encode("utf-8"))
    assert response.status_code == 200
    data = response.json()
    assert data["imported_count"] == 1

    questions = session.exec(
        select(Question).where(Question.bank_id == bank.id)
    ).all()
    assert len(questions) == 1
    assert questions[0].answer == ["B"]
    assert "**" not in questions[0].content


def test_import_file_docx(client: TestClient, session: Session, monkeypatch):
    """上传 docx（打桩 docx2txt.process）"""
    bank = create_test_bank(session)
    monkeypatch.setattr(parsers.docx2txt, "process", lambda f: KEYVALUE_TXT)

    response = upload(client, bank.id, "questions.docx", b"fake docx bytes")
    assert response.status_code == 200
    data = response.json()
    assert data["imported_count"] == 2


def test_import_file_unknown_extension(client: TestClient, session: Session):
    """不支持的扩展名返回 400"""
    bank = create_test_bank(session)

    response = upload(client, bank.id, "a.xlsx", b"data")
    assert response.status_code == 400
    assert "不支持的文件扩展名" in response.json()["detail"]


def test_import_file_bank_not_found(client: TestClient):
    """题库不存在返回 404"""
    response = upload(client, 9999, "a.txt", KEYVALUE_TXT.encode("utf-8"))
    assert response.status_code == 404


def test_import_file_empty(client: TestClient, session: Session):
    """空文件返回 400"""
    bank = create_test_bank(session)

    response = upload(client, bank.id, "a.txt", b"")
    assert response.status_code == 400
    assert response.json()["detail"] == "File content is empty"


def test_import_file_too_large(
    client: TestClient, session: Session, monkeypatch
):
    """超过大小限制返回 413"""
    bank = create_test_bank(session)
    monkeypatch.setattr(api_module, "MAX_IMPORT_FILE_SIZE", 10)

    response = upload(client, bank.id, "a.txt", b"x" * 20)
    assert response.status_code == 413


# ======================================================
# 主测试运行
# ======================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
