# 应用组装层：FastAPI 实例、CORS、lifespan 与路由挂载。
# 注意：conftest 与 backend_main 依赖 `from api.api import app, get_session`，勿移除 get_session 的再导出。
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.deps import get_session  # noqa: F401 —— re-export 保持既有导入点稳定
from api.migrations import run_migrations
from api.models import engine
from api.routers import banks, questions, sessions, mistakes, records, llm_config, backup
from api.services import backup as backup_service
from sqlmodel import Session


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 建表（全新库）+ 迁移链升级（旧库）——见 ADR-0003
    run_migrations(engine)
    # 每日首次启动自动备份（保留最近 7 份，失败不阻断启动）
    with Session(engine) as session:
        try:
            backup_service.maybe_daily_backup(session)
        except Exception:
            pass
    yield


app = FastAPI(title="Quiz App API", version="2.0", lifespan=lifespan)

# ===== CORS（给 React / Tauri 用）=====


def _cors_origins() -> list[str]:
    env = os.environ.get("CORS_ORIGINS")
    if env:
        return [o.strip() for o in env.split(",") if o.strip()]
    return [
        "http://localhost:5173",  # Vite dev
        "http://tauri.localhost",  # Tauri WebView (Windows)
        "tauri://localhost",  # Tauri WebView (macOS/Linux)
    ]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(banks.router)
app.include_router(questions.router)
app.include_router(sessions.router)
app.include_router(mistakes.router)
app.include_router(records.router)
app.include_router(llm_config.router)
app.include_router(backup.router)
