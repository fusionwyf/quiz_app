# 发布检查清单

每次发布（`uv run python scripts/publish-release.py`）后、对外公布前，按本清单人工验证。
自动更新链路的信任完全依赖签名私钥：**私钥丢失 = 老用户永远无法再收到自动更新**。
私钥位于 `%USERPROFILE%\.tauri\quiz_app_updater.key`，不入库、不分享、注意备份。

## 发布前

- [ ] `frontend/src-tauri/tauri.conf.json` 与 `Cargo.toml` 的 `version` 已递增
- [ ] `CHANGELOG.md` 已写入该版本段落（发布说明自动取自这里）
- [ ] `uv run pytest` 全绿；CI（push 后 Actions）双 job 绿
- [ ] 后端有改动时确认发布脚本执行了 PyInstaller 重新打包（脚本已内置，勿手工跳过）

## 发布后（必做人工验证）

- [ ] **真实升级路径**：在一台装着上一版本的机器上启动应用，页头出现「新版本 vX」入口，
      点击下载并安装，应用自动重启后版本号正确（关于/安装包属性确认）
- [ ] **升级失败兜底**：断网状态启动应用，不崩溃、无弹窗轰炸；手动下载链接可达 Release 页
- [ ] **sidecar 双保险清理**：正常退出后任务管理器无残留 `quiz-backend` 进程树；
      强杀 Tauri 壳进程后，后端进程随 `--parent-pid` 监听自行退出
- [ ] **老数据升级**：用发布前的旧数据目录启动一次，确认迁移链执行（日志 backend.log 无
      OperationalError），题库/错题/记录完好；首页总览数据正常
- [ ] **备份恢复冒烟**：设置页备份 → 恢复，数据完整
- [ ] **全新安装**：干净虚拟机（或全新用户目录）安装，首次引导出现、示例题库可导入可练习
- [ ] **自动备份**：删除 `%APPDATA%\quiz-app\backups` 后启动，当日自动备份生成
- [ ] Release 页资产齐全：安装包 `.exe`、签名 `.sig`、`latest.json`（windows-x86_64）

## 已知事项

- 未购买 Windows 代码签名证书：首次安装会有 SmartScreen 警告，README 已说明绕过方式
- 更新源为 GitHub Releases，国内直连不稳时用户走手动下载兜底（页头入口失败时自动提示）
