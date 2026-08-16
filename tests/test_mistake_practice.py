"""
错题练习模式测试（CONTEXT.md「错题练习」）：/session/start 的 source=mistake 题源行为。
"""
from fastapi.testclient import TestClient
from sqlmodel import Session

from api.models import QuestionBank, Question


def _make_bank_with_questions(session: Session, n: int = 3) -> tuple[int, list[int]]:
    bank = QuestionBank(name=f"错题练习库{n}")
    session.add(bank)
    session.commit()
    ids = []
    for i in range(n):
        q = Question(
            bank_id=bank.id,
            type="single",
            content=f"题目{i}",
            options={"A": "对", "B": "错"},
            answer=["A"],
            score=1.0,
        )
        session.add(q)
        session.commit()
        session.refresh(q)
        ids.append(q.id)
    return bank.id, ids


def _answer(client: TestClient, sid: int, question_id: int, choice: str) -> bool:
    resp = client.post(
        f"/session/{sid}/answer",
        json={"question_id": question_id, "user_choices": [choice]},
    )
    assert resp.status_code == 200
    return resp.json()["is_correct"]


def _make_mistakes(client: TestClient, bank_id: int, qids: list[int]):
    """把给定题目答错入本"""
    for qid in qids:
        resp = client.post(f"/session/start?bank_id={bank_id}")
        sid = resp.json()["id"]
        _answer(client, sid, qid, "B")


def test_mistake_session_starts_with_mistake_set(client, session):
    """错题练习：题源 = 该库当前错题，快照时刻的集合"""
    bank_id, qids = _make_bank_with_questions(session, 3)
    _make_mistakes(client, bank_id, qids[:2])  # 前两题答错入本

    resp = client.post(
        f"/session/start?bank_id={bank_id}&source=mistake&mode=sequential"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert set(data["question_ids"]) == set(qids[:2])
    assert data["mode"] == "mistake"


def test_mistake_session_recent_wrong_first(client, session):
    """顺序模式：最近答错的题在前"""
    bank_id, qids = _make_bank_with_questions(session, 2)
    _make_mistakes(client, bank_id, [qids[0]])  # 先错第 1 题
    _make_mistakes(client, bank_id, [qids[1]])  # 后错第 2 题（最近）

    resp = client.post(f"/session/start?bank_id={bank_id}&source=mistake")
    data = resp.json()
    assert data["question_ids"] == qids[::-1]  # 最近错的在前


def test_mistake_session_random_is_same_set(client, session):
    bank_id, qids = _make_bank_with_questions(session, 3)
    _make_mistakes(client, bank_id, qids)

    resp = client.post(
        f"/session/start?bank_id={bank_id}&source=mistake&mode=random"
    )
    assert resp.status_code == 200
    assert set(resp.json()["question_ids"]) == set(qids)


def test_mistake_session_empty_book(client, session):
    """空错题库：404 + 明确提示"""
    bank_id, _ = _make_bank_with_questions(session, 2)
    resp = client.post(f"/session/start?bank_id={bank_id}&source=mistake")
    assert resp.status_code == 404
    assert "暂无错题" in resp.json()["detail"]


def test_mistake_session_invalid_source(client, session):
    bank_id, _ = _make_bank_with_questions(session, 1)
    resp = client.post(f"/session/start?bank_id={bank_id}&source=whatever")
    assert resp.status_code == 400


def test_normal_session_unchanged(client, session):
    """不带 source：行为与原先一致（全部题目）"""
    bank_id, qids = _make_bank_with_questions(session, 2)
    resp = client.post(f"/session/start?bank_id={bank_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert set(data["question_ids"]) == set(qids)
    assert data["mode"] == "sequential"


def test_mistake_session_answers_update_book(client, session):
    """错题练习中的作答同样走自动入本/连对出本语义"""
    bank_id, qids = _make_bank_with_questions(session, 1)
    _make_mistakes(client, bank_id, qids)  # wrong_count=1

    resp = client.post(f"/session/start?bank_id={bank_id}&source=mistake")
    sid = resp.json()["id"]

    # 连对两次（阈值 2）→ 自动出本
    assert _answer(client, sid, qids[0], "A") is True
    assert _answer(client, sid, qids[0], "A") is True

    book = client.get(f"/mistakes?bank_id={bank_id}").json()["mistakes"]
    assert book == []
