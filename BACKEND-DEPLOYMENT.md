# 后端服务部署指南

## 📋 环境变量配置

### 生产环境（Vercel）

**重要**: 以下环境变量需要在 Vercel 控制台中配置，**不要**提交到代码仓库。

#### 必需的环境变量

| 变量名 | 说明 | 示例值 |
|--------|------|--------|
| `DATABASE_URL` | Neon PostgreSQL 连接字符串 | `postgresql://user:pass@host/neondb?sslmode=require` |
| `USE_SEPOLIA` | 是否使用 Sepolia 测试网 | `true` |
| `SEPOLIA_RPC_URL` | Sepolia RPC 端点 | `https://ethereum-sepolia-rpc.publicnode.com` |
| `CONTRACT_ADDRESS_SEPOLIA` | Sepolia 合约地址 | `0x860418e7713A346c829Bc539C93c7A2d576897C5` |
| `PINATA_API_KEY` | Pinata API Key | `99608ce2692e0a266838` |
| `PINATA_SECRET_API_KEY` | Pinata Secret API Key | `b9ac92a982ffab8128a6fcc39c7eecb505525c47ca280f53795cc1a897f37237` |
| `PINATA_JWT_TOKEN` | Pinata JWT Token | `eyJhbGci...` |
| `CORS_ORIGINS` | 允许的前端域名 | `https://meditrace.baozaolaoba.top` |

#### 不需要的环境变量

| 变量名 | 说明 | 原因 |
|--------|------|------|
| `DEEPSEEK_API_KEY` | DeepSeek API Key | **生产环境不需要** - AI 推理在 Vercel Serverless 函数中运行，API Key 通过 Vercel 环境变量管理；后端使用模拟返回 |

### 本地开发环境

本地开发时需要完整的 `.env` 文件（已在 `.gitignore` 中忽略）：

```bash
# src/backend/.env

# ⚠️ 生产环境部署配置
# 注意：DEEPSEEK_API_KEY 不部署到生产环境，使用模拟返回
# Qwen3.5 API 配置 (备用)
# QWEN_API_KEY=sk-xxx

# 区块链配置 (本地开发)
BLOCKCHAIN_RPC_URL=http://localhost:8545
CONTRACT_ADDRESS=

# 使用 Sepolia 测试网 (true = 使用 Sepolia, false = 使用本地)
USE_SEPOLIA=true

# 区块链配置 (Sepolia 测试网)
SEPOLIA_RPC_URL=https://ethereum-sepolia-rpc.publicnode.com
SEPOLIA_PRIVATE_KEY=7e4cffc5275557070d807f772f65312bc9e561a92bad19c474871f663291f705
CONTRACT_ADDRESS_SEPOLIA=0x860418e7713A346c829Bc539C93c7A2d576897C5

# IPFS 配置 (Pinata)
PINATA_API_KEY=99608ce2692e0a266838
PINATA_SECRET_API_KEY=b9ac92a982ffab8128a6fcc39c7eecb505525c47ca280f53795cc1a897f37237
PINATA_JWT_TOKEN=eyJhbGci...

# CORS 配置 - 生产环境
CORS_ORIGINS=https://meditrace.baozaolaoba.top

# PostgreSQL 数据库配置 (Neon)
DATABASE_URL=postgresql://neondb_owner:npg_rXpDkonM8mS0@ep-nameless-truth-arrrgjuc-pooler.c-4.us-west-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require
```

## 🔧 依赖安装

### 本地开发环境

在安装依赖前，确保已创建 Python 虚拟环境：

```bash
cd src/backend
python3 -m venv venv
source venv/bin/activate
```

安装依赖（可能需要较长时间，取决于网络）：

```bash
pip install -r requirements.txt
```

如果网络超时，可以分批安装：

```bash
pip install fastapi uvicorn pydantic python-dotenv
pip install httpx aiohttp python-multipart
pip install web3 ipfshttpclient psycopg2-binary sqlalchemy
```

## 🔧 Vercel 部署步骤

### 1. 配置 Vercel 环境变量

在 Vercel 控制台 → Project Settings → Environment Variables 中添加以下变量：

```
DATABASE_URL=postgresql://neondb_owner:npg_rXpDkonM8mS0@ep-nameless-truth-arrrgjuc-pooler.c-4.us-west-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require
USE_SEPOLIA=true
SEPOLIA_RPC_URL=https://ethereum-sepolia-rpc.publicnode.com
CONTRACT_ADDRESS_SEPOLIA=0x860418e7713A346c829Bc539C93c7A2d576897C5
PINATA_API_KEY=99608ce2692e0a266838
PINATA_SECRET_API_KEY=b9ac92a982ffab8128a6fcc39c7eecb505525c47ca280f53795cc1a897f37237
PINATA_JWT_TOKEN=eyJhbGci...
CORS_ORIGINS=https://meditrace.baozaolaoba.top
```

**注意**: 不要添加 `DEEPSEEK_API_KEY`

### 2. 部署配置

项目使用 Vercel Services 架构，`vercel.json` 已配置：

```json
{
  "services": {
    "frontend": {
      "root": "src/frontend/",
      "framework": "nextjs"
    },
    "backend": {
      "root": "src/backend/",
      "framework": "fastapi",
      "entrypoint": "main:app"
    }
  },
  "rewrites": [
    {
      "source": "/health",
      "destination": { "service": "backend" }
    },
    {
      "source": "/api/(.*)",
      "destination": { "service": "backend" }
    },
    {
      "source": "/(.*)",
      "destination": { "service": "frontend" }
    }
  ]
}
```

### 3. 推送代码并部署

```bash
git add .
git commit -m "deploy: 配置生产环境数据库连接"
git push origin main
```

Vercel 会自动检测并部署前后端服务。

## 🧪 本地测试

### 启动后端服务

```bash
cd src/backend
source venv/bin/activate
python main.py
```

后端将在 `http://localhost:8000` 启动。

### 验证数据库连接

启动后检查日志，应该看到：
```
🔧 使用 PostgreSQL 数据库：postgresql://neondb_owner:***@...
✅ 数据库表初始化完成
```

### 测试 API

```bash
# 健康检查
curl http://localhost:8000/health

# 测试诊断 API（演示模式，使用模拟回复）
curl -X POST http://localhost:8000/api/diagnose \
  -H "Content-Type: application/json" \
  -d '{"symptoms": "发热、咳嗽", "userId": "test-user-001"}'
```

## ⚠️ 安全注意事项

1. **不要提交 `.env` 文件** - 包含敏感密钥
2. **生产环境不使用 DEEPSEEK_API_KEY** - 避免消耗 token
3. **数据库连接字符串包含密码** - 确保只配置在安全的环境变量中
4. **区块链私钥** - 仅用于测试，生产环境应使用更安全的密钥管理方案

## 📚 相关文档

- [VERCEL-FULLSTACK-DEPLOYMENT.md](./VERCEL-FULLSTACK-DEPLOYMENT.md) - 完整部署指南
- [VERCEL-DEPLOYMENT-CHECKLIST.md](./VERCEL-DEPLOYMENT-CHECKLIST.md) - 部署检查清单
- [AGENTS.md](./AGENTS.md) - 项目开发指南
