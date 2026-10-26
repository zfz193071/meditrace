# MediTrace V1 发布与回退

状态：MT-21 源码已实施；尚未发布或完成 MT-24 线上验收。当前生产站点可能仍运行旧应用，不能当成安全回退版本。

## 架构与配置

根目录 `vercel.json` 将 `/api/*` 转发到 FastAPI，将其他页面转发到 Next.js。新业务 API 位于 `/api/v1`；旧诊断、聊天、报告、验证及链上入口在当前源码中统一返回 410。旧数据表保留，不在启动时迁移或删除。生产使用 PostgreSQL，须配置 `DATABASE_URL`；新功能的其余变量见 [配置表](docs/referral-review/CONFIGURATION.md)。新应用不依赖钱包、RPC、Pinata 或 IPFS 凭据。旧配置可以留在 Vercel 待另行清理，但新入口不读取它们。

## 部署脚本

`vercel.json` 设置 `git.deploymentEnabled: false`，关闭 Git 推送触发的自动部署。代码推送用于备份和 GitHub Actions 验证，正式发布必须使用下方脚本，避免绕过验收、迁移及安全回退检查。该设置只控制 Git 自动部署，不关闭 CLI 发布。依据：[Vercel Git 配置](https://vercel.com/docs/project-configuration/git-configuration)。

`./deploy-vercel.sh --check` 只检查 Vercel 项目、套餐、数据库环境变量及上传文件。`--verify` 只发 GET：首页、`/api/v1/readiness` 及旧 API 退役探测；readiness 必须返回 200，数据库、迁移和清单检查均为 `ready`。探测旧路由时要求 410 和 `LEGACY_API_RETIRED`，不读取旧业务记录。脚本不会建包、执行 AI、支付或链上调用。

`./deploy-vercel.sh` 构建两个 Services、先验证暂存部署，再 promote 并复验生产。发布前必须确认当前生产版本已经通过同一组新 readiness 与旧 API 退役探测，才允许将它记录为自动回退候选。现有旧生产版本未达到该条件时，脚本会在构建前停止；不能将旧公开读接口版本当作候选。

首次安全切换由 MT-24 在所有发布前置条件通过后执行专用流程：先确认生产数据库备份／恢复方案和 `rr_` 迁移兼容性，再执行 `./deploy-vercel.sh --first-cutover --confirm-production-cutover https://meditrace.baozaolaoba.top --backup-reference <已核验的备份工单或快照编号>`。此命令先构建候选，应用审核过的追加迁移，验证暂存版本的 readiness 与旧路由 410，然后才 promote 并复验生产。备份编号是操作者的显式确认，脚本不会访问备份平台核验它；迁移使用受控环境中的 PostgreSQL `DATABASE_URL`，不使用 Vercel 密钥导出。切换期间若暂存验证失败，生产别名保持原版本；切换后若验证失败，脚本**不会回滚**到可能重新开放旧资料接口的版本，必须检查 `.vercel/last-deploy.json` 并修复前向。普通部署只有在首次基线验证成功后才恢复可用。此流程尚未在生产执行。

验证失败时只在当前生产仍指向本次发布 ID 的情况下回退。回退后再次只读验证；若回退命令或验证失败，脚本非零退出，`.vercel/last-deploy.json` 保留失败状态，不报告成功。人工回退也必须先核对目标版本已封闭旧接口，不能盲目执行旧文档中的任意 `vercel rollback` 命令。

## 迁移

`./deploy-vercel.sh --migrate` 是显式选择，要求后端 venv 和 PostgreSQL `DATABASE_URL`。它仅调用 `referral_review.persistence.migrations.upgrade` 至审核 allowlist 中的 `rr_` head，使用一个事务，不执行旧 `migrations/001_conversations.sql` 或 `002_vercel_schema_compatibility.sql`。普通部署不做数据库 DDL。生产迁移前仍须完成 [迁移手册](docs/referral-review/MIGRATIONS.md) 的 PostgreSQL、备份和授权条件；当前条件尚未满足。首次切换会在构建后、promote 前执行该追加迁移。

若网络在提交时断开，只读检查 schema 版本后再决定下一步；不推断失败或自动降级。应用回退不删除 `rr_` 表，也不恢复旧 API。

## 离线检查

```bash
python3 scripts/test_deploy_workflow.py
PYTHON_DOTENV_DISABLED=1 src/backend/.venv/bin/python -m pytest -q src/backend/tests/referral_review/test_retired_api.py
pnpm --dir src/frontend typecheck
pnpm --dir src/frontend build
```

本地服务由操作者手动启停。在线 `--verify` 会联网访问生产，但只执行 GET；尚未完成 MT-24 时不能据此声称 V1 已发布。部署状态与脱敏日志位于 `.vercel/`。禁止在日志或工单粘贴数据库连接串、密钥或原始资料。
