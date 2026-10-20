# MediTrace - 医疗 AI 诊断溯源系统

MediTrace 提供医疗咨询对话、诊断报告和链上记录查询，结合 Next.js、FastAPI、PostgreSQL、IPFS 与 Solidity。诊断建议仅用于辅助参考，不能替代医生诊断。

在线地址：https://meditrace.baozaolaoba.top

## 新版开发规划

已确定下一版方向为 **MediTrace — Referral Review Copilot**：转诊材料核对、原文证据定位、人工审核和交接导出，用于 AI 应用／全栈求职展示。架构、模块规格、24 张开发工单和最终验收标准见 [V1 开发基线](docs/referral-review/README.md)。当前为规划，尚未完成新版开发；以下仍描述现有实现。

## 项目结构

```text
meditrace/
├── AGENTS.md                          # 项目协作与测试约束
├── BACKEND-DEPLOYMENT.md              # 前后端部署、环境变量及恢复步骤
├── BUGFIX-VERCEL-BACKEND-DEPLOYMENT.md # 后端部署修复及验证记录
├── deploy-vercel.sh                   # 前后端一键部署入口
├── vercel.json                       # Vercel Services 与路由配置
├── scripts/                          # 部署流程测试
└── src/
    ├── frontend/                     # Next.js 前端
    ├── backend/                      # FastAPI 后端、数据库迁移及测试
    └── contracts/                    # Solidity 合约及部署脚本
```

## 部署

前后端运行在同一个 Vercel 项目，生产数据保存在 Neon PostgreSQL。`/health` 和 `/api/*` 交给后端，其余路径交给前端。

在本项目中对助手说“部署”，或在终端运行：

```bash
./deploy-vercel.sh
```

脚本检查项目和免费套餐，发布前后端，验证线上接口，并在验证失败时尝试回退。

```bash
./deploy-vercel.sh --check   # 检查部署前置条件，不发布
./deploy-vercel.sh --verify  # 只读验证当前线上服务
```

账号登录、环境变量、数据库迁移及故障恢复见 [前后端部署指南](./BACKEND-DEPLOYMENT.md)。

## 本地开发

需要 Node.js 18+、pnpm 和 Python 3.10+。本地服务由开发者手动启动和停止。

### 后端

在仓库根目录执行：

```bash
cd src/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# 按需编辑 .env；不设置 DATABASE_URL 时使用本地 SQLite。
./venv/bin/python main.py
```

后端默认地址为 http://localhost:8000。真实 AI 推理需要 `DEEPSEEK_API_KEY`；未配置时使用演示回复。

### 前端

另开终端，从仓库根目录执行：

```bash
cd src/frontend
pnpm install
cp .env.example .env.local
pnpm dev
```

访问 http://localhost:3000。对话页面为 `/chat` 和 `/chat/{id}`。

### 区块链与报告

合约源码和部署脚本位于 `src/contracts/`。启用链上写入需要配置 RPC、合约地址及后端签名私钥；IPFS 报告存储需要 Pinata 配置。详细变量说明见 [部署指南](./BACKEND-DEPLOYMENT.md#环境变量)。

## 验证

```bash
# 部署与回退流程测试，不创建真实部署
python3 scripts/test_deploy_workflow.py

# 后端数据库集成测试，使用临时 SQLite，不调用 AI
DATABASE_URL=sqlite:///:memory: src/backend/venv/bin/python -m pytest src/backend/test_database_deployment.py -q
```

**禁止自动在浏览器发送 AI 消息测试。** 对话及流式显示请手动发送消息验证，以避免自动测试消耗 API token。

## 文档

- [项目助手指南](./AGENTS.md)
- [前后端部署指南](./BACKEND-DEPLOYMENT.md)
- [Vercel 后端修复与发布记录](./BUGFIX-VERCEL-BACKEND-DEPLOYMENT.md)

## 许可证

MIT License
