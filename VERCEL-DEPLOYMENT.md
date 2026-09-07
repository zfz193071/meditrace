# MediTrace Vercel 部署指南

## 📊 Vercel 部署方案对比

### 方案 A: 前后端分离部署（推荐）

```
前端：Vercel (Next.js)
后端：Render / Railway / Fly.io (FastAPI)
域名：meditrace.baozaolaoba.top (Cloudflare)
```

**优点**:
- ✅ Vercel 对 Next.js 优化最好
- ✅ 后端独立服务，无 60 秒超时限制
- ✅ 两个平台都有免费套餐
- ✅ 架构清晰，易于维护

**缺点**:
- ⚠️ 需要配置两个部署平台
- ⚠️ 跨域配置（但 Cloudflare 可解决）

---

### 方案 B: 前后端都在 Vercel

```
前端：Vercel (Next.js)
后端：Vercel Serverless Functions (Python)
域名：meditrace.baozaolaoba.top
```

**优点**:
- ✅ 单一平台，简化部署
- ✅ 无需跨域配置
- ✅ 自动 HTTPS、CDN 加速

**缺点**:
- ❌ 函数超时 60 秒（AI 对话可能超时）
- ❌ 无持久化存储
- ❌ 冷启动延迟
- ❌ 不适合长时间运行的任务

---

## 🚀 方案 A: Vercel 前端 + Render 后端（推荐）

### 第一步：Vercel 部署前端

#### 1. 准备代码

确保 `src/frontend/.env.production` 配置正确：

```bash
# Vercel 前端配置
NEXT_PUBLIC_BACKEND_URL=https://meditrace-api.onrender.com
# 或您的后端地址
NEXT_PUBLIC_CONTRACT_ADDRESS=0x860418e7713A346c829Bc539C93c7A2d576897C5
NEXT_PUBLIC_RPC_URL=https://ethereum-sepolia-rpc.publicnode.com
```

#### 2. 在 Vercel 部署

```bash
# 安装 Vercel CLI
npm i -g vercel

# 登录 Vercel
vercel login

# 部署（在项目根目录）
vercel

# 生产部署
vercel --prod
```

**或使用 Vercel Dashboard**:
1. 访问 https://vercel.com/new
2. 导入 GitHub 仓库
3. 设置根目录：`src/frontend`
4. 添加环境变量：
   - `NEXT_PUBLIC_BACKEND_URL` = 后端地址
   - `NEXT_PUBLIC_CONTRACT_ADDRESS` = 合约地址
   - `NEXT_PUBLIC_RPC_URL` = RPC 地址
5. 点击 "Deploy"

#### 3. 自定义域名

在 Vercel Dashboard:
1. 进入项目 Settings → Domains
2. 添加域名：`meditrace.baozaolaoba.top`
3. 在 Cloudflare DNS 添加 CNAME 记录指向 Vercel

---

### 第二步：Render 部署后端

#### 1. 创建 `render.yaml`

在项目根目录：

```yaml
services:
  - type: web
    name: meditrace-backend
    env: python
    region: oregon
    plan: free
    buildCommand: pip install -r src/backend/requirements.txt
    startCommand: cd src/backend && uvicorn main:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: DEEPSEEK_API_KEY
        sync: false
      - key: USE_SEPOLIA
        value: true
      - key: SEPOLIA_RPC_URL
        value: https://ethereum-sepolia-rpc.publicnode.com
      - key: CONTRACT_ADDRESS_SEPOLIA
        value: 0x860418e7713A346c829Bc539C93c7A2d576897C5
      - key: PINATA_API_KEY
        sync: false
      - key: PINATA_SECRET_API_KEY
        sync: false
      - key: PINATA_JWT_TOKEN
        sync: false
      - key: CORS_ORIGINS
        value: https://meditrace.baozaolaoba.top
```

#### 2. 在 Render 部署

1. 访问 https://render.com/dashboard
2. 点击 "New +" → "Web Service"
3. 连接 GitHub 仓库
4. 配置：
   - **Name**: meditrace-backend
   - **Region**: Oregon (或最近地区)
   - **Branch**: main
   - **Root Directory**: (留空)
   - **Build Command**: `pip install -r src/backend/requirements.txt`
   - **Start Command**: `cd src/backend && uvicorn main:app --host 0.0.0.0 --port $PORT`
5. 环境变量：在 Dashboard 手动添加
6. 选择 "Free" 计划
7. 点击 "Create Web Service"

#### 3. 配置 CORS

确保后端 `src/backend/.env` 包含：

```bash
CORS_ORIGINS=https://meditrace.baozaolaoba.top,https://meditrace.vercel.app
```

---

### 第三步：Cloudflare DNS 配置

在 Cloudflare Dashboard 添加记录：

| 类型 | 名称 | 内容 | TTL | 代理 |
|------|------|------|-----|------|
| CNAME | meditrace | meditrace.vercel.app | Auto | 🟡 已代理 |

---

## 🔄 方案 B: 前后端都在 Vercel

### 第一步：创建 Vercel Serverless 后端

