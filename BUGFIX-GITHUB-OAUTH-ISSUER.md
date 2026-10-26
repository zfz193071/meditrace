# GitHub OAuth 回调包含 iss 时无法登录

2026-10-26，MT-04 真实本地登录验收发现。操作者在 GitHub 完成授权后回到 `/login?error=oauth_failed`，没有用户或会话写入。数据库 state 尚未被认领，说明失败发生在 token 交换之前。

## 根因及复现

仅检查浏览器请求的参数名与 cookie 是否存在，确认真实回调为 `code`、`state`、`iss`，nonce cookie 已携带。`iss` 的值与 GitHub 公布的 `https://github.com/login/oauth` 一致；没有记录授权码、state、cookie、密钥或完整回调 URL。

认证路由此前只允许 code/state/error 等字段，将 `iss` 判为未知参数，提前拒绝。用合成回调重现相同请求形状，在 HTTPS 和 HTTP loopback 下均失败：`test_github_issuer_callback_completes_real_provider_response_shape` 为 **2 failed**，实际跳转到失败页而非 workspace。离线测试此前只模拟不含 iss 的回调，因此未覆盖供应商实际行为。

## 修复及安全边界

回调允许单个 `iss`，在任何 token 请求前将解码后的值与固定 GitHub issuer 作精确字符串比较。错误域名、根域而非 issuer 路径、HTTP、尾斜线、空值和重复参数均拒绝；测试确认不调用 token endpoint、不创建会话。保留未知参数与重复参数拒绝、state/nonce/PKCE 校验及一次性 state 认领。

本客户端只支持固定 GitHub.com endpoints，不从 iss 动态发现或请求网络地址。按 RFC 9207 2.4 的本地策略，兼容不带 iss 的历史响应；存在 iss 时必须精确验证。若未来增加其他身份供应商，须逐供应商固定 issuer 并重新审查缺失 iss 的策略。

依据：[GitHub authentication discovery endpoints](https://docs.github.com/en/apps/github-authentication-discovery-endpoints)（官方 issuer）、[RFC 9207 §2.4](https://www.rfc-editor.org/rfc/rfc9207.html#section-2.4)（精确验证、拒绝不匹配及缺失参数的本地策略）。这些依据不替代真实往返验收。
