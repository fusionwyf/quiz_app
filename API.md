# Quiz App API 文档

> 基于代码（`api/routers/` 各域路由与 `api/models.py`）人工维护。包含：**已实现接口** ✅ 与 **待开发接口** ⚠️。

---

## 快速说明 🔧
- 后端：FastAPI（自动文档：`/docs`）。
- 主要实体：`QuestionBank`、`Question`、`QuizSession`、`ExamRecord`、`Mistake`（参见 `models.py`）。

---

## DTO / 数据模型（简要）
- `QuestionDTO`:
  - `id: int`
  - `type: str`（`single|multi|judge|blank`）
  - `question: str`
  - `options?: dict[str,str]`
  - `score: float`

- `AnswerSubmission`:
  - `question_id: int`
  - `user_choices: List[str]`

- `CheckResult`:
  - `question_id: int`
  - `is_correct: bool`
  - `correct_answer: List[str]`
  - `score_obtained: float`

- `CreateQuestionDTO`:
  - `bank_id: int`
  - `type: str`（`single|multi|judge|blank`）
  - `content: str`
  - `options?: dict[str, str]`
  - `answer?: List[str]`
  - `blank_answer?: List[str]`
  - `score: float = 1.0`

- `UpdateQuestionDTO`:
  - `type?: str`（`single|multi|judge|blank`）
  - `content?: str`
  - `options?: dict[str, str]`
  - `answer?: List[str]`
  - `blank_answer?: List[str]`
  - `score?: float`

---

## 已实现接口 ✅

### 1) 列出题库
- 方法：GET
- 路径：`/banks`
- 描述：返回所有题库
- 返回：`List<QuestionBank & {question_count: int}>`（`id, name, source, created_at, question_count`，题目数由后端聚合查询直接给出）

### 2) 创建题库
- 方法：POST
- 路径：`/banks/create`
- 参数：`name: str`（query 或表单；首尾空白自动去除）
- 描述：创建题库并返回 `QuestionBank`
- 错误：名称为空/纯空白 400；**同名题库已存在 409**（`detail` 形如 `题库名称已存在：xxx`）

### 2.1) 删除题库
- 方法：DELETE
- 路径：`/banks/{bank_id}`
- 描述：删除题库，并级联删除该库全部**题目、做题 Session、答题记录（含无 Session 的直接作答）与错题**
- 返回：`{"message": str}`
- 错误：题库不存在 404
- 说明：级联在应用层完成（除 `Question.bank_id` 外其余表无外键约束）；操作不可恢复，前端有二次确认

### 3) 随机出题
- 方法：GET
- 路径：`/quiz/random`
- 查询参数：
  - `bank_id: int`（必需）
  - `count: int = 5`
  - `qtype?: str`（可选）
- 返回：`List[QuestionDTO]`
- 说明：从题库中随机抽题，若题库为空返回 `[]`。

示例响应：
```json
[
  {"id":10,"type":"single","question":"1+1=?","options":{"A":"1","B":"2"},"score":1.0}
]
```

### 4) 开始做题 Session
- 方法：POST
- 路径：`/session/start`
- 参数：`bank_id: int`, `mode: str = "sequential"`（`sequential` 或 `random`，题序）, `source: str = "normal"`（`normal` 全部题目 / `mistake` 错题练习：题源为该库当前错题快照，按最近答错在前，`random` 时打乱）
- 返回：`QuizSession` 对象（`source=mistake` 时 `mode` 记为 `mistake`）
- 错误：题库无题 404（"No questions in bank"）；错题练习但库中无错题 404（"该题库暂无错题…"）；`source`/`mode` 非法 400

### 5) 获取当前题（Session）
- 方法：GET
- 路径：`/session/{session_id}/current`
- 返回：`QuestionDTO`
- 错误：session 不存在或已完成返回 404（"Session finished or not found"）