#### 1. 创建 API 入口文件

在项目根目录创建 `api/[[...route]].py`:

```python
# api/[[...route]].py - Vercel Serverless Function
import os
import sys
from typing import Any

# 添加后端目录到 Python 路径
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
BACKEND_DIR = os.path.join(BASE_DIR, 'src', 'backend')
sys.path.insert(0, BACKEND_DIR)

# 导入 FastAPI 应用
from main import app as fastapi_app

# Vercel Serverless Handler
async def handler(request):
    """Vercel Serverless Function Handler"""
    # 将 Vercel 请求转换为 ASGI 格式
    from fastapi.requests import Request as FastAPIRequest
    from fastapi.responses import Response as FastAPIResponse
    
    # 获取请求信息
    method = request.get('method', 'GET')
    path = request.get('path', '/')
    headers = request.get('headers', {})
    body = request.get('body', '')
    
    # 创建 FastAPI Request 对象
    fastapi_request = FastAPIRequest(
        scope={
            'type': 'http',
            'method': method,
            'path': path,
            'headers': [(k.encode(), v.encode()) for k, v in headers.items()],
        },
        receive=lambda: {'body': body.encode()}
    )
    
    # 调用 FastAPI 应用
    response = await fastapi_app(fastapi_request)
    
    # 转换为 Vercel 响应格式
    return {
        'statusCode': response.status_code,
        'headers': dict(response.headers),
        'body': await response.body(),
    }

# 导出 handler
export = handler
```

> ⚠️ **注意**: Vercel 对 Python Serverless Functions 的支持有限，可能需要使用 `vercel-python` 运行时。

#### 2. 创建 `vercel.json`

```json
{
  "buildCommand": "cd src/frontend && pnpm build",
  "outputDirectory": "src/frontend/.next",
  "framework": "nextjs",
  "regions": ["hkg1"],
  "env": {
    "NEXT_PUBLIC_BACKEND_URL": "/api",
    "NEXT_PUBLIC_CONTRACT_ADDRESS": "0x860418e7713A346c829Bc539C93c7A2d576897C5",
    "NEXT_PUBLIC_RPC_URL": "https://ethereum-sepolia-rpc.publicnode.com"
  },
  "functions": {
    "api/**/*.py": {
      "runtime": "vercel-python@1.0.0"
    }
  }
}
```

#### 3. 创建 `requirements.txt` (项目根目录)

```txt
fastapi>=0.100.0
uvicorn[standard]>=0.30.0
pydantic>=2.7.0
python-dotenv>=1.0.0
httpx>=0.27.0
aiohttp>=3.9.0
python-multipart>=0.0.9
web3>=7.0.0
ipfshttpclient>=0.8.0a2
```

#### 4. 部署

```bash
# 部署到 Vercel
vercel --prod
```

---

## 📋 配置检查清单

### Vercel 前端

- [ ] `src/frontend/.env.production` 配置正确
- [ ] Vercel 项目创建成功
- [ ] 环境变量已设置
- [ ] 自定义域名已配置
- [ ] Cloudflare DNS CNAME 记录已添加

### Render 后端

- [ ] `render.yaml` 配置正确
- [ ] Render 服务创建成功
- [ ] 环境变量已设置（API Key 等）
- [ ] CORS 配置包含前端域名
- [ ] 后端健康检查通过

### Cloudflare

- [ ] DNS 记录已添加
- [ ] SSL 证书已获取（Cloudflare 自动处理）
- [ ] 代理状态已开启（橙色云）

---

## 🔧 常见问题

### Vercel 部署失败

**问题**: Python 函数无法识别

**解决**: 确保使用 `vercel-python` 运行时，并在 `vercel.json` 中配置：

```json
{
  "functions": {
    "api/**/*.py": {
      "runtime": "vercel-python@1.0.0"
    }
  }
}
```

### 后端超时

**问题**: AI 对话超过 60 秒超时

**解决**: 
- 方案 A: 使用 Render/Railway（无超时限制）
- 方案 B: 优化 AI 响应速度，使用流式响应

### 跨域错误

**问题**: CORS 错误

**解决**: 
```bash
# 后端 .env
CORS_ORIGINS=https://meditrace.baozaolaoba.top,https://meditrace.vercel.app
```

---

## 💰 成本对比

| 方案 | 前端 | 后端 | 总计 |
|------|------|------|------|
| Vercel + Render | 免费 | 免费 | **$0/月** |
| Vercel + Railway | 免费 | 免费 ($5/月) | **$5/月** |
| 全 VPS | $5-10/月 | $5-10/月 | **$5-10/月** |
| Cloudflare Pages + Workers | 免费 | 免费 | **$0/月** |

---

## ✅ 推荐方案总结

对于 MediTrace 项目，**推荐方案 A**：

```
前端：Vercel (Next.js 优化最好)
后端：Render (免费、无超时限制)
域名：Cloudflare (免费 SSL + CDN)
成本：$0/月
```

这种方式平衡了性能、成本和可维护性，适合个人/小团队项目。
