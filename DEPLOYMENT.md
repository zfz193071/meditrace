# MediTrace 部署指南

本指南介绍如何部署 MediTrace 项目到生产环境。

## 环境要求

- Node.js >= 18
- Python >= 3.10
- Hardhat (本地区块链)
- DeepSeek API Key

## 本地开发环境设置

### 1. 克隆项目

```bash
git clone <repository-url>
cd meditrace
```

### 2. 部署智能合约

```bash
cd src/contracts
npm install

# 启动本地区块链节点 (新终端)
npx hardhat node

# 部署合约 (新终端)
npx hardhat run scripts/deploy.ts --network localhost
```

部署成功后会生成 `deployment.json`，记录合约地址。

### 3. 设置后端环境

⚠️ **重要：必须使用 Python 虚拟环境 (venv)**

后端依赖 `httpx`、`python-dotenv` 等第三方库，**必须使用虚拟环境**，否则会出现 `ModuleNotFoundError`。

```bash
cd src/backend

# 创建虚拟环境（仅首次）
python -m venv venv

# 激活虚拟环境
source venv/bin/activate  # macOS/Linux
# 或
venv\Scripts\activate     # Windows

# 安装依赖
pip install -r requirements.txt

# 验证依赖安装成功
./venv/bin/python3 -c "import httpx; print('httpx:', httpx.__version__)"

# 创建 .env 文件
cat > .env << EOF
DEEPSEEK_API_KEY=your_api_key_here
CONTRACT_ADDRESS=0xYourContractAddress
EOF

# 启动后端（确保使用 venv 的 Python）
./venv/bin/python3 -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**常见错误：**

❌ **错误方式**（不使用 venv）：
```bash
cd src/backend
python3 -m uvicorn main:app  # 可能缺少 httpx 等依赖
```

✅ **正确方式**（使用 venv）：
```bash
cd src/backend
source venv/bin/activate
python3 -m uvicorn main:app  # 使用 venv 中的依赖
# 或直接
./venv/bin/python3 -m uvicorn main:app
```

后端 API 文档：http://localhost:8000/docs

### 4. 设置前端环境

```bash
cd src/frontend
npm install

# 创建 .env.local 文件
cat > .env.local << EOF
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
EOF

# 启动前端
npm run dev
```

前端访问：http://localhost:3000

## 部署到生产环境

### 🎯 推荐方案：单域名部署（前后端一起）

**域名**: `https://meditrace.baozaolaoba.top`

**架构**:
```
用户访问
   ↓
https://meditrace.baozaolaoba.top
   ↓
[Cloudflare + Nginx 反向代理]
   ├── / → 前端 Next.js (端口 3000)
   └── /api → 后端 FastAPI (端口 8000)
```

**为什么选择单域名部署？**

| 优势 | 说明 |
|------|------|
| ✅ **简单** | 一个域名、一个 SSL 证书、一套配置 |
| ✅ **便宜** | 单服务器，成本减半 |
| ✅ **无跨域** | 同源策略，无需配置 CORS |
| ✅ **易维护** | 统一日志、统一监控 |
| ✅ **适合项目规模** | MediTrace 是个人/小团队项目，用户量有限 |

**何时需要分开部署？**
- 企业级应用，需要独立扩展前后端
- 前端需要全球 CDN 加速，后端需要内网隔离
- 前后端由不同团队维护，独立发布

---

### 单域名部署步骤

#### 1. Cloudflare DNS 设置