### 6) 提交答案（Session 单题判题）
- 方法：POST
- 路径：`/session/{session_id}/answer`
- 请求体：`AnswerSubmission`
- 返回：`CheckResult`
- 行为：记录 `ExamRecord`；**答错自动入错题本**（`Mistake` upsert：已存在则 `wrong_count` +1 并刷新时间，连对清零）；答对且已在错题本中则连对 +1、达到阈值自动出本（已掌握）；若答完则把 `QuizSession.finished` 设为 `True`。
- 错误：session 或题目不存在返回 404

### 7) 错题列表（已改道）
> `GET /records/mistakes`（由答题记录派生的视图）**已废除**：错题本统一以 `Mistake` 表为唯一事实源，答错自动入本，见「10) 错题本管理」。

### 8) 核心题目 CRUD
- **题目分页列表**
  - 方法：GET
  - 路径：`/banks/{bank_id}/questions`
  - 查询参数：`page: int = 1`，`page_size: int = 20`（上限 100，非法值自动钳制）
  - 返回：`{"bank_id", "bank_name", "total", "page", "page_size", "questions": [...]}`；题目含完整字段（`options` / `answer` / `blank_answer` / `score` / `created_at`），供题目管理页与编辑弹窗使用
  - 错误：题库不存在 404；**空题库返回 `total=0` 而非 404**

- **添加题目**
  - 方法：POST
  - 路径：`/questions`
  - 请求体：`CreateQuestionDTO`
  - 返回：`QuestionDTO`
  - 校验：验证题库存在、题目类型有效、答案字段符合类型要求

- **获取题目详情**
  - 方法：GET
  - 路径：`/questions/{question_id}`
  - 返回：`QuestionDTO`
  - 错误：题目不存在返回 404

- **更新题目**
  - 方法：PUT
  - 路径：`/questions/{question_id}`
  - 请求体：`UpdateQuestionDTO`
  - 返回：`QuestionDTO`
  - 说明：只更新提供的字段

- **删除题目**
  - 方法：DELETE
  - 路径：`/questions/{question_id}`
  - 返回：`{"message": "Question deleted successfully"}`
  - 错误：题目不存在返回 404

### 9) 导入 / 导出功能
- **导入题目**
  - 方法：POST
  - 路径：`/banks/{bank_id}/import`
  - 查询参数：`format: str = "json"`（`json` 或 `txt`）
  - 请求体：文件内容字符串
  - 返回：`{"message": "Successfully imported X questions", "imported_count": X}`
  - 说明：支持 JSON 格式（对象数组）和简单 TXT 格式

- **导出题目**
  - 方法：GET
  - 路径：`/banks/{bank_id}/export`
  - 查询参数：`format: str = "json"`（`json` 或 `txt`）
  - 返回：JSON 对象或 TXT 字符串
  - 说明：导出指定题库的所有题目

