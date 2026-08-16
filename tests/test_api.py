"""
Quiz App API 单元测试

使用 pytest 和 FastAPI TestClient 测试所有API接口。
使用内存SQLite数据库进行测试，确保测试隔离。
"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from api.models import QuestionBank, Question, QuizSession, ExamRecord, Mistake


# ======================================================
# 测试数据工厂
# ======================================================


def create_test_bank(session: Session, name: str = "测试题库") -> QuestionBank:
    """创建测试题库"""
    bank = QuestionBank(name=name)
    session.add(bank)
    session.commit()
    session.refresh(bank)
    return bank


def create_test_question(
    session: Session,
    bank_id: int,
    qtype: str = "single",
    content: str = "测试题目",
    options: dict = None,
    answer: list = None,
    score: float = 1.0,
) -> Question:
    """创建测试题目"""
    if options is None:
        options = {"A": "选项A", "B": "选项B"}
    if answer is None:
        answer = ["A"]

    question = Question(
        bank_id=bank_id,
        type=qtype,
        content=content,
        options=options,
        answer=answer,
        score=score,
    )
    session.add(question)
    session.commit()
    session.refresh(question)
    return question


# ======================================================
# 题库管理测试
# ======================================================


def test_list_banks_empty(client: TestClient):
    """测试获取空题库列表"""
    response = client.get("/banks")
    assert response.status_code == 200
    assert response.json() == []


def test_create_bank(client: TestClient):
    """测试创建题库"""
    response = client.post("/banks/create", params={"name": "数学题库"})
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "数学题库"
    assert "id" in data
    assert "created_at" in data


def test_list_banks_with_data(client: TestClient, session: Session):
    """测试获取有数据的题库列表"""
    # 先创建题库
    create_test_bank(session, "数学题库")
    create_test_bank(session, "英语题库")

    response = client.get("/banks")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["name"] == "数学题库"
    assert data[1]["name"] == "英语题库"


def test_list_banks_with_question_count(client: TestClient, session: Session):
    """GET /banks 返回每个库的题目数 question_count"""
    bank1 = create_test_bank(session, "数学题库")
    bank2 = create_test_bank(session, "英语题库")
    create_test_question(session, bank1.id, content="题目1")
    create_test_question(session, bank1.id, content="题目2")
    create_test_question(session, bank2.id, content="题目3")

    response = client.get("/banks")
    assert response.status_code == 200
    counts = {b["name"]: b["question_count"] for b in response.json()}
    assert counts["数学题库"] == 2
    assert counts["英语题库"] == 1


def test_create_bank_duplicate_name(client: TestClient, session: Session):
    """同名题库不允许重复创建，返回 409"""
    create_test_bank(session, "已存在题库")

    response = client.post("/banks/create", params={"name": "已存在题库"})
    assert response.status_code == 409
    assert "已存在" in response.json()["detail"]


def test_create_bank_name_normalization(client: TestClient):
    """名称首尾空白被去除；纯空白名称返回 400；去除后重名同样 409"""
    ok = client.post("/banks/create", params={"name": "  带空格题库  "})
    assert ok.status_code == 200
    assert ok.json()["name"] == "带空格题库"

    blank = client.post("/banks/create", params={"name": "   "})
    assert blank.status_code == 400

    dup = client.post("/banks/create", params={"name": " 带空格题库 "})
    assert dup.status_code == 409


def test_delete_bank_not_found(client: TestClient):
    """删除不存在的题库返回 404"""
    response = client.delete("/banks/9999")
    assert response.status_code == 404


def test_delete_bank_cascades(client: TestClient, session: Session):
    """删除题库级联清理题目、Session、答题记录与错题"""
    bank = create_test_bank(session, "待删除题库")
    other = create_test_bank(session, "保留题库")

    q1 = create_test_question(session, bank.id, content="题1")
    q2 = create_test_question(session, bank.id, content="题2")
    keep_q = create_test_question(session, other.id, content="保留题")

    quiz_session = QuizSession(
        bank_id=bank.id, mode="sequential", question_ids=[q1.id, q2.id], total=2
    )
    session.add(quiz_session)
    session.commit()
    session.refresh(quiz_session)

    session.add(ExamRecord(session_id=quiz_session.id, question_id=q1.id, user_answer=["A"], is_correct=True))
    session.add(ExamRecord(question_id=q2.id, user_answer=["B"], is_correct=False))  # 无 session 直接作答
    session.add(ExamRecord(question_id=keep_q.id, user_answer=["A"], is_correct=True))
    session.add(Mistake(bank_id=bank.id, question_id=q1.id))
    session.add(Mistake(bank_id=other.id, question_id=keep_q.id))
    session.commit()

    response = client.delete(f"/banks/{bank.id}")
    assert response.status_code == 200

    assert session.get(QuestionBank, bank.id) is None
    assert session.exec(select(Question).where(Question.bank_id == bank.id)).all() == []
    assert session.exec(select(QuizSession).where(QuizSession.bank_id == bank.id)).all() == []
    # 该库题目的答题记录（含无 session 的）与错题全部清除
    assert session.exec(select(ExamRecord).where(ExamRecord.question_id.in_([q1.id, q2.id]))).all() == []
    assert session.exec(select(Mistake).where(Mistake.bank_id == bank.id)).all() == []

    # 其他题库的数据不受影响
    assert session.get(QuestionBank, other.id) is not None
    assert session.exec(select(Question).where(Question.bank_id == other.id)).all()[0].id == keep_q.id
    assert len(session.exec(select(ExamRecord)).all()) == 1
    assert len(session.exec(select(Mistake)).all()) == 1


# ======================================================
# 题目CRUD测试
# ======================================================


def test_create_question(client: TestClient, session: Session):
    """测试创建题目"""
    # 先创建题库
    bank = create_test_bank(session)

    question_data = {
        "bank_id": bank.id,
        "type": "single",
        "content": "1+1=?",
        "options": {"A": "1", "B": "2", "C": "3", "D": "4"},
        "answer": ["B"],
        "score": 1.0,
    }

    response = client.post("/questions", json=question_data)
    assert response.status_code == 200
    data = response.json()
    assert data["question"] == "1+1=?"
    assert data["type"] == "single"
    assert data["score"] == 1.0
    assert "id" in data


def test_create_question_invalid_bank(client: TestClient):
    """测试创建题目时使用不存在的题库"""
    question_data = {
        "bank_id": 999,  # 不存在的题库ID
        "type": "single",
        "content": "测试题目",
        "answer": ["A"],
    }

    response = client.post("/questions", json=question_data)
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_create_question_invalid_type(client: TestClient, session: Session):
    """测试创建题目时使用无效的类型"""
    bank = create_test_bank(session)

    question_data = {
        "bank_id": bank.id,
        "type": "invalid_type",  # 无效类型
        "content": "测试题目",
        "answer": ["A"],
    }

    response = client.post("/questions", json=question_data)
    assert response.status_code == 400
    assert "invalid" in response.json()["detail"].lower()


def test_get_question(client: TestClient, session: Session):
    """测试获取题目详情"""
    bank = create_test_bank(session)
    question = create_test_question(session, bank.id)

    response = client.get(f"/questions/{question.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == question.id
    assert data["question"] == question.content
    assert data["type"] == question.type


def test_get_question_not_found(client: TestClient):
    """测试获取不存在的题目"""
    response = client.get("/questions/999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_update_question(client: TestClient, session: Session):
    """测试更新题目"""
    bank = create_test_bank(session)
    question = create_test_question(session, bank.id, content="原题目")

    update_data = {"content": "更新后的题目", "score": 2.0}

    response = client.put(f"/questions/{question.id}", json=update_data)
    assert response.status_code == 200
    data = response.json()
    assert data["question"] == "更新后的题目"
    assert data["score"] == 2.0


def test_delete_question(client: TestClient, session: Session):
    """测试删除题目"""
    bank = create_test_bank(session)
    question = create_test_question(session, bank.id)

    # 删除题目
    response = client.delete(f"/questions/{question.id}")
    assert response.status_code == 200
    assert "deleted" in response.json()["message"].lower()

    # 验证题目已删除
    response = client.get(f"/questions/{question.id}")
    assert response.status_code == 404


# ======================================================
# 随机出题测试
# ======================================================


def test_get_random_quiz_empty_bank(client: TestClient, session: Session):
    """测试从空题库随机出题"""
    bank = create_test_bank(session)

    response = client.get(f"/quiz/random?bank_id={bank.id}")
    assert response.status_code == 200
    assert response.json() == []


def test_get_random_quiz(client: TestClient, session: Session):
    """测试随机出题"""
    bank = create_test_bank(session)

    # 创建多个题目
    for i in range(10):
        create_test_question(session, bank.id, content=f"题目{i}")

    # 请求5个随机题目
    response = client.get(f"/quiz/random?bank_id={bank.id}&count=5")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 5
    assert all("id" in q for q in data)
    assert all("question" in q for q in data)
    assert all("type" in q for q in data)


def test_get_random_quiz_with_type_filter(client: TestClient, session: Session):
    """测试按题型过滤随机出题"""
    bank = create_test_bank(session)

    # 创建单选和多选题目
    create_test_question(session, bank.id, qtype="single", content="单选题")
    create_test_question(session, bank.id, qtype="multi", content="多选题")
    create_test_question(session, bank.id, qtype="single", content="单选题2")

    # 只请求单选题
    response = client.get(f"/quiz/random?bank_id={bank.id}&qtype=single")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert all(q["type"] == "single" for q in data)


# ======================================================
# 做题Session测试
# ======================================================


def test_start_session(client: TestClient, session: Session):
    """测试开始做题Session"""
    bank = create_test_bank(session)

    # 先创建一些题目
    for i in range(3):
        create_test_question(session, bank.id, content=f"题目{i}")

    response = client.post(f"/session/start?bank_id={bank.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["bank_id"] == bank.id
    assert data["mode"] == "sequential"
    assert data["total"] == 3
    assert data["finished"] is False
    assert "id" in data


def test_start_session_empty_bank(client: TestClient, session: Session):
    """测试从空题库开始Session"""
    bank = create_test_bank(session)  # 没有题目

    response = client.post(f"/session/start?bank_id={bank.id}")
    assert response.status_code == 404
    assert "no questions" in response.json()["detail"].lower()


def test_start_session_random_mode(client: TestClient, session: Session):
    """测试随机模式开始Session"""
    bank = create_test_bank(session)

    for i in range(5):
        create_test_question(session, bank.id, content=f"题目{i}")

    response = client.post(f"/session/start?bank_id={bank.id}&mode=random")
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "random"


def test_get_current_question(client: TestClient, session: Session):
    """测试获取当前题目"""
    bank = create_test_bank(session)
    question1 = create_test_question(session, bank.id, content="题目1")
    create_test_question(session, bank.id, content="题目2")

    # 开始Session
    session_response = client.post(f"/session/start?bank_id={bank.id}")
    session_id = session_response.json()["id"]

    # 获取当前题目（应该是第一个）
    response = client.get(f"/session/{session_id}/current")
    assert response.status_code == 200
    data = response.json()
    assert data["question"] == "题目1"


def test_submit_answer(client: TestClient, session: Session):
    """测试提交答案"""
    bank = create_test_bank(session)
    question = create_test_question(session, bank.id, content="测试题目", answer=["B"])

    # 开始Session
    session_response = client.post(f"/session/start?bank_id={bank.id}")
    session_id = session_response.json()["id"]

    # 提交正确答案
    answer_data = {"question_id": question.id, "user_choices": ["B"]}

    response = client.post(f"/session/{session_id}/answer", json=answer_data)
    assert response.status_code == 200
    data = response.json()
    assert data["is_correct"] is True
    assert data["score_obtained"] == 1.0
    assert data["question_id"] == question.id


def test_submit_wrong_answer(client: TestClient, session: Session):
    """测试提交错误答案"""
    bank = create_test_bank(session)
    question = create_test_question(session, bank.id, content="测试题目", answer=["B"])

    # 开始Session
    session_response = client.post(f"/session/start?bank_id={bank.id}")
    session_id = session_response.json()["id"]

    # 提交错误答案
    answer_data = {"question_id": question.id, "user_choices": ["A"]}  # 错误答案

    response = client.post(f"/session/{session_id}/answer", json=answer_data)
    assert response.status_code == 200
    data = response.json()
    assert data["is_correct"] is False
    assert data["score_obtained"] == 0.0


# ======================================================
# Session增强功能测试
# ======================================================


def test_get_session_status(client: TestClient, session: Session):
    """测试获取Session状态"""
    bank = create_test_bank(session)
    question1 = create_test_question(session, bank.id, content="题目1", score=2.0)
    question2 = create_test_question(session, bank.id, content="题目2", score=3.0)

    # 开始Session
    session_response = client.post(f"/session/start?bank_id={bank.id}")
    session_id = session_response.json()["id"]

    # 提交一个正确答案
    answer_data = {"question_id": question1.id, "user_choices": question1.answer}
    client.post(f"/session/{session_id}/answer", json=answer_data)

    # 获取状态
    response = client.get(f"/session/{session_id}/status")
    assert response.status_code == 200
    data = response.json()

    assert data["session_id"] == session_id
    assert data["current_index"] == 1  # 已回答1题
    assert data["total"] == 2  # 总共2题
    assert data["progress_percentage"] == 50.0  # 50%进度
    assert data["correct_count"] == 1  # 答对1题
    assert data["total_score"] == 2.0  # 得分2.0
    assert data["finished"] is False


def test_finish_session(client: TestClient, session: Session):
    """测试手动结束Session"""
    bank = create_test_bank(session)
    question1 = create_test_question(session, bank.id, content="题目1", score=2.0)
    question2 = create_test_question(session, bank.id, content="题目2", score=3.0)

    # 开始Session
    session_response = client.post(f"/session/start?bank_id={bank.id}")
    session_id = session_response.json()["id"]

    # 提交一个答案
    answer_data = {"question_id": question1.id, "user_choices": question1.answer}
    client.post(f"/session/{session_id}/answer", json=answer_data)

    # 手动结束Session
    response = client.post(f"/session/{session_id}/finish")
    assert response.status_code == 200
    data = response.json()

    assert data["session_id"] == session_id
    assert data["total_questions"] == 2
    assert data["answered_questions"] == 1
    assert data["correct_count"] == 1
    assert data["total_score_obtained"] == 2.0
    assert data["max_possible_score"] == 5.0
    assert data["accuracy_percentage"] == 100.0  # 只答了1题且正确
    assert data["finished_at"] is not None


# ======================================================
# 错题本测试
# （答错自动入本/连对出本语义见 test_mistake_book.py；
#  POST /mistakes/mark 与 GET /records/mistakes 已随双机制合一废除）
# ======================================================


def test_unmark_mistake(client: TestClient, session: Session):
    """测试取消错题标记"""
    bank = create_test_bank(session)
    question = create_test_question(session, bank.id, content="测试题目")

    # 先标记为错题
    mistake = Mistake(bank_id=bank.id, question_id=question.id, wrong_count=1)
    session.add(mistake)
    session.commit()

    # 取消标记
    response = client.delete(f"/mistakes/{question.id}")
    assert response.status_code == 200
    assert "removed" in response.json()["message"].lower()

    # 验证错题已删除
    mistake = session.get(Mistake, mistake.id)
    assert mistake is None


def test_get_mistake_book(client: TestClient, session: Session):
    """测试获取错题本"""
    bank1 = create_test_bank(session, "题库1")
    bank2 = create_test_bank(session, "题库2")

    question1 = create_test_question(session, bank1.id, content="题目1")
    question2 = create_test_question(session, bank2.id, content="题目2")

    # 添加错题记录
    mistake1 = Mistake(bank_id=bank1.id, question_id=question1.id, wrong_count=2)
    mistake2 = Mistake(bank_id=bank2.id, question_id=question2.id, wrong_count=1)
    session.add_all([mistake1, mistake2])
    session.commit()

    # 获取所有错题
    response = client.get("/mistakes")
    assert response.status_code == 200
    data = response.json()
    assert len(data["mistakes"]) == 2

    # 按题库过滤
    response = client.get(f"/mistakes?bank_id={bank1.id}")
    assert response.status_code == 200
    data = response.json()
    assert len(data["mistakes"]) == 1
    assert data["mistakes"][0]["question_content"] == "题目1"


# ======================================================
# 统计与记录测试
# ======================================================


def test_get_records_pagination(client: TestClient, session: Session):
    """测试分页获取答题记录"""
    bank = create_test_bank(session)
    question = create_test_question(session, bank.id, content="测试题目")

    # 创建多个答题记录
    for i in range(15):
        record = ExamRecord(
            session_id=1,
            question_id=question.id,
            user_answer=["A"],
            is_correct=(i % 2 == 0),  # 交替正确/错误
        )
        session.add(record)
    session.commit()

    # 第一页
    response = client.get("/records?page=1&page_size=10")
    assert response.status_code == 200
    data = response.json()
    assert data["page"] == 1
    assert data["page_size"] == 10
    assert data["total"] == 15
    assert len(data["records"]) == 10

    # 第二页
    response = client.get("/records?page=2&page_size=10")
    assert response.status_code == 200
    data = response.json()
    assert len(data["records"]) == 5  # 第二页只有5条


def test_get_records_filtering(client: TestClient, session: Session):
    """测试过滤答题记录"""
    bank = create_test_bank(session)
    question1 = create_test_question(session, bank.id, content="题目1")
    question2 = create_test_question(session, bank.id, content="题目2")

    # 创建不同条件的记录
    records = [
        ExamRecord(
            session_id=1, question_id=question1.id, user_answer=["A"], is_correct=True
        ),
        ExamRecord(
            session_id=1, question_id=question2.id, user_answer=["B"], is_correct=False
        ),
        ExamRecord(
            session_id=2, question_id=question1.id, user_answer=["A"], is_correct=True
        ),
    ]
    session.add_all(records)
    session.commit()

    # 按题目过滤
    response = client.get(f"/records?question_id={question1.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert all(r["question_id"] == question1.id for r in data["records"])

    # 按正确性过滤
    response = client.get("/records?is_correct=true")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert all(r["is_correct"] is True for r in data["records"])


def test_get_question_stats(client: TestClient, session: Session):
    """测试获取题目统计"""
    bank = create_test_bank(session)
    question = create_test_question(session, bank.id, content="测试题目", score=2.0)

    # 创建答题记录（3次正确，2次错误）
    for i in range(5):
        record = ExamRecord(
            session_id=1,
            question_id=question.id,
            user_answer=["A"],
            is_correct=(i < 3),  # 前3次正确
        )
        session.add(record)
    session.commit()

    response = client.get(f"/stats/questions/{question.id}")
    assert response.status_code == 200
    data = response.json()

    assert data["question_id"] == question.id
    assert data["total_attempts"] == 5
    assert data["correct_attempts"] == 3
    assert data["wrong_attempts"] == 2
    assert data["correct_rate"] == 60.0  # 3/5 = 60%
    assert data["average_score"] == 1.2  # 3*2.0/5 = 1.2
    assert data["total_score_obtained"] == 6.0  # 3*2.0
    assert data["total_possible_score"] == 10.0  # 5*2.0


# ======================================================
# 导入导出测试
# ======================================================


def test_export_questions_json(client: TestClient, session: Session):
    """测试导出题目为JSON格式"""
    bank = create_test_bank(session, "测试题库")

    # 创建几个题目
    for i in range(3):
        create_test_question(
            session,
            bank.id,
            content=f"题目{i}",
            qtype="single" if i % 2 == 0 else "multi",
            score=float(i + 1),
        )

    response = client.get(f"/banks/{bank.id}/export?format=json")
    assert response.status_code == 200
    data = response.json()

    assert data["bank_id"] == bank.id
    assert data["bank_name"] == "测试题库"
    assert data["question_count"] == 3
    assert len(data["questions"]) == 3

    for i, q in enumerate(data["questions"]):
        assert q["content"] == f"题目{i}"
        assert q["score"] == float(i + 1)


def test_export_questions_txt(client: TestClient, session: Session):
    """测试导出题目为TXT格式"""
    bank = create_test_bank(session, "测试题库")
    question = create_test_question(
        session,
        bank.id,
        content="测试题目",
        options={"A": "选项A", "B": "选项B"},
        answer=["A"],
        score=1.5,
    )

    response = client.get(f"/banks/{bank.id}/export?format=txt")
    assert response.status_code == 200
    txt_content = response.text

    # 检查TXT内容包含关键信息
    assert "题目：测试题目" in txt_content
    assert "类型：single" in txt_content
    assert '选项：{"A": "选项A", "B": "选项B"}' in txt_content
    assert '答案：["A"]' in txt_content
    assert "分数：1.5" in txt_content


def test_import_questions_json(client: TestClient, session: Session):
    """测试从JSON导入题目"""
    bank = create_test_bank(session, "目标题库")

    import_data = [
        {
            "type": "single",
            "content": "导入题目1",
            "options": {"A": "选项A", "B": "选项B"},
            "answer": ["A"],
            "score": 1.0,
        },
        {
            "type": "multi",
            "content": "导入题目2",
            "options": {"A": "选项A", "B": "选项B", "C": "选项C"},
            "answer": ["A", "B"],
            "score": 2.0,
        },
    ]

    import_json = (
        "[\n  "
        + ",\n  ".join(str(item).replace("'", '"') for item in import_data)
        + "\n]"
    )

    response = client.post(
        f"/banks/{bank.id}/import?format=json",
        content=import_json,
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["imported_count"] == 2

    # 验证题目已导入
    questions = session.exec(select(Question).where(Question.bank_id == bank.id)).all()
    assert len(questions) == 2
    assert {q.content for q in questions} == {"导入题目1", "导入题目2"}


def test_import_questions_txt(client: TestClient, session: Session):
    """测试从TXT导入题目"""
    bank = create_test_bank(session, "目标题库")

    txt_content = """题目：TXT导入题目1
类型：single
选项：{"A": "选项A", "B": "选项B"}
答案：["A"]
分数：1.0

题目：TXT导入题目2
类型：multi
选项：{"A": "选项A", "B": "选项B", "C": "选项C"}
答案：["A", "B"]
分数：2.0"""

    response = client.post(
        f"/banks/{bank.id}/import?format=txt",
        content=txt_content,
        headers={"Content-Type": "text/plain"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["imported_count"] == 2

    # 验证题目已导入
    questions = session.exec(select(Question).where(Question.bank_id == bank.id)).all()
    assert len(questions) == 2


# ======================================================
# 主测试运行
# ======================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
