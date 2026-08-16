from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from api.deps import get_session
from api.models import AppSetting
from api import llm

router = APIRouter()


class LlmConfigIn(BaseModel):
    """LLM 配置写入体：空 base_url/model 表示清除覆盖（回退环境变量/默认值），
    空 api_key 表示保留已存 Key"""

    provider: str = "none"
    base_url: str = ""
    model: str = ""
    api_key: str = ""


def _llm_config_payload(cfg: dict) -> dict:
    return {
        "provider": cfg["provider"],
        "base_url": cfg["base_url"],
        "model": cfg["model"],
        "api_key_masked": llm.mask_api_key(cfg["api_key"]),
        "api_key_set": bool(cfg["api_key"]),
        "enabled": llm.get_llm_status(cfg)["enabled"],
    }


def _resolve_test_config(body: LlmConfigIn | None, session: Session) -> dict:
    """测试连接用的配置：body 提供的字段覆盖已存配置（未保存即可先测）"""
    cfg = llm.resolve_llm_config(session)
    if body is None:
        return cfg
    provider = body.provider.strip().lower()
    if provider not in ("none", "openai"):
        raise HTTPException(400, "provider 仅支持 none / openai")
    cfg["provider"] = provider
    if body.base_url.strip():
        cfg["base_url"] = body.base_url.strip().rstrip("/")
    if body.model.strip():
        cfg["model"] = body.model.strip()
    if body.api_key.strip():
        cfg["api_key"] = body.api_key.strip()
    return cfg


@router.get("/llm/config")
def get_llm_config_route(session: Session = Depends(get_session)):
    """查询当前生效的 LLM 配置（数据库覆盖 > 环境变量），API Key 脱敏"""
    return _llm_config_payload(llm.resolve_llm_config(session))


@router.put("/llm/config")
def update_llm_config(body: LlmConfigIn, session: Session = Depends(get_session)):
    """保存 LLM 配置到数据库（AppSetting 表）"""
    provider = body.provider.strip().lower()
    if provider not in ("none", "openai"):
        raise HTTPException(400, "provider 仅支持 none / openai")
    base_url = body.base_url.strip().rstrip("/")
    if base_url and not base_url.startswith(("http://", "https://")):
        raise HTTPException(400, "base_url 必须以 http:// 或 https:// 开头")

    def _save(key: str, value: str):
        if value:
            row = session.get(AppSetting, key) or AppSetting(key=key)
            row.value = value
            session.add(row)
        else:
            row = session.get(AppSetting, key)
            if row is not None:
                session.delete(row)

    # provider 始终落库（none 也存，用于显式禁用环境变量启用的 LLM）
    _save("LLM_PROVIDER", provider)
    _save("LLM_BASE_URL", base_url)
    _save("LLM_MODEL", body.model.strip())
    # 空 api_key = 保留已存 Key
    if body.api_key.strip():
        _save("LLM_API_KEY", body.api_key.strip())
    session.commit()

    return _llm_config_payload(llm.resolve_llm_config(session))


@router.post("/llm/test")
def test_llm_route(
    body: LlmConfigIn | None = None, session: Session = Depends(get_session)
):
    """
    测试 LLM 连通性：带 body 时用 body 字段（未保存即可先测），
    不带 body 时测已保存配置。失败返回 400 + 可读原因
    """
    cfg = _resolve_test_config(body, session)
    try:
        reply = llm.test_llm_connection(cfg)
    except RuntimeError as e:
        raise HTTPException(400, str(e))
    return {"ok": True, "model": cfg["model"], "reply": reply}


@router.get("/llm/status")
def llm_status(session: Session = Depends(get_session)):
    """
    查询 LLM 智能整理配置状态（数据库覆盖 > 环境变量，供前端导入弹窗展示提示）
    """
    return llm.get_llm_status(llm.resolve_llm_config(session))
