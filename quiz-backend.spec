# pyinstaller spec — 产物：dist/quiz-backend.exe（单文件，Tauri sidecar 用）
# 构建：uv run pyinstaller quiz-backend.spec --noconfirm
import sys
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = [
    # uvicorn 运行时按需懒加载这些模块，需显式收集
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan.on",
]

a = Analysis(
    ["backend_main.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="quiz-backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,  # sidecar 进程，保留控制台便于排错
    disable_windowed_traceback=False,
)
