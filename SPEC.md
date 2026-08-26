# MediTrace 详细规格说明

> 版本：1.0.0
> 最后更新：2024
> 状态：草稿

---

## 1. 项目概述

### 1.1 问题定义

医疗 AI 诊断系统在实际应用中面临三个核心问题：

| 问题 | 影响 | 现有方案不足 |
|------|------|-------------|
| 数据溯源困难 | 无法验证诊断建议的数据基础 | 中心化日志易篡改、难审计 |
| 合规审计缺失 | 不符合医疗监管要求 | 缺乏不可篡改的记录机制 |
| 模型版本混乱 | 无法区分历史诊断的模型版本 | 版本管理分散、难以追溯 |

### 1.2 解决方案

MediTrace 是一个**医疗 AI 诊断溯源系统**，核心创新点：

1. **AI 诊断引擎**: 基于 DeepSeek API + 医学知识库 RAG，提供专业诊断建议
2. **区块链溯源**: 每次诊断的元数据（数据哈希、模型版本、时间戳）记录在智能合约
3. **去中心化存储**: 完整诊断报告存储于 IPFS，保证数据持久性和可验证性
4. **审计界面**: 医生/监管者可查询和验证历史诊断记录

### 1.3 目标用户

| 用户类型 | 使用场景 | 核心需求 |
|---------|---------|---------|
| 患者 | 输入症状获取初步诊断 | 快速、准确、可追溯 |
| 医生 | 辅助诊断 + 记录存档 | 合规、可审计、可验证 |
| 监管机构 | 审查诊断记录 | 不可篡改、完整溯源 |

---

## 2. 功能需求

### 2.1 核心功能模块

#### FR-01: 医疗问答对话

| 属性 | 描述 |
|------|------|
| **ID** | FR-01 |
| **名称** | 医疗问答对话 |
| **优先级** | P0 (必须) |
| **描述** | 用户输入症状描述，系统返回 AI 诊断建议 |
| **输入** | 症状文本描述（支持多轮对话） |
| **输出** | 诊断建议（包含可能疾病、建议检查、风险提示） |
| **约束** | 响应时间 < 10 秒；必须包含免责声明 |

**用户故事**:
> 作为患者，我希望输入症状并获得初步诊断建议，以便了解可能的健康问题并决定是否需要就医。

**验收标准**:
- [ ] 用户可输入症状文本
- [ ] 系统返回结构化诊断建议（疾病列表、置信度、建议检查）
- [ ] 每条建议包含免责声明
- [ ] 支持多轮对话（用户可追问）

---

#### FR-02: 诊断记录上链

| 属性 | 描述 |
|------|------|
| **ID** | FR-02 |
| **名称** | 诊断记录上链 |
| **优先级** | P0 (必须) |
| **描述** | 每次诊断完成后，自动将元数据记录到区块链 |
| **记录内容** | 患者 ID 哈希、症状哈希、诊断结果哈希、模型版本、时间戳 |
| **约束** | 上链失败不影响诊断流程；需记录失败日志 |

**用户故事**:
> 作为医生，我希望每次诊断自动记录到区块链，以便满足合规审计要求。

**验收标准**:
- [ ] 诊断完成后自动触发上链
- [ ] 记录包含所有必要元数据
- [ ] 上链失败有明确日志和重试机制
- [ ] 用户可查询上链状态

---

#### FR-03: 历史记录查询

| 属性 | 描述 |
|------|------|
| **ID** | FR-03 |
| **名称** | 历史记录查询 |
| **优先级** | P0 (必须) |
| **描述** | 用户可查询自己的历史诊断记录 |
| **筛选条件** | 时间范围、疾病类型、诊断状态 |
| **约束** | 仅用户可查询自己的记录（隐私保护） |

**用户故事**:
> 作为患者，我希望查看自己的历史诊断记录，以便跟踪健康状况。

**验收标准**:
- [ ] 用户可查询自己的诊断历史
- [ ] 支持时间范围和疾病类型筛选
- [ ] 每条记录可查看详情和链上验证状态

---

#### FR-04: 链上记录验证

| 属性 | 描述 |
|------|------|
| **ID** | FR-04 |
| **名称** | 链上记录验证 |
| **优先级** | P1 (重要) |
| **描述** | 验证诊断记录是否真实存在于区块链 |
| **验证内容** | 数据哈希匹配、时间戳验证、模型版本确认 |
| **约束** | 验证过程透明，用户可理解 |

