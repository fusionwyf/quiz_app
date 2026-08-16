# AGENTS.md

在线答题系统：FastAPI + SQLModel 后端（`api/`）+ React/TypeScript/AntD 前端（`frontend/`）。SQLite 数据库，uv 管理 Python 依赖。

## 常用命令

```bash
# 后端（启动时自动建表；注意是 api:app，不是 api.api:app）
uv run uvicorn api:app --reload --port 8000

# 后端测试
uv run pytest
uv run pytest tests/test_api.py -v

# 前端（固定 5173 端口，需后端在 8000 运行）
cd frontend && npm install && npm run dev
npm run build   # tsc && vite build，产物在 frontend/dist

# 桌面安装包（PyInstaller 后端 + Tauri NSIS，一步到位）
build-desktop.bat
```

Windows 环境：shell 为 cmd，`ls`/`tail` 不可用，用 `dir`、`findstr`。

## 结构与分层

- `api/api.py` — 应用组装层（FastAPI 实例、CORS、lifespan、路由挂载）；`conftest.py` 与 `backend_main.py` 依赖 `from api.api import app, get_session`，勿破坏这两个导入点
- `api/routers/` — 按域拆分的路由（banks / questions / sessions / mistakes / records / llm_config），路由只做参数校验与编排
- `api/services/` — 业务规则（grading 判分、banks 级联删除）；新业务逻辑落这里，不进路由
- `api/deps.py` — `get_session` 依赖；`api/constants.py` — 题目类型等常量；`api/schemas.py` — 跨路由共享 DTO
- `api/migrations.py` — 数据库迁移链（`PRAGMA user_version`，ADR-0003）：改 schema 必须"改模型 + 链尾追加步骤 + SCHEMA_VERSION 递增"，已发布步骤不可修改
- `api/models.py` — SQLModel 数据模型与数据库配置
- `api/parsers.py` — 题库文件解析（txt/md/docx，键值格式 + 通用试卷格式）
- `api/llm.py` — 可选 LLM 智能整理（解析出 0 题自动兜底，导入接口 `force_llm` 可强制整理；配置优先级：数据库 AppSetting 表（`/llm/config` 写入）> `LLM_PROVIDER` 等环境变量）
- `api/__init__.py` 导出 `app`（uvicorn 入口）
- `frontend/src/api/` — API 封装层（types/client）；`pages/`、`components/`、`layouts/`
- `tests/` — pytest 单元测试；`API.md` 为详细接口文档

改动约定：新增接口需同步更新 `API.md`；新功能按 models → services → routers → 测试 → 文档顺序。

## 桌面打包架构（Tauri + sidecar）

- 打包链：`backend_main.py`（`--host/--port` 入口）→ `quiz-backend.spec`（PyInstaller onefile，显式收集 uvicorn 隐藏导入）→ 复制为 `frontend/src-tauri/binaries/quiz-backend-x86_64-pc-windows-msvc.exe`（externalBin 要求目标三元组后缀）→ `npx tauri build` 出 NSIS 安装包。全流程见 `build-desktop.bat`。
- `frontend/src-tauri/src/lib.rs`：选空闲端口 → 拉起 sidecar（带 `--parent-pid`）→ TCP 健康检查 → 建窗口并在 `initialization_script` 注入 `window.__BACKEND_PORT__`；含单实例插件。
- 后端进程清理是双保险：正常退出走 `RunEvent::Exit` → `taskkill /PID <pid> /T /F`（onefile 是 bootloader→server 进程树，必须整树杀）→ `std::process::exit(0)`；壳崩溃/被强杀时由 `backend_main.py` 的 `--parent-pid` 监听线程自杀兜底。改这两处时两条路径都要保住。
- `frontend/src/api/client.ts` 优先读 `window.__BACKEND_PORT__`，其次 `VITE_API_BASE`，最后 8000——改端口逻辑时保持这个优先级。
- **改后端代码后必须重跑 PyInstaller（build-desktop.bat 的 1、2 步）再 tauri build/dev**，否则桌面端跑的还是旧 sidecar。
- 数据库固定在用户数据目录（`%APPDATA%/quiz-app/database.db`，见 `api/models.py` 的 `get_app_data_dir`），与工作目录无关。

## 注意事项

- Python >= 3.12；Pydantic v2。
- CORS 白名单默认 `http://localhost:5173`（`CORS_ORIGINS` 可改）。
- 数据库固定在用户数据目录（`%APPDATA%/quiz-app/database.db`，见 `api/models.py`），与工作目录无关，自动生成勿提交；schema 变更走 `api/migrations.py` 迁移链。
- LLM 整理默认在解析结果为 0 题时触发（`force_llm=true` 时强制），长文本按空行分块（≤8000 字符/块，上限 40 块）逐块整理；输出仍经解析器校验，失败自动回退并在响应 `ai_error` 说明原因。
- 提交信息使用中文 conventional 风格（如 `feat(api): ...`、`fix: ...`）。

## Agent skills

### Issue tracker

Issues 与 PRD 以 GitHub Issues 跟踪，通过 `gh` CLI 操作。See `docs/agents/issue-tracker.md`.

### Triage labels

使用五个默认 triage 标签（needs-triage / needs-info / ready-for-agent / ready-for-human / wontfix）。See `docs/agents/triage-labels.md`.

### Domain docs

单上下文布局：根 `CONTEXT.md`（词汇表）+ `docs/adr/`。See `docs/agents/domain.md`.
