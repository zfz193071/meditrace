# Referral PostgreSQL 驱动选择修复

日期：2026-10-20。MT-04 配置认证模块时发现：新领域持久化的 `create_engine` 对 `postgresql://` 仍依赖 SQLAlchemy 默认驱动，而当前锁定的 SQLAlchemy 2.1.5 默认尝试导入 `psycopg`；项目显式安装的是 `psycopg2-binary`。因此仅构造认证应用就会报 `ModuleNotFoundError`，不必实际连接数据库即可复现。

修复将 `postgres://` 和 `postgresql://` 都明确映射为 `postgresql+psycopg2`。显式带驱动的 URL 保持原样；保留连接参数、隐藏 SQL 参数、无默认生产连接和启动不迁移的约束。没有修改旧数据库模块、表或数据。

回归位于 `src/backend/tests/referral_review/test_identity.py` 的 `test_configured_postgres_auth_starts_without_connecting_or_migrating`。测试使用不可连接的合成地址，验证应用可以构造、匿名会话查询与 capabilities 不触发连接。它不替代 MT-02 的 PostgreSQL 迁移和并发事务验收。