**用户故事**:
> 作为监管者，我希望验证诊断记录的真实性和完整性，以确保合规。

**验收标准**:
- [ ] 用户可点击"验证"按钮检查链上记录
- [ ] 显示验证结果（成功/失败）和详细信息
- [ ] 提供区块链浏览器链接

---

#### FR-05: IPFS 报告存储

| 属性 | 描述 |
|------|------|
| **ID** | FR-05 |
| **名称** | IPFS 报告存储 |
| **优先级** | P1 (重要) |
| **描述** | 完整诊断报告存储于 IPFS，链上仅存哈希 |
| **报告内容** | 症状描述、诊断建议、推荐检查、免责声明 |
| **约束** | 报告格式为 PDF；需保证 IPFS 持久化 |

**用户故事**:
> 作为医生，我希望诊断报告永久存储，以便长期存档和审计。

**验收标准**:
- [ ] 诊断报告自动生成 PDF
- [ ] PDF 上传至 IPFS 并获取 CID
- [ ] CID 记录在智能合约
- [ ] 用户可通过 CID 下载报告

---

### 2.2 非功能需求

#### NFR-01: 性能

| 指标 | 目标值 |
|------|--------|
| 对话响应时间 | < 10 秒 |
| 上链确认时间 | < 30 秒（本地链）/ < 2 分钟（测试网） |
| 历史记录查询 | < 2 秒 |

#### NFR-02: 安全性

| 要求 | 描述 |
|------|------|
| 数据加密 | 患者数据在传输和存储时加密 |
| 隐私保护 | 链上仅存哈希，不存明文数据 |
| 访问控制 | 用户只能访问自己的记录 |

#### NFR-03: 可靠性

| 要求 | 描述 |
|------|------|
| 服务可用性 | 99%（MVP 阶段） |
| 数据持久性 | IPFS 保证报告长期可用 |
| 故障恢复 | 上链失败有重试机制 |

---

## 3. 技术规格

### 3.1 技术栈

| 层级 | 技术 | 版本 | 说明 |
|------|------|------|------|
| 前端 | Next.js | 14.x | React 全栈框架 |
| 前端样式 | Tailwind CSS | 3.x | 原子化 CSS |
| 后端 | FastAPI | 0.100+ | Python 异步框架 |
| 大模型 | DeepSeek API | - | 通过 API 调用 |
| 区块链 | Solidity | 0.8.20 | 智能合约语言 |
| 区块链开发 | Hardhat | 2.x | 以太坊开发框架 |
| 区块链交互 | Ethers.js | 6.x | JavaScript 库 |
| 存储 | IPFS | - | 去中心化存储 |
| 部署 | Vercel + Render | - | 前端 + 后端托管 |

### 3.2 系统接口

#### API 接口定义

```typescript
// POST /api/diagnose
// 请求
{
  "symptoms": string;        // 症状描述
  "userId": string;          // 用户 ID（哈希）
}

// 响应
{
  "diagnosisId": string;     // 诊断记录 ID
  "suggestions": [           // 诊断建议列表
    {
      "disease": string;     // 可能疾病
      "confidence": number;  // 置信度 0-1
      "recommendations": string[]; // 建议检查
    }
  ];
  "disclaimer": string;      // 免责声明
  "ipfsCid": string;         // IPFS 报告 CID
  "chainTxHash": string;     // 区块链交易哈希
}

// GET /api/history/:userId
// 响应
{
  "records": [
    {
      "diagnosisId": string;
      "timestamp": number;
      "diseaseTypes": string[];
      "chainStatus": "pending" | "confirmed" | "failed";
      "ipfsCid": string;  // IPFS 报告 CID（FR-05 要求）
    }
  ]
}

// GET /api/verify/:diagnosisId
// 响应
{
  "isValid": boolean;
  "chainRecord": {
    "dataHash": string;
    "modelVersion": string;
    "timestamp": number;
  };
  "ipfsCid": string;
}
```

