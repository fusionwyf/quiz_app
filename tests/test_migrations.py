"""
数据库迁移链测试（唯一新增 seam：迁移函数直测，不经 HTTP）。

场景覆盖：
- 全新库 → 盖最新版本号，不跑任何步骤
- 迁移机制前的旧库（有表、user_version=0）→ 盖基线 1，数据完好
- 有步骤时按序执行、数据保留、版本号推进
- 幂等：重复运行不重跑已执行步骤
"""
import pytest
from sqlalchemy import create_engine
from sqlmodel import SQLModel, Session, select

import api.migrations as migrations
from api.models import QuestionBank, Question


@pytest.fixture(name="file_engine")
def file_engine_fixture(tmp_path):
    """文件型 SQLite（迁移基于文件头 user_version，内存库共享连接时行为不一致）"""
    return create_engine(f"sqlite:///{tmp_path / 'mig.db'}")


def _version(engine) -> int:
    with engine.connect() as conn:
        return int(conn.exec_driver_sql("PRAGMA user_version").fetchone()[0])


def test_fresh_db_stamped_latest(file_engine):
    """全新库：create_all 已建出最新结构，直接盖 SCHEMA_VERSION，不跑步骤"""
    ran = []
    migrations.run_migrations(file_engine)
    assert _version(file_engine) == migrations.SCHEMA_VERSION
    assert ran == []


def test_legacy_db_stamped_baseline_with_data(file_engine, monkeypatch):
    """迁移机制前的旧库（有表、version=0）：盖基线 1，已有数据完好。

    注：隔离真实迁移链（链上有 v2 步骤，会与本测试用当前模型建的表冲突），
    真实链的旧库升级由 test_real_chain_upgrades_v1_mistake_table 覆盖。"""
    monkeypatch.setattr(migrations, "MIGRATIONS", [])
    monkeypatch.setattr(migrations, "SCHEMA_VERSION", 1)
    SQLModel.metadata.create_all(file_engine)
    with file_engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA user_version = 0")  # 模拟旧库从未登记版本
        conn.commit()
    with Session(file_engine) as s:
        s.add(QuestionBank(name="旧库"))
        s.commit()

    migrations.run_migrations(file_engine)

    assert _version(file_engine) == 1
    with Session(file_engine) as s:
        assert len(s.exec(select(QuestionBank)).all()) == 1


def test_steps_apply_in_order_and_keep_data(file_engine, monkeypatch):
    """有步骤时按序执行：结构升级、数据保留、版本号推进到最新步骤"""
    SQLModel.metadata.create_all(file_engine)
    with Session(file_engine) as s:
        bank = QuestionBank(name="带数据的库")
        s.add(bank)
        s.commit()
        s.add(
            Question(bank_id=bank.id, type="single", content="旧题", answer=["A"])
        )
        s.commit()

    def step_add_column(conn):
        conn.exec_driver_sql(
            "ALTER TABLE mistake ADD COLUMN marker_col TEXT"
        )

    def step_add_table(conn):
        conn.exec_driver_sql("CREATE TABLE marker_v3 (id INTEGER PRIMARY KEY)")

    monkeypatch.setattr(
        migrations,
        "MIGRATIONS",
        [(2, step_add_column), (3, step_add_table)],
    )
    monkeypatch.setattr(migrations, "SCHEMA_VERSION", 3)

    migrations.run_migrations(file_engine)

    assert _version(file_engine) == 3
    with file_engine.connect() as conn:
        cols = [r[1] for r in conn.exec_driver_sql("PRAGMA table_info(mistake)")]
        assert "marker_col" in cols
        assert conn.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE name='marker_v3'"
        ).fetchone() is not None
    with Session(file_engine) as s:
        assert len(s.exec(select(Question)).all()) == 1  # 数据保留


def test_rerun_is_idempotent(file_engine, monkeypatch):
    """第二次运行：版本已就位，步骤不重跑（ALTER 再次执行会因列已存在而失败）"""
    SQLModel.metadata.create_all(file_engine)

    calls = []

    def step(conn):
        calls.append(1)
        conn.exec_driver_sql("ALTER TABLE mistake ADD COLUMN marker_col2 TEXT")

    monkeypatch.setattr(migrations, "MIGRATIONS", [(2, step)])
    monkeypatch.setattr(migrations, "SCHEMA_VERSION", 2)

    migrations.run_migrations(file_engine)
    assert _version(file_engine) == 2
    assert len(calls) == 1

    migrations.run_migrations(file_engine)  # 不抛错、不重跑
    assert _version(file_engine) == 2
    assert len(calls) == 1


def test_fresh_db_skips_pending_steps(file_engine, monkeypatch):
    """全新库直接盖最新版：即便链上有步骤也不执行（create_all 已含最新结构）"""
    calls = []

    def step(conn):
        calls.append(1)
        conn.exec_driver_sql("CREATE TABLE should_not_exist (id INTEGER)")

    monkeypatch.setattr(migrations, "MIGRATIONS", [(2, step)])
    monkeypatch.setattr(migrations, "SCHEMA_VERSION", 2)

    migrations.run_migrations(file_engine)

    assert _version(file_engine) == 2
    assert calls == []
    with file_engine.connect() as conn:
        assert conn.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE name='should_not_exist'"
        ).fetchone() is None


def test_failing_step_rolls_back_version(file_engine, monkeypatch):
    """步骤失败：版本号不推进（回滚），异常上抛"""
    SQLModel.metadata.create_all(file_engine)
    with file_engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA user_version = 1")
        conn.commit()

    def bad_step(conn):
        conn.exec_driver_sql("THIS IS NOT SQL")

    monkeypatch.setattr(migrations, "MIGRATIONS", [(2, bad_step)])
    monkeypatch.setattr(migrations, "SCHEMA_VERSION", 2)

    with pytest.raises(Exception):
        migrations.run_migrations(file_engine)
    assert _version(file_engine) == 1


def test_real_chain_upgrades_v1_mistake_table(file_engine):
    """真实迁移链：v1 结构的 mistake 表（无连对列）带数据升级到当前版本"""
    # 手工建 v1 时期的 mistake 表并写入数据（模拟老用户库）
    with file_engine.connect() as conn:
        conn.exec_driver_sql(
            """
            CREATE TABLE mistake (
                id INTEGER PRIMARY KEY,
                bank_id INTEGER NOT NULL,
                question_id INTEGER NOT NULL UNIQUE,
                wrong_count INTEGER NOT NULL,
                last_wrong_at TIMESTAMP NOT NULL
            )
            """
        )
        conn.exec_driver_sql(
            "INSERT INTO mistake (bank_id, question_id, wrong_count, last_wrong_at) "
            "VALUES (1, 42, 3, '2026-01-01 00:00:00')"
        )
        conn.exec_driver_sql("PRAGMA user_version = 1")
        conn.commit()

    migrations.run_migrations(file_engine)  # 真实链：应用 v2 步骤

    assert _version(file_engine) == migrations.SCHEMA_VERSION
    with file_engine.connect() as conn:
        cols = [r[1] for r in conn.exec_driver_sql("PRAGMA table_info(mistake)")]
        assert "consecutive_correct" in cols
        row = conn.exec_driver_sql(
            "SELECT wrong_count, consecutive_correct FROM mistake WHERE question_id = 42"
        ).fetchone()
    assert row[0] == 3  # 数据保留
    assert row[1] == 0  # 新列默认值
