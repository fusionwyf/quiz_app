"""
填空题判分规则测试（经练习作答 HTTP seam，见 spec 测试决定）。

规则（CONTEXT.md「备选答案」）：
- 比较前归一化：去首尾空格、忽略大小写、全角转半角（含标点）
- 每空多个可接受写法用 | 分隔，任一匹配即判对该空
- 多空逐空比较，全对才判对；空数不等直接判错
"""
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from api.models import QuestionBank, Question


def _make_bank_with_blank(session: Session, blank_answer: list[str]) -> tuple[int, int]:
    bank = QuestionBank(name="填空判分测试库")
    session.add(bank)
    session.commit()
    q = Question(
        bank_id=bank.id,
        type="blank",
        content="填空题干",
        answer=blank_answer,
        blank_answer=blank_answer,
        score=1.0,
    )
    session.add(q)
    session.commit()
    return bank.id, q.id


def _answer(client: TestClient, bank_id: int, question_id: int, user_answer: list[str]) -> bool:
    resp = client.post(f"/session/start?bank_id={bank_id}")
    assert resp.status_code == 200
    session_id = resp.json()["id"]
    resp = client.post(
        f"/session/{session_id}/answer",
        json={"question_id": question_id, "user_choices": user_answer},
    )
    assert resp.status_code == 200
    return resp.json()["is_correct"]


def test_blank_case_insensitive(client, session):
    bank_id, qid = _make_bank_with_blank(session, ["TCP"])
    assert _answer(client, bank_id, qid, ["tcp"]) is True
    assert _answer(client, bank_id, qid, ["Tcp"]) is True


def test_blank_strip_spaces(client, session):
    bank_id, qid = _make_bank_with_blank(session, ["  TCP  "])
    assert _answer(client, bank_id, qid, ["TCP"]) is True
    assert _answer(client, bank_id, qid, ["  tcp  "]) is True


def test_blank_fullwidth_to_halfwidth(client, session):
    bank_id, qid = _make_bank_with_blank(session, ["TCP"])
    assert _answer(client, bank_id, qid, ["ＴＣＰ"]) is True

    bank_id, qid = _make_bank_with_blank(session, ["1949"])
    assert _answer(client, bank_id, qid, ["１９４９"]) is True

    bank_id, qid = _make_bank_with_blank(session, ["Hello!"])
    assert _answer(client, bank_id, qid, ["Ｈｅｌｌｏ！"]) is True


def test_blank_alternatives_pipe_separated(client, session):
    bank_id, qid = _make_bank_with_blank(session, ["TCP|传输控制协议|tcp协议"])
    assert _answer(client, bank_id, qid, ["tcp"]) is True
    assert _answer(client, bank_id, qid, ["传输控制协议"]) is True
    assert _answer(client, bank_id, qid, ["TCP协议"]) is True  # 备选之一本身
    assert _answer(client, bank_id, qid, ["UDP"]) is False


def test_blank_multiple_blanks_all_must_match(client, session):
    bank_id, qid = _make_bank_with_blank(session, ["TCP", "UDP"])
    assert _answer(client, bank_id, qid, ["tcp", "udp"]) is True
    assert _answer(client, bank_id, qid, ["tcp", "tcp"]) is False
    assert _answer(client, bank_id, qid, ["tcp"]) is False


def test_blank_legacy_single_answer_compatible(client, session):
    """存量数据：单答案无 |，行为不变（仅多了归一化容错）"""
    bank_id, qid = _make_bank_with_blank(session, ["万维网"])
    assert _answer(client, bank_id, qid, ["万维网"]) is True
    assert _answer(client, bank_id, qid, ["局域网"]) is False


def test_choice_grading_unchanged(client, session, test_question):
    """单选判分行为不受填空重构影响"""
    bank_id = test_question.bank_id
    assert _answer(client, bank_id, test_question.id, ["A"]) is True
    assert _answer(client, bank_id, test_question.id, ["B"]) is False
