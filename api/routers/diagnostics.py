# 诊断路由：日志目录定位/打开、诊断包导出（spec P1）
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from api.services import diagnostics

router = APIRouter()


@router.get("/diagnostics/info")
def diagnostics_info_route():
    """日志目录与运行环境信息"""
    return diagnostics.diagnostics_info("2.0")


@router.post("/diagnostics/open-folder")
def open_log_folder_route():
    """用系统文件管理器打开日志目录"""
    try:
        diagnostics.open_log_folder()
    except Exception as e:
        raise HTTPException(500, f"无法打开日志目录：{e}")
    return {"message": "已打开日志目录", "path": str(diagnostics.LOG_DIR)}


@router.get("/diagnostics/export")
def export_diagnostics_route():
    """导出诊断包 zip（日志 + 版本 + 系统信息），供用户附到 Issue"""
    content, filename = diagnostics.export_diagnostics_zip("2.0")
    return Response(
        content=content,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
