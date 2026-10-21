# Referral Review 配置与工程操作

当前已实现基础配置、契约、持久化、合成资产和 MT-04 认证代码。认证默认禁用，真实 GitHub 往返尚待配置验收；资料包业务、完整示例页面、模型执行及付款仍未实现。`/api/v1/capabilities` 明确列出各能力为 false；`/api/v1/readiness` 返回 503 / not_ready，不能用于宣称 V1 已可上线。完整示例属于 MT-03/16，就绪检查属于 MT-02/03/19。

MT-02 已添加领域持久化与显式追加迁移，但尚待 PostgreSQL 实测。独立测试库和迁移操作见 [迁移手册](MIGRATIONS.md)；这些改动不会自动连接或升级生产数据库。

## 配置模式

- `bundled_demo`：默认模式，不要求密钥，不允许真实执行。固定合成示例后续打包，不能自动接收并持久化访客输入。
- `sandbox`：可配置 GitHub 登录；Stripe test 权益尚未实现，后续模型执行只能使用 Fake／Replay，绝不静默回退并伪装为真实模型结果。
- `invited_real`：只是配置意图。真实执行还必须有邀请账号、会员、共享预算及并发预留（MT-04/10/11），不能仅凭开关或配置验证成功放行。

MT-01 不注册任何 execute、grant 或开发登录接口。`X-User-ID`、`X-Member` 不被信任；未知 `RR_*` 配置（含 fake identity / dev grant）直接拒绝。配置错误不回显输入；即使完整填写真实配置，capabilities 的真实执行能力仍为 false。

这些限制只覆盖新的 `/api/v1` 模块。旧 `/api/diagnose`、聊天等功能尚未退役，旧模块并不使用新的预算开关；因此不能把 MT-01 视为旧站的费用／安全改造。旧入口封闭是 MT-21 的发布前置条件。

## 环境变量表

下表全部是 **FastAPI 服务端 runtime** 变量，不能添加 `NEXT_PUBLIC_` 前缀或放入 Next.js `env`。空字符串按未配置处理。配置在创建应用时读取，修改后须由开发者手动重启后端；生产通过 Vercel 环境配置后重新发布。本工单不写入供应商密钥或控制台。

| 变量 | 默认／约束 | 使用方 |
| --- | --- | --- |
| `RR_ENVIRONMENT` | development；允许 test / production；Vercel preview 与 production 强制 production，不能降级 | config |
| `RR_MODE` | bundled_demo；可选 sandbox / invited_real | capabilities、未来执行策略 |
| `DATABASE_URL` | 未设置；生产若设置必须 PostgreSQL URL，实际生产数据库必配 | MT-02 |
| `RR_SITE_ORIGIN` | 未设置；仅 origin，无路径／用户信息／query／fragment；生产 HTTPS | MT-04 CSRF/OAuth |
| `RR_GITHUB_CLIENT_ID` | 未设置 | MT-04 |
| `RR_GITHUB_CLIENT_SECRET` | 未设置，秘密 | MT-04 |
| `RR_GITHUB_CALLBACK_URL` | 未设置；若设置必须等于 origin + `/api/v1/auth/github/callback` | MT-04 |
| `RR_SESSION_ENCRYPTION_KEY` | 未设置；启用认证时必须为 Fernet key，即 32 个随机字节的 URL-safe Base64 编码，不能使用普通口令 | MT-04 OAuth verifier 加密 |
| `BLOB_READ_WRITE_TOKEN` | 未设置，秘密 | MT-05 |
| `RR_STORAGE_BACKEND` | disabled；允许 local / vercel；生产禁止 local；vercel 必须配私有 store 的 token | MT-05 |
| `RR_PRIVATE_STORAGE_DIR` | 未设置；local 必填绝对路径；不在仓库或 public 下；私有目录 0700、对象 0600 | MT-05 |
| `RR_STORAGE_GLOBAL_BYTES` | 1073741824（1 GiB）；非负整数；0 禁止新上传，仍可读和清理 | MT-05 |
| `RR_STRIPE_SECRET_KEY` | 未设置；只接受 `sk_test_` / `rk_test_` 前缀；后续仍需校验 webhook 的 livemode | MT-17 |
| `RR_STRIPE_WEBHOOK_SECRET` | 未设置，秘密 | MT-17 |
| `RR_STRIPE_PRICE_ID` | 未设置，服务端固定测试商品 | MT-17 |
| `RR_STRIPE_AMOUNT_MINOR` | 0；非负整数；真正启用 Checkout 前必须核对固定商品金额 | MT-17 |
| `RR_STRIPE_CURRENCY` | usd；3 位小写字母 | MT-17 |
| `REAL_AI_ENABLED` | false；不能单独授权调用 | MT-10/11 |
| `DEEPSEEK_API_KEY` | 未设置，秘密；旧聊天也读取此变量，不能用新开关控制旧聊天 | MT-08/21 |
| `RR_MODEL_ID` | 未设置；明确模型标识，不能使用客户端指定值 | MT-08 |
| `RR_MODEL_PRICE_VERSION` | 未设置；有日期的人工核实价格版本 | MT-10 |
| `RR_MODEL_INPUT_MICROUSD_PER_MILLION_TOKENS` | 0；每百万输入 token 的整数 micro-USD，启用真实调用须 > 0 | MT-10 |
| `RR_MODEL_OUTPUT_MICROUSD_PER_MILLION_TOKENS` | 0；每百万输出 token 的整数 micro-USD，启用真实调用须 > 0 | MT-10 |
| `RR_DAILY_BUDGET_MICROUSD` | 0；UTC 日预算，整数且非负；启用真实调用须 > 0 | MT-10 |
| `RR_MONTHLY_BUDGET_MICROUSD` | 0；UTC 月预算，整数且非负；启用真实调用须 > 0 | MT-10 |
| `RR_REAL_AI_USER_IDS` | 空；逗号分隔的内部 user UUID，不是 GitHub 昵称；真实配置预检要求非空 | MT-04/10 |
| `RR_MAINTENANCE_TOKEN` | 未设置；若设置至少 32 字符的高熵秘密 | MT-18/19 |

