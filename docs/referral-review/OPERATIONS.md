# Referral Review 运维与故障恢复

MT-19 的代码及离线演练说明。仅使用合成资料；真实 PostgreSQL、Stripe、Private Blob、平台时限和通知到达仍需 MT-22／24 验收。本文件不授权真实模型费用、部署或手动修改账本。

## 只读诊断与关联

公开 GET `/api/v1/readiness` 返回 DB、迁移、清单三个检查。连接成功、迁移为 `rr_0007`、全部领域表和列可查询、C01—C08 纯函数探针通过才返回 200；否则 503。不会建表、迁移、生成记录、调用模型／支付／链上。已有 DB 可以在未配置 OAuth 时单独检查；缺失的 SQLite 文件不会被探针创建。readiness 不证明登录、支付、存储和整版发布门槛已验收。

GET `/api/v1/capabilities` 说明已接线的模式和配置能力，不公开邀请名单；真实执行仍逐次检查身份、邀请、会员、额度和预算。

应用 logger `meditrace.referral.telemetry` 输出 JSON：服务器生成的 `request_id`、`phase`、`duration_ms`、HTTP 状态和安全错误码；执行阶段另含 `run_id`、状态、mode、token 数、费用及 reservation UUID。不会记录 URL／query／headers、文档、完整模型响应、供应商 request ID、密钥或异常 traceback。模型和价格版本用完整 SHA-256 摘要标识，避免供应商把任意字符串放进版本字段；对受控配置字符串计算相同摘要即可比对。

`rr_audit_events` 在批次变更的同一事务内保存 request → run → action，已有 reservation 的 `run_id` 关联费用。日志在 reserve／dispatch 提交后及执行退出时读取持久状态。日志写失败不改变结算；函数被硬终止而没有退出日志时，以审计和 DB 状态为准。查询接口最多返回 100 条关联审计；默认展示最早 20 个 unknown 批次及 20 项清理任务，各类告警计数不受列表条数限制。审计沿用 30 天保留，删除资料会清除其关联；平台 stdout 保留时长仍需实际配置核验。

费用均为 **micro-USD（1 USD = 1,000,000 micro-USD）**：

| 字段 | 含义 |
| --- | --- |
| `estimated_microusd` | 冻结价格计算出的预留上限 |
| `booked_microusd` | 已入账金额，加上追加更正；可能仍是估计 |
| `actual_microusd` | 已有可信 usage 的金额或确定的零成本；保守估计期间为 null |
| `usage_state`、`adjustment_count` | 区分预留、未知、估计入账、已结算及后续追加更正 |

status 返回当前 UTC 日／月 bucket 的保留限额与当前配置限额、reserved、spent；有效限额取两者较小值。新日期没有 bucket 时只展示配置及零计数，不创建 bucket。历史批次仍结算到原预留日期，不重计入今天。

## 运维 CLI 与权限

使用仓库根目录 `python3 scripts/referral_operations.py`。操作者在受控环境提供 `RR_MAINTENANCE_SITE_ORIGIN`（纯 HTTPS origin）和 `RR_MAINTENANCE_TOKEN`（与后端维护 token 一致）。不要把 token 放进命令参数、URL、工单或日志。该 CLI 不依赖后端虚拟环境，不读取 `.env`，不跟随重定向；网络失败不自动重试。

```bash
# 默认和 status 都只读；返回预算、告警、未知批次和队列元数据
python3 scripts/referral_operations.py
python3 scripts/referral_operations.py status --request-id "$REQUEST_ID"
python3 scripts/referral_operations.py status --run-id "$RUN_ID"

# 无 --apply 时仅查询状态；不会恢复／支付补处理／删除文件
python3 scripts/referral_operations.py reconcile --run-id "$RUN_ID"
python3 scripts/referral_operations.py reconcile --run-id "$RUN_ID" --apply
python3 scripts/referral_operations.py retry-payment --event-id "$EVENT_ID" --apply
python3 scripts/referral_operations.py retry-cleanup --job-id "$JOB_ID" --apply
# 仅修复根因后，对选定 failed 任务恢复十次上限
python3 scripts/referral_operations.py retry-cleanup --job-id "$JOB_ID" --apply --retry-exhausted
```

运维 HTTP 只有精确路径 `/internal/operations`，GET 只读，POST 使用带 `action` 的类型化 body 且必须 `apply:true`。普通 session、CSRF、X-User-ID 都不赋予运维权限；缺失／错误／重复 Authorization 一律 403。GET 仅允许 run_id／request_id 查询参数，不接受 URL 凭据。POST 不允许任意对象路径、金额或用户 ID。支付补处理仅处理已记录的事件，不创建付款或增发手工权益；事件 ID 从 Stripe 测试事件记录取得。被拒绝的事件不会被该命令强制重开。

## 故障演练与恢复