登录 [Cloudflare Dashboard](https://dash.cloudflare.com/) 并添加 DNS 记录：

| 类型 | 名称 | 内容 | TTL | Proxy 状态 |
|------|------|------|-----|-----------|
| A | meditrace | 你的服务器 IP | Auto | 🟡 代理 (橙色云) |

**注意**: 只需一个 `meditrace` 记录，前端和后端共用同一域名！

#### 2. 前端环境变量 (`src/frontend/.env.production`)

```bash
NEXT_PUBLIC_BACKEND_URL=https://meditrace.baozaolaoba.top/api
NEXT_PUBLIC_CONTRACT_ADDRESS=0x860418e7713A346c829Bc539C93c7A2d576897C5
NEXT_PUBLIC_RPC_URL=https://ethereum-sepolia-rpc.publicnode.com
```

#### 3. 后端环境变量 (`src/backend/.env`)

```bash
# 已有配置保持不变...
DEEPSEEK_API_KEY=your-api-key
USE_SEPOLIA=true
# ...

# 添加 CORS 配置（单域名部署理论上不需要，但保留以防万一）
CORS_ORIGINS=https://meditrace.baozaolaoba.top
```

#### 4. Nginx 配置

创建 `/etc/nginx/sites-available/meditrace`:

```nginx
server {
    listen 80;
    server_name meditrace.baozaolaoba.top;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name meditrace.baozaolaoba.top;
    
    ssl_certificate /etc/letsencrypt/live/meditrace.baozaolaoba.top/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/meditrace.baozaolaoba.top/privkey.pem;
    
    # 前端 - 根路径
    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Next.js SSR 需要
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
    
    # 后端 API - /api 路径
    location /api {
        rewrite ^/api(.*)$ $1 break;
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

启用配置：
```bash
sudo ln -s /etc/nginx/sites-available/meditrace /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

#### 5. SSL 证书 (Let's Encrypt)

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d meditrace.baozaolaoba.top
```

#### 6. 使用 PM2 管理进程

创建 `ecosystem.config.js`:
```javascript
module.exports = {
  apps: [
    {
      name: 'meditrace-frontend',
      cwd: './src/frontend',
      script: 'pnpm',
      args: 'start',
      env: { NODE_ENV: 'production', PORT: 3000 }
    },
    {
      name: 'meditrace-backend',
      cwd: './src/backend',
      script: './venv/bin/python',
      args: 'main.py',
      env: { PYTHONUNBUFFERED: '1' }
    }
  ]
};
```

启动：
```bash
pm2 start ecosystem.config.js
pm2 save
pm2 startup
```

---

### 方案 B: 前后端分开部署（双域名）

#### 前端部署 (Vercel)

1. 将项目推送到 GitHub
2. 在 Vercel 导入项目
3. 设置环境变量：
   - `NEXT_PUBLIC_BACKEND_URL`: 后端 API 地址
4. 部署

### 后端部署 (Render)

1. 创建 `render.yaml`:

```yaml
services:
  - type: web
    name: meditrace-backend
    env: python
    buildCommand: pip install -r src/backend/requirements.txt
    startCommand: cd src/backend && uvicorn main:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: DEEPSEEK_API_KEY
        sync: false
      - key: CONTRACT_ADDRESS
        sync: false
```

2. 在 Render 导入项目并部署

### 智能合约部署到 Sepolia 测试网

#### 1. 准备 MetaMask 钱包

```bash
# 1. 安装 MetaMask 插件
# 2. 添加 Sepolia 测试网
#    网络名称：Sepolia Testnet
#    RPC 地址：https://rpc.sepolia.org
#    链 ID：11155111
#    代币符号：ETH
#    区块浏览器：https://sepolia.etherscan.io

# 3. 从 faucet 获取 Sepolia ETH (免费)
#    Google Cloud: https://cloud.google.com/application/web3/faucet/ethereum/sepolia
#    Alchemy: https://alchemy.com/faucets/ethereum-sepolia
#    ⚠️ 不需要花钱购买测试币!
```

#### 2. 配置环境变量

```bash
cd src/contracts

# 编辑 .env 文件
cat > .env << EOF
SEPOLIA_RPC_URL=https://rpc.sepolia.org
SEPOLIA_PRIVATE_KEY=your_private_key_here  # 从 MetaMask 导出
ETHERSCAN_API_KEY=your_etherscan_api_key   # 用于验证合约
EOF

# ⚠️ 安全警告：私钥不要提交到 Git!
```

#### 3. 部署合约

```bash
# 使用新的部署脚本
npx hardhat run scripts/deploy-sepolia.ts --network sepolia
```

**输出示例:**
```
🚀 开始部署到 Sepolia 测试网...
📝 使用账户：0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb
💰 账户余额：0.5 Sepolia ETH

🔨 正在部署 DiagnosisRecord 合约...
✅ 合约部署成功!
📍 合约地址：0x1234567890abcdef...

📋 下一步:
1. 在 Etherscan 验证合约
2. 更新后端配置
```

#### 4. 在 Etherscan 验证合约

```bash
# 验证合约 (可选，但推荐)
npx hardhat verify --network sepolia DEPLOYED_CONTRACT_ADDRESS
```

#### 5. 更新后端配置

在 Render 或本地 .env 中添加:
```
USE_SEPOLIA=true
CONTRACT_ADDRESS_SEPOLIA=0x1234567890abcdef...
```

## 环境变量说明

### 后端 (.env)

| 变量 | 说明 | 示例 |
|------|------|------|
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥 | `sk-xxx` |
| `CONTRACT_ADDRESS` | 智能合约地址 | `0x...` |

### 前端 (.env.local)

| 变量 | 说明 | 示例 |
|------|------|------|
| `NEXT_PUBLIC_BACKEND_URL` | 后端 API 地址 | `https://api.example.com` |

## 验证部署

1. 访问前端页面，检查是否正常显示
2. 输入症状，测试诊断功能
3. 检查后端日志，确认 API 调用成功
4. 在区块链浏览器查看合约交易

## 故障排查

### 后端无法启动：ModuleNotFoundError

**症状：**
```
ModuleNotFoundError: No module named 'httpx'
```

**原因：** 后端未使用虚拟环境 (venv) 启动

**解决方案：**
```bash
cd src/backend
source venv/bin/activate  # 激活虚拟环境
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000

# 或者直接使用 venv 的 Python
./venv/bin/python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
```

**验证：**
```bash
./venv/bin/python3 -c "import httpx; print('✓ httpx 已安装')"
```

### IPFS 报告上传失败

**症状：**
```
Pinata 上传失败：Invalid type for value. Expected primitive type, got <class 'dict'>
```

**原因：** `pinOptions` 参数格式错误

**解决方案：** 确保 `ipfs_service.py` 中的代码使用 JSON 字符串格式：
```python
# 正确格式
data = {"pinOptions": '{"public":true}'}  # JSON 字符串

# 错误格式
data = {"pinOptions": {"public": True}}  # Python 字典
```

### IPFS 报告下载失败

**症状：**
```
无法下载报告：所有 IPFS 网关均不可用
```

**原因：** IPFS 网关连接超时或不可达

**解决方案：** 确保使用 `gateway.pinata.cloud` 作为首选网关：
```python
gateways = [
    (f"https://gateway.pinata.cloud/ipfs/{ipfs_cid}", {}, 60, "gateway"),  # 首选
    (f"https://ipfs.io/ipfs/{ipfs_cid}", {}, 60, "gateway"),
    (f"https://cloudflare-ipfs.com/ipfs/{ipfs_cid}", {}, 60, "gateway")
]
```

**测试网关连通性：**
```bash
CID="your_cid_here"
curl -I "https://gateway.pinata.cloud/ipfs/$CID"
```

### 下载报告显示"报告未找到"

**症状：**
```
报告未找到：诊断 ID xxx 的记录中 IPFS CID 为空
```

**原因：** 历史记录中的 `ipfsCid` 字段为空（可能是之前 IPFS 上传失败导致的）

**解决方案：**
1. 新诊断：确保 IPFS 配置正确并重启后端
2. 历史记录：这些记录无法恢复，需要重新进行诊断

### 前端无法连接后端

- 检查 `NEXT_PUBLIC_BACKEND_URL` 是否正确
- 检查 CORS 配置
- 确认后端服务正在运行

### 合约部署失败

- 检查 RPC URL 是否正确
- 确认账户有足够 Gas
- 查看 Hardhat 错误日志

### API 调用失败

- 检查 API Key 是否正确
- 确认网络连通性
- 查看后端日志

## 监控与维护

### 日志查看

- Vercel: Dashboard → Logs
- Render: Dashboard → Logs
- 本地：终端输出

### 性能监控

- 使用 Vercel Analytics
- 使用 Render Metrics
- 自定义 API 响应时间监控

## 安全建议

1. **不要提交 .env 文件到版本控制**
2. 使用环境变量管理敏感信息
3. 定期更新依赖包
4. 启用 API 速率限制
5. 使用 HTTPS

## 下一步

- 集成真实的 DeepSeek API
- 实现 IPFS 报告存储
- 完善智能合约功能
- 添加用户认证系统
