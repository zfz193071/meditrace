# MT-21 实施与验收证据

日期：2026-10-23。状态：代码与离线验证完成；工单保持 `TODO`，因为 MT-11／17／19 前置尚未关闭，安全生产基线、真实 PostgreSQL 和线上验收未完成。没有部署、迁移或发送浏览器 AI 请求。

## 改动

- `src/backend/main.py` 仅挂载 `/api/v1`，旧 `/api/*` 与 `/health` 七种常用 HTTP 方法一律 410；不导入旧数据库、DeepSeek、Web3/IPFS 模块，不执行旧启动 DDL。旧数据库和历史服务文件未删除。
- `/chat`、`/chat/[id]`、`/history`、`/verify` 转到 `/legacy-retired`，说明旧记录没有自动迁入新 Packet。英文首页保持转诊核对定位。
- 后端 `pyproject.toml`、`uv.lock`、`requirements.txt` 移除 Web3/IPFS 运行依赖；前后端环境模板移除旧钱包／RPC／Pinata 指引。
- `deploy-vercel.sh` 验证首页、新 readiness 的三项 ready 检查，以及旧路由 410；全部请求为 GET。`--migrate` 只调用 `rr_` 审核 allowlist。发布前须确认现有生产已是安全回退基线；失败回退不写成功状态。首次基线建立留待 MT-24。
- 旧聊天优化 Issue 模板移入 `archived/`，新的默认模板面向转诊核对；部署文档、架构、配置及迁移手册更新。

## 离线结果

| 检查 | 结果 |
| --- | --- |
| 旧 API 路径 × 七种方法、无旧服务导入 | `test_retired_api.py`：85 passed |
| 发布、迁移和回退 mock 故障路径 | 原有 13 项；含首次切换、迁移失败和 CLI 防误触现为 `python3 scripts/test_deploy_workflow.py`：18 passed |
| 全部 referral 后端回归 | 548 passed、69 skipped（跳过项含未配置独立 PostgreSQL） |
| 前端类型检查、生产构建 | 均通过；构建生成旧页面重定向路由和 `/legacy-retired` |
| 前端 Jest | 14 suites、68 passed |
| ESLint | 0 errors、2 个既有未使用变量 warning |
| 后端依赖锁 | `scripts/check_backend_lock.py`：通过，使用仓库内 uv 缓存 |
| shell 语法与 diff | `bash -n`、`git diff --check` 通过 |

首次切换流程（2026-10-26）：已增加 `--first-cutover`，要求精确生产域名确认和操作者提供的备份参考。流程构建候选后执行审核过的追加迁移，验证暂存 readiness／旧路由 410，再 promote。迁移或暂存失败不切流；上线后验证失败保留新版本并标记 `first-cutover-unverified`，不回滚到旧公开接口版本。备份参考不会由脚本自动核验，迁移连接串须由受控环境提供。18 项离线 mock 测试通过；包含该实现的 [完整 CI](CI-2026-10-26.md) 两个 job 均通过；未连接生产、未迁移或发布。

失败路径包括旧方法收到无效 JSON 仍为 410、旧服务未导入、线上 readiness／旧接口异常阻止 promote、缺安全回退基线时构建前阻断、回退命令失败时保留 `rolling-back` 而不报告成功。原 `test_conversations_api.py` 与 `test_database_deployment.py` 属于退役产品回归，保留源码并显式 skip；新路由和新领域迁移由当前测试覆盖。

## 验收项状态

- 旧入口方法封闭：**离线通过**；尚未线上直连检查。
- 无钱包／Pinata／RPC 启动与构建：**离线通过**；尚未部署验证。
- 发布 verify 全 GET：**离线 mock 通过**；尚未线上验证。
- 迁移与安全回退：**离线 mock 通过**；真实 PostgreSQL、首次安全基线与真实 Vercel 回退未验收。
- 文档及导航：**源码与构建检查通过**；线上页面未验收。

风险：当前生产可能仍提供旧 API；首次切换不可将它当作安全回退候选。建立兼容且关闭旧接口的生产基线后，才可使用常规部署脚本。保留的历史模块不在新入口注册，但仓库仍保存它们以便追溯，不得从旧模块运行开发服务冒充 V1。详见 [部署手册](../../BACKEND-DEPLOYMENT.md)和 [BUGFIX 记录](../../BUGFIX-MT-21-LEGACY-ROUTES.md)。