### 3.3 智能合约设计

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract DiagnosisRecord {
    struct Record {
        bytes32 dataHash;        // 诊断数据哈希
        string modelVersion;     // 模型版本
        uint256 timestamp;       // 时间戳
        string ipfsCid;          // IPFS 报告 CID
        address patient;         // 患者地址（哈希）
    }
    
    mapping(bytes32 => Record) public records;  // diagnosisId => Record
    mapping(address => bytes32[]) public patientRecords;  // patient => recordIds
    
    event DiagnosisRecorded(
        bytes32 indexed diagnosisId,
        address indexed patient,
        uint256 timestamp
    );
    
    function recordDiagnosis(
        bytes32 _dataHash,
        string memory _modelVersion,
        string memory _ipfsCid,
        address _patient
    ) external returns (bytes32);
    
    function getRecord(bytes32 _diagnosisId) external view returns (Record memory);
    
    function getPatientRecords(address _patient) external view returns (bytes32[] memory);
}
```

---

## 4. 数据模型

### 4.1 核心实体

```typescript
// 用户
interface User {
  id: string;              // UUID
  walletAddress: string;   // 区块链地址（用于身份）
  createdAt: Date;
}

// 诊断记录
interface Diagnosis {
  id: string;              // UUID
  userId: string;          // 关联用户
  symptoms: string;        // 症状描述（加密存储）
  suggestions: DiagnosisSuggestion[];
  disclaimer: string;
  status: 'processing' | 'completed' | 'failed';
  
  // 溯源信息
  dataHash: string;        // SHA-256 哈希
  modelVersion: string;
  ipfsCid: string;
  chainTxHash: string;
  chainStatus: 'pending' | 'confirmed' | 'failed';
  
  createdAt: Date;
  updatedAt: Date;
}

interface DiagnosisSuggestion {
  disease: string;
  confidence: number;      // 0-1
  recommendations: string[];
}
```

### 4.2 数据流

```
用户输入症状
    │
    ▼
┌─────────────┐
│  FastAPI    │  1. 接收症状
│  Backend    │  2. 生成数据哈希
└─────────────┘
    │
    ▼
┌─────────────────┐
│ DeepSeek API    │  3. 调用 AI 生成诊断
│ + RAG Engine    │
└─────────────────┘
    │
    ▼
┌─────────────┐
│  FastAPI    │  4. 生成 PDF 报告
│  Backend    │  5. 上传 IPFS
└─────────────┘
    │
    ▼
┌─────────────┐
│  Hardhat    │  6. 调用智能合约上链
│  Contract   │
└─────────────┘
    │
    ▼
返回诊断结果给用户
```

---

## 5. 项目里程碑

### Phase 1: 核心功能 (Week 1)

| 任务 | 产出 | 验收标准 |
|------|------|---------|
| 项目 scaffold | 完整目录结构 | 可运行 `npm install` |
| 智能合约开发 | DiagnosisRecord.sol | 本地测试通过 |
| 后端 API 开发 | FastAPI 基础框架 | API 文档可访问 |
| DeepSeek 集成 | 诊断功能 MVP | 可返回诊断建议 |

### Phase 2: 前端开发 (Week 1.5)

| 任务 | 产出 | 验收标准 |
|------|------|---------|
| 对话界面 | Next.js 页面 | 可输入症状并显示结果 |
| 历史记录页面 | 查询和展示 | 可筛选和查看详情 |
| 链上验证组件 | 验证界面 | 显示验证结果 |

### Phase 3: 集成与部署 (Week 2)

| 任务 | 产出 | 验收标准 |
|------|------|---------|
| 端到端测试 | 测试脚本 | 核心流程可自动化测试 |
| 部署文档 | README + 部署指南 | 他人可复现部署 |
| 演示视频 | 5 分钟演示 | 展示核心功能 |

---

## 6. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| DeepSeek API 不可用 | 核心功能失效 | 准备备用模型 API |
| IPFS 节点不稳定 | 报告无法访问 | 使用 Pinata 等付费 Pin 服务 |
| 区块链 Gas 费用过高 | 上链成本不可控 | 本地链开发，测试网演示 |
| 时间不足 | 功能 incomplete | 优先 P0 功能，P1 作为扩展 |

---

## 7. 附录

### 7.1 医学免责声明模板

```
重要提示：本系统提供的诊断建议仅供参考，不能替代专业医疗意见。
请咨询合格医疗专业人士获取准确诊断和治疗建议。如有紧急医疗情况，
请立即联系当地急救服务。
```

### 7.2 参考资源

- [DeepSeek API 文档](https://platform.deepseek.com/)
- [Hardhat 教程](https://hardhat.org/tutorial)
- [Next.js 文档](https://nextjs.org/docs)
- [FastAPI 文档](https://fastapi.tiangolo.com/)
