# 备份/恢复路由（spec P1：手动全库备份/恢复 + 每日自动备份）
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session

from api.deps import get_session
from api.services import backup as backup_service

router = APIRouter()


@router.post("/backup")
def create_backup(session: Session = Depends(get_session)):
    """生成全库备份 JSON（题库/题目/错题/答题记录/应用设置；不含 LLM API Key）"""
    return backup_service.create_backup(session)


@router.get("/backup/list")
def list_auto_backups():
    """每日自动备份列表（最近 7 份）"""
    return {"backups": backup_service.list_auto_backups()}


async def _read_backup_body(request: Request) -> dict:
    """读取备份 JSON body；解析失败与非对象一律 400（避免 FastAPI 422 混淆前端提示）"""
    try:
        payload = json.loads((await request.body()).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise HTTPException(400, "备份文件不是有效的 JSON")
    if not isinstance(payload, dict):
        raise HTTPException(400, "备份文件格式不正确")
    return payload


@router.post("/backup/restore")
async def restore_backup(request: Request, session: Session = Depends(get_session)):
    """从上传的备份恢复全部数据——覆盖现有数据，前端必须先做用户确认"""
    payload = await _read_backup_body(request)
    try:
        counts = backup_service.restore_backup(session, payload)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"message": "恢复完成", "restored": counts}


@router.post("/backup/restore/auto/{filename}")
def restore_auto_backup(filename: str, session: Session = Depends(get_session)):
    """从自动备份恢复（同上，覆盖现有数据）"""
    try:
        payload = backup_service.load_auto_backup(filename)
        counts = backup_service.restore_backup(session, payload)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"message": f"已从自动备份 {filename} 恢复", "restored": counts}
