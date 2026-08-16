# 应用外观设置（spec P3：浅色/深色/跟随系统，持久化到 AppSetting）
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from api.deps import get_session
from api.models import AppSetting

router = APIRouter()

THEME_KEY = "UI_THEME"
VALID_THEMES = ("light", "dark", "system")


def get_theme(session: Session) -> str:
    row = session.get(AppSetting, THEME_KEY)
    return row.value if row and row.value in VALID_THEMES else "system"


class ThemeIn(BaseModel):
    value: str


@router.get("/settings/theme")
def get_theme_route(session: Session = Depends(get_session)):
    """外观主题（light / dark / system，默认 system 跟随系统）"""
    return {"theme": get_theme(session)}


@router.put("/settings/theme")
def set_theme_route(body: ThemeIn, session: Session = Depends(get_session)):
    if body.value not in VALID_THEMES:
        raise HTTPException(400, f"theme 仅支持 {' / '.join(VALID_THEMES)}")
    row = session.get(AppSetting, THEME_KEY) or AppSetting(key=THEME_KEY)
    row.value = body.value
    session.add(row)
    session.commit()
    return {"theme": body.value}
