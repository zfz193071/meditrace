# Vercel 后端启动及 PostgreSQL 兼容性修复

日期：2026-09-22。

## 故障与证据

Vercel 已构建 frontend/backend 两个服务，但生产域名 `/health` 返回 HTTP 500 `FUNCTION_INVOCATION_FAILED`。
生产启动日志和本地 FastAPI TestClient 均复现：

```text
startup_event -> init_database -> with get_db()
TypeError: 'generator' object does not support the context manager protocol
```

原 `database.py` 混用了 SQLAlchemy Session 与 SQLite 连接接口，同时重复定义 `init_database`。
仅添加 contextmanager 不够：查询中的 `?` 参数、字符串 SQL、按字段名/数字访问结果，以及 PostgreSQL JSONB 自动解码也需要兼容。

修复启动代码后，生产日志进一步暴露 `column "patient_id" does not exist`。
只读检查确认线上两张表均为 0 条记录，旧表缺少 `patient_id/metadata/timestamp/context_refs`。
新增 `002_vercel_schema_compatibility.sql` 追加字段和索引，保留原 UUID 主键、外键与 `created_at`，不删除表。

## 修复

- `get_db` 通过 SQLAlchemy 事务上下文管理连接，成功提交、失败回滚并释放连接。
- 参数化查询统一适配 SQLite/PostgreSQL，保留原调用方的结果访问方式和 JSON 文本约定。
- 删除重复初始化函数，保留幂等建表及索引操作；不执行旧的破坏性开发迁移。
- Vercel 缺少 `DATABASE_URL` 时明确报错；Neon 使用 NullPool 避免空闲函数保留连接。
- 删除包含数据库口令的连接串日志。
- dotenv 不覆盖显式环境变量，避免测试和部署配置被本地 `.env` 覆盖。
- 合约 ABI 随后端源码部署，按模块位置读取，避免依赖构建机目录或本地 Hardhat artifacts。
- 补充 PDF 生成依赖 `fpdf2`。
- 部署忽略内部文档和测试文件，保留 README；部署文档移除明文凭据示例。

## 回归覆盖

`src/backend/test_database_deployment.py` 验证真实 FastAPI 启动、健康检查、会话增删改查、JSON 字段、上下文读取、关联删除及事务回滚。
SQLite 使用临时文件；PostgreSQL 使用随机隔离 schema，测试结束后清理。
PostgreSQL 另覆盖旧 Neon 表结构，验证兼容迁移可重复执行。
测试不调用 DeepSeek、Pinata 或区块链写入。

生产发布采用 `vercel deploy --prod --skip-domain`，构建和数据库测试通过后通过 `vercel promote` 切换域名。
本机网络无法连接临时 vercel.app 域名，云端验证在自定义生产域名完成。
真实 AI 回复、IPFS 上传和区块链写入仍需按配置由用户手动验证。

## 发布结果

- 生产部署：`dpl_2dPz5ALUPPzQja1vxVZAxmQ1LDhx`，已 promote 到 `https://meditrace.baozaolaoba.top`。
- Neon 兼容迁移已执行；迁移前后 conversations/messages 均为 0 条，未删除原始数据。
- 生产 `/health`：HTTP 200，`{"status":"healthy","version":"0.1.0"}`。
- 生产首页：HTTP 200 HTML。
- 生产会话创建、列表、详情、更新、删除验证全部通过；测试会话已删除并验证返回 404。
- SQLite、新 PostgreSQL 表及旧 Neon 表迁移场景：6 项集成测试通过。
- 上下文逻辑：12 项测试通过；本地合约 ABI 加载、PDF 字体及生成检查通过。
- Vercel 账号套餐为 Hobby；未开通付费套餐，也未调用真实 AI 或发送链上交易。

## 一键部署流程整理

同日将人工执行步骤统一到可执行文件 `deploy-vercel.sh`，旧 `VERCEL-DEPLOYMENT-SCRIPT.sh` 转发到该入口。
修正旧脚本每次交互登录、重复覆盖环境变量、使用错误 `/api/health` 路径且不自动验证的问题。
新流程复用现有环境变量，检查上传内容，同时构建两项 Services，再发布并通过只读 HTTP 验证；失败时尝试回退并返回非零退出码。
构建期间若其他人改变生产版本，脚本停止，避免覆盖其他发布。

`--check` 和 `--verify` 已在真实账号/生产站点验证通过；10 项离线流程测试覆盖正常发布、构建失败、临时域名网络失败、线上失败回退、部分发布失败及并发发布保护。
本次脚本验证没有创建新的生产部署。详细使用说明见 `BACKEND-DEPLOYMENT.md`。
