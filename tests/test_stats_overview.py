"""仪表盘总览接口测试"""
from fastapi.testclient import TestClient
from sqlmodel import Session

from api.models import QuestionBank, Question


def _answer(client: TestClient, sid: int, question_id: int, choice: str):
    client.post(
        f"/session/{sid}/answer",
        json={"question_id": question_id, "user_choices": [choice]},
    )


def test_overview_empty(client):
    data = client.get("/stats/overview").json()
    assert data["total_banks"] == 0
    assert data["total_questions"] == 0
    assert data["accuracy"] == 0.0
    assert data["pending_mistakes"] == 0
    assert len(data["trend"]) == 14
    assert data["recent_sessions"] == []
    assert data["bank_progress"] == []


def test_overview_with_activity(client, session):
    bank = QuestionBank(name="总览库")
    session.add(bank)
    session.commit()
    qs = [
        Question(bank_id=bank.id, type="single", content=f"题{i}",
                 options={"A": "a", "B": "b"}, answer=["A"])
        for i in range(3)
    ]
    session.add_all(qs)
    session.commit()

    sid = client.post(f"/session/start?bank_id={bank.id}").json()["id"]
    _answer(client, sid, qs[0].id, "A")  # 对
    _answer(client, sid, qs[1].id, "B")  # 错 → 入错题本
    _answer(client, sid, qs[2].id, "A")  # 对

    data = client.get("/stats/overview").json()
    assert data["total_banks"] == 1
    assert data["total_questions"] == 3
    assert data["total_attempts"] == 3
    assert data["accuracy"] == 66.7
    assert data["pending_mistakes"] == 1

    # 今日趋势有一条非零
    assert data["trend"][-1]["attempts"] == 3
    assert data["trend"][-1]["correct"] == 2

    # 最近练习包含该会话（3 题 2 对）
    recent = data["recent_sessions"]
    assert len(recent) == 1
    assert recent[0]["bank_name"] == "总览库"
    assert recent[0]["answered"] == 3
    assert recent[0]["accuracy"] == 66.7

    # 题库进度：3 题全部作答过
    progress = data["bank_progress"]
    assert progress[0]["answered_questions"] == 3
    assert progress[0]["progress"] == 100.0
