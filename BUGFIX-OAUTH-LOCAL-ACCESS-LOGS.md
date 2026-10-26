# OAuth 本地回调日志与验收环境

2026-10-26，归属 MT-04。准备真实 GitHub 登录验收时发现：应用日志虽已脱敏，Next.js 开发请求日志和 Uvicorn 默认 access formatter 仍会输出完整 callback query，包含授权码与 state。

## 复现与根因

离线调用已安装 Next.js 的 `logRequests`，传入带合成 code/state 的 `/api/v1/auth/github/callback`，输出包含两个 sentinel；Uvicorn 默认 access formatter 同样输出合成 code。两项断言均退出 1。没有启动服务、使用真实授权码或发起模型请求。

直接原因是两个框架默认记录完整请求 URL，应用的结构化日志脱敏不作用于框架 access logger。本次是可直接复现的配置问题，无需扩大到会话或供应商 token 交换逻辑。

## 修复

- Next.js 使用安装版本文档支持的 `logging.incomingRequests.ignore`，不打印 `/api/v1/auth` 请求；普通页面请求继续记录。
- `operations/access_logging.py` 给 Uvicorn access handler 加过滤器，保留路径、状态码、方法，剥离 query；非预期记录格式拒绝输出。根 `main.py` 的直接启动入口和独立验收入口都使用此配置。
- 增加 `scripts/referral_auth_local.py`：显式创建仅本机使用的 OAuth 配置和 SQLite 库；目录 0700、凭据及数据库 0600，已加入 gitignore，不覆盖已有环境。配置由显式字段构造，不继承 shell 中的生产连接或模型开关；初始化只迁移新建本地库，服务启动时只读核对版本。`prepare`／`check` 不启动监听服务。
- 本地 GitHub App 与生产 App 分开，回调精确指向 `http://127.0.0.1:3000/api/v1/auth/github/callback`。服务仅由操作者执行 `backend`／`frontend` 子命令启动，绑定 loopback。

## 回归与边界

回归测试直接执行 Next.js 请求 logger 和 Uvicorn access handler，检查成功／拒绝回调不输出敏感参数，保留普通页面日志。身份测试对 HTTPS 与本地 HTTP 两种 origin 执行同一组登录、退出、CSRF、重放、归属及失败路径验证。隔离环境测试验证生产环境变量无法覆盖 sandbox、文件权限校验和拒绝覆盖已有凭据。

真实 GitHub consent 及往返仍需运行服务后验证。SQLite 本地登录不替代 PostgreSQL／Vercel 线上验收。Vercel 的上游访问日志不受本地 Uvicorn 配置控制，必须独立检查；其他自定义 Uvicorn CLI 启动方式须显式使用该日志配置。