| 故障 | 检查与操作 | 成功／保留条件 |
| --- | --- | --- |
| DB 或迁移不可用 | 检查 readiness 的固定检查值、数据库连通及 [MIGRATIONS](MIGRATIONS.md) 审核版本；由部署流程执行已审核追加迁移，再查 readiness | 三项 ready；GET 本身不修库。不要把旧版本 stamp 成新版本 |
| 模型不可用、超时或函数终止 | 用请求 ID 查 run，检查 dispatched 阶段；等待 240 秒 lease 结束后显式 reconcile | 未派发则 failed 并释放费用；已派发则 outcome_unknown，不再次调用模型 |
| 费用未知 | 首次 reconcile 保留预留；24 小时后再次 reconcile 或等待每日维护 | 真实模式以预留上限 estimated_spent 入账，actual 为 null，run 仍 unknown；Fake 费用零并 released。不会伪造成功结果 |
| 后到的可信 usage | 保留供应商核验依据，在受审查的内部集成中调用已有 `Usage.adjust`，使用唯一 adjustment_key；无证据时不更正 | 追加调整幂等、保留原记录，status 反映 booked／actual／adjustment_count。CLI 不接受任意费用，禁止直接 UPDATE 账本 |
| 模型价格变化 | 先关闭 REAL_AI_ENABLED，核验供应商价格后更新模型／价格版本／输入输出单价和日月预算，按发布流程部署；对照摘要并只读检查 | 已预留批次仍按冻结价格结算；新批次使用新版本。旧 pending 模型不一致会拒绝，应取消后新建；不得重写历史价格 |
| 实际费用超预留或异常资金 | 查看 financial_halt、budget_overrun、预算和相关 run；关闭真实执行并核对可信 usage／追加更正 | 全局 halt 保持 fail closed。当前 CLI 无解除 halt 功能；修复根因并完成受审查恢复变更前保持暂停，不手工清零预算 |
| Stripe 回调失败 | 核查测试 key、签名 secret、Price、订单绑定及已记录事件；修复配置后对选定 event ID retry-payment | processed／拒绝状态由原校验器决定；重复执行不会重复发权益。未入库的签名失败需由 Stripe 测试控制台重新投递 |
| 清理失败或上限 | 查看 cleanup_jobs 的 ID、kind、次数；修复存储／DB 后 retry-cleanup；达到十次需显式 --retry-exhausted | 只重排选定 failed 任务并执行原清理器；running lease 不被抢占。外部删除成功、配额提交失败仍由持久 lease 和原幂等逻辑恢复；不要删 job 或手减容量 |
| 清理尚有依赖／积压 | 查询任务，检查 pending/running 的到期时间与 unknown 费用；等待 lease／24 小时恢复窗口后显式维护 | 未满足原领域条件会继续等待；200 不等于所有资料已清除，以 backlog／任务状态为准 |
| 函数时限 | 对照架构的模型 120 秒、应用 180 秒、前端 195 秒、lease 240 秒，以及目标平台函数 300 秒；上线前核查实际项目限制 | 平台设置与目标一致才验收；提前终止按 unknown 恢复，不能开启 SDK 自动重试掩盖问题 |

Stripe 运维单次补处理使用 45 秒剩余时间预算；CLI 最多等待 55 秒。对象删除沿用 30 秒存储超时及持久 lease。数据库超时／平台强制终止可能让请求中断；恢复前再次只读查询，不据 HTTP 断线推断“未发生操作”。

## 告警与通知路径

`.github/workflows/referral-maintenance.yml` 每日 03:17 UTC 或手动触发 `scripts/referral_maintenance.py`。维护失败、耗尽或十批后积压都非零退出；维护完成后追加只读 status 检查，以下任一计数非零也使 Actions job 失败：

- financial_halt／budget_overrun：资金熔断或已用加预留超 bucket 限额。
- persistent_failures：过去 24 小时内的 UTC 固定窗口中，单账号失败计数达到十次。
- payment_failures／payment_backlog：失败事件或等待超过一小时的 pending 事件。
- cleanup_failures／cleanup_exhausted／cleanup_overdue：失败、十次上限、到期超过一天仍未完成。
- unknown_runs：结果未知，需要保留或核对费用；估计入账不自动取消此提示。

通知链路：应用元数据 → 有界维护／只读告警计数 → Actions 非零退出 → GitHub workflow 失败通知。输出只含固定告警名称和数量；不包含文档、模型响应、密钥、对象路径和账号名。监控自身无法认证／读取状态也失败退出，不默默当作健康。每日检查不是实时告警，定时任务延迟也可能延迟通知。

**待操作者验收**：配置两个仓库 secrets；启用该仓库 Actions 失败通知并指定接收者；在隔离测试部署故意使用错误 token 手动运行 workflow，确认失败通知实际到达；恢复正确 token 后再手动运行确认可恢复。保存仅含 run URL、时间、固定错误码和数量的证据。当前未配置／发送通知，也未验证线上调度。MT-24 不能仅凭脚本单测宣称通知链路已经上线。
