# MediTrace Vercel + Render 部署指南

## 📋 部署架构

```
用户 → meditrace.baozaolaoba.top (Cloudflare CDN)
              ↓
    ┌──────────────────────┐
    │   前端：Vercel       │
    │   Next.js + React    │
    │   免费套餐           │
    └──────────┬───────────┘
               │ API 调用
               ↓
    ┌──────────────────────┐
    │   后端：Render       │
    │   FastAPI + Python   │
    │   免费套餐           │
    └──────────┬───────────┘
               │
               ↓
    ┌──────────────────────┐
    │   SQLite 数据库      │
    │   (Render 文件系统)  │
    └──────────────────────┘
```

## 🎯 成本

- **前端 (Vercel)**: 免费
- **后端 (Render)**: 免费
- **域名 (Cloudflare)**: 免费
- **总成本**: **$0/月** ⭐

---

## 🚀 部署步骤

### 第一步：部署后端到 Render

#### 1.1 创建 Render 账户

1. 访问 https://render.com
2. 点击 "Get Started for Free"
3. 使用 GitHub 账户登录

#### 1.2 创建 Web Service

1. 在 Dashboard 点击 **"New +"** → **"Web Service"**
2. 连接 GitHub 仓库：
   - 选择 `meditrace` 仓库
   - 选择分支（如 `main` 或 `master`）

#### 1.3 配置服务

| 配置项 | 值 |
|--------|-----|
| **Name** | `meditrace-backend` |
| **Region** | Oregon (美国西海岸) |
| **Branch** | main |
| **Root Directory** | (留空) |
| **Build Command** | `pip install -r src/backend/requirements.txt` |
| **Start Command** | `cd src/backend && uvicorn main:app --host 0.0.0.0 --port $PORT` |
| **Plan** | Free |

#### 1.4 设置环境变量

在 Render Dashboard 的 **Environment** 标签页添加以下变量：

```bash
# DeepSeek API (必需)
DEEPSEEK_API_KEY=sk-xxx

# Ethereum Sepolia 配置
USE_SEPOLIA=true
SEPOLIA_RPC_URL=https://ethereum-sepolia-rpc.publicnode.com
CONTRACT_ADDRESS_SEPOLIA=0x860418e7713A346c829Bc539C93c7A2d576897C5

# IPFS Pinata 配置 (必需)
PINATA_API_KEY=99608ce2692e0a266838
PINATA_SECRET_API_KEY=b9ac92a982ffab8128a6fcc39c7eecb505525c47ca280f53795cc1a897f37237
PINATA_JWT_TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# CORS 配置
CORS_ORIGINS=https://meditrace.baozaolaoba.top,https://meditrace.vercel.app,http://localhost:3000

# 其他配置
PYTHON_VERSION=3.11.0
DATABASE_URL=sqlite:///./meditrace.db
```

⚠️ **重要**: 将 `PINATA_JWT_TOKEN` 替换为你实际的 JWT 令牌（完整的长字符串）

#### 1.5 创建服务

点击 **"Create Web Service"**，Render 将开始构建和部署。

首次部署需要 3-5 分钟。

#### 1.6 获取后端 URL

部署完成后，Render 会分配一个自动域名：
```
https://meditrace-backend.onrender.com
```

记录这个 URL，后续前端配置需要用到。

---

### 第二步：部署前端到 Vercel

#### 2.1 创建 Vercel 账户

1. 访问 https://vercel.com
2. 点击 "Sign Up"
3. 使用 GitHub 账户登录

#### 2.2 导入项目

1. 在 Vercel Dashboard 点击 **"Add New..."** → **"Project"**
2. 导入 GitHub 仓库：
   - 选择 `meditrace` 仓库
   - 点击 "Import"

#### 2.3 配置项目

| 配置项 | 值 |
|--------|-----|
| **Framework Preset** | Next.js |
| **Root Directory** | `src/frontend` |
| **Build Command** | `pnpm build` |
| **Output Directory** | `.next` |

#### 2.4 设置环境变量

在 Vercel Dashboard 的 **Settings** → **Environment Variables** 添加：

```bash
NEXT_PUBLIC_BACKEND_URL=https://meditrace-backend.onrender.com
NEXT_PUBLIC_CONTRACT_ADDRESS=0x860418e7713A346c829Bc539C93c7A2d576897C5
NEXT_PUBLIC_RPC_URL=https://ethereum-sepolia-rpc.publicnode.com
```

⚠️ **重要**: 需要为所有环境（Production, Preview, Development）添加这些变量

#### 2.5 部署

点击 **"Deploy"**，Vercel 将开始构建和部署。

首次部署需要 2-3 分钟。

#### 2.6 获取前端 URL

部署完成后，Vercel 会分配一个自动域名：
```
https://meditrace-frontend.vercel.app
```

---

### 第三步：配置自定义域名

#### 3.1 在 Vercel 添加域名

1. 进入 Vercel 项目 Dashboard
2. 点击 **Settings** → **Domains**
3. 点击 **"Add"**
4. 输入域名：`meditrace.baozaolaoba.top`
5. 点击 **"Add"**

#### 3.2 在 Cloudflare 配置 DNS

1. 登录 Cloudflare Dashboard: https://dash.cloudflare.com
2. 选择域名 `baozaolaoba.top`
3. 点击 **DNS** → **Records**
4. 点击 **"Add record"**

添加 CNAME 记录：

