# MT-01 工程基线验收记录

日期：2026-10-20。结论：MT-01 基础工程验收通过；不代表完整 Referral Review 业务完成或已部署。本次没有启动／停止用户服务、访问生产数据库、执行真实模型请求、触发浏览器会话测试或发布代码。

## 版本与兼容性

| 层 | 锁定版本或约束 | 验证 |
| --- | --- | --- |
| Node / pnpm | Node 22.x，本机 22.19.0；pnpm 10.34.7 | frozen-lockfile 离线安装成功 |
| Next / React | 16.4.2 / 19.3.1 | Webpack 生产 build、类型检查、17 项测试通过 |
| TypeScript / ESLint | 5.9.3 / 10.13.0 | 与 typescript-eslint 8.72.0 匹配，lint 0 errors |
| Python / uv | Python 3.12.x，本机 3.12.14；uv 0.13.3 | 新 `.venv` 从冻结锁文件安装成功，原 `venv` 保留 |
| FastAPI / Starlette / Pydantic | 0.150.0 / 1.9.0 / 2.14.1 | import、挂载路由、配置／错误／契约测试通过 |
| SQLAlchemy / psycopg2-binary | 2.1.5 / 2.9.13 | 临时 SQLite 持久化与回滚回归通过；PostgreSQL 实连未做 |
| Uvicorn / httpx | 0.54.0 / 0.28.1 | 锁文件安装与模块兼容检查通过 |

