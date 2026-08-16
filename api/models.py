# models.py
from datetime import datetime, UTC
from typing import Optional, Dict, List
from pathlib import Path
import os, sys

from sqlmodel import SQLModel, Field, create_engine, Column, JSON


# =========================
# App data dir (Tauri-friendly)
# =========================
def get_app_data_dir(app_name="quiz-app"):
    if os.name == "nt":
        base = Path(os.environ["APPDATA"])
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path.home() / ".local" / "share"

    path = base / app_name
    path.mkdir(parents=True, exist_ok=True)
    return path


DATA_DIR = get_app_data_dir()
DB_PATH = DATA_DIR / "database.db"

engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)


# =========================
# Question Bank
# =========================
class QuestionBank(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    source: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


# =========================
# Question
# =========================
class Question(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    bank_id: int = Field(foreign_key="questionbank.id", index=True)

    type: str  # single | multi | judge | blank
    content: str

    options: Optional[Dict[str, str]] = Field(default=None, sa_column=Column(JSON))

    answer: Optional[List[str]] = Field(default=None, sa_column=Column(JSON))

    blank_answer: Optional[List[str]] = Field(default=None, sa_column=Column(JSON))

    score: float = 1.0

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


# =========================
# Quiz Session (顺序 / 随机做题)
# =========================
class QuizSession(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    bank_id: int = Field(index=True)
    mode: str  # sequential | random | mistake

    question_ids: List[int] = Field(sa_column=Column(JSON))
    current_index: int = 0
    total: int

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    finished: bool = False
    finished_at: Optional[datetime] = None


# =========================
# Answer Record (单题作答记录)
# =========================
class ExamRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    session_id: Optional[int] = Field(default=None, index=True)
    question_id: int = Field(index=True)

    user_answer: List[str] = Field(sa_column=Column(JSON))
    is_correct: bool

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


# =========================
# App Settings (键值配置，如 LLM 智能整理的 API 配置)
# =========================
class AppSetting(SQLModel, table=True):
    key: str = Field(primary_key=True)
    value: str = ""


# =========================
# Mistake Book (错题本)
# =========================
class Mistake(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    bank_id: int = Field(index=True)
    question_id: int = Field(unique=True, index=True)
    wrong_count: int = 1
    last_wrong_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    # 连续答对次数（已掌握判定）：答错清零，达到阈值自动出本（见 services/mistakes.py）
    consecutive_correct: int = 0


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


if __name__ == "__main__":
    create_db_and_tables()
    print("🎉 数据库 database.db 创建成功")
