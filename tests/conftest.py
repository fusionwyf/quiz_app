"""
pytest 配置和共享fixture
"""

import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

# Ensure project root is on sys.path so tests can import `api` package
root = Path(__file__).resolve().parents[1]
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

from api.api import app, get_session
from api.models import QuestionBank, Question, QuizSession, ExamRecord, Mistake


@pytest.fixture(name="session")
def session_fixture():
    """
    创建测试数据库会话
    使用内存SQLite数据库，确保测试隔离
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session):
    """
    创建测试客户端，覆盖依赖注入
    """

    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def test_bank(session: Session) -> QuestionBank:
    """创建测试题库fixture"""
    bank = QuestionBank(name="测试题库")
    session.add(bank)
    session.commit()
    session.refresh(bank)
    return bank


@pytest.fixture
def test_question(session: Session, test_bank: QuestionBank) -> Question:
    """创建测试题目fixture"""
    question = Question(
        bank_id=test_bank.id,
        type="single",
        content="测试题目",
        options={"A": "选项A", "B": "选项B"},
        answer=["A"],
        score=1.0,
    )
    session.add(question)
    session.commit()
    session.refresh(question)
    return question
