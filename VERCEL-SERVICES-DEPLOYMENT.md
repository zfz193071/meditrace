# Vercel 全栈部署指南（Vercel Services 架构）

> 修复日期：2026-09-16
> 适用架构：**一个 Vercel 项目同时部署 Next.js 前端 + Python FastAPI 后端**

---

## 1. 问题现象与根因

### 现象
线上 `https://meditrace.baozaolaoba.top/api/health` 返回的是 **Next.js 的 404 HTML 页面**，
证明 `/api/*` 请求根本没有到达 Python 后端——**后端从未被部署**。

### 根因（三条，互相叠加）

| # | 问题 | 证据 |
|---|------|------|
| 1 | 前端实际调用的后端是 `https://meditrace-backend.onrender.com`，**该 Render 服务已不存在** | 线上打包产物 `/_next/static/chunks/app/page-*.js` 中字面量即为该域名；`curl` 该域名返回 `404 Not Found` |
| 2 | 仓库根目录的 `api/[[...route]]/index.py` **写法完全不成立** | ① `[[...route]]` 是 Next.js App Router 的 catch-all 命名约定，对 Vercel Python 函数无效；② 结尾 `export = handler` 是无效导出（Vercel Python 需要导出 ASGI 对象 `app`）；③ `from vercel.asgi import VercelASGI` 依赖的 `vercel` PyPI 包并非受支持的适配方式 |
| 3 | 前端聊天页硬编码 `http://localhost:8000` | `app/chat/page.tsx`、`app/chat/[id]/page.tsx` 共 4 处，生产环境必然失败 |

### 结论
原架构（见已删除的 `DEPLOYMENT-VERCEL-RENDER.md`）是 **Vercel 前端 + Render 后端**；
Render 后端下线后，前端指向了一个不存在的地址，因此表现为"只部署了前端"。

---

## 2. 采用的方案：Vercel Services

Vercel Services 允许**在同一个项目、同一域名下**分别构建多个服务，正是本项目的官方支持路径：

