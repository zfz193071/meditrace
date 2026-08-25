# MediTrace - 医疗 AI 诊断溯源系统

> 一个结合大模型与 Web3 技术的医疗诊断辅助系统，通过区块链记录每次 AI 诊断的数据来源和模型版本，满足医疗合规审计需求。

![License](https://img.shields.io/badge/license-MIT-blue)
![Status](https://img.shields.io/badge/status-MVP%20Complete-brightgreen)
![Tech Stack](https://img.shields.io/badge/tech-Next.js%20%7C%20FastAPI%20%7C%20Solidity%20%7C%20DeepSeek%20API-green)
![Phase](https://img.shields.io/badge/phase-Phase%202%20Complete-brightgreen)

---

## 📁 项目结构

```
meditrace/
├── README.md              # 项目概述
├── SPEC.md                # 详细规格说明
├── CONTEXT.md             # 领域模型
├── DEPLOYMENT.md          # 部署指南
├── DEMO_SCRIPT.md         # 演示脚本 ⭐新增
├── TODO.md                # 开发任务清单
├── docs/
│   └── adr/
│       ├── 0001-project-vision.md    # 项目愿景决策
│       ├── 0002-tech-stack.md        # 技术栈选择
│       └── 0003-blockchain-design.md # 区块链设计决策
├── src/
│   ├── frontend/          # Next.js 前端
│   │   ├── app/
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx           # 诊断主页
│   │   │   ├── history/page.tsx   # 历史记录页 ⭐新增
│   │   │   └── verify/page.tsx    # 链上验证页 ⭐新增
│   │   ├── package.json
│   │   ├── tsconfig.json
│   │   └── tailwind.config.js
│   ├── backend/
│   │   ├── main.py           # FastAPI 主应用
│   │   ├── deepseek_client.py # DeepSeek 集成 ⭐新增
│   │   ├── blockchain_client.py # 区块链客户端 ⭐新增
│   │   ├── ipfs_service.py    # IPFS 服务 ⭐新增
│   │   ├── test_deepseek.py   # 测试脚本 ⭐新增
│   │   └── requirements.txt
│   └── contracts/
│       ├── contracts/
│       │   └── DiagnosisRecord.sol
│       ├── scripts/
│       │   ├── deploy.ts
│       │   └── deploy-sepolia.ts # Sepolia 部署 ⭐新增
│       ├── test/
│       │   └── DiagnosisRecord.test.ts
│       └── hardhat.config.ts
└── scripts/               # 部署和测试脚本
```

## 📖 项目背景

### 问题陈述
当前医疗 AI 诊断系统面临以下挑战：
- **数据溯源困难**: 无法追溯诊断建议基于哪些患者数据和模型版本
- **合规审计缺失**: 医疗监管机构要求诊断记录可审计、不可篡改
- **模型版本混乱**: 模型更新后无法区分历史诊断使用哪个版本

### 解决方案
MediTrace 通过以下技术栈解决上述问题：
- **大模型**: DeepSeek API + 医学知识库 RAG，提供专业诊断建议
- **区块链**: Solidity 智能合约记录诊断元数据，确保不可篡改
- **去中心化存储**: IPFS 存储诊断报告，保证数据持久性

## 🎯 项目目标

### 主要目标
1. 实现医疗问答机器人，提供初步诊断建议
2. 每次诊断自动记录到区块链（数据哈希、模型版本、时间戳）
3. 提供审计界面，可查询和验证历史诊断记录
4. 完整部署文档，展示全栈工程能力

### 雇主价值点
- ✅ 展示 **AI + Web3 全栈能力**
- ✅ 医疗合规场景有**商业故事**
- ✅ 智能合约设计体现**工程严谨性**
- ✅ 完整部署文档体现**产品思维**

## 🏗 技术架构

```
┌─────────────────────────────────────────────────────────────┐
│                        前端 (Next.js)                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │  对话界面   │  │  历史记录   │  │  链上验证   │          │
│  └─────────────┘  └─────────────┘  └─────────────┘          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    后端 (FastAPI)                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │  对话 API   │  │  RAG 引擎   │  │  区块链客户端│          │
│  └─────────────┘  └─────────────┘  └─────────────┘          │
└─────────────────────────────────────────────────────────────┘
         │                                      │
         ▼                                      ▼
┌─────────────────────┐          ┌─────────────────────────────┐
│   DeepSeek API      │          │    区块链层 (Hardhat)        │
│   + 医学知识库      │          │  ┌─────────────┐            │
└─────────────────────┘          │  │ 诊断记录合约│            │
                                 │  └─────────────┘            │
                                 │  ┌─────────────┐            │
                                 │  │   IPFS     │            │
                                 │  └─────────────┘            │
                                 └─────────────────────────────┘
```

## 📁 项目结构

```
meditrace/
├── README.md              # 项目概述
├── SPEC.md                # 详细规格说明
├── CONTEXT.md             # 领域模型
├── docs/
│   └── adr/
│       ├── 0001-project-vision.md    # 项目愿景决策
│       ├── 0002-tech-stack.md        # 技术栈选择
│       └── 0003-blockchain-design.md # 区块链设计决策
├── src/
│   ├── frontend/          # Next.js 前端
│   ├── backend/           # FastAPI 后端
│   └── contracts/         # Solidity 智能合约
└── scripts/               # 部署和测试脚本
```

## 🚀 快速开始

### 环境要求

| 工具 | 版本 | 说明 |
|------|------|------|
| Node.js | >= 18 | 前端和合约开发 |
| Python | >= 3.10 | 后端开发 |
| Hardhat | 2.x | 区块链开发 |
| DeepSeek API | - | 大模型调用 |

### 安装步骤

```bash
# 1. 克隆项目
git clone <repository-url>
cd meditrace

# 2. 部署智能合约
cd src/contracts
npm install
npx hardhat node                    # 终端 1: 启动本地节点
# 新终端
npx hardhat run scripts/deploy.ts --network localhost

# 3. 安装并启动后端
cd ../../src/backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env，填入 API Key
uvicorn main:app --reload

# 4. 安装并启动前端
cd ../../src/frontend
npm install
cp .env.example .env.local
npm run dev
```

访问 http://localhost:3000 开始使用。

## 📋 功能清单

- [ ] 用户输入症状，AI 返回诊断建议
- [ ] 诊断记录自动上链
- [ ] 历史诊断记录查询
- [ ] 链上记录验证界面
- [ ] 诊断报告 IPFS 存储
- [ ] 完整部署文档

## 📚 相关文档

- [详细规格说明](./SPEC.md)
- [领域模型](./CONTEXT.md)
- [架构决策记录](./docs/adr/)

## 🤝 贡献

欢迎提出 Issue 和 Pull Request！

## 📄 许可证

MIT License
