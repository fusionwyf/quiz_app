# 后端分层：按域拆 APIRouter + 薄服务层，不引入 repository/DI

路由与业务逻辑此前全部内联在 api/api.py（~1230 行），新功能（错题自动入本、备份、仪表盘统计）都会撞上这个结构。决定：按域拆分为 APIRouter（banks / questions / import / session / mistakes / records / llm / settings），业务规则下沉到薄服务模块（grading、mistakes、stats、backup），路由只做参数校验与编排。

明确不做：repository 模式、依赖注入框架、CQRS——本地单用户 SQLite 应用，这些是负资产。

## Consequences

- 判分规则只存在于 grading 模块（P0 填空判分重构的唯一落点）；错题"入本/出本"语义只存在于 mistakes 模块；delete_bank 的级联清理收敛为单一函数，后续加"已掌握"字段时只改一处。
- 服务层函数以 SQLModel Session 为参数，保持现有 TestClient 集成测试不变即可回归。
