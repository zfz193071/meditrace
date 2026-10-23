# Stripe 测试支付与恢复（MT-17）

这是沙箱会员，不是真实收费。一次测试购买提供 30 天／20 次模拟核对，无自动续费。`sandbox` 模式永远不因付款获得真实 AI 权限；`invited_real` 仍须通过服务端邀请、开关、会员、额度、预算和并发检查。

## 配置及接口

服务端配置 `RR_STRIPE_SECRET_KEY`（仅 `sk_test_` / `rk_test_`）、`RR_STRIPE_WEBHOOK_SECRET`、`RR_STRIPE_PRICE_ID`、`RR_STRIPE_AMOUNT_MINOR`、`RR_STRIPE_CURRENCY` 及 `RR_SITE_ORIGIN`，并完成 MT-04 登录配置、显式迁移到 `rr_0006`。不能将密钥放入前端或提交到仓库。配置只是启用条件，不代表真实 Stripe 验收成功。

- `POST /api/v1/billing/checkout`：登录、同源 Origin、CSRF、Idempotency-Key；请求只有 `return_path`，不接受 Price／金额／会员／模式。只允许账户、工作区或当前账号有权访问的资料包路径。
- `GET /api/v1/billing/orders/{id}`：按当前账号查服务器订单，不查供应商、不修改权益、不执行核对。
- `POST /api/v1/billing/webhook`：只对这一个 POST 路径免 Cookie CSRF；原始 body 上限 256 KB，验证 HMAC-SHA256、签名时间 ±300 秒、test mode 和允许的事件类型。签名时间是本次投递时间，旧事件重送可使用新签名；超过订单 90 天保留边界不得重新激活。
- `POST /api/v1/internal/maintenance`：只接受 `Authorization: Bearer <RR_MAINTENANCE_TOKEN>`，普通登录无权限；MT-18 已接入费用恢复、资料生命周期与支付恢复，统一返回计数及 backlog，详见 [生命周期手册](LIFECYCLE.md)。仓库提供每日／手动 Actions workflow，线上配置与调度尚待验收。

`/account` 展示会员有效期、剩余／预留额度和明确的测试购买入口；确认服务器订单后再提供 Stripe 链接。`/account/payment?order=<uuid>` 最多查询 10 次，每次间隔 3 秒，之后可手动刷新。URL 中的 `paid=true` 等标记不参与判断。页面不创建 run、不执行模型；回到原包时读取已有服务端草稿。工作区有未保存编辑时不显示支付导航，先保存再离开。

## 幂等与撤销

先持久化订单再调用 Stripe；供应商幂等键固定为 `rr-order-<order-id>`，商品／金额／币种／回跳地址在订单中冻结。测试 Price 在供应商端必须是 active、one_time、livemode=false，且金额和币种完全匹配。Checkout 是 payment 模式，不启用订阅。订单固定 31 分钟过期窗口（留出请求处理时间），30 分钟内可恢复创建请求；未结束订单通过 `(owner, test)` 唯一索引避免不同请求键重复创建。已有有效会员不能叠加购买，即使次数已用完也要等有效期结束。

事件先保存最小 ID、类型、对象 ID 和状态，不存完整 body／邮箱／卡号。每次处理重新查询 Stripe Session、唯一 line item 和 PaymentIntent／Charge。校验订单引用、metadata 中服务端写入的订单 ID、Session ID、Price、金额、币种及 test mode 后，按 user → order → event 顺序加锁，在同一事务内更新付款、发放一次会员和标记事件完成。PaymentIntent 和 source_order_id 各自唯一，重复事件 ID 或不同事件通知同一笔付款均不重复发放。

只有 complete、paid 且成功的 PaymentIntent／Charge 才发权益；未到账保持 pending。失败／expired 不发放。退款（包括部分退款）或争议撤销剩余权益，不删资料；撤销为单向状态，后来的 paid 快照不能复活它。已发生的运行／费用由原账本保留，取消或退款不构成费用回滚。

## 异常与恢复

1. 签名／测试环境／订单绑定错误：拒绝，绝不发权益；经过验签的无效订单事件可记录为 rejected。
2. Stripe 暂时不可用、事务失败：事件记 failed 并返回可重试 503；供应商重送或受保护维护调用可重入。权益和事件状态在同一事务，提交失败不会留下半个会员。
3. 已知 Session 的 pending 订单：维护重新查询当前状态，处理延迟到账或过期。GET 和支付返回页没有补偿副作用。
4. 创建 Checkout 已发出但响应丢失：客户端用同 key 重试，维护也可在订单创建后 23 小时内用原参数和原供应商键恢复。过期时间不重置；超过这个安全窗口不盲目创建第二个 Session，订单保持待核查，需操作者在 Stripe 核对原订单并重送其签名事件。未查清前不自动解除 pending 唯一约束。
5. 没有创建成功且已超过原 expires_at 的订单也可能保持待核查；本版不通过“超时等于失败”猜测财务状态。此类人工核查能力和通知在 MT-19 运维验收中检查。

维护每组最多 20 条；每个 HTTP 请求 15 秒超时，无自动网络重试。调用时间上限及调度监控仍须 MT-19／24 实测；勿把本接口当成无限后台 worker。

## 真实测试环境验收步骤（尚未执行）

1. 完成 PostgreSQL 和 OAuth 前置验收，操作者配置固定的 Stripe **测试**商品、金额与 webhook。后端启动／重启按项目规则手动操作。不要切换 Live mode。
2. webhook 订阅 `checkout.session.completed`、`checkout.session.async_payment_succeeded`、`checkout.session.async_payment_failed`、`checkout.session.expired`、`charge.refunded`、`charge.dispute.created`、`charge.dispute.closed`，地址必须是同一项目的 `/api/v1/billing/webhook`。CLI 转发与 Dashboard 的签名 secret 不混用。
3. 保存合成资料包和草稿，进入账户测试购买，使用 Stripe 测试支付方式完成 Checkout。记录脱敏 `evt_…`、`cs_test_…`、订单 ID、test mode、服务器状态和 30 天／20 次权益；不保留卡信息或完整事件 body。
4. 重送同一事件和同笔付款的另一个事件；权益仍一份。取消另一次未付款 Checkout 后资料仍在；返回页不自动核对。
5. 在测试控制台退款并重送 completion，权益保持失效；测试回调暂时不可用后的重试／维护恢复。
6. 检查公共沙箱账号仍不能进行真实 AI 核对。验证会员过期后手动审核与导出可用。测试不要求发送模型请求。
7. 执行 PostgreSQL 多进程同账号购买／重复回调竞争，记录唯一订单／会员结果。SQLite 测试不能替代这一项。

实现参考：[Checkout Session 创建](https://docs.stripe.com/api/checkout/sessions/create)、[Webhook 验签与重送](https://docs.stripe.com/events/manage-webhook-endpoints)、[Charge 退款与争议字段](https://docs.stripe.com/api/charges/object)。当前本地未配置 Stripe 四项必要变量，尚无真实事件 ID 或供应商往返验收记录。