- **文件上传导入题目**
  - 方法：POST
  - 路径：`/banks/{bank_id}/import/file`
  - 请求格式：`multipart/form-data`，字段 `file`（上传文件）
  - 查询参数：`force_llm: bool = false`（可选，强制 AI 整理）
  - 支持扩展名：`.txt` / `.md`（`.markdown`）/ `.docx`，按扩展名自动识别格式
  - 限制：单文件最大 10MB；文本编码支持 UTF-8（自动回退 GBK）
  - 返回：`{"message": str, "imported_count": int, "skipped_count": int, "errors": [str], "truncated": bool, "ai_normalized": bool, "ai_error": str | null, "duplicate_count": int}`
  - 错误：题库不存在 404；不支持的扩展名/无法解码/空内容 400；超过大小限制 413；`force_llm=true` 但 LLM 未启用 400
  - 说明：文本内容自动探测两种题目格式，解析失败的题目跳过并在 `errors` 中给出原因（最多 50 条）
  - 去重：入库前按**题干（去首尾空白）**与库内已有题目及本文件已收录题目比对，重复的跳过并计入 `duplicate_count`（同时进 `errors` 明细），重复导入同一文件不会产生两份题目
  - AI 兜底：解析出 0 题且 LLM 已启用（见 `GET /llm/status`）时，自动调用 LLM 将原文整理成键值格式后重新解析；`ai_normalized=true` 表示本次导入的题目来自 AI 整理结果。LLM 未启用/调用失败/整理后仍 0 题时保持原结果不变，失败原因写入 `ai_error`
  - 强制整理：`force_llm=true` 时跳过直接解析结果，全部经 LLM 整理后解析（适合"能被解析器硬解出一部分错题"的混乱文件）；LLM 失败时回退直接解析结果并设置 `ai_error`
  - 分块：长文本按空行切块（单块 ≤ 8000 字符）逐块整理后合并解析，不再截断丢题；分块数上限 40（约 32 万字符），超出报错提示拆分文件

  **格式一：键值格式**（与 `/import` 的 txt 格式一致）：
  ```
  题目：1+1=?
  类型：single
  选项：{"A": "1", "B": "2"}
  答案：["B"]
  分数：1.0
  ```

  **格式二：通用试卷格式**：
  ```
  1. 1+1等于几？（单选题）
  A. 1
  B. 2
  答案：B

  2. 地球是圆的。（判断题）
  答案：对
  ```
  题型判定优先级：题干括号标注（单选/多选/判断/填空）> 答案形态推断（单字母→单选、多字母→多选、对/错/√/×→判断）> 默认填空。

  > 提示：字符串内容导入请使用 `/banks/{bank_id}/import`；本地文件上传请使用 `/banks/{bank_id}/import/file`。

### 10) 错题本管理（基于 Mistake 表，唯一事实源）
> 错题由**答错自动入本**（见 6)）；`POST /mistakes/mark`（手动标记）**已废除**。

- **已掌握（移出错题本）**
  - 方法：DELETE
  - 路径：`/mistakes/{question_id}`
  - 返回：`{"message": "Question removed from mistake book"}`
  - 错误：错题记录不存在返回 404

- **获取错题本**
  - 方法：GET
  - 路径：`/mistakes`
  - 查询参数：`bank_id?: int`（可选，按题库过滤）
  - 返回：错题列表，包含题目内容、题型、错误计数 `wrong_count`、连续答对次数 `consecutive_correct`、最后错误时间等

- **连对出本阈值**
  - GET `/mistakes/master-threshold` → `{"threshold": int}`（默认 2）
  - PUT `/mistakes/master-threshold`，请求体 `{"value": int}`（须 >= 1，存 `AppSetting`）→ `{"threshold": int}`；非法值 400

### 11) Session 增强
- **获取 Session 状态**
  - 方法：GET
  - 路径：`/session/{session_id}/status`
  - 返回：`SessionStatus`（包含进度百分比、答对数量、累计得分、平均得分等）
  - 错误：Session 不存在返回 404

- **手动结束 Session**
  - 方法：POST
  - 路径：`/session/{session_id}/finish`
  - 返回：`SessionSummary`（包含答题统计、准确率、得分总结等）
  - 错误：Session 不存在或已结束返回相应错误

### 12) 统计与记录
- **获取答题记录（分页）**
  - 方法：GET
  - 路径：`/records`
  - 查询参数：
    - `page: int = 1`
    - `page_size: int = 20`
    - `question_id?: int`（按题目过滤）
    - `session_id?: int`（按 Session 过滤）
    - `is_correct?: bool`（按正确性过滤）
  - 返回：分页的答题记录，包含题目内容和类型

- **获取题目统计**
  - 方法：GET
  - 路径：`/stats/questions/{question_id}`
  - 返回：`QuestionStats`（包含总尝试次数、正确次数、错误率、平均得分等）
  - 错误：题目不存在返回 404

