# MediTrace 项目概览

> 生成时间：2024

---

## 🎯 项目定位

**MediTrace** 是一个结合大模型与 Web3 技术的医疗诊断辅助系统，旨在：
- 解决医疗 AI 诊断的**数据溯源**问题
- 通过区块链确保诊断记录的**不可篡改性**
- 满足医疗合规**审计要求**

**目标**: 1-2 周内完成 MVP，展示 AI + Web3 全栈能力，用于求职展示。

---

## ✅ 已完成工作 (Phase 1 - Scaffold)

### 文档体系

| 文档 | 路径 | 说明 |
|------|------|------|
| 项目概述 | `README.md` | 项目介绍、技术架构、快速开始 |
| 规格说明 | `SPEC.md` | 详细功能需求、API 定义、数据模型 |
| 领域模型 | `CONTEXT.md` | 核心概念、业务规则、术语表 |
| 部署指南 | `DEPLOYMENT.md` | 本地开发、生产部署、故障排查 |
| 任务清单 | `TODO.md` | 开发进度、技术债务、未来扩展 |
| 愿景 ADR | `docs/adr/0001-project-vision.md` | 为什么选择医学 + 数据溯源 |
| 技术栈 ADR | `docs/adr/0002-tech-stack.md` | 为什么选择这些技术 |
| 合约设计 ADR | `docs/adr/0003-blockchain-design.md` | 智能合约设计决策 |

### 智能合约

| 文件 | 说明 | 状态 |
|------|------|------|
| `DiagnosisRecord.sol` | 诊断记录存储合约 | ✅ 完成 |
| `hardhat.config.ts` | Hardhat 配置 | ✅ 完成 |
| `deploy.ts` | 部署脚本 | ✅ 完成 |
| `DiagnosisRecord.test.ts` | 合约测试 | ✅ 完成 |

**合约功能**:
- `recordDiagnosis()`: 记录诊断元数据
- `getRecord()`: 查询诊断记录
- `getPatientRecords()`: 查询患者所有记录
- 事件日志支持 off-chain 索引

### 后端 API

| 文件 | 说明 | 状态 |
|------|------|------|
| `main.py` | FastAPI 主应用 | ✅ 完成 (Mock) |
| `requirements.txt` | Python 依赖 | ✅ 完成 |

**API 端点**:
- `POST /api/diagnose`: 诊断接口 (Mock)
- `GET /api/history/{userId}`: 历史记录 (Mock)
- `GET /api/verify/{diagnosisId}`: 链上验证 (Mock)

### 前端页面

| 文件 | 说明 | 状态 |
|------|------|------|
| `page.tsx` | 主页面 (诊断表单 + 结果) | ✅ 完成 |
| `layout.tsx` | 根布局 | ✅ 完成 |
| `globals.css` | Tailwind 样式 | ✅ 完成 |

**前端功能**:
- 症状输入表单
- AI 诊断结果展示
- 免责声明显示
- 溯源状态指示

---

## 📋 下一步计划 (Phase 2 - 功能完善)

### Week 1.5: 核心功能实现

#### 后端 (优先级：高)

- [ ] **集成 DeepSeek API**
  - 替换 Mock 数据为真实 AI 诊断
  - 实现医学知识库 RAG
  - 优化 Prompt 工程

- [ ] **集成智能合约**
  - 使用 Web3.py 连接本地/测试网
  - 实现诊断记录自动上链
  - 添加错误处理和重试

- [ ] **IPFS 报告存储**
  - 生成 PDF 诊断报告
  - 上传到 Pinata/IPFS
  - 存储 CID 到合约

#### 前端 (优先级：中)

- [ ] **完善对话界面**
  - 支持多轮对话
  - 添加加载状态
  - 优化响应式设计

- [ ] **历史记录页面**
  - 查询用户所有诊断
  - 筛选和排序
  - 查看详情

- [ ] **链上验证组件**
  - 调用合约验证记录
  - 显示验证结果
  - 区块链浏览器链接

#### 智能合约 (优先级：低)

- [ ] 添加访问控制
- [ ] Gas 优化
- [ ] 安全审计

---

## 📊 项目进度

```
Phase 1: Scaffold          ████████████████████ 100%
Phase 2: 功能完善          ████░░░░░░░░░░░░░░░░  20%
Phase 3: 集成与部署        ░░░░░░░░░░░░░░░░░░░░   0%
```

**总体进度**: 约 25%

---

## 🚀 快速启动指南

### 1. 启动本地开发环境

```bash
# 终端 1: 区块链节点
cd src/contracts
npm install
npx hardhat node

# 终端 2: 部署合约
npx hardhat run scripts/deploy.ts --network localhost

# 终端 3: 后端
cd src/backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload

# 终端 4: 前端
cd src/frontend
npm install
npm run dev
```

### 2. 访问应用

- 前端：http://localhost:3000
- 后端 API 文档：http://localhost:8000/docs

### 3. 测试功能

1. 输入症状，点击"获取诊断建议"
2. 查看返回的 Mock 诊断结果
3. 检查后端日志确认 API 调用

---

## 💡 项目亮点 (用于简历/GitHub)

### 技术亮点

| 亮点 | 说明 |
|------|------|
| **AI + Web3 全栈** | 展示大模型集成 + 智能合约开发能力 |
| **医疗合规场景** | 有真实商业应用场景，非玩具项目 |
| **完整工程实践** | 从需求到部署的完整流程 |
| **文档齐全** | SPEC、ADR、部署文档体现专业素养 |

### 雇主价值

- **AI 公司**: 展示 RAG、Prompt 工程、API 集成能力
- **Web3 公司**: 展示 Solidity、智能合约、链上验证能力
- **传统科技公司**: 展示全栈开发、系统设计、文档能力
- **初创公司**: 展示产品思维、快速迭代、商业理解能力

---

## 📝 待办事项

### 必须完成 (P0)

- [ ] 集成 DeepSeek API 获取真实诊断
- [ ] 实现智能合约调用（上链）
- [ ] 完善前端交互体验
- [ ] 编写部署文档和演示视频

### 建议完成 (P1)

- [ ] IPFS 报告存储
- [ ] 历史记录查询功能
- [ ] 链上验证组件
- [ ] 单元测试和集成测试

### 可选扩展 (P2)

- [ ] 用户认证系统
- [ ] 移动端适配
- [ ] 模型微调功能
- [ ] 数据可视化

---

## 📚 参考资源

- [DeepSeek API 文档](https://platform.deepseek.com/)
- [Hardhat 教程](https://hardhat.org/tutorial)
- [Next.js 文档](https://nextjs.org/docs)
- [FastAPI 文档](https://fastapi.tiangolo.com/)
- [医疗 AI 合规指南](https://www.fda.gov/medical-devices/digital-health-center-excellence/ai-in-medical-products)

---

## 🤝 贡献

欢迎提出 Issue 和 Pull Request！

## 📄 许可证

MIT License