> "A Next.js frontend at `/` + A Python FastAPI backend at `/api`"
> — [The Complete Guide to Vercel Services](https://vercel.com/kb/guide/vercel-services)

- 可用性：**Beta，所有套餐（含 Hobby）均可用**
- 配置键名：**`services`**（依据官方 JSON Schema：`experimentalServicesV2` 的描述为 *"Deprecated alias for services"*）
- 参考资料：
  - [Vercel Services 指南](https://vercel.com/kb/guide/vercel-services)
  - [Experimental Services 文档](https://vercel.com/docs/services/experimental)
  - [Python Functions in the /api Directory](https://vercel.com/docs/functions/runtimes/python/api-directory)

### 最终 `vercel.json`

```json
{
  "services": {
    "frontend": { "root": "src/frontend/", "framework": "nextjs" },
    "backend": {
      "root": "src/backend/",
      "framework": "fastapi",
      "entrypoint": "main:app"
    }
  },
  "rewrites": [
    { "source": "/health",       "destination": { "service": "backend" } },
    { "source": "/api/(.*)",     "destination": { "service": "backend" } },
    { "source": "/(.*)",         "destination": { "service": "frontend" } }
  ]
}
```

**路由规则**：服务收到的是**原始路径**。`/api/conversations` 会以 `/api/conversations`
到达后端，与 `src/backend/main.py` 中已有的 `/api/...` 路由完全对应，**后端代码无需改动**。

---

## 3. 已完成的代码改动

| 文件 | 改动 |
|------|------|
| `vercel.json` | 重写为 `services` + `rewrites`；移除顶层 `framework`/`buildCommand`/`outputDirectory`（services 模式下这些字段非法，必须下放到各 service） |
| `api/[[...route]]/index.py` | **已删除**（整个 `api/` 目录），其写法不成立，由 Services 取代 |
| `.vercelignore` | 重写：确保 `src/backend/` Python 源码**不被排除**；排除 `venv/`、`__pycache__/`、`*.db`、`.env` 等 |
| `src/frontend/lib/backend.ts` | **新增**：统一后端地址解析入口 |
| `src/frontend/.env.production` | 修正 `NEXT_PUBLIC_BACKEND_URL=/api` → 生产站点源地址（原值会拼成 `/api/api/xxx`） |
| `src/frontend/lib/api.ts` | 改用 `lib/backend.ts` |
| `src/frontend/app/page.tsx`<br>`app/verify/page.tsx`<br>`app/history/page.tsx` | 改用 `BACKEND_URL`，去掉内联的 `process.env` 拼接 |
| `src/frontend/app/chat/page.tsx`<br>`app/chat/[id]/page.tsx` | **修复硬编码 `localhost:8000`**（4 处），改用 `BACKEND_URL` |

### `lib/backend.ts` 的取值规则

代码统一按 `源地址 + /api/xxx` 拼接，因此 `NEXT_PUBLIC_BACKEND_URL` 必须是**源地址**，
不能带 `/api` 后缀（否则会拼成 `/api/api/xxx`）：

| 环境 | `NEXT_PUBLIC_BACKEND_URL` | 实际请求 |
|------|---------------------------|----------|
| 生产（推荐） | `https://meditrace.baozaolaoba.top` | 同域名绝对地址 |
| 生产（未设置） | — | `/api/xxx`（相对路径，同域名） |
| 本地开发（未设置） | — | `http://localhost:8000/api/xxx` |

---

## 4. ⚠️ 必须手动完成的 Vercel 控制台配置

代码改完**还不能直接生效**，以下 3 项必须在 Vercel 控制台手动设置：

### 4.1 项目 Root Directory 必须改为仓库根目录

**Settings → General → Root Directory → 清空（留空 = 仓库根目录）**

> 原因：目前构建上下文疑似被设为 `src/frontend`（构建日志"Downloading 61 deployment files"
> 与根目录无 `pnpm-lock.yaml` 但检测到 `pnpm-lock.yaml` 相矛盾）。
> 若 Root Directory 不是仓库根目录，则 `vercel.json`、`src/backend/` 都不会进入构建，
> services 配置无从生效。

### 4.2 Framework Preset 必须改为 Services

**Settings → Build and Development Settings → Framework Preset → 选择 `Services`**

同时确认 **Build Command / Output Directory / Install Command 均为空**（不覆盖），
services 模式下这些字段由各 service 自行拥有。

### 4.3 环境变量

**Settings → Environment Variables**

| 变量 | 值 | 说明 |
|------|-----|------|
| `NEXT_PUBLIC_BACKEND_URL` | `https://meditrace.baozaolaoba.top` | **当前值是指向已失效 Render 的地址，必须修改**。这是构建期内联值，改后必须重新部署 |
| `DATABASE_URL` | Neon PostgreSQL 连接串 | **必需**。缺失时后端回退到 SQLite，而 Serverless 文件系统只读且临时，数据不会留存 |
| `DEEPSEEK_API_KEY` | `sk-...` | **必需**。AI 推理在后端进行，缺失则诊断/对话接口不可用 |
| `PINATA_API_KEY` | — | IPFS 存证 |
| `PINATA_SECRET_API_KEY` | — | IPFS 存证 |
| `PINATA_JWT_TOKEN` | — | IPFS 存证 |
| `USE_SEPOLIA` | `true` | 链上存证开关 |
| `SEPOLIA_RPC_URL` | — | Sepolia RPC |
| `CONTRACT_ADDRESS_SEPOLIA` | `0x8604...` | 合约地址 |
| `SEPOLIA_PRIVATE_KEY` | — | 仅当后端需要写链时必需 |
| `CORS_ORIGINS` | `https://meditrace.baozaolaoba.top` | 同域名部署下非严格必需，建议保留 |

> ⚠️ `AGENTS.md` 中"生产环境不需要 `DEEPSEEK_API_KEY`"的说法**不成立**：
> AI 推理在 FastAPI 后端执行，必须配置该变量。

---

## 5. 部署与验证

```bash
# 提交并推送（Vercel 会自动触发部署）
git add -A
git commit -m "fix(deploy): 改用 Vercel Services 同时部署前端与 Python 后端"
git push
```

部署完成后验证：

```bash
# 1) 后端存活（新增的 /health 转发规则）
curl https://meditrace.baozaolaoba.top/health
# 期望: {"status":"healthy","version":"0.1.0"}

# 2) 后端 API 可达（路由需要真实 ID，404 也算"已到达后端"，关键看是否还是 Next.js HTML 404）
curl -i https://meditrace.baozaolaoba.top/api/history/test-user
# 期望: JSON 响应（不再是 <!DOCTYPE html> 的 Next.js 404）

# 3) 前端正常
curl -o /dev/null -w "%{http_code}\n" https://meditrace.baozaolaoba.top/
```

**判定标准**：只要 `/api/*` 返回 JSON 而非 Next.js 的 HTML 404，就说明后端已成功挂载。

---

## 6. 已知注意事项

1. **函数执行时长** — 配置中**故意没有**设置 `maxDuration`，使用套餐默认上限。
   ⚠️ `services.<name>` 下**不允许** `maxDuration` / `memory` 字段
   （schema 为 `additionalProperties: false`，写了会直接导致部署失败）。
   需要调高时，改用该 service 的 `functions` 块：

   ```json
   "backend": {
     "root": "src/backend/",
     "framework": "fastapi",
     "entrypoint": "main:app",
     "functions": { "**/*": { "maxDuration": 60 } }
   }
   ```

   AI 流式对话（`/api/conversations/{id}/messages/stream`，SSE）若被默认上限中断，按此调整。
2. **冷启动** — 依赖含 `web3`、`psycopg2-binary`，首次调用可能较慢。
3. **`NEXT_PUBLIC_*` 是构建期内联** — 修改后必须重新部署才能生效。
4. **数据库表结构** — Neon 中的表需已按 `src/backend/migrations/` 初始化。
5. **根目录 `requirements.txt` 已不再使用**（后端服务读取 `src/backend/requirements.txt`），
   其中 `vercel>=1.0.0` 为无效依赖，可安全删除。
6. `src/frontend/app/verify/page.tsx.bak` 为历史备份文件，未纳入版本控制，可删除。
7. **区域（regions）** — 原 `vercel.json` 的顶层 `regions: ["hkg1"]` 已移除。
   services 模式下顶层构建/运行字段受平台限制，本次优先保证部署成功；
   如平台接受，可再试加回以贴近香港节点（历史构建日志显示实际构建在 `iad1`）。
