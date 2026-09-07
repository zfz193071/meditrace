# MediTrace 部署操作指南

## 📌 部署目标
- **域名**: https://meditrace.baozaolaoba.top
- **前端**: Vercel (Next.js)
- **后端**: Render (FastAPI)
- **模式**: 演示模式（模拟 AI 回复）
- **成本**: $0/月

---

## 🚀 第一步：在 Vercel 部署前端

### 1.1 访问 Vercel
打开 https://vercel.com/new

### 1.2 导入项目
1. 点击 "Continue with GitHub"
2. 授权访问您的 GitHub 账户
3. 在 "Import Project" 页面找到您的仓库，点击 "Import"

### 1.3 配置项目
**Framework Preset**: Next.js

**Root Directory**:
```
src/frontend
```

**Build and Output Settings**:
- Build Command: `pnpm build`
- Output Directory: `.next`
- Install Command: `pnpm install`

### 1.4 添加环境变量
点击 "Environment Variables"，添加以下内容：

| 变量名 | 值 |
|--------|-----|
| `NEXT_PUBLIC_BACKEND_URL` | `https://meditrace-backend.onrender.com` |
| `NEXT_PUBLIC_CONTRACT_ADDRESS` | `0x860418e7713A346c829Bc539C93c7A2d576897C5` |
| `NEXT_PUBLIC_RPC_URL` | `https://ethereum-sepolia-rpc.publicnode.com` |

### 1.5 部署
点击 "Deploy"，等待构建完成（约 2-5 分钟）

### 1.6 配置自定义域名
1. 部署完成后，进入项目 Dashboard
2. 点击 "Settings" → "Domains"
3. 点击 "Add"，输入：`meditrace.baozaolaoba.top`
4. 点击 "Add" 确认

---

## 🔧 第二步：在 Render 部署后端

### 2.1 访问 Render
打开 https://render.com/dashboard
- 如果没有账号，先点击 "Sign Up" 使用 GitHub 注册

### 2.2 创建 Web Service
1. 点击 "New +" → "Web Service"
2. 点击 "Connect a repository"，选择您的 GitHub 仓库
3. 配置服务：

**Name**: `meditrace-backend`

**Region**: Oregon (或选择离您最近的地区)

**Branch**: `main` (或您的主分支名)

**Root Directory**: (留空)

**Runtime**: `Python`

**Build Command**: 
```bash
pip install -r src/backend/requirements.txt
```

**Start Command**: 
```bash
cd src/backend && uvicorn main:app --host 0.0.0.0 --port $PORT
```

**Plan**: 选择 "Free"

### 2.3 添加环境变量
滚动到 "Environment Variables" 部分，添加以下内容：

| 键 | 值 | 说明 |
|----|-----|------|
| `USE_SEPOLIA` | `true` | 使用 Sepolia 测试网 |
| `SEPOLIA_RPC_URL` | `https://ethereum-sepolia-rpc.publicnode.com` | Sepolia RPC 地址 |
| `CONTRACT_ADDRESS_SEPOLIA` | `0x860418e7713A346c829Bc539C93c7A2d576897C5` | 合约地址 |
| `CORS_ORIGINS` | `https://meditrace.baozaolaoba.top,https://meditrace.vercel.app,http://localhost:3000` | 允许的前端域名 |
| `DATABASE_URL` | `sqlite:///./meditrace.db` | SQLite 数据库 |
| `PINATA_API_KEY` | 您的 Pinata API Key | **必需** - IPFS 存储功能 |
| `PINATA_SECRET_API_KEY` | 您的 Pinata Secret API Key | **必需** - IPFS 存储功能 |
| `PINATA_JWT_TOKEN` | 您的 Pinata JWT Token | **必需** - IPFS 存储功能 |

**⚠️ 演示模式：以下环境变量可以不设置**

| 键 | 说明 |
|----|------|
| `DEEPSEEK_API_KEY` | **不设置** = 演示模式（模拟 AI 回复，免费）<br>**设置后** = 真实 AI 功能（消耗 API token） |

**演示模式说明**：
- ✅ 不需要 DeepSeek API Key，后端会自动使用模拟回复
- ✅ AI 对话功能完全可用（返回模拟的医疗建议）
- ✅ 所有前端界面功能正常
- ✅ IPFS 存储功能正常（需要 Pinata API Key）
- ✅ 区块链溯源功能正常
| `CORS_ORIGINS` | `https://meditrace.baozaolaoba.top,https://meditrace.vercel.app,http://localhost:3000` |
| `DATABASE_URL` | `sqlite:///./meditrace.db` |

