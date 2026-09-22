# MediTrace 前后端一键部署

更新日期：2026-09-22。

## 当前架构

- Vercel 项目：`meditrace`，使用 Hobby 免费套餐。
- 仓库根目录的 `vercel.json` 定义两个 Services：Next.js 前端和 FastAPI 后端。
- `/health`、`/api/*` 转发到后端，其余路径交给前端。
- 生产数据库使用 Neon PostgreSQL；Vercel 上必须配置 `DATABASE_URL`，不能依赖本地 SQLite。
- 生产域名：`https://meditrace.baozaolaoba.top`。

## 环境变量

密钥仅放在 Vercel 项目的 Production 环境变量中，勿写进文档或提交到仓库。

| 变量 | 用途 |
| --- | --- |
| `DATABASE_URL` | 必需，Neon 的 PostgreSQL 连接字符串，启用 SSL；可使用 pooled 地址 |
| `NEXT_PUBLIC_BACKEND_URL` | 前端构建配置，当前为 `https://meditrace.baozaolaoba.top`，不要添加 `/api` 后缀 |
| `CORS_ORIGINS` | 允许访问后端的前端源地址，多个值用逗号分隔 |
| `USE_SEPOLIA` | 当前为 `true`，使用 Sepolia 测试网 |
| `SEPOLIA_RPC_URL` | Sepolia RPC 地址 |
| `CONTRACT_ADDRESS_SEPOLIA` | 已部署的合约地址 |
| `PINATA_API_KEY`、`PINATA_SECRET_API_KEY`、`PINATA_JWT_TOKEN` | IPFS 报告存储配置 |
| `SEPOLIA_PRIVATE_KEY` | 仅后端签名写链时需要；未配置时不能完成后端签名上链 |
| `DEEPSEEK_API_KEY` | 可选；当前生产环境未配置，诊断和对话使用代码中的演示回复 |

真实 AI 推理在 FastAPI 中执行。需要真实回复时才配置 `DEEPSEEK_API_KEY`，这会产生独立于 Vercel 的 API 费用。Vercel 和 Neon 免费套餐均有用量限制。

## 部署

在本项目中对助手说“部署”，会自动执行仓库根目录的可执行文件，同时发布前端和后端：

```bash
./deploy-vercel.sh
```

原 `./VERCEL-DEPLOYMENT-SCRIPT.sh` 也会转到同一个入口。脚本从自身位置定位仓库，可从任意目录调用。

流程：检查项目绑定、登录状态、Hobby 套餐、Production 数据库变量和上传文件；使用 `--prod --skip-domain` 构建两个服务；验证新部署后 promote 到现有域名；检查生产首页 HTML、`/health` 及带随机患者标记的会话列表 JSON。

临时 `vercel.app` 地址发生网络故障或访问保护拦截时，脚本会明确提示并改为切换后验证自定义域名。若新部署可访问但返回 HTTP 500 或错误响应，则停止，不切换生产。

切换后验证失败会尝试回退到运行前记录的版本，脚本仍以非零退出；如果检测到其他人已发布另一个版本，则不覆盖对方的发布。回退失败时停止并保留状态，供人工排查。

脚本复用 Vercel 已配置的环境变量，不自动覆盖密钥、不升级套餐、不提交或推送 Git，也不启动/停止本地服务。发布的是当前工作目录内容，包含未提交但未被忽略的修改。

### 只检查或验证

```bash
./deploy-vercel.sh --check   # 检查账号、项目及实际上传文件，不发布、不迁移
./deploy-vercel.sh --verify  # 只读验证当前线上前端、后端及数据库
./deploy-vercel.sh --help
```

首次在新机器使用时，需要安装 Vercel CLI 并完成 `vercel login`，然后执行
`vercel link --project meditrace --scope lucyzhus-projects --yes`。
脚本使用后端 venv 中的 Python（若存在），否则普通部署可使用 Python 3.9+。

项目 Root Directory 应为仓库根目录，Framework Preset 为 Services。不要只上传 `src/frontend`。
后端依赖由 `src/backend/requirements.txt` 提供，合约 ABI 位于 `src/backend/abi/DiagnosisRecord.json`，PDF 字体位于 `src/backend/fonts/`。

`.vercelignore` 排除密钥文件、虚拟环境、数据库文件、测试与内部文档，保留 README 和应用源码。

如果 Neon 最初创建的 `conversations` 只有 `id/title/created_at/updated_at`，需要先运行
`src/backend/migrations/002_vercel_schema_compatibility.sql`。它追加当前 API 需要的字段，
保留原表、UUID 主键、外键和旧时间字段；可重复执行。不要运行会 DROP TABLE 的旧开发迁移。

当前生产数据库已经完成该迁移，普通部署不再执行迁移。确实需要重复兼容迁移时：

```bash
./deploy-vercel.sh --migrate
```

该选项先执行唯一指定的 `002_vercel_schema_compatibility.sql`，然后部署。数据库地址取当前进程 `DATABASE_URL`，其次取 `src/backend/.env`；运行前应确认它指向待迁移数据库。迁移需要后端 venv 和 requirements.txt 中的依赖。它不读取或覆盖 Vercel 的敏感变量，也不自动扫描执行其他 SQL 文件。应用回退不会撤销已完成的追加字段迁移。

### 日志与恢复

- 本次日志：`.vercel/deploy-YYYYMMDD-HHMMSS.log`。
- 最近发布状态、前后版本 ID：`.vercel/last-deploy.json`，`status: verified` 才表示发布且验证通过。
- 同一检出中的部署/检查使用进程锁，避免两个脚本同时操作。
- 如需人工回退：`vercel rollback <last-deploy.json 中的 previous_id> --yes --scope lucyzhus-projects`，随后运行 `./deploy-vercel.sh --verify`。
- 登录失效、套餐不符或配置缺失时脚本会停止并说明原因；不会无限重试部署。

## 验证

```bash
curl --fail https://meditrace.baozaolaoba.top/health
curl --fail 'https://meditrace.baozaolaoba.top/api/conversations?patientId=deployment-check'
```

健康检查应返回 `{"status":"healthy","version":"0.1.0"}`；会话列表应返回 JSON。

数据库回归测试不发起 AI 请求，也不需要启动本地服务：

```bash
DATABASE_URL=sqlite:///:memory: src/backend/venv/bin/python -m pytest src/backend/test_database_deployment.py -q
```

设置 `TEST_DATABASE_URL` 可同时验证真实 PostgreSQL。测试在随机独立 schema 中运行，结束后只删除该测试 schema；Neon 测试连接使用 unpooled 地址来设置 `search_path`，应用仍使用 pooled 地址。
测试包含新建表和旧 Neon 表迁移后两种 PostgreSQL 场景。

请手动在浏览器发送消息测试对话；禁止自动在浏览器触发 AI 回复。
部署脚本的验证仅发出 GET 请求，不创建业务记录，不调用 DeepSeek、IPFS 上传或区块链写入。

部署和回退流程的离线测试：`python3 scripts/test_deploy_workflow.py`。它模拟 Vercel 和 HTTP 响应，不产生真实发布。

## 故障记录

见 `BUGFIX-VERCEL-BACKEND-DEPLOYMENT.md`。查看日志时不要输出连接串或密钥。
