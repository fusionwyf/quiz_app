# 数据库迁移链（ADR-0003：PRAGMA user_version 轻量迁移，不引入 Alembic）。
#
# 规则：
# 1. 每个迁移步骤 = (目标版本, 升级函数)，目标版本必须严格递增、从 2 开始
#    （版本 1 是迁移机制引入时的基线，即当时的 create_all 结构）。
# 2. 已随安装包发布的步骤【不可修改、不可删除】，只能在链尾追加——
#    用户库上已执行过的步骤没有“重来”的机会。
# 3. 任何 schema 变更都必须：改 models.py + 追加迁移步骤 + SCHEMA_VERSION 递增，
#    禁止“改模型 + create_all 就完事”的心智（create_all 不会给已有表加列）。
# 4. 启动引导：user_version=0 且无表 = 全新库（create_all 已建出最新结构），
#    直接盖 SCHEMA_VERSION；有表 = 迁移机制引入前的旧库，盖基线 1 后走链。
from sqlalchemy.engine import Engine
from sqlalchemy.engine import Connection
from typing import Callable, List, Tuple

from api.models import create_db_and_tables

# 当前最新结构版本；追加迁移步骤时递增
SCHEMA_VERSION = 1

# (目标版本, 从 target-1 升到 target 的步骤函数)。基线之后暂无步骤。
MIGRATIONS: List[Tuple[int, Callable[[Connection], None]]] = []


def _get_user_version(conn: Connection) -> int:
    return int(conn.exec_driver_sql("PRAGMA user_version").fetchone()[0])


def _set_user_version(conn: Connection, version: int) -> None:
    # PRAGMA 不支持参数绑定；version 来自本模块内部的 int，无注入面
    conn.exec_driver_sql(f"PRAGMA user_version = {int(version)}")


def _has_legacy_tables(conn: Connection) -> bool:
    row = conn.exec_driver_sql(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='questionbank'"
    ).fetchone()
    return row is not None


def run_migrations(engine: Engine) -> None:
    """把数据库升级到 SCHEMA_VERSION；幂等，可安全地在每次启动时调用。"""
    create_db_and_tables()  # 全新库先建出最新结构（旧库此调用无副作用）

    with engine.connect() as conn:
        version = _get_user_version(conn)

        if version == 0:
            # 迁移机制引入前的库：无表 = 刚建出的最新结构；有表 = 旧结构，从基线 1 起步
            version = 1 if _has_legacy_tables(conn) else SCHEMA_VERSION
            _set_user_version(conn, version)
            conn.commit()

        for target, step in MIGRATIONS:
            if target <= version:
                continue  # 已执行过（或全新库已盖最新版），不重跑
            try:
                step(conn)
                _set_user_version(conn, target)
                conn.commit()
                version = target
            except Exception:
                conn.rollback()
                raise
