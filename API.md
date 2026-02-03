# Quiz App API 文档

> 自动生成自代码（`api.py` / `models.py`）。包含：**已实现接口** ✅ 与 **待开发接口** ⚠️。

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

- `MistakeDTO`:
  - `record_id: int`
  - `question_content: str`
  - `timestamp: datetime`

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
- 返回：`List[QuestionBank]`（`id, name, source, created_at`）

### 2) 创建题库
- 方法：POST
- 路径：`/banks/create`
- 参数：`name: str`（query 或表单）
- 描述：创建题库并返回 `QuestionBank`

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
- 参数：`bank_id: int`, `mode: str = "sequential"`（`sequential` 或 `random`）
- 返回：`QuizSession` 对象
- 错误：题库无题时返回 404（"No questions in bank"）

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
- 行为：记录 `ExamRecord`，若答完则把 `QuizSession.finished` 设为 `True`。
- 错误：session 或题目不存在返回 404

### 7) 获取错题列表（错题本）
- 方法：GET
- 路径：`/records/mistakes`
- 返回：`List[MistakeDTO]`（由 `ExamRecord` 与 `Question` join 得到）

### 8) 核心题目 CRUD
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

### 10) 错题本管理（基于 Mistake 表）
- **标记错题**
  - 方法：POST
  - 路径：`/mistakes/mark`
  - 请求体：`{"question_id": int, "bank_id": int}`
  - 返回：`{"message": "Question marked as mistake"}`
  - 说明：如果已标记，则增加错误计数

- **取消错题标记**
  - 方法：DELETE
  - 路径：`/mistakes/{question_id}`
  - 返回：`{"message": "Question removed from mistake book"}`
  - 错误：错题记录不存在返回 404

- **获取错题本**
  - 方法：GET
  - 路径：`/mistakes`
  - 查询参数：`bank_id?: int`（可选，按题库过滤）
  - 返回：错题列表，包含题目内容、错误计数、最后错误时间等

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

---

## 判题逻辑说明
- `check_answer` 支持：
  - 单选/多选/判断：集合不分顺序匹配（选项字母统一大写后比较）
  - 填空（`blank`）：做了基础的小写字符串比较（`blank_answer` 字段在模型中存在，但接口未完全使用）
- 分数规则：答对则返回题目 `score`，否则 `0.0`。

---

## 待开发接口 / 建议 ⚠️

### 1. 多用户 / 认证（低→中优先级）
- 用户认证（JWT）
- 用户维度错题本与记录隔离
- 用户个人学习进度统计

---

## 实施注意事项 & 建议 ✨
- 为 `POST /questions` 等关键接口添加输入校验（存在的 `bank_id`、选项格式、答案与类型一致性）。
- 列表接口加分页参数 (`limit` / `offset`)。
- 为关键流程编写单元测试（`pytest` + `TestClient`）。
- 若需要：我可以生成 `Postman` collection 或 `OpenAPI` 示例请求。

---

## 项目状态
✅ **核心功能已全部实现** - 题目管理、做题 Session、错题本、统计报表等核心功能均已可用。

🚀 **下一步建议**：
1. 添加用户认证系统（JWT）
2. 编写前端界面（React/Vue + 本 API）
3. 部署到服务器（Docker + Nginx）
4. 编写单元测试和集成测试