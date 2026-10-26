# MT-10 权益、费用预留与限流验收记录

日期：2026-10-21。代码已实施；前置 MT-02／04 和真实 PostgreSQL 多进程验收未完成，工单保持 `TODO`。没有真实模型调用、收费、服务启动或生产迁移。

## 交付与边界

2026-10-26 验收补充：`test_usage.py` 的 PostgreSQL 参数化与 `test_usage_pg.py` 的 5 项跨进程竞争／幂等结算已在 [PostgreSQL 17 CI](https://github.com/zfz193071/meditrace/actions/runs/40255313217/job/121355790255) 通过（整个 job 133 passed／0 skipped）。MT-02 已关闭，MT-04 及完整运行／导出验收仍未完成，本票保持 `TODO`。下方早期“未运行 PostgreSQL”描述为实施时快照。

`referral_review/usage/` 提供服务器内部 `reserve`、`settle`、`retain_unknown`、`adjust`、`check_export` 和会话限定的 `membership`。只新增 `GET /api/v1/membership`，返回当前账号的测试会员有效期、剩余／预留次数及真实资格提示；不返回邀请名单、其他账号或全站财务信息，不注册 grant／execute／退款后门。支付授权发放由 MT-17 完成，测试直接在隔离 fixture 中创建权益。

MT-11 必须从服务器会话取得 owner、从已验证请求计算完整输入 token 上界，使用持久 run 的模式和模型。预留不等于派发：同 run 返回已有 reservation 只用于幂等查询，不能再次调用供应商。MT-11 仍必须执行 run CAS、资料版本及解析覆盖检查、持久化 provider_dispatched_at 和单次模型派发。当前 capabilities 的真实执行能力继续关闭。旧诊断接口不经过该账本，MT-21 仍须退役；不能据此称旧站已有全局费用保护。

## 原子预留

- 当前账号未停用、资料包未删除／到期、run 属于账号且为未派发 pending；只接受持久 run 的 fake／real，拒绝 bundled_demo 消费。
- 真实模式还检查服务端开关、邀请名单、模型、价格版本、正输入／输出价格和正 UTC 日／月预算。客户端会员标记、请求参数、普通沙箱付款不能替代这些条件。
- 同环境必须恰好一份有效未撤销会员；新预留检查剩余次数。权益到期不影响已授权的人工编辑和导出，不会把旧任务结算到新会员期。
- 价格采用配置的最高适用输入价，不使用缓存折扣。`ceil((input_bound * input_price + max_output * output_price) / 1,000,000)`，全程整数 micro-USD；保存 token 上界、输出限制、模式／模型、输入／输出价格和版本快照。上限为 16,000／6,000 tokens，价格缺失失败关闭。
- 锁顺序：user → packet → run → membership → real_ai control → 日／月桶键排序 → 账号／全站槽。账号 1 槽、全站 2 槽，240 秒 lease。已过期槽可重用，旧任务迟到结算只释放仍属于自己的槽。
- 两个费用桶和会员次数／并发槽／reservation 在同一事务中写入，失败全回滚。重复 run 不会生成第二条预留；同 run 的输入／输出上界发生变化返回冲突。

## 结算与恢复

- 成功消费 1 次；已知失败释放成功次数，但按可信 usage 记实际费用。未派发的失败／取消为零费用并释放预留；已派发任务不能当作零费用取消。
- 已派发且 usage 缺失时使用预留上界，标 `estimated_spent`，不记为已知零成本；Fake 的供应商费用恒为零，但成功仍使用一次测试权益。
- unknown 标 `retained_unknown`、保持全部费用预留并计一次失败频率。保留一个未消费的次数预留，允许在可信成功恢复时消费；这不是成功扣次。24 小时后显式协调仍 unknown 则转 `estimated_spent` 并释放次数。并发槽仅到 lease 才可重用，不声称已经终止供应商任务。MT-11／19／18 负责调用恢复，不存在后台 worker 假设。
- 跨日／跨月按预留关联的原桶结算。配置价格后来变化不改写旧请求费用。重复相同 settle 幂等，冲突 outcome／usage 拒绝；数据库写入失败整体回滚，可重复结算而不重新调用供应商。
- 终态迟到可信 usage 只能走内部 `adjust`：追加调整行、幂等 key、差额更新原桶，不改写原 reservation 成本／状态。实际费用超过预留上界时保留实际账目并将共享 real_ai control 标 halted，后续真实预留一律拒绝。不会自动解除熔断，也不提供对外退款接口。

## 共享限流

所有计数存 `rr_rate_limit_buckets`，UTC 固定窗口，在账号锁下更新。execute 尝试事务先提交，后续配置／会员／预算拒绝不会抹去计数；每分钟 3 次、每小时 20 次、每天 10 次失败／unknown。幂等 reservation 查询不重新消费次数或授权新派发。

上传为每分钟 10 次／每小时 50 次，已接入 `Documents.begin`，在读上传正文和对象操作之前检查，失败上传也计数。该频率限制与已有字节／对象／文档配额同时生效。导出为每分钟 10 次／每小时 60 次，`check_export` 使用会话和资料归属、不要求会员；MT-13 实现导出端点时必须接入。没有浏览器层或进程内限流替代共享计数。

## 迁移与运行维护

新增 `rr_0004`，只追加 `rr_usage_details`（价格和结算快照）、`rr_usage_controls`（共享熔断）、`rr_usage_adjustments`（追加调整）三表，不修改旧业务数据。未执行生产迁移。旧开发阶段的 reservation 没有价格快照，拒绝自动结算或重用，须人工核实，不能倒填当前价格冒充历史价格。

预算桶初次创建时保存当时上限；后续预留同时取当前配置与该桶上限中更严格者。提高环境变量不会悄悄提高现有桶额度；若需要提高当前桶或解除熔断，运维须先核实供应商账目、估计器和价格，再经审核显式修改对应记录。新桶使用当时配置；默认预算仍为零。

## 验收项与证据

1. 多进程竞争：已提供真实 PostgreSQL spawn 进程测试，覆盖同账号、全站 2 槽、会员次数、双预算和重复 reserve／settle。未配置 TEST_DATABASE_URL 时明确跳过，SQLite 不作为此项通过证据。
2. 幂等：离线验证同 run 只有一条预留，重复 settle／adjust 不重复扣款，冲突参数拒绝，结算事务故障回滚。
3. 失败／unknown：已知费用、缺 usage、未派发取消、unknown 24 小时、unknown 恢复、跨日／价格变化、超上界熔断及原账追加调整均有隔离测试。
4. 权限：未邀请、开关关闭、零预算、缺价格、到期／撤销／零额度、已取消 run 均拒绝；Fake 无供应商费用，HTTP 不接受客户端权益伪造。
5. 手动流程：会员到期后仍可修改已授权资料；导出检查不要求会员。完整复制／导出 UI 属 MT-13／15，尚未执行端到端验证。

## 验证结果

- 最终全量 `cd src/backend && DATABASE_URL=sqlite:///:memory: .venv/bin/python -m pytest -q tests/referral_review`：**314 passed、65 skipped、4 项既有弃用警告**。跳过项包含未配置 TEST_DATABASE_URL 的 PostgreSQL 集成与 5 项多进程竞争测试，未当作通过。
- 首轮全量发现新增 `/membership` 未更新基础测试的路由集合断言，更新明确路径白名单后完整重跑通过。
- 迁移 metadata 对比、SQLite `rr_0003 → rr_0004` 旧账保留，以及 PostgreSQL 全迁移 SQL 离线编译通过；未连接真实 PostgreSQL。
- `src/backend/.venv/bin/python scripts/referral_contracts.py --write` 生成契约，`--check` 无漂移。
- `pnpm --dir src/frontend typecheck` 通过；没有 UI 变更，未重复生产 build。
- `git diff --check` 通过。未修改用户已有未跟踪的 `TASK-PREVISIT-SUMMARY.md`。
