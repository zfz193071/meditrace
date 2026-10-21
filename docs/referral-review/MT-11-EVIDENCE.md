# MT-11 核对批次执行与恢复验收记录

日期：2026-10-21。后端编排与离线测试已实施，前置 MT-07／08／09／10 尚未完成全部验收，工单保持 `TODO`。真实供应商请求和 PostgreSQL 多进程竞争未实际验收，不代表完整产品已交付。

## 交付

`referral_review/runs/` 接入创建 pending、execute、GET、cancel 和 reconcile 五类操作。新增 CreateRunInput／RunResponse 契约与生成客户端类型。已有表足以保存批次、事实、证据、事项及关联，本票不新增迁移。

- 创建输入只接受 revision_id 和 checklist_version，不接受 owner／mode／model／会员标记。按当前会话与服务器配置选择 fake 或 real；固定 bundled_demo 不允许执行。真实模式还要求已受邀且配置完整。
- 保存资料版本、完整输入哈希、模型、提示词、Schema、清单版本。加载完整不可变 revision，验证每份文档、页数、连续页码、解析质量及 hash；不允许空版本或缺页资料自动核对。用 MT-08 共用的完整请求字节上界在创建和执行前拒绝超限，绝不截断。
- 创建 key 按账号／资料包归属绑定 payload，相同 key 复用同一批次，不同 payload 冲突。同内容 pending／running 批次复用，终态后新 key 可以创建新批次。所有写路由要求 CSRF 与 Idempotency-Key；execute／cancel／reconcile 的 key 绑定账号、动作和 run，重复操作返回该资源当前状态，不能换 run 使用同 key。
- GET 返回状态、可见阶段、stale、provenance、usage 和仅成功时可见的结果；不更新过期状态、不结算、不调用模型。未登录 401，越权／不存在／已删除统一 404，响应 private/no-store。

## 派发与事务

execute 先持久化共享尝试计数，随后在同一数据库事务完成归属／当前版本检查、会员／价格／预算／并发预留和 pending → running CAS，写入 240 秒 lease。MT-10 新增 caller-owned transaction 接口，使批次 CAS 与预留不可部分提交；独立使用账本的原有行为仍保留。

事务提交后再次校验归属、版本、有效会员和真实资格／熔断，单独提交 provider_dispatched_at；只有这个获胜请求才进入模型 Adapter。等待模型期间不持有数据库事务。重复 execute 对 running 返回 202，对终态返回已有状态，不再次派发。首次 execute 在请求内 await 到结果，不注册响应后后台任务、队列或常驻 worker。

通过提取与清单校验后，在同一事务写入 Evidence／Fact／Finding 及引用关系、结算费用与成功次数、更新 succeeded。纯规则的稳定 ID 转为 run namespace 下的 ID，避免新批次的缺失项与旧批次主键碰撞。失败与 unknown 不暴露部分结果。

若资料在模型返回前更新，结果仍绑定原资料版本，并派生 stale=true；不覆盖新版本或旧审核记录。若资料包到期、删除或账号停用，丢弃内容，按已取得的 usage 结算失败费用，不消费成功次数。

## 中断与恢复

- 应用期限 180 秒，模型 Adapter 总期限 120 秒；请求内使用 asyncio deadline，结果写入线程在逐项写入及提交前复核单调时钟期限，超时回滚，不在超时后提交成功结果。请求超时后先等待当前数据库线程结束，再开始恢复事务，避免回滚与恢复相互争抢。数据库锁等待／错误清理可能需要额外短时间，不承诺即时终止远端模型。
- pending 超过 30 分钟，在 execute／reconcile 或创建新同内容批次时显式取消；GET 不执行清理。
- lease 到期后 reconcile：没有派发标记则 failed 并释放费用／次数；已有派发标记则 outcome_unknown，保留费用上界。绝不为了恢复而再次调用模型。
- 供应商超时、传输失败、应用中断或结果提交不确定均保守标 unknown。非法 JSON、假引用和截断是已知失败，按可用 usage 结算，否则使用上界估计。
- unknown 24 小时后由显式 reconcile 使用 MT-10 保守结算，仍保持 outcome_unknown，不能把无法确认的结果显示成成功。若原请求在 lease 恢复后仍返回有效结果，且预留尚未最终估算结清，可以原子恢复到 succeeded，不重新派发。
- 函数死亡可能来不及执行异常处理。派发标记和 lease 是跨实例恢复依据；浏览器断开不保证任务继续。MT-18／19 需将同类恢复接入维护任务，当前没有后台自动调度。
- 响应已经收到但未成功固化时，允许内容丢失并保持 unknown；不把进程内结果当成持久恢复证据，不因丢失结果重复付费请求。终态费用的迟到 usage 修正仍使用 MT-10 的追加调整接口。

