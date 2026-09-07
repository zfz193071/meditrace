# MediTrace 后端 Render 部署指南

## 📋 当前状态

- **前端域名**: `meditrace.baozaolaoba.top` (Vercel)
- **后端域名**: 待部署到 Render
- **预设后端 URL**: `https://meditrace-backend.onrender.com`

---

## 🚀 部署步骤

### 第一步：准备部署

1. **确保代码已推送到 GitHub**
   ```bash
   cd /Users/zhuwenfang/a-working/meditrace
   git add .
   git commit -m "Prepare for Render deployment"
   git push origin main
   ```

2. **确认 `render.yaml` 文件存在**
   - 位置：项目根目录 `render.yaml`
   - 已配置好后端服务

---

### 第二步：在 Render 创建后端服务

1. **访问 Render Dashboard**
   - https://render.com/dashboard
   - 登录你的账户

2. **创建新的 Web Service**
   - 点击 **"New +"** → **"Web Service"**
   - 选择 **"Connect a repository"**
   - 选择你的 `meditrace` GitHub 仓库

3. **配置服务**

   | 配置项 | 值 |
   |--------|-----|
   | Name | `meditrace-backend` |
   | Region | Oregon (或亚洲最近的) |
   | Branch | `main` |
   | Root Directory | (留空，或填 `src/backend` 如果代码在那) |
   | Runtime | `Python` |
   | Build Command | `pip install -r src/backend/requirements.txt` |
   | Start Command | `cd src/backend && uvicorn main:app --host 0.0.0.0 --port $PORT` |
   | Plan | **Free** (免费套餐) |

4. **设置环境变量**

   在 "Environment Variables" 部分添加：

   | Key | Value |
   |-----|-------|
   | `DATABASE_URL` | `sqlite:///./meditrace.db` |
   | `DEEPSEEK_API_KEY` | `sk-f15ba6fc66f34a4c9c0dcaf664f2e94a` |
   | `USE_SEPOLIA` | `true` |
   | `SEPOLIA_RPC_URL` | `https://ethereum-sepolia-rpc.publicnode.com` |
   | `CONTRACT_ADDRESS_SEPOLIA` | `0x860418e7713A346c829Bc539C93c7A2d576897C5` |
   | `PINATA_API_KEY` | `99608ce2692e0a266838` |
   | `PINATA_SECRET_API_KEY` | `b9ac92a982ffab8128a6fcc39c7eecb505525c47ca280f53795cc1a897f37237` |
   | `PINATA_JWT_TOKEN` | `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySW5mb3JtYXRpb24iOnsiaWQiOiIwYWI4MzIxNi1mNDllLTQ0MjYtODZjYi01MTViMTA1NjI5M2UiLCJlbWFpbCI6InpmezE5MzA3MUBvdXRsb29rLmNvbSIsImVtYWlsX3ZlcmlmaWVkIjp0cnVlLCJwaW5fcG9saWN5Ijp7InJlZ2lvbnMiOlt7ImRlc2lyZWRSZXBsaWNhdGlvbkNvdW50IjoxLCJpZCI6IkZSQTEifSx7ImRlc2lyZWRSZXBsaWNhdGlvbkNvdW50IjoxLCJpZCI6Ik5ZQzEifV0sInZlcnNpb24iOjF9LCJtZmFfZW5hYmxlZCI6ZmFsc2UsInN0YXR1cyI6IkFDVElWRSJ9LCJhdXRoZW50aWNhdGlvblR5cGUiOiJzY29wZWRLZXkiLCJzY29wZWRLZXlLZXkiOiI5OTYwOGNlMjY5MmUwYTI2NjgzOCIsInNjb3BlZEtleVNlY3JldCI6ImI5YWM5MmE5ODJmZmFiODEyOGE2ZmNjMzljN2VlY2I1MDU1MjVjNDdjYTI4MGY1Mzc5NWNjMWE4OTdmMzcyMzciLCJleHAiOjE4MTkyNjU2MzJ9.22PpCU922FH60soj9k7BLXyoPMGmuZMc1L1HqXYSv8E` |
   | `CORS_ORIGINS` | `https://meditrace.baozaolaoba.top,https://meditrace.vercel.app,http://localhost:3000` |
   | `PYTHON_VERSION` | `3.11.0` |

   ⚠️ **注意**: 复制粘贴时注意：
   - 不要有多余的空格或换行
   - 确保所有特殊字符正确转义