| 类型 | 名称 | 内容 | TTL | 代理状态 |
|------|------|------|-----|----------|
| CNAME | meditrace | meditrace.vercel.app | Auto | 🟡 已代理 |

⚠️ **重要**: 确保代理状态为"已代理"（橙色云），这样 Cloudflare 会提供 SSL 证书和 CDN 加速

#### 3.3 验证域名

1. 回到 Vercel Dashboard
2. 在 Domains 页面等待 DNS 验证
3. Vercel 会自动检查 DNS 配置
4. 验证通过后，域名状态变为 **"Ready"**

---

### 第四步：更新后端 CORS 配置

确保 Render 后端允许自定义域名访问：

在 Render Dashboard 的 **Environment** 变量中，确认 `CORS_ORIGINS` 包含：

```bash
CORS_ORIGINS=https://meditrace.baozaolaoba.top,https://meditrace.vercel.app,http://localhost:3000
```

---

## ✅ 部署检查清单

### 后端 (Render)

- [ ] Render 账户已创建
- [ ] Web Service 创建成功
- [ ] 构建命令正确：`pip install -r src/backend/requirements.txt`
- [ ] 启动命令正确：`cd src/backend && uvicorn main:app --host 0.0.0.0 --port $PORT`
- [ ] 所有环境变量已设置
- [ ] 健康检查通过：访问 `https://meditrace-backend.onrender.com/docs`
- [ ] 后端 API 可访问：测试 `https://meditrace-backend.onrender.com/api/health`

### 前端 (Vercel)

- [ ] Vercel 账户已创建
- [ ] 项目导入成功
- [ ] Root Directory 设置为 `src/frontend`
- [ ] 环境变量已设置
- [ ] 构建成功
- [ ] 前端页面可访问

### 域名配置

- [ ] Vercel 域名添加成功
- [ ] Cloudflare DNS 记录已添加
- [ ] DNS 验证通过
- [ ] SSL 证书自动获取（Cloudflare）
- [ ] 访问 `https://meditrace.baozaolaoba.top` 正常

### 功能测试

- [ ] 页面加载正常
- [ ] API 调用成功（检查浏览器 Network）
- [ ] 对话功能正常
- [ ] 区块链功能正常
- [ ] IPFS 上传/下载正常

---

## 🔧 常见问题

### 1. Render 后端休眠

**问题**: 免费套餐的服务在 15 分钟无活动后会休眠，下次请求需要 30-60 秒冷启动

**解决方案**:
- 接受冷启动延迟（免费套餐的限制）
- 或使用付费套餐（$7/月）避免休眠
- 或使用第三方监控服务定期 ping 后端保持活跃

### 2. CORS 错误

**问题**: 前端访问后端时报 CORS 错误

**解决方案**:
```bash
# 确保后端环境变量包含所有域名
CORS_ORIGINS=https://meditrace.baozaolaoba.top,https://meditrace.vercel.app,http://localhost:3000
```

### 3. 数据库连接错误

**问题**: SQLite 数据库无法连接

**解决方案**:
- Render 的文件系统是持久化的，SQLite 数据库会保存在 `./meditrace.db`
- 确保启动命令中的相对路径正确
- 检查数据库文件是否已提交到 Git（建议添加到 `.gitignore`，首次部署会自动创建）

### 4. API Key 泄露

**问题**: 敏感信息可能泄露

**解决方案**:
- 确保所有 API Key 都通过环境变量设置
- 不要将 `.env` 文件提交到 Git
- 在 Render/Vercel Dashboard 设置敏感变量

### 5. 构建失败

**问题**: Vercel 或 Render 构建失败

**解决方案**:
- 检查 `package.json` 和 `requirements.txt` 是否正确
- 查看构建日志定位错误
- 确保所有依赖都已安装

---

## 📊 监控和维护

### Render 监控

- 访问 https://render.com/dashboard
- 查看服务状态和日志
- 设置告警通知

### Vercel 监控

- 访问 https://vercel.com/dashboard
- 查看分析数据和日志
- 设置告警通知

### 日志查看

**Render 后端日志**:
```bash
# 在 Render Dashboard 点击 "Logs" 标签页
# 或使用 Render CLI
render logs -f meditrace-backend
```

**Vercel 前端日志**:
```bash
# 在 Vercel Dashboard 点击 "Logs" 标签页
# 或使用 Vercel CLI
vercel logs
```

---

## 🔄 更新部署

### 自动部署

配置好后，每次推送到 GitHub 主分支都会自动触发部署：

- **前端**: 推送到 GitHub → Vercel 自动构建部署
- **后端**: 推送到 GitHub → Render 自动构建部署

### 手动部署

**Render 后端**:
```bash
# 在 Render Dashboard 点击 "Manual Deploy" → "Deploy Latest Commit"
```

**Vercel 前端**:
```bash
# 在 Vercel Dashboard 点击 "Redeploy"
# 或使用 Vercel CLI
vercel --prod
```

---

## 📞 技术支持

- **Vercel 文档**: https://vercel.com/docs
- **Render 文档**: https://render.com/docs
- **Next.js 部署**: https://nextjs.org/docs/deployment
- **FastAPI 部署**: https://fastapi.tiangolo.com/deployment/

---

## 🎉 部署完成

恭喜你！MediTrace 项目已成功部署到生产环境。

访问：https://meditrace.baozaolaoba.top

享受你的免费部署！🚀
