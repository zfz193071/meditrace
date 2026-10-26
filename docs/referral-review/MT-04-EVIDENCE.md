# MT-04 认证实现与验收证据

2026-10-26 更新：MT-02 已完成，MT-04 改为 `BLOCKED`。[OAuth App](https://github.com/settings/applications/3964320) 已创建且核对精确 callback；六项 Vercel production OAuth 配置已保存并经 API 存在性复核，client secret 类型为 `sensitive`。真实应用 consent、登录／退出／错误回跳及平台日志验收仍未执行。最新资源状态见 [阻碍记录](BLOCKERS-AND-DEPLOYMENT-PREREQUISITES.md)，不以 GitHub 设置页面登录成功替代应用 OAuth 验收。

日期：2026-10-20。认证代码和离线回归已通过；工单尚不可关闭。前置 MT-02 缺 PostgreSQL 实测，MT-04 自身缺真实 GitHub 配置、用户 consent 和完整登录往返。按依赖规则保留 `TODO`，不将模拟供应商响应记为外部验收。

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

1. MT-02 的独立 PostgreSQL 迁移和事务竞争验证。SQLite 不证明 PostgreSQL 并发行为。
2. 按 [认证手册](AUTHENTICATION.md) 配置真实 GitHub OAuth，并由用户完成 consent、登录、安全回跳及退出，回填脱敏结果。验收记录仅保留配置存在性及类型；密钥仅通过内存传入平台表单，不记录实际值。
3. 实际浏览器的页面布局与托管平台敏感日志配置检查。组件测试与构建通过不替代这些检查。

capabilities 继续为 false，readiness 继续为 503；身份代码通过离线测试不代表私人工作区、会员、受控 AI 或完整产品已交付。MT-03 的人工标注复核也仍待完成。
