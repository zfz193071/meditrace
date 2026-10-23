# MT-19 实施与验收证据

日期：2026-10-23。代码与离线验证已实施；前置 MT-11／17／18 未全部验收，工单仍为 **TODO**。这不是线上验收或整票关闭记录。

## 改动

- `referral_review/operations/`：只读 readiness；模型／价格摘要、费用及 token 元数据日志；持久 request/run/账本关联查询；独立 Bearer 运维接口；选定 run reconcile、支付事件补处理、failed 清理任务重试和日月预算查询。
- `runs/service.py`、`lifecycle/service.py`：审计与状态／账本同事务写入，复用原恢复逻辑；预留／派发提交后和执行结束输出安全元数据。没有新增模型调用、自动派发或手工账本更改接口。
- `app.py`、`errors.py`、`identity/authorization.py`：服务器生成请求 ID、安全错误码和耗时；仅精确运维路径使用独立 operator 鉴权。readiness 不再是恒定 503 占位，检查真实 DB/schema 和确定性清单。
- `scripts/referral_operations.py`：默认 GET，只在 `--apply` 时 POST；凭据只来自环境，禁止重定向。`scripts/referral_maintenance.py` 在维护完成后读取告警计数，异常及监控故障使 Actions 失败退出。
- [OPERATIONS](OPERATIONS.md)：模型故障、unknown、冻结价格、支付回调、清理、函数时限、资金熔断及通知验收手册。LIFECYCLE 的手工重置清理表步骤已替换为选定任务 CLI。
- OpenAPI 和前端 TypeScript 契约由生成器更新。复用 `rr_0006`，没有新增迁移、修改用户数据库或部署。

此前 MT-18 已按用户要求提交为 `6fd7306`；本次 MT-19 代码与证据一同提交，未推送／部署。用户已有 `TASK-PREVISIT-SUMMARY.md` 未修改或加入提交。

## 验收逐项

| 条件 | 离线证据 | 未完成部分 |
| --- | --- | --- |
| request_id 关联 run、状态、账本 | HTTP 请求 ID 可查询事务审计、reservation、冻结估计及追加更正；日志有阶段／状态／模式／版本摘要／tokens／费用／耗时 | 实际平台日志接收、保留和故障关联 |
| readiness 只读且失败 503 | 全领域表前后快照相同，捕获 SQL 无 DML／DDL；缺 DB、错误版本、缺表、清单失败均 503；无 OAuth 也能检查已有 DB；不创建不存在的 SQLite 文件 | 真实 PostgreSQL 和线上访问 |
| 独立运维权限 | 已登录 session、错误／重复 Bearer、替代 header、URL token 均不能授权；POST 无 apply 拒绝；CLI 默认和无 apply 的恢复命令只发送 GET | 线上密钥注入、轮换和权限配置 |
| 日志及错误脱敏 | 在模型版本、provider request ID、usage、错误码、资金控制原因及支付元数据注入原文／密钥哨兵；输出只保留摘要、固定错误码及计数；异常文本和 CLI 错误不回显 | 平台访问日志及第三方日志接收配置 |
| runbook 恢复保持真实状态 | Fake／真实计费模式均用离线 DB 演练；未派发释放，已派发 unknown 保留，24 小时真实费用按上限入账并保持 unknown；追加可信 usage 更正后金额可查询；模型调用数零 | PostgreSQL 竞争、真实供应商／平台硬终止 |
| 支付和清理补处理 | Fake Stripe 已记录失败事件重复恢复只发一次权益；选定 exhausted 任务需额外确认参数；running lease 拒绝抢占；本地对象故障后通过运维接口删除文件并释放容量 | 真实 Stripe／Private Blob |
| 通知路径 | 各类资金／持续失败／支付／清理／unknown 告警和监控失败均触发非零退出；stdout 仅固定名称与数量 | 真实 Actions 调度、接收者设置及实际通知到达 |

## 验证记录

- 相关后端回归：`test_operations.py`、`test_operations_cli.py`、`test_maintenance_runner.py`、`test_runs.py`、`test_lifecycle.py`、`test_billing.py`、`test_foundation.py` 合计 **138 passed**。
- 首轮新增测试为 **17 passed, 1 failed**：错误地预期 Fake unknown 产生估计费用。已按现有零成本契约修正，并增加真实计费模式的预留／保守结算／后到更正演练，没有修改账本规则来迎合测试。
- 完整后端回归：**477 passed, 69 skipped, 4 warnings**，用时 649.04 秒；跳过项包括缺少 `TEST_DATABASE_URL` 的真实 PostgreSQL 用例，不作为验收通过。四条 warning 来自现有旧入口的 SQLAlchemy／Pydantic／FastAPI 弃用提示。
- 补充的本地对象删除故障恢复用例单独执行：**1 passed**，验证文件实际消失、storage reservation 释放及容量归零。
- `python3 scripts/referral_contracts.py --check`、`pnpm --dir src/frontend typecheck`、`git diff --check`：全部通过。类型检查产生的 `tsconfig.tsbuildinfo` 缓存已恢复，未混入变更。

所有后端命令使用 CI 隔离环境：

```bash
PYTHON_DOTENV_DISABLED=1 DATABASE_URL=sqlite:///:memory: RR_ENVIRONMENT=test REAL_AI_ENABLED=false \
  src/backend/.venv/bin/python -m pytest src/backend/tests/referral_review -q
python3 scripts/referral_contracts.py --check
pnpm --dir src/frontend typecheck
git diff --check
```

没有调用真实模型／支付／存储服务，没有浏览器 AI 测试，没有启动或停止服务，没有配置或发送外部通知。测试中的真实计费模式仅验证状态／金额规则，不代表真实调用已验收。下一实施项是 MT-21；原有外部验收缺项继续保留。
