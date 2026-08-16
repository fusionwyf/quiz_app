"""题目分页列表接口测试（GET /banks/{bank_id}/questions）"""
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from api.models import QuestionBank, Question


def _bank_with_questions(session: Session, n: int) -> tuple[int, list[int]]:
    bank = QuestionBank(name=f"列表测试库{n}")
    session.add(bank)
    session.commit()
    ids = []
    for i in range(n):
        q = Question(
            bank_id=bank.id,
            type="single",
            content=f"题目{i}",
            options={"A": "a", "B": "b"},
            answer=["A"],
        )
        session.add(q)
        session.commit()
        session.refresh(q)
        ids.append(q.id)
    return bank.id, ids


def test_list_empty_bank_returns_zero(client, session):
    """空题库：200 + total=0（不再是 404）"""
    bank = QuestionBank(name="空库")
    session.add(bank)
    session.commit()

    resp = client.get(f"/banks/{bank.id}/questions")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["questions"] == []
    assert data["bank_name"] == "空库"


def test_list_pagination(client, session):
    bank_id, ids = _bank_with_questions(session, 5)

    resp = client.get(f"/banks/{bank_id}/questions?page=1&page_size=2")
    data = resp.json()
    assert data["total"] == 5
    assert [q["id"] for q in data["questions"]] == ids[:2]

    resp = client.get(f"/banks/{bank_id}/questions?page=3&page_size=2")
    data = resp.json()
    assert data["total"] == 5
    assert [q["id"] for q in data["questions"]] == ids[4:]

    # 超出范围的页：空列表而非报错
    resp = client.get(f"/banks/{bank_id}/questions?page=9&page_size=2")
    assert resp.json()["questions"] == []


def test_list_full_fields_for_editing(client, session):
    """返回完整字段（含答案/备选答案），供编辑弹窗使用"""
    bank = QuestionBank(name="字段库")
    session.add(bank)
    session.commit()
    session.add(
        Question(
            bank_id=bank.id,
            type="blank",
            content="填空",
            answer=["TCP|tcp协议"],
            blank_answer=["TCP|tcp协议"],
        )
    )
    session.commit()

    resp = client.get(f"/banks/{bank.id}/questions")
    q = resp.json()["questions"][0]
    assert q["type"] == "blank"
    assert q["blank_answer"] == ["TCP|tcp协议"]
    assert q["answer"] == ["TCP|tcp协议"]
    assert q["score"] == 1.0
    assert q["bank_id"] == bank.id


def test_list_bank_not_found(client):
    assert client.get("/banks/99999/questions").status_code == 404


def test_list_page_params_clamped(client, session):
    """非法分页参数被钳制而非报错"""
    bank_id, ids = _bank_with_questions(session, 3)
    resp = client.get(f"/banks/{bank_id}/questions?page=0&page_size=9999")
    assert resp.status_code == 200
    data = resp.json()
    assert data["page"] == 1
    assert data["page_size"] == 100
    assert data["total"] == 3
