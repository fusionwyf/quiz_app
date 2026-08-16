# -*- coding: utf-8 -*-
"""一键发布脚本（spec P2 自动更新）。

用法：
    uv run python scripts/publish-release.py           # 构建 + 创建 GitHub Release（v<version>）
    uv run python scripts/publish-release.py --dry-run # 只构建并生成产物清单，不发布

前置条件：
    1. 已更新 frontend/src-tauri/tauri.conf.json 与 Cargo.toml 的 version，并写入 CHANGELOG.md
    2. updater 私钥在 %USERPROFILE%\\.tauri\\quiz_app_updater.key（不入库；丢失则无法再发更新）
    3. gh 已登录；远端为 github.com/fusionwyf/quiz_app
"""
import argparse
import json
import os
import pathlib
import shutil
import subprocess
import sys
import urllib.parse
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
SRC_TAURI = FRONTEND / "src-tauri"
REPO = "fusionwyf/quiz_app"
KEY_PATH = pathlib.Path.home() / ".tauri" / "quiz_app_updater.key"


def run(cmd, cwd=None, env=None, check=True):
    print(f"$ {' '.join(str(c) for c in cmd)}")
    result = subprocess.run(
        cmd, cwd=cwd, env=env, shell=False,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if result.stdout.strip():
        print(result.stdout.strip()[-2000:])
    if check and result.returncode != 0:
        print(result.stderr.strip()[-2000:], file=sys.stderr)
        raise SystemExit(f"命令失败（{result.returncode}）：{cmd[0]}")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="只构建，不发布 Release")
    args = parser.parse_args()

    conf = json.loads((SRC_TAURI / "tauri.conf.json").read_text(encoding="utf-8"))
    version = conf["version"]
    product = conf["productName"]
    tag = f"v{version}"
    print(f"== 发布 {product} {tag} ==")

    if not KEY_PATH.exists():
        raise SystemExit(f"未找到 updater 私钥：{KEY_PATH}（参见 docs/release-checklist.md）")

    existing = run(["gh", "release", "view", tag], check=False)
    if existing.returncode == 0:
        raise SystemExit(f"Release {tag} 已存在；请先递增版本号并更新 CHANGELOG.md")

    # 1) PyInstaller 后端 sidecar
    run(["uv", "run", "pyinstaller", "quiz-backend.spec", "--noconfirm"], cwd=ROOT)
    sidecar = SRC_TAURI / "binaries" / "quiz-backend-x86_64-pc-windows-msvc.exe"
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "dist" / "quiz-backend.exe", sidecar)
    print(f"sidecar 已更新：{sidecar}")

    # 2) tauri build（签名密钥经环境变量传入，绝不写入仓库；空密码也要显式给，避免交互挂起）
    env = os.environ.copy()
    env["TAURI_SIGNING_PRIVATE_KEY_PATH"] = str(KEY_PATH)
    env["TAURI_SIGNING_PRIVATE_KEY_PASSWORD"] = os.environ.get(
        "TAURI_SIGNING_PRIVATE_KEY_PASSWORD", ""
    )
    run(["npx", "tauri", "build"], cwd=FRONTEND, env=env)

    # 3) 收集 NSIS 安装包与签名
    nsis_dir = SRC_TAURI / "target" / "release" / "bundle" / "nsis"
    exe = next(p for p in nsis_dir.glob("*-setup.exe"))
    sig = exe.with_suffix(".sig")
    if not sig.exists():
        raise SystemExit(f"未找到更新签名文件：{sig}（检查 createUpdaterArtifacts 配置）")
    print(f"安装包：{exe.name}（{exe.stat().st_size / 1024 / 1024:.1f} MB）")

    # 4) 生成 latest.json（tauri v2 updater 格式）
    exe_url_name = urllib.parse.quote(exe.name)
    latest = {
        "version": version,
        "pub_date": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "platforms": {
            "windows-x86_64": {
                "signature": sig.read_text(encoding="utf-8").strip(),
                "url": f"https://github.com/{REPO}/releases/download/{tag}/{exe_url_name}",
            }
        },
    }
    latest_path = nsis_dir / "latest.json"
    latest_path.write_text(json.dumps(latest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"更新清单：{latest_path}")

    # 5) CHANGELOG 中该版本段落作为发布说明
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    marker = f"## [{version}]"
    if marker in changelog:
        body = changelog.split(marker, 1)[1].split("\n## [", 1)[0].strip()
    else:
        body = f"{product} {tag}"
        print(f"警告：CHANGELOG.md 未找到 {marker} 段落，使用默认发布说明")

    if args.dry_run:
        print("\n--dry-run：产物已生成，未发布。清单：")
        print(f"  {exe}\n  {sig}\n  {latest_path}")
        return

    # 6) 创建 Release 并上传安装包、签名、更新清单
    notes_file = nsis_dir / "release-notes.md"
    notes_file.write_text(body, encoding="utf-8")
    run([
        "gh", "release", "create", tag,
        "--title", f"{product} {tag}",
        "--notes-file", str(notes_file),
        str(exe), str(sig), str(latest_path),
    ])
    print(f"\n发布完成：https://github.com/{REPO}/releases/tag/{tag}")
    print("发布后按 docs/release-checklist.md 做人工验证（升级路径、sidecar 清理等）。")


if __name__ == "__main__":
    main()
