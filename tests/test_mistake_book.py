"""
错题本核心语义测试（经 HTTP seam）：答错自动入本、连对出本、已掌握、阈值可配。

词汇依据 CONTEXT.md：错题（答错自动入本，Mistake 表唯一事实源）、
已掌握（手动移出或连对 N 次自动移出）。
"""
from fastapi.testclient import TestClient
from sqlmodel import Session

from api.models import QuestionBank, Question


def _make_bank_with_question(session: Session, answer: list[str] = None) -> tuple[int, int]:
    bank = QuestionBank(name="错题语义测试库")
    session.add(bank)
    session.commit()
    q = Question(
        bank_id=bank.id,
        type="single",
        content="测试题",
        options={"A": "对", "B": "错"},
        answer=answer or ["A"],
        score=1.0,
    )
    session.add(q)
    session.commit()
    return bank.id, q.id


def _answer(client: TestClient, bank_id: int, question_id: int, choice: str) -> bool:
    resp = client.post(f"/session/start?bank_id={bank_id}")
    assert resp.status_code == 200
    sid = resp.json()["id"]
    resp = client.post(
        f"/session/{sid}/answer",
        json={"question_id": question_id, "user_choices": [choice]},
    )
    assert resp.status_code == 200
    return resp.json()["is_correct"]


def _book(client: TestClient, bank_id: int = None) -> list[dict]:
    params = f"?bank_id={bank_id}" if bank_id else ""
    resp = client.get(f"/mistakes{params}")
    assert resp.status_code == 200
    return resp.json()["mistakes"]


def _entry(client: TestClient, question_id: int) -> dict | None:
    return next((m for m in _book(client) if m["question_id"] == question_id), None)


def test_wrong_answer_auto_records(client, session):
    """答错自动入本，无需手动标记"""
    bank_id, qid = _make_bank_with_question(session)
    assert _answer(client, bank_id, qid, "B") is False
    entry = _entry(client, qid)
    assert entry is not None
    assert entry["wrong_count"] == 1
    assert entry["consecutive_correct"] == 0


def test_wrong_again_increments_count(client, session):
    bank_id, qid = _make_bank_with_question(session)
    _answer(client, bank_id, qid, "B")
    _answer(client, bank_id, qid, "B")
    entry = _entry(client, qid)
    assert entry["wrong_count"] == 2


def test_correct_once_does_not_remove(client, session):
    """重做答对一次不出本（默认阈值 2）"""
    bank_id, qid = _make_bank_with_question(session)
    _answer(client, bank_id, qid, "B")
    assert _answer(client, bank_id, qid, "A") is True
    entry = _entry(client, qid)
    assert entry is not None
    assert entry["consecutive_correct"] == 1


def test_consecutive_correct_auto_removes_at_threshold(client, session):
    """连对达到阈值（默认 2）自动已掌握出本"""
    bank_id, qid = _make_bank_with_question(session)
    _answer(client, bank_id, qid, "B")
    _answer(client, bank_id, qid, "A")
    _answer(client, bank_id, qid, "A")
    assert _entry(client, qid) is None


def test_wrong_resets_consecutive_counter(client, session):
    """连对中途答错：清零并留在错题本"""
    bank_id, qid = _make_bank_with_question(session)
    _answer(client, bank_id, qid, "B")
    _answer(client, bank_id, qid, "A")  # 连对 1
    _answer(client, bank_id, qid, "B")  # 清零
    entry = _entry(client, qid)
    assert entry is not None
    assert entry["wrong_count"] == 2
    assert entry["consecutive_correct"] == 0


def test_threshold_configurable(client, session):
    """阈值可调：设为 1 后答对一次即出本"""
    bank_id, qid = _make_bank_with_question(session)
    resp = client.put("/mistakes/master-threshold", json={"value": 1})
    assert resp.status_code == 200
    assert resp.json()["threshold"] == 1

    _answer(client, bank_id, qid, "B")
    _answer(client, bank_id, qid, "A")
    assert _entry(client, qid) is None

    # 恢复默认，避免影响其他用例（client fixture 每用例重建但共享 app 级设置表？不——session 是每用例独立的内存库，此处仅显式归位）
    client.put("/mistakes/master-threshold", json={"value": 2})


def test_threshold_validation(client):
    assert client.put("/mistakes/master-threshold", json={"value": 0}).status_code == 400
    resp = client.get("/mistakes/master-threshold")
    assert resp.status_code == 200
    assert resp.json()["threshold"] == 2  # 默认


def test_manual_mastered_removes(client, session):
    """手动已掌握移出"""
    bank_id, qid = _make_bank_with_question(session)
    _answer(client, bank_id, qid, "B")
    assert client.delete(f"/mistakes/{qid}").status_code == 200
    assert _entry(client, qid) is None
    # 再删：404
    assert client.delete(f"/mistakes/{qid}").status_code == 404


def test_correct_answer_never_in_book(client, session):
    """一直答对的题不会入本"""
    bank_id, qid = _make_bank_with_question(session)
    _answer(client, bank_id, qid, "A")
    _answer(client, bank_id, qid, "A")
    assert _entry(client, qid) is None


def test_delete_question_cascades_mistake(client, session):
    """删除题目时级联清理其错题与记录（回归：孤儿错题导致错题练习 500）"""
    bank_id, qid = _make_bank_with_question(session)
    _answer(client, bank_id, qid, "B")
    assert _entry(client, qid) is not None

    assert client.delete(f"/questions/{qid}").status_code == 200

    assert _entry(client, qid) is None
    # 错题练习开练不再撞孤儿数据：明确 404 暂无错题
    resp = client.post(f"/session/start?bank_id={bank_id}&source=mistake")
    assert resp.status_code == 404
    assert "暂无错题" in resp.json()["detail"]
    # 答题记录同样清理
    records = client.get("/records").json()["records"]
    assert all(r["question_id"] != qid for r in records)