Next 14 已不在支持范围，本次升级到 active LTS 16 系列，依据 [Next.js 支持策略](https://nextjs.org/support-policy)。保留官方支持的 [Webpack 构建选项](https://nextjs.org/docs/app/api-reference/cli/next)：当前环境的 Turbopack 在 PostCSS 子进程通信时遇到端口权限错误。移除构建时 Google Fonts 下载，沿用已有 globals.css 系统字体栈，避免字体网络故障阻断构建。

[Vercel Python runtime 文档](https://vercel.com/docs/functions/runtimes/python) 支持 Python 3.12、pyproject.toml 和 uv.lock。保留原有 Services 配置与 `/api/(.*)` rewrite，新模块挂载 `/api/v1`。Linux x86_64 / manylinux_2_28 / Python 3.12 的依赖 dry-run 成功解析 87 个运行依赖；这是目标平台解析验证，不是 Linux 执行或线上 smoke，实际 Vercel 构建及发布在 MT-24 验收。

依赖唯一维护入口为 pyproject.toml + uv.lock。backend requirements 从锁文件导出，根 requirements 仅转引。删除未使用且旧声明版本不可解析的 `vercel>=1.0.0`：FastAPI 部署不依赖该全量 SDK，后续 Blob 集成在 MT-05 选择所需包。旧 web3 / ipfshttpclient 暂时保留以兼容原应用，不用于新模块；后者是历史预发布依赖，MT-21 退役旧功能时应移除对应运行依赖。

## 验收命令与结果

以下均在仓库根目录执行；本机 uv 位于 `src/backend/venv/bin/uv`，锁检查使用 `UV=src/backend/venv/bin/uv UV_CACHE_DIR=.uv-cache`。环境及常规安装命令见 [配置与工程操作](CONFIGURATION.md)。

| 命令或检查 | 结果 |
| --- | --- |
| `pnpm --dir src/frontend install --frozen-lockfile --offline` | 通过，锁文件无需修改 |
| `uv sync --project src/backend --frozen` | 111 个含开发依赖的包安装成功 |
| `uv pip check --python src/backend/.venv/bin/python` | 111 个已安装包兼容 |
| `python3 scripts/check_backend_lock.py` | pyproject、uv.lock、两层 requirements 一致 |
| `python3 scripts/referral_contracts.py --write` 后 `--check` | OpenAPI、JSON Schema、TypeScript 确定且匹配 |
| `PYTHON_DOTENV_DISABLED=1 DATABASE_URL=sqlite:///:memory: src/backend/.venv/bin/python -m pytest -q src/backend/tests/referral_review src/backend/test_database_deployment.py` | **39 passed / 4 skipped**；37 项新基础测试 + 2 项旧 SQLite 回归；4 项旧 PostgreSQL 测试因没有 TEST_DATABASE_URL 跳过 |
| `python3 scripts/test_deploy_workflow.py` | **10 passed**；纯 mock 发布／回退流程，不改变线上 |
| `pnpm --dir src/frontend test --runInBand` | **4 suites / 17 tests passed** |
| `pnpm --dir src/frontend lint` | **0 errors / 28 warnings**，警告来自保留的旧聊天／历史页面等代码 |
| `NEXT_TELEMETRY_DISABLED=1 pnpm --dir src/frontend build` | 通过，6 个路由，含动态 `/chat/[id]` |
| `pnpm --dir src/frontend typecheck` | 通过 |
| `git diff --check` | 通过 |

CI 定义为 `.github/workflows/referral-foundation.yml`，涵盖同样的冻结安装、契约漂移、测试、构建与生产依赖审计。本次在本地执行对应命令，未推送，因此没有远程 Actions 运行记录。

### 失败路径

- 配置矩阵验证未知 RR 开关、开发 grant、生产降级、不安全 OAuth origin/callback、Stripe live key、负预算、非法 UUID 均拒绝且不泄露值。
- 默认配置不要求任何服务密钥；三种模式不会自动启用真实执行，删除任一真实配置前置项均拒绝预检。真实配置齐全也不提供 execute 接口。
- 在 development 和 production 两种配置下，伪造身份头不赋权；dev/grant 返回 404。
- 请求 ID 由服务端生成，忽略客户端伪造值；422 与 500 都不回显原始输入。异常在新模块 middleware 捕获，不再交由 ASGI server 生成含 provider 错误内容的 traceback。
- 生成工具测试在临时目录连续生成并逐字节比较；分别手工改变 OpenAPI、JSON Schema、TS 的内容后，`--check` 均退出 1，CI 使用同一检查命令。
- UUID、时区归一 UTC、非 BMP Unicode code-point span、重复 ID、缺失引用和多余字段有确定性校验；实际源页切片／hash 验证属于 MT-06。

## 体积记录

本机最后一次成功 Webpack build 后执行 `du -sk`，单位 KiB，文件系统占用而非 gzip 网络传输体积：

| 目录 | 大小 KiB | 含义 |
| --- | ---: | --- |
| `src/frontend/.next` | 100848 | 含本地构建缓存，不等于部署包 |
| `src/frontend/.next/server` | 1276 | 生成的服务端内容，不包含所有 traced 外部依赖 |
| `src/frontend/.next/static` | 1068 | 构建静态资产 |
| `src/backend/.venv/lib/python3.12/site-packages` | 160580 | macOS 环境全部依赖，含测试／审计工具，不等于 Linux 生产包 |

`.vercelignore` 排除 venv、.venv、uv 缓存及测试目录。实际 Vercel 函数打包大小、冷启动和请求时限仍需在 MT-24 的目标环境记录，不能用这些本地数值代替部署验收。

## 依赖审计与风险处置

2026-10-20，pnpm 10.34.7 / pip-audit 2.10.1 的在线数据库结果：

- `pnpm --dir src/frontend audit --prod --json --registry=https://registry.npmjs.org`：94 个依赖，已知漏洞 0。
- `src/backend/.venv/bin/pip-audit -r src/backend/requirements.txt --no-deps --disable-pip --format=json`：运行依赖已知漏洞 0；输入来自带 hash 的完整冻结 requirements，不审计未锁定的任意版本。
- 前端包含开发工具的全量审计：573 个依赖，剩余 **1 high / 1 moderate**，不能宣称全仓零漏洞。

已修复 source-map-js 1.2.1 → 1.2.2，以及开发间接依赖 js-yaml、brace-expansion、postcss-selector-parser；补丁约束集中在 pnpm-workspace.yaml，重跑 build／test／lint 验证。对 selector parser 的跨主版本约束仅用于现有 Tailwind 3 工具链兼容，未来升级 Tailwind 时应重新审查并移除不再必要的 override。

剩余条目及处置：

| 条目 | 当前可达范围与限制 | 后续检查 |
| --- | --- | --- |
| braces 3.0.3，high，[GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm) | 上游暂无补丁；由 Next lint plugin／Tailwind 的 glob 工具引入。仅处理仓库构建配置，不接收 HTTP 用户输入。不要将未信任输入传入构建 glob | MT-22/24 重审；有上游修复即升级 |
| sprintf-js 1.0.3，moderate，[GHSA-hp3w-g68c-fv3c](https://github.com/advisories/GHSA-hp3w-g68c-fv3c) | 上游暂无补丁；只在 Jest coverage 的 YAML CLI 配置链中。不要用用户输入构造格式串 | MT-22/24 重审测试工具链 |

`pnpm why braces sprintf-js` 确认均为 devDependencies；检索 `.next/**/*.nft.json` 未发现二者。基于该依赖链和当前应用代码，判断它们不在当前生产请求路径中；这是当前版本的可达性判断，不是对依赖本身安全性的保证。CI 保留生产依赖高危阻断，不忽略这两个 advisory。全量开发审计仍会非零退出，发布前按 QUALITY 的供应链门槛重新评估。

## 残余范围

新模块 readiness 有意返回 503，数据库／迁移／清单尚未实现；无密钥提供的是 bundled_demo 模式声明，完整合成示例与界面分别在 MT-03/16。现有旧聊天仍受旧配置控制，REAL_AI_ENABLED 不约束旧入口，MT-21 必须先退役它们才能宣称新产品费用控制覆盖全站。

Starlette 的旧 httpx TestClient 兼容路径及历史 SQLAlchemy／Pydantic／startup API 存在弃用警告；当前锁定版本测试通过，后续更新依赖必须重新验收。浏览器视觉回归与真实供应商往返未执行，分别归属 MT-22／24。现有 `TASK-PREVISIT-SUMMARY.md` 未改动。本次未 Git commit、push 或部署。