### 13) LLM 智能整理（可选）

配置优先级：数据库（`AppSetting` 表，经 `/llm/config` 写入）> 环境变量（`LLM_PROVIDER` / `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL`）> 内置默认值。数据库中存 `provider=none` 可显式禁用环境变量启用的 LLM。

- **查询 LLM 配置**
  - 方法：GET
  - 路径：`/llm/config`
  - 返回：`{"provider": str, "base_url": str, "model": str, "api_key_masked": str, "api_key_set": bool, "enabled": bool}`
  - 说明：API Key 脱敏展示（如 `sk-****cdef`），不返回明文

- **保存 LLM 配置**
  - 方法：PUT
  - 路径：`/llm/config`
  - 请求体：`{"provider": str, "base_url"?: str, "model"?: str, "api_key"?: str}`
    - `provider`：`none`（禁用）/ `openai`（任意 OpenAI 兼容端点）
    - `base_url`：须以 `http://` 或 `https://` 开头；空值清除覆盖（回退环境变量/默认值 `http://localhost:11434/v1`，即 Ollama）
    - `model`：空值清除覆盖（回退环境变量/默认值 `qwen2.5:3b`）
    - `api_key`：**空值表示保留已存 Key**（前端无需重输），不支持显式清空
  - 返回：同 GET（脱敏后的生效配置）
  - 错误：`provider` 非法或 `base_url` 协议不对返回 400
  - 说明：配置明文存储在本地数据库 `AppSetting` 表；`local`（llama-cpp-python）模式仅支持环境变量配置，不提供前端写入

- **测试 LLM 连通性**
  - 方法：POST
  - 路径：`/llm/test`
  - 请求体：可选，同 PUT（带 body 时用 body 字段覆盖已存配置测试，先测后存；不带 body 测已保存配置）
  - 返回：`{"ok": true, "model": str, "reply": str}`（`reply` 为模型对 ping 消息的回复）
  - 错误：未启用 400；连接失败/鉴权失败等 400，`detail` 含可读原因

- **获取 LLM 配置状态**
  - 方法：GET
  - 路径：`/llm/status`
  - 返回：`{"provider": str, "enabled": bool, "model": str}`
    - `provider`：`none`（默认，未配置）/ `openai`（任意 OpenAI 兼容端点）/ `local`（llama-cpp-python 内嵌 GGUF）
    - `enabled`：`provider` 非 `none` 时为 `true`
  - 说明：反映数据库+环境变量合并后的最终状态，供前端导入弹窗展示"已启用 AI 智能整理"提示使用

---

## 判题逻辑说明
- `check_answer` 支持：
  - 单选/多选/判断：集合不分顺序匹配（选项字母统一大写后比较）
  - 填空（`blank`）：逐空比较，比较前归一化（全角转半角含标点、去首尾空格、忽略大小写）；每空支持 `|` 分隔多个备选答案，任一匹配即判对该空；空数不等判错（`blank_answer` 每空一项）
- 分数规则：答对则返回题目 `score`，否则 `0.0`。

---

## 待开发接口 / 建议 ⚠️

> 暂无排队项。多用户 / 登录 / JWT 已被明确否决（见 `docs/adr/0001`），本产品保持本地单用户。

---

## 实施注意事项 & 建议 ✨
- 为 `POST /questions` 等关键接口添加输入校验（存在的 `bank_id`、选项格式、答案与类型一致性）。
- 列表接口加分页参数 (`limit` / `offset`)。
- 为关键流程编写单元测试（`pytest` + `TestClient`）。
- 若需要：我可以生成 `Postman` collection 或 `OpenAPI` 示例请求。

---

## 项目状态
✅ **核心功能已全部实现** - 题目管理、做题 Session、错题本、统计报表等核心功能均已可用。

🚀 **下一步**：错题练习模式、备份/恢复、自动更新、暗色模式等，路线图见 GitHub Issues。