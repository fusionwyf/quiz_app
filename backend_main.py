# backend_main.py — PyInstaller 打包入口。
# 桌面端（Tauri）以 sidecar 方式启动：quiz-backend.exe --host 127.0.0.1 --port <N> --parent-pid <PID>
import argparse
import os
import threading


def _watch_parent(pid: int) -> None:
    """监听父进程（Tauri 壳）：壳崩溃/被强杀后本进程自杀，防止后端残留。仅 Windows。"""
    import ctypes

    SYNCHRONIZE = 0x00100000
    INFINITE = 0xFFFFFFFF
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(SYNCHRONIZE, False, pid)
    if not handle:
        os._exit(1)  # 打不开说明父进程已死
    kernel32.WaitForSingleObject(handle, INFINITE)
    kernel32.CloseHandle(handle)
    os._exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Quiz App backend server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--parent-pid",
        type=int,
        default=None,
        help="宿主进程 PID，宿主退出后本进程自动退出（桌面打包用）",
    )
    args = parser.parse_args()

    if args.parent_pid and os.name == "nt":
        threading.Thread(target=_watch_parent, args=(args.parent_pid,), daemon=True).start()

    import uvicorn

    from api.api import app

    # 冻结环境下直接传 app 对象（不用 "api.api:app" 导入字符串，避免二次导入）
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
