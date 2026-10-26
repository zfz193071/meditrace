# Referral Review 认证配置与验收

MT-04 提供 GitHub 登录、不透明会话、退出和共享资料归属校验。它不提供资料编辑、会员、付款或模型权限。默认 `bundled_demo` 下登录禁用；新认证规则不保护仍待 MT-21 退役的旧聊天接口。

## 启用条件

2026-10-26 配置进度：[MediTrace Referral Review Copilot OAuth App](https://github.com/settings/applications/3964320) 已创建，首页为 `https://meditrace.baozaolaoba.top`，callback 为 `https://meditrace.baozaolaoba.top/api/v1/auth/github/callback`，wildcard 和 device flow 关闭。生产站点、client ID、callback、session key 与 sandbox 模式已写入 Vercel；client secret 已通过浏览器表单保存；Vercel API 复核六项 production 配置均存在，`RR_GITHUB_CLIENT_SECRET` 类型为 `sensitive`。本次没有发布，资源创建不代表真实登录已验收。

聊天中曾暴露的客户端密钥均已撤销，替代密钥已保存到 Vercel。浏览器文件导出受限后，本轮通过工具编排在内存中将页面值传入 Vercel Secret 表单并保存，没有导出本地文件或在聊天、仓库中记录密钥值。后续手动轮换也应将 `RR_GITHUB_CLIENT_SECRET` 作为固定变量名，密钥仅填写到平台的 Value 字段或 CLI 的变量值提示中。

后端使用 `RR_MODE=sandbox`，同时配置 `DATABASE_URL`、`RR_SITE_ORIGIN`、`RR_GITHUB_CLIENT_ID`、`RR_GITHUB_CLIENT_SECRET`、`RR_GITHUB_CALLBACK_URL` 和 `RR_SESSION_ENCRYPTION_KEY`。缺任意项时 `/auth/session` 返回匿名且 `login_available=false`，登录入口返回 503，不生成开发账号。错误格式的加密 key 会阻止已配置认证模块启动。

GitHub OAuth App 的 callback 必须精确等于 `RR_SITE_ORIGIN` 加 `/api/v1/auth/github/callback`。只申请公开身份，不申请邮箱或仓库权限；用服务端 `GET /user` 的稳定数字 ID 映射内部 UUID，不信任昵称、客户端 subject 或 `X-User-ID`。OAuth 使用 Authlib、S256 PKCE 和每次登录的新 state。[GitHub OAuth 文档](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/authorizing-oauth-apps)／[Authlib 客户端文档](https://docs.authlib.org/en/stable/oauth2/client/http/index.html)。

加密 key 必须是 32 个随机字节的 URL-safe Base64 编码，使用 Fernet 的 `generate_key()` 在私有终端生成，并直接存入本地未跟踪环境文件或托管平台密钥配置；不要贴到聊天、截图或提交记录。所有实例共享同一个 key；更换会使尚未完成的 OAuth 登录失效，需要重新开始，不会解密或恢复会话 cookie。[Fernet 格式](https://cryptography.io/en/latest/fernet/)。

先按 [迁移手册](MIGRATIONS.md) 在明确指定的开发／测试库运行迁移。应用构造不连接数据库，也不在启动时执行 DDL。配置更新后由开发者手动重启后端；不要覆盖现有环境文件或对生产库试跑。

## 会话与请求边界

- state 和浏览器 nonce 各为 256 bit 随机值，数据库只保存其哈希；PKCE verifier 加密保存。有效期 10 分钟；state 在访问 GitHub 前原子认领并提交，即使供应商失败也不可重试同一 state。
- 会话 cookie 是新的 256 bit 随机值，数据库只存 SHA-256 哈希。有效期 7 天，不滑动续期；再次登录旋转当前 cookie，退出立即撤销当前会话，停用账号拒绝登录及后续身份检查。
- HTTPS 使用 `__Host-rr_session`／`__Host-rr_oauth`，HttpOnly、Secure、SameSite=Lax、Path=/、无 Domain。仅本地 HTTP 使用不带前缀且非 Secure 的 cookie；生产配置强制 HTTPS。
- `/auth/session` 可向同源页面返回内部用户 UUID、显示名、CSRF token、到期时间与登录可用状态，不返回 cookie 或 GitHub token。前端只将这些状态保存在内存；响应使用 `private, no-store` 和 `no-referrer`。
- 已注册的非 GET／HEAD／OPTIONS 请求默认要求有效会话、精确同源 Origin 和 `X-CSRF-Token`。OAuth callback 为 GET，由 state／nonce／PKCE 校验；没有 `/auth/*` 或 webhook 前缀通用免检规则。MT-17／18 接入支付回调／维护接口时须显式实现并测试其专有认证。
- 回跳只允许 `/workspace`、`/account` 或 `/workspace/packets/{小写 UUID}`；禁用绝对 URL、query 和 fragment。packet 不存在、不归属当前账号、已删除或已到期时回退 `/workspace`。packet 页面属于后续工单，本票只实现安全回跳判断。

共享 `require_owner(request, connection, packet_id)` 必须在业务读写所用的同一事务内调用。按用户、会话、资料包顺序加锁；匿名／失效为 401，越权／不存在／已删除／已到期统一为 404。后续子资源查询必须限制到返回的 packet，不能只验证一个客户端传入的 owner ID。

## 人工 GitHub 验收

仅在独立测试库准备好、迁移通过且配置齐全后执行。真实 consent 必须由用户完成，不记录密钥、授权码、state、cookie 或患者信息。

1. 开发者手动启动前后端，打开 `/login?return_path=/workspace`，确认显示 GitHub 登录按钮；未配置时应显示不可用提示。
2. 点击登录并在 GitHub 完成授权，确认安全返回 `/workspace`、显示当前账号。记录日期、环境、脱敏账号别名和成功状态，不录制 OAuth URL 或网络敏感字段。
3. 刷新页面应保持会话；访问 `/account` 后退出，再刷新工作区，应恢复未登录状态。第二账号的越权验证在后续真实资料包端点可用时补充，当前集中 Interface 已有离线测试。
4. 拒绝一次 GitHub consent，确认通用失败提示且不创建新会话；随后重新发起登录应可恢复。非法回跳应被拒绝。
5. 核对托管平台访问／错误日志不记录 cookie、Authorization、GitHub 响应正文或带敏感 query 的 callback URL。应用日志脱敏测试不能代替平台日志配置验收。

过期、重放、跨账号、CSRF 和网络异常由离线测试覆盖，无需为了测试修改生产会话或等待 7 天。UI 的过期与退出失败状态已做组件测试，浏览器布局尚未人工验收。全程不发送 AI 消息。
