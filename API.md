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

---

## 判题逻辑说明
- `check_answer` 支持：
  - 单选/多选/判断：集合不分顺序匹配（选项字母统一大写后比较）
  - 填空（`blank`）：做了基础的小写字符串比较（`blank_answer` 字段在模型中存在，但接口未完全使用）
- 分数规则：答对则返回题目 `score`，否则 `0.0`。

---

## 待开发接口 / 建议 ⚠️
（按优先级排序）

1. 核心题目 CRUD（高）
   - `POST /questions`：添加题目（`bank_id`, `type`, `content`, `options`, `answer`, `score`）
   - `GET /questions/{id}`：获取题目详情
   - `PUT /questions/{id}`：更新题目
   - `DELETE /questions/{id}`：删除题目

2. 导入 / 导出（高）
   - `POST /banks/{id}/import`：TXT/JSON 批量导入（README 中提到的 TXT->JSON）
   - `GET /banks/{id}/export`：导出为 JSON / TXT

3. 错题本管理（中）
   - 标记 / 取消错题、按题库过滤错题

4. Session 增强（中）
   - `GET /session/{id}/status`：返回进度、累计得分等
   - `POST /session/{id}/finish`：手动结束并返回 summary

5. 统计与记录（中）
   - `GET /records`：答题记录及分页查询
   - `GET /stats/questions/{id}`：题目错误率、平均得分

6. 多用户 / 认证（低→中）
   - 用户认证（JWT）、用户维度错题本与记录隔离

---

## 实施注意事项 & 建议 ✨
- 为 `POST /questions` 等关键接口添加输入校验（存在的 `bank_id`、选项格式、答案与类型一致性）。
- 列表接口加分页参数 (`limit` / `offset`)。`
- 为关键流程编写单元测试（`pytest` + `TestClient`）。
- 若需要：我可以生成 `Postman` collection 或 `OpenAPI` 示例请求。

---

## 下一步
- 选择一项：实现题目 CRUD / 实现导入功能 / 生成 Postman 测试集合。请回复你优先要做的项，我可以继续实现并提交代码。 ✅
