# MT-04 认证实现与验收证据

2026-10-26 最新：MT-02 已完成，生产 OAuth 六项配置已保存；**独立本地环境的真实 GitHub consent、登录／回跳／刷新／退出已经通过**。MT-04 仍为 `BLOCKED`，剩余托管平台日志配置与实测；Vercel 尚未部署新代码。本地 SQLite 结果不能替代托管环境验收。

## 2026-10-26 真实本地 OAuth 验收

- 环境：独立 [Local OAuth App](https://github.com/settings/applications/3964380)，`http://127.0.0.1:3000`，隔离 SQLite `rr_0006`，sandbox；账号别名 `local-reviewer-01`。用户明确授权代理启动两个本地服务，并确认亲自在 GitHub 页面点击授权。
- 首次回调失败：GitHub 带 `iss`，此前严格参数白名单提前拒绝。两个离线复现用例先失败；补充精确 issuer 校验后，身份套件 **86 passed**（HTTPS／HTTP loopback）。错误／空／重复 issuer 不触发 token 交换。见 [修复记录](../../BUGFIX-GITHUB-OAUTH-ISSUER.md)。
- 修复后真实 GitHub 往返返回 `/workspace`，session 为已登录并含 CSRF；刷新保持会话，响应 `private, no-store`／`no-referrer`，页面脚本不可读取 session cookie。
- 不带 CSRF 的退出请求为 **403** 且会话保持；通过账户页 Sign out 正常退出，session 恢复匿名且 CSRF 清空，私有 `/api/v1/packets` 返回 **401**，刷新工作区显示登录入口。数据库计数为 1 个用户、1 个会话且该会话已撤销。
- 非法外部 return URL 返回 **422**；无有效 state 的合成失败回调返回 **303** 通用失败页。实际供应商 consent 拒绝路径尚未再次操作；离线拒绝／过期／重放测试通过。
- 运行中前后端日志检查未见 callback query、cookie 或 Authorization 凭据头；合成 query 通过真实前端代理后也未进入日志。原始敏感网络内容未保存到仓库或文件。
- 本次其余定向验证：隔离环境／日志与初始身份测试 **75 passed**；旧入口及运维测试 **119 passed**；Next 日志测试 **1 passed**，修改文件 ESLint 通过。未运行模型、创建资料包、购买会员、修改生产库或部署。

以下是同日准备阶段与早期历史记录，状态以上述实测为准。

2026-10-26 本地验收准备：已创建独立 [Local OAuth App](https://github.com/settings/applications/3964380)，精确 callback 使用 `http://127.0.0.1:3000/api/v1/auth/github/callback`。专用脚本已创建私有凭据和独立 SQLite 数据库，显式迁移至 `rr_0006`；`check` 返回 ready，不连接生产库。等待操作者按仓库规则启动两个服务及完成 consent，尚未取得真实往返证据。HTTPS／HTTP loopback 身份与环境隔离／日志测试 **75 passed**，Next 开发日志回归 **1 passed**。发现并修复框架 access log 输出 callback query 的问题，见 [BUGFIX](../../BUGFIX-OAUTH-LOCAL-ACCESS-LOGS.md)。

以下为 2026-10-20 历史实施记录；当时的依赖／配置缺项以上方最新记录为准。认证代码和离线回归已通过；工单尚不可关闭。前置 MT-02 缺 PostgreSQL 实测，MT-04 自身缺真实 GitHub 配置、用户 consent 和完整登录往返。当时按依赖规则保留 `TODO`，不将模拟供应商响应记为外部验收。

MT-03 已先提交为 `24b710e`；本记录与 MT-04 实现一同提交，提交可通过 `git log -- docs/referral-review/MT-04-EVIDENCE.md` 定位。未推送远程。

## 实现范围

- `src/backend/referral_review/identity/`：Authlib GitHub Adapter、一次性 OAuth state、PKCE、会话、退出、CSRF 与共享 require_owner。
- `app.py`、`schemas/__init__.py`、`errors.py` 及生成契约：4 个认证端点、默认变更防护、类型化 session、安全错误与响应头。
- 前端 `/login`、`/workspace`、`/account`、`IdentityPanel` 和同源 API 客户端：未登录、未配置、已登录、过期、退出及失败状态。没有提前实现上传或资料包业务。
- `persistence/database.py`：明确选择已安装的 PostgreSQL 驱动；复现和修复范围见 [修复记录](../../BUGFIX-REFERRAL-POSTGRES-DRIVER.md)。
- 后端依赖新增 Authlib、requests 和 cryptography，更新 lock 及生成的 requirements；cryptography 最终锁定并实际安装 50.0.2，本机 Intel macOS 使用源码构建，没有保留存在已知漏洞的临时兼容降级。

身份模块集中隐藏 OAuth、哈希、加密和事务细节；外部 GitHub HTTP transport 可注入测试，运行环境没有 Fake identity 开关。测试使用显式迁移的临时 SQLite，不连接现有生产库。

## 测试驱动记录

用户已确认三个测试边界：FastAPI `/auth/*`、共享 require_owner、登录／工作区 UI。按垂直切片先观察失败，再实现：匿名会话 404、缺失身份模块、退出 404、缺失归属 Interface、未保护的新变更端点，随后逐项通过。默认 CSRF 检查还覆盖 `/api/v1` 挂载和 webhook 样式路径，不能靠路径名称绕过认证。

新增后端身份测试 37 项，覆盖 state／nonce／PKCE、重放、10 分钟过期、非法回跳、供应商异常与伪造 subject、7 天非滑动会话、旋转、退出、账号停用、跨账号及删除／到期资料拒绝、秘密不回显、Origin／CSRF、无数据库连接启动。

新增 UI 测试 6 项，覆盖匿名、已登录退出、失效刷新、未配置／网络错误、退出失败重试及不反射危险回跳／错误参数。测试不请求 GitHub、不调用模型，也不操作浏览器会话。

## 命令与结果

以下命令在仓库根目录执行，后端使用 Python 3.12.14 虚拟环境，cryptography 50.0.2。

| 检查 | 结果 |
| --- | --- |
| `PYTHON_DOTENV_DISABLED=1 DATABASE_URL=sqlite:///:memory: src/backend/.venv/bin/python -m pytest -q src/backend/tests/referral_review src/backend/test_database_deployment.py` | 158 passed、31 skipped、5 个现有弃用警告 |
| `python3 scripts/referral_contracts.py --check` | Pydantic、OpenAPI、TS 生成契约一致 |
| `UV=src/backend/venv/bin/uv UV_CACHE_DIR=.uv-cache python3 scripts/check_backend_lock.py` | lock 与 requirements 一致 |
| `python3 scripts/test_deploy_workflow.py` | 10 项通过；只验证脚本，不发布 |
| `pnpm --dir src/frontend lint` | 0 error、28 个旧代码 warning；新文件无警告 |
| `pnpm --dir src/frontend typecheck` | 通过 |
| `pnpm --dir src/frontend test --runInBand` | 5 suites、23 tests 通过 |
| `pnpm --dir src/frontend build` | 生产构建通过，包含三个新页面 |
| `src/backend/.venv/bin/pip-audit -r src/backend/requirements.txt --no-deps --disable-pip` | 未发现已知漏洞 |
| `src/backend/.venv/bin/pip-audit --local` | 实际安装环境未发现已知漏洞 |

31 项 skip 属于尚无独立 `TEST_DATABASE_URL` 的 PostgreSQL 验证，不能视为通过。没有执行付费模型测试、浏览器 AI 对话、部署或数据库迁移；应用服务未自动启动／停止。

## 待完成的验收

1. MT-02 的独立 PostgreSQL 迁移和事务竞争验证已于 2026-10-26 完成，见 [CI 证据](CI-2026-10-26.md)。本地 SQLite 登录不替代 PostgreSQL 或托管环境验证。
2. 独立本地环境的用户 consent、登录、安全回跳及退出已完成，见本页最新记录。托管环境的 HTTPS cookie 和同源路由仍须随部署验证；不保存实际密钥。
3. 登录、工作区及账户页面已作真实浏览器交互检查。托管平台敏感日志配置与实测仍未完成；本地日志检查不能代替。

capabilities 继续为 false，readiness 继续为 503；身份代码通过离线测试不代表私人工作区、会员、受控 AI 或完整产品已交付。MT-03 的人工标注复核也仍待完成。