### 2.4 部署
点击 "Create Web Service"，等待构建完成（约 3-10 分钟）

### 2.5 获取后端 URL
部署完成后，Render 会分配一个 URL，格式类似：
```
https://meditrace-backend.onrender.com
```

**重要**: 将这个 URL 更新到 Vercel 的环境变量 `NEXT_PUBLIC_BACKEND_URL` 中

---

## 🌐 第三步：配置 Cloudflare DNS

### 3.1 登录 Cloudflare
打开 https://dash.cloudflare.com/sign-in

### 3.2 添加 DNS 记录
1. 选择您的域名 `baozaolaoba.top`
2. 点击 "DNS" → "Records"
3. 点击 "Add record"，添加：

**类型**: `CNAME`

**名称**: `meditrace`

**目标**: `<您的 Vercel 域名>` (例如：meditrace-project.vercel.app)

**TTL**: Auto

**代理状态**: 🟡 Proxied (已代理)

### 3.3 等待 DNS 生效
DNS 传播通常需要几分钟到几小时

---

## ✅ 第四步：验证部署

### 4.1 检查后端健康
访问：`https://meditrace-backend.onrender.com/docs`
- 应该看到 FastAPI 的 Swagger 文档

### 4.2 检查前端
访问：`https://meditrace.baozaolaoba.top`
- 应该看到 MediTrace 前端界面

### 4.3 测试功能
1. 尝试创建新的对话
2. 发送消息测试 AI 响应
3. 检查区块链功能是否正常

---

## 🔍 常见问题

### Q1: Vercel 构建失败
**问题**: `pnpm: command not found`

**解决**: 在 Vercel Dashboard → Settings → General → Build & Development Settings
- 设置 "Install Command": `npm i -g pnpm && pnpm install`

### Q2: 后端启动失败
**问题**: `ModuleNotFoundError: No module named 'xxx'`

**解决**: 检查 `src/backend/requirements.txt` 是否包含所有依赖

### Q3: CORS 错误
**问题**: 前端无法访问后端 API

**解决**: 
1. 检查 Render 环境变量 `CORS_ORIGINS` 是否包含前端域名
2. 确保 Vercel 的 `NEXT_PUBLIC_BACKEND_URL` 正确

### Q4: 后端休眠（免费套餐）
**问题**: 首次请求需要 30-60 秒

**解决**: 
- 免费套餐的服务会在 15 分钟无活动后休眠
- 可以使用 Render 的免费监控服务保持服务活跃
- 或升级到付费套餐（$7/月）

---

## 📊 部署后配置

### 更新后端 URL
如果 Render 分配的后端 URL 不是 `https://meditrace-backend.onrender.com`，需要：

1. 在 Vercel Dashboard → Settings → Environment Variables
2. 更新 `NEXT_PUBLIC_BACKEND_URL` 为实际的 Render URL
3. 重新部署：Vercel 会自动触发重新部署

### 更新后端 CORS
如果前端域名不是预期的：

1. 在 Render Dashboard → Settings → Environment Variables
2. 更新 `CORS_ORIGINS` 包含实际的前端域名
3. 重启服务：Deploy → Redeploy

---

## 💰 成本总结

| 服务 | 平台 | 计划 | 成本 |
|------|------|------|------|
| 前端 | Vercel | Hobby | $0/月 |
| 后端 | Render | Free | $0/月 |
| DNS | Cloudflare | Free | $0/月 |
| **总计** | | | **$0/月** |

---

## 📝 检查清单

部署前：
- [x] 代码已推送到 GitHub
- [x] `render.yaml` 文件存在
- [x] `src/frontend/.env.production` 配置正确
- [ ] **准备好 Pinata API Key**（必需 - IPFS 功能）
- [ ] 如需真实 AI：准备好 DeepSeek API Key（可选）

部署中：
- [ ] Vercel 项目创建成功
- [ ] Render 服务创建成功
- [ ] 环境变量已设置（包含 Pinata API Keys）
- [ ] Cloudflare DNS 记录已添加

部署后：
- [ ] 后端健康检查通过
- [ ] 前端可以正常访问
- [ ] AI 对话功能正常（演示模式返回模拟回复）
- [ ] IPFS 存储功能正常（需要 Pinata）
- [ ] 区块链功能正常

---

## 🆘 需要帮助？

如果遇到问题：
1. 查看 Vercel/Render 的部署日志
2. 检查环境变量是否正确
3. 确认 CORS 配置
4. 查看后端 `/docs` 接口是否可用

祝您部署成功！🎉
