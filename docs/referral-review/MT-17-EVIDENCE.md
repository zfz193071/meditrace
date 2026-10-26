# MT-17 实施与验收证据

日期：2026-10-22。开始前已提交 MT-23 初稿 `de3225f`。本票代码已实施、离线验证完成；前置 MT-04／10 尚未关闭，真实 Stripe 和 PostgreSQL 并发验收未完成，工单保持 TODO。没有部署、启动／停止服务、真实支付或模型调用。

## 改动

- [billing 模块](../../src/backend/referral_review/billing/service.py)：登录订单归属、固定商品、幂等 Checkout、一次会员、单向退款／争议撤销、持久事件恢复。网络在数据库事务之外，user／order 锁及唯一约束保护权益。
- [Stripe Adapter](../../src/backend/referral_review/billing/provider.py)：test-only key／Price、原始 body HMAC 与投递时效、当前 Session／line item／PaymentIntent／Charge 验证，不持久化完整支付事件。
- [HTTP 接口](../../src/backend/referral_review/billing/routes.py)：checkout、只读订单、签名 webhook、运维 bearer 保护的 billing 恢复。其余变更接口继续默认 CSRF。
- [rr_0006](../../src/backend/migrations_referral/versions/rr_0006_checkout_details.py)：追加最小 checkout_details，保留回跳位置、URL 和固定有效窗口，不修改旧表数据。只在隔离测试数据库迁移，未迁移用户数据库。
- [账户会员面板](../../src/frontend/components/referral/BillingPanel.tsx)、[支付返回页](../../src/frontend/components/referral/PaymentReturn.tsx)：明确测试支付，保留同一重试键，有效会员禁止再购；返回页仅有限轮询订单，恢复原包导航，不自动生成。工作区未保存状态阻止支付导航。
- OpenAPI／TypeScript 契约已同步。运行与真实验收步骤见 [BILLING](BILLING.md)。

## 验证结果

| 检查 | 结果与边界 |
| --- | --- |
| 新增 billing 后端测试 | 19 项通过：重复／不同事件同笔付款、待到账、异步成功、退款先／后到、争议撤销、错金额／Price／账号／live mode、伪签／过期签名、CSRF、跨账号查询、响应丢失、原子事务失败重试、受保护恢复、安全回跳 |
| 后端相关范围最终复测 | `PYTHON_DOTENV_DISABLED=1 DATABASE_URL=sqlite:///:memory: src/backend/.venv/bin/python -m pytest src/backend/tests/referral_review/test_foundation.py src/backend/tests/referral_review/test_identity.py src/backend/tests/referral_review/test_persistence.py src/backend/tests/referral_review/test_billing.py -q`：127 passed，27 skipped（PostgreSQL 未配置），4 个旧入口弃用警告 |
| 后端完整回归初跑 | 411 passed、68 skipped、4 failed；三个失败是新增路由／迁移带来的旧测试清单断言（已更新），另一个是未隔离本地 dotenv 引入旧 PostgreSQL 驱动配置（已改用上面的项目标准隔离命令）。四项及相关范围最终复测通过；没有将初跑记为完整全绿 |
| 前端全部组件／库测试 | `pnpm --dir src/frontend exec jest --runInBand`：13 suites、65 tests 通过，包含 5 项新增支付测试；稳定重试键、有效期内零余额禁购、只读返回、有限轮询、恶意跳转拒绝 |
| 前端类型与构建 | `pnpm --dir src/frontend typecheck` 和 `pnpm --dir src/frontend build` 通过；构建包含 `/account`、`/account/payment`，没有启动应用服务 |
| Lint | `pnpm --dir src/frontend lint`：0 errors、28 个已有旧页面 warnings，无新增文件警告 |
| 契约／差异 | `python3 scripts/referral_contracts.py --check` 和 `git diff --check` 通过 |
| 供应商配置检查 | 只检查变量是否存在，不输出值：本地运行环境及常用 .env 中四项必需 Stripe 配置均未设置；没有真实事件 ID |

初次调用旧 `venv` 时发现缺少 cryptography，随后使用项目锁文件对应的 `.venv` 完成测试，未临时安装或修改依赖。后端 full suite 含 PostgreSQL skipped 用例，不能据此宣称跨实例竞争已验证。

## 验收逐项状态

1. 实际 Stripe 测试 Checkout→签名 webhook→权益：**未验收**，缺测试配置、真实 OAuth／数据库前置及实际往返。
2. 伪造成功页／签名／金额／账号无权益、同事件及不同事件只发一次：离线 HTTP／Mock Provider 测试通过；真实多实例仍待验收。
3. 退款早到／晚到不复活、事务失败可重入：离线通过；注入数据库事件更新失败时会员和订单变更整体回滚，随后重送成功。
4. 取消／延迟／失败不修改资料，成功页不启动 AI：UI 与服务接口测试通过；原包的真实浏览器支付往返、过期后的完整人工编辑／导出集成留 MT-22 实测。
5. Live key／Price／livemode 拒绝，公共沙箱仅 Fake：配置已有 Live key 拒绝测试及新增 Adapter／事件测试通过；真实 Stripe 测试仍待执行。

## 剩余限制

- 需要真实 Stripe 测试账号、固定 Price、签名 secret；不以本地签名／Mock 成功代替外部验收。
- PostgreSQL 同账号购买／回调竞争、重复事件、退款竞争待实测；新迁移不自动用于生产。
- 创建响应丢失超过供应商幂等安全窗口的订单保持待核查，操作者核对原 Session 并重送事件；不将未知结果猜成失败。维护调度、时限和告警由 MT-19／24 验收。
- 本票没有执行浏览器支付、尺寸截图或真实模型测试，完整 UI／外部集成在 MT-22 验收。
- 本记录随 MT-17 实现一并提交；下一实施工单为 MT-18 数据删除、保留期限和清理补偿。

## 2026-10-26：PostgreSQL 回调竞争验收补充

新增独立 `test_billing_pg.py`，使用 PostgreSQL 临时 schema、独立进程和 Fake Stripe 响应，竞争四个不同成功事件处理同一订单，以及一次付款和退款事件同时处理。检查一笔付款只发一份权益，退款最终撤销且迟到／并发 paid 快照不能复活。没有真实 Stripe、HTTP provider、OAuth、模型调用或生产数据；仅补数据库并发证据，不关闭 MT-17。用例已加入 PostgreSQL 17 CI 的零跳过检查。本地未设置 `TEST_DATABASE_URL`，专项结果 2 skipped，明确不计为通过；远端实际执行结果待本提交 CI。
