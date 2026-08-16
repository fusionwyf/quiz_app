# 数据库演进：PRAGMA user_version 轻量迁移链，不引入 Alembic

create_all 只建缺失的表、不给已有表加列；产品带自动更新发布后，用户会带着旧 database.db 升级到含 schema 变更的新版本，若无迁移机制将静默崩溃。决定：用 SQLite 的 PRAGMA user_version 记录库版本，启动时按序执行手写迁移函数链（每版本一段 Python + SQL），Alembic 对单表体量、单文件本地库是过度设计。

## Consequences

- 任何 schema 变更必须新增一个迁移步骤并递增版本号，禁止"改模型 + create_all 就完事"的心智。
- 迁移链一旦随安装包发布就不可收回重写（用户库上已执行过），只能在链尾追加。
- 备份/恢复功能恢复旧版本备份时，同一条迁移链负责把旧数据升到当前结构。