## 模拟与真实模式

生产默认 sandbox 使用显式 FakeAdapter，固定空事实输出，目的是演示批次／费用／审核前的状态链路，不分析用户资料、不伪称真实提取；对应事项会体现模拟的缺失状态，响应始终标 mode=fake。测试可通过进程内 Adapter seam 提供合成事实或 Mock HTTP，但没有 HTTP／环境变量可注入该 seam。

真实模式使用独立 DeepSeek Adapter，只有服务器资格、权益、预算及派发链路通过才可请求。本轮只使用 MockTransport，未访问供应商或产生 API 费用。完整 UI／固定示例／支付及外部验收尚未完成，capabilities 保持保守的 foundation 状态，不据此宣称上线就绪。

## 逐项验收证据

1. 幂等：API 测试覆盖同 key 同 payload、冲突 payload、同内容活跃复用、终态新批次、重复 execute 和跨 run 复用操作 key。GET／reconcile／cancel 不请求 Adapter。
2. 多实例：两个独立 Runs 实例同时执行一个批次，仅一次调用；等待期间第二次 execute 为 running/202。已提供真实 PostgreSQL 三个独立 spawn 进程竞争测试，缺 TEST_DATABASE_URL 明确跳过，SQLite 不替代多进程验收。
3. 故障：reserve 前／后异常整体回滚；claim 提交后、派发标记后模拟进程死亡，按 lease 恢复；响应收到后／结果事务提交前故障无半成品图或成功扣次；提交线程超出应用期限回滚；timeout／非法 JSON／假引用／截断／usage 缺失均覆盖。
4. 权限与变化：跨账号各路径统一 404；伪造客户端 real 被 Schema 拒绝；缺会员或派发前撤销会员不调用；旧版本执行拒绝，调用期间修改版本保留旧结果，删除时丢内容结费用。
5. Provenance：fake／real、模型请求／返回标识、Schema／prompt／清单／revision 与 usage 可查；实际响应图与账本一次提交。真实 Adapter 的 Mock HTTP handler 验证收到请求时标记与预留已经提交。

## 验证结果

- `cd src/backend && DATABASE_URL=sqlite:///:memory: .venv/bin/python -m pytest -q tests/referral_review`：最终 **341 passed、66 skipped、4 项既有弃用警告**。跳过项包含没有 TEST_DATABASE_URL 的 PostgreSQL 测试，不计为验收通过。
- `tests/referral_review/test_runs.py` 专项 **27 passed**；`test_runs_pg.py` 已提供三进程竞争，缺测试库跳过。
- 初轮回归更新了“执行端点未注册”时期的 404 预期：现在未登录伪造会员请求必须返回 401/AUTH_REQUIRED。提交阶段超时用例发现 SQLite 回滚／恢复争抢，加入数据库线程收尾等待后专项及完整回归均通过。
- `src/backend/.venv/bin/python scripts/referral_contracts.py --write` 生成契约，`--check` 无漂移。
- `pnpm --dir src/frontend typecheck` 通过；无页面改动，未重复生产 build。
- `git diff --check` 通过。未修改用户已有的 `TASK-PREVISIT-SUMMARY.md`，未启动／停止服务或自动在浏览器触发 AI。