`VERCEL=1` 或 `VERCEL_ENV=preview/production` 是平台注入的 runtime 信号，不是应用身份凭据。`Settings.require_real_ai_configuration()` 仅检查配置完整性，不替代账号鉴权、会员、余额或事务预留。1 USD = 1,000,000 micro-USD；这里不提供会自动启用消费的价格／预算示例。

前端 build-time：Node 22、pnpm 10.34.7；旧 `NEXT_PUBLIC_BACKEND_URL` 只供旧页面使用。新客户端固定同源 `/api/v1`，无公开密钥／名单配置。开发时 Next.js 将此路径代理到 `127.0.0.1:8000`；生产不生成此代理，沿用根 `vercel.json` 的 Services rewrite。`.env.example` 是模板，复制前请确认不会覆盖现有 `.env`；配置模块本身不主动读取文件，旧 `main.py` 加载环境后挂载新模块，CI 使用 `PYTHON_DOTENV_DISABLED=1` 避免本地密钥影响测试。

认证的启用条件、Cookie、归属 Interface 和手动 GitHub 验收步骤见 [认证手册](AUTHENTICATION.md)。身份配置不会自动迁移数据库、授予会员或放开真实 AI。

MT-05 的上传、存储配置、补偿操作及真实供应商验证见 [私有存储手册](STORAGE.md)。存储默认禁用，没有公开桶或本地自动回退。MT-06 解析代码已接入，配置成功不代表 MT-07 资料包流程或 MT-14 上传 UI 已实现。

## 安装和生成（仓库根目录）

依赖权威源为前端 package.json + pnpm-lock.yaml，以及后端 pyproject.toml + uv.lock。后端 requirements 是带 hashes 的生成产物；根 requirements 只转引，禁止手动维护第二份版本清单。

```bash
# 预装 Node 22、pnpm 10.34.7、uv 0.13.3、Python 3.12
pnpm --dir src/frontend install --frozen-lockfile
uv sync --project src/backend --frozen

# Pydantic → OpenAPI / JSON Schema → TypeScript
python3 scripts/referral_contracts.py --write
python3 scripts/referral_contracts.py --check
python3 scripts/check_backend_lock.py

# 仅在主动改依赖时重锁并导出；这些产物一同提交
uv lock --project src/backend
uv export --project src/backend --frozen --no-dev --no-emit-project --output-file src/backend/requirements.txt
```

uv 使用独立 `src/backend/.venv`，不会替换已有 `venv`。启动必须仍使用虚拟环境：开发者在 `src/backend` 手动执行 `./.venv/bin/python main.py`；前端手动 `pnpm dev`。不自动启动／停止服务。契约工具默认优先 `.venv`，可用 `REFERRAL_PYTHON` 指定解释器；依赖锁检查可用 `UV` 指定 uv 路径，二者只是工具配置，不进入部署应用。

## 验证

```bash
PYTHON_DOTENV_DISABLED=1 DATABASE_URL=sqlite:///:memory: src/backend/.venv/bin/python -m pytest -q src/backend/tests/referral_review src/backend/test_database_deployment.py
python3 scripts/test_deploy_workflow.py
pnpm --dir src/frontend lint
pnpm --dir src/frontend test --runInBand
pnpm --dir src/frontend build
pnpm --dir src/frontend typecheck
pnpm --dir src/frontend audit --prod --registry=https://registry.npmjs.org
src/backend/.venv/bin/pip-audit -r src/backend/requirements.txt --no-deps --disable-pip
```

没有 `TEST_DATABASE_URL` 时旧 PostgreSQL 集成测试明确 skip，不访问现有生产库。禁止运行不加筛选的旧模型测试，更不能自动在浏览器发送 AI 消息。本次基础测试只用 TestClient、合成字段和 mock fetch，不消耗模型 token。CI 执行同样的构建／测试／漂移检查，并阻止生产依赖高危漏洞。

契约文件位于 `contracts/referral-review/`，TS 类型位于 `src/frontend/lib/referral-api/generated.d.ts`。只编辑 Pydantic 源文件；导出的 OpenAPI 额外携带尚未绑定业务端点的领域 components，不能据此认为业务路由已实现。UUID、带时区时间归一 UTC、证据 code-point 半开区间及引用完整性在基础层验证；源文件 hash／精确定位由 MT-06 验证。