5. **点击 "Create Web Service"**

---

### 第三步：等待部署完成

1. **监控部署日志**
   - Render 会自动开始构建和部署
   - 预计时间：3-5 分钟

2. **检查部署状态**
   - ✅ **Live** = 部署成功
   - ❌ **Error** = 查看日志排查问题

---

### 第四步：验证后端服务

1. **获取后端 URL**
   - Render 会分配一个域名：`https://meditrace-backend.onrender.com`
   - 在 Dashboard 顶部可以看到

2. **测试后端 API**
   - 访问：`https://meditrace-backend.onrender.com/docs`
   - 应该看到 Swagger API 文档

3. **测试健康检查**
   ```bash
   curl https://meditrace-backend.onrender.com/api/health
   ```

---

### 第五步：更新前端配置

部署成功后，确认以下配置：

1. **检查 `src/frontend/.env.production`**
   ```bash
   NEXT_PUBLIC_BACKEND_URL=https://meditrace-backend.onrender.com
   ```

2. **如果 Render 给你的域名不同**, 更新为实际的域名

3. **重新部署 Vercel 前端**
   - 访问 Vercel Dashboard
   - 触发新的部署

---

## 🔧 故障排查

### 问题 1: 构建失败

**错误**: `pip install` 失败

**解决**:
1. 查看 Render 构建日志
2. 确认 `src/backend/requirements.txt` 存在且正确
3. 检查依赖名称是否拼写正确

### 问题 2: 启动失败

**错误**: `uvicorn` 无法启动

**解决**:
1. 查看 Render 运行日志
2. 确认 `src/backend/main.py` 存在
3. 确认 `app` 对象已正确导出
   ```python
   # main.py 末尾应该有
   if __name__ == "__main__":
       uvicorn.run(app, host="0.0.0.0", port=8000)
   ```

### 问题 3: CORS 错误

**错误**: 前端无法访问后端 API

**解决**:
1. 检查 `CORS_ORIGINS` 环境变量
2. 确保包含 `https://meditrace.baozaolaoba.top`
3. 重启 Render 服务使配置生效

### 问题 4: 服务休眠

**问题**: 免费套餐 15 分钟无活动后休眠

**影响**: 首次请求需要 30-60 秒冷启动

**解决**:
- 接受冷启动延迟
- 或升级到付费套餐 ($7/月)

---

## ✅ 部署完成检查清单

- [ ] Render 服务状态为 "Live"
- [ ] 访问 `https://meditrace-backend.onrender.com/docs` 成功
- [ ] API 健康检查通过
- [ ] `CORS_ORIGINS` 配置正确
- [ ] 所有环境变量已设置
- [ ] Vercel 前端已更新后端 URL
- [ ] 前端可以成功调用后端 API

---

## 📊 服务信息

| 项目 | 信息 |
|------|------|
| Render 服务名 | `meditrace-backend` |
| Render URL | `https://meditrace-backend.onrender.com` |
| 计划 | Free |
| 区域 | Oregon |
| 运行时 | Python 3.11.0 |
| 构建命令 | `pip install -r src/backend/requirements.txt` |
| 启动命令 | `cd src/backend && uvicorn main:app --host 0.0.0.0 --port $PORT` |

---

## 🔗 快速链接

- [Render Dashboard](https://dashboard.render.com)
- [Render 文档](https://render.com/docs)
- [免费套餐说明](https://render.com/pricing)

---

**部署完成后，你的完整架构将是**:

```
用户 → meditrace.baozaolaoba.top (Cloudflare + Vercel)
              ↓
         前端 (Next.js)
              ↓ (API 请求)
         /api/* → https://meditrace-backend.onrender.com/api/*
              ↓
         后端 (FastAPI)
              ↓
         DeepSeek AI + IPFS + Blockchain
```
