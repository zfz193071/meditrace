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

```bash
cd src/backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 创建 .env 文件
cat > .env << EOF
DEEPSEEK_API_KEY=your_api_key_here
CONTRACT_ADDRESS=0xYourContractAddress
EOF

# 启动后端
uvicorn main:app --reload --host 0.0.0.0 --port 8000
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

### 前端部署 (Vercel)

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

```bash
# 设置环境变量
export SEPOLIA_RPC_URL="https://rpc.sepolia.org"
export PRIVATE_KEY="your_private_key"

# 部署
npx hardhat run scripts/deploy.ts --network sepolia
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
