# Quiz App API

一个功能完整的在线答题系统后端API，基于FastAPI和SQLModel构建。

## 🚀 功能特性

- **题库管理**：创建、查看题库
- **题目CRUD**：完整的题目增删改查功能
- **智能出题**：支持随机出题、按题型过滤
- **做题Session**：顺序/随机做题模式，自动判题
- **错题本系统**：自动记录错题，支持手动标记/取消
- **学习统计**：题目错误率、答题准确率、得分统计
- **数据导入导出**：支持JSON/TXT格式批量导入导出
- **RESTful API**：完整的API文档，支持CORS

## 📋 技术栈

- **后端框架**：FastAPI (Python 3.8+)
- **数据库**：SQLite + SQLModel (ORM)
- **数据验证**：Pydantic v2
- **API文档**：自动生成 OpenAPI 文档 (`/docs`)
- **项目管理**：uv (快速依赖管理)

## 🏃 快速开始

### 1. 安装依赖
```bash
uv add fastapi sqlmodel pydantic
```

### 2. 初始化数据库
```bash
python models.py
```

### 3. 启动API服务器
```bash
uv run uvicorn api:app --reload --host 0.0.0.0 --port 8000
```

### 4. 访问API文档
打开浏览器访问：http://localhost:8000/docs

## 📚 API文档

详细API文档请查看 [API.md](./API.md)，包含：
- 所有已实现接口的详细说明
- 请求/响应示例
- 错误代码说明
- 数据模型定义

### 主要接口概览

| 功能模块 | 主要接口 | 说明 |
|---------|---------|------|
| 题库管理 | `GET /banks`, `POST /banks/create` | 题库的查看与创建 |
| 题目管理 | `POST /questions`, `GET /questions/{id}`, `PUT /questions/{id}`, `DELETE /questions/{id}` | 完整的题目CRUD |
| 随机出题 | `GET /quiz/random` | 从题库随机抽题 |
| 做题Session | `POST /session/start`, `GET /session/{id}/current`, `POST /session/{id}/answer` | 顺序/随机做题，自动判题 |
| Session增强 | `GET /session/{id}/status`, `POST /session/{id}/finish` | 进度统计、手动结束 |
| 错题本 | `GET /records/mistakes`, `POST /mistakes/mark`, `DELETE /mistakes/{id}` | 错题记录与管理 |
| 数据导入导出 | `POST /banks/{id}/import`, `GET /banks/{id}/export` | JSON/TXT格式支持 |
| 统计报表 | `GET /records`, `GET /stats/questions/{id}` | 答题记录、题目统计 |

## 🗄️ 数据模型

系统包含以下核心数据模型：

- **QuestionBank**：题库，包含题目集合
- **Question**：题目，支持单选、多选、判断、填空四种题型
- **QuizSession**：做题会话，记录做题进度
- **ExamRecord**：答题记录，保存每次作答结果
- **Mistake**：错题本，记录需要重点练习的题目

## 🔧 开发指南

### 项目结构
```
quiz_app_uv/
├── api.py              # FastAPI应用和所有接口
├── models.py           # 数据模型和数据库配置
├── API.md              # 详细API文档
├── README.md           # 项目说明
├── pyproject.toml      # 项目配置
└── database.db         # SQLite数据库文件（自动生成）
```

### 添加新功能
1. 在 `models.py` 中添加数据模型（如果需要）
2. 在 `api.py` 中添加新的路由处理函数
3. 更新 `API.md` 文档
4. 测试接口功能

### 运行测试
```bash
# 安装测试依赖（使用可选依赖）
uv add --optional test

# 或者单独安装
# uv add pytest httpx

# 运行所有测试
uv run pytest

# 运行特定测试文件
uv run pytest tests/test_api.py -v

# 运行特定测试函数
uv run pytest tests/test_api.py::test_create_question -v

# 生成测试覆盖率报告（需要安装pytest-cov）
# uv add pytest-cov
# uv run pytest --cov=api --cov=models --cov-report=html
```

## 📊 示例使用场景

### 1. 创建题库和题目
```bash
# 创建题库
curl -X POST "http://localhost:8000/banks/create?name=数学题库"

# 添加题目
curl -X POST "http://localhost:8000/questions" \
  -H "Content-Type: application/json" \
  -d '{
    "bank_id": 1,
    "type": "single",
    "content": "1+1=?",
    "options": {"A": "1", "B": "2", "C": "3", "D": "4"},
    "answer": ["B"],
    "score": 1.0
  }'
```

### 2. 开始做题
```bash
# 开始Session
curl -X POST "http://localhost:8000/session/start?bank_id=1&mode=sequential"

# 获取当前题目
curl -X GET "http://localhost:8000/session/1/current"

# 提交答案
curl -X POST "http://localhost:8000/session/1/answer" \
  -H "Content-Type: application/json" \
  -d '{
    "question_id": 1,
    "user_choices": ["B"]
  }'
```

### 3. 查看统计
```bash
# 查看Session进度
curl -X GET "http://localhost:8000/session/1/status"

# 查看题目统计
curl -X GET "http://localhost:8000/stats/questions/1"
```

## 🚢 部署

### 生产环境部署
```bash
# 使用Gunicorn运行（Linux/macOS）
uv run gunicorn api:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000

# 使用Docker
docker build -t quiz-app .
docker run -p 8000:8000 quiz-app
```

### 环境变量配置
| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `DATABASE_URL` | `sqlite:///./database.db` | 数据库连接字符串 |
| `CORS_ORIGINS` | `http://localhost:5173` | 允许的CORS来源 |

## 🤝 贡献指南

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情

## 📞 支持与反馈

如有问题或建议，请提交 Issue 或联系维护者。

---

**Happy Coding!** 🎯