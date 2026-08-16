"""内置示例题库导入测试"""
from sqlmodel import Session, select

from api.models import Question


def test_import_sample_bank_covers_all_types(client, session):
    resp = client.post("/banks/import/sample")
    assert resp.status_code == 200
    bank = resp.json()
    assert bank["name"] == "示例题库"

    questions = session.exec(select(Question)).all()
    types = {q.type for q in questions}
    assert types == {"single", "multi", "judge", "blank"}
    # 多空 + | 备选答案示例存在
    blanks = [q for q in questions if q.type == "blank"]
    assert any(len(q.blank_answer) > 1 for q in blanks)  # 双空
    assert any("|" in b for q in blanks for b in q.blank_answer)  # 备选


def test_import_sample_bank_duplicate_409(client):
    assert client.post("/banks/import/sample").status_code == 200
    resp = client.post("/banks/import/sample")
    assert resp.status_code == 409


def test_sample_bank_fully_playable(client):
    """示例题库可直接开练（AC：一键导入即可完整练习）"""
    bank_id = client.post("/banks/import/sample").json()["id"]
    resp = client.post(f"/session/start?bank_id={bank_id}")
    assert resp.status_code == 200
    assert resp.json()["total"] == 8
