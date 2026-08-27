# MediTrace 方案 A 需求规格文档

> **版本**: 1.0.0  
> **状态**: 已批准  
> **最后更新**: 2026-08-27  
> **目标**: 让项目达到"可演示、可面试"状态

---

## 📋 目录

1. [项目背景](#1-项目背景)
2. [目标与范围](#2-目标与范围)
3. [多轮对话功能规格](#3-多轮对话功能规格)
4. [演示材料规格](#4-演示材料规格)
5. [测试覆盖规格](#5-测试覆盖规格)
6. [技术架构设计](#6-技术架构设计)
7. [时间规划](#7-时间规划)
8. [验收标准](#8-验收标准)

---

## 1. 项目背景

### 1.1 当前状态

MediTrace 已完成 MVP 核心功能：
- ✅ 智能合约部署到 Sepolia
- ✅ AI 诊断集成 (DeepSeek API)
- ✅ 区块链记录溯源
- ✅ IPFS 报告存储
- ✅ 历史记录查询
- ✅ 链上验证功能
- ✅ 下载报告功能

### 1.2 待完善问题

| 问题 | 影响 | 优先级 |
|------|------|--------|
| 单次对话，无法追问 | 用户体验不完整 | P0 |
| 无演示材料 | 面试/展示困难 | P0 |
| 无单元测试 | 代码可信度低 | P1 |

### 1.3 方案 A 定位

**目标**: 短期冲刺 (1 周)，让项目达到"可演示、可面试"状态

**核心价值**:
- 提升用户体验 (多轮对话)
- 准备面试材料 (演示脚本 + Q&A)
- 展示工程严谨性 (单元测试)

---

## 2. 目标与范围

### 2.1 核心目标

| 目标 | 成功标准 | 优先级 |
|------|----------|--------|
| 实现多轮对话 | 用户可进行 5 轮以上连续对话 | P0 |
| 准备演示材料 | 3 分钟面试演示 + 5 分钟产品演示 | P0 |
| 添加单元测试 | 核心 API 测试覆盖率 > 80% | P1 |

### 2.2 范围边界

**包含**:
- ✅ 多轮对话功能 (完整实现)
- ✅ 演示脚本和 Q&A 文档
- ✅ 后端 + 前端单元测试
- ✅ 数据库持久化

**不包含**:
- ❌ 医学知识库 RAG (方案 B)
- ❌ 性能优化 (方案 B)
- ❌ 安全加固 (方案 B)
- ❌ 生产环境部署

---

## 3. 多轮对话功能规格

### 3.1 功能概述

**功能名称**: 多轮对话系统  
**功能 ID**: FT-001  
**优先级**: P0

**描述**: 支持用户与 AI 进行多轮连续对话，AI 能引用历史对话内容，主动追问补充信息。

### 3.2 用户故事

> **作为患者**, 我希望可以追问诊断细节，以便更好地理解病情并决定下一步行动。

**验收场景**:
1. 用户输入症状 → AI 返回初步诊断
2. 用户追问"这种情况严重吗？" → AI 引用历史诊断结果回答
3. AI 主动追问"症状持续多久了？" → 用户补充信息
4. AI 根据补充信息更新诊断建议

### 3.3 功能清单

| 功能点 | ID | 描述 | 优先级 |
|--------|-----|------|--------|
| 对话历史列表 | FT-001-01 | 左侧显示历史对话列表，支持切换 | P0 |
| 上下文引用 | FT-001-02 | AI 在回答时能引用之前的对话内容 | P0 |
| 追问引导 | FT-001-03 | AI 主动询问补充信息 | P0 |
| 对话状态持久化 | FT-001-04 | 刷新页面后对话历史不丢失 | P0 |
| 多诊断会话 | FT-001-05 | 支持同时保存多个患者的诊断记录 | P0 |

### 3.4 UI 布局设计

**布局方案**: 左右分栏布局

```
┌─────────────────────────────────────────────────────┐
│  左侧栏 (300px)              │  主内容区 (自适应)    │
│  ┌──────────────────────┐    │  ┌─────────────────┐ │
│  │  新建对话按钮         │    │  │  当前对话标题   │ │
│  └──────────────────────┘    │  └─────────────────┘ │
│  ┌──────────────────────┐    │  ┌─────────────────┐ │
│  │  对话 1 - 头痛        │    │  │  对话消息列表   │ │
│  │  对话 2 - 发烧        │    │  │  - 用户消息     │ │
│  │  对话 3 - 咳嗽        │    │  │  - AI 消息       │ │
│  │  ...                │    │  │  ...            │ │
│  └──────────────────────┘    │  └─────────────────┘ │
│  ┌──────────────────────┐    │  ┌─────────────────┐ │
│  │  清空历史按钮         │    │  │  输入框 + 发送   │ │
│  └──────────────────────┘    │  └─────────────────┘ │
└─────────────────────────────────────────────────────┘
```

### 3.5 上下文窗口设计

**窗口大小**: 最近 5 轮对话

**原因**:
- 平衡 token 消耗和上下文完整性
- 医疗诊断通常 3-5 轮即可完成
- 避免上下文过长导致 AI 注意力分散

**数据结构**:
```typescript
interface Conversation {
  id: string;              // UUID
  patientId: string;       // 患者 ID
  title: string;           // 对话标题 (如"头痛诊断")
  createdAt: number;       // 创建时间戳
  updatedAt: number;       // 最后更新时间戳
  messages: Message[];     // 消息列表
}

interface Message {
  id: string;              // 消息 ID
  role: 'user' | 'assistant';
  content: string;         // 消息内容
  timestamp: number;       // 时间戳
  context?: string[];      // 引用历史对话 (可选)
}
```

### 3.6 追问引导场景

**场景清单**:
1. **症状持续时间** - "这种情况持续多久了？"
2. **症状严重程度** - "如果用 1-10 分评分，您觉得有多严重？"
3. **相关症状补充** - "还有其他不舒服的地方吗？"
4. **既往病史** - "您之前有过类似的情况吗？"
5. **智能追问** - 根据诊断结果动态选择追问方向

**触发逻辑**:
```python
# 伪代码
def generate_follow_up_questions(diagnosis_result):
    """根据诊断结果生成追问问题"""
    questions = []
    
    if diagnosis_result.confidence < 0.7:
        questions.append("症状持续多久了？")
    
    if "疼痛" in diagnosis_result.symptoms:
        questions.append("疼痛程度 1-10 分是多少？")
    
    if diagnosis_result.has_chronic_conditions:
        questions.append("您有既往病史吗？")
    
    return questions[:3]  # 最多 3 个问题
```

### 3.7 数据库设计

**方案**: 混合方案 - 主表 + JSON

**原因**:
- 支持未来扩展 (图片、附件等)
- 查询灵活
- 开发效率高

**表结构**:
```sql
-- 对话主表
CREATE TABLE conversations (
    id VARCHAR(36) PRIMARY KEY,
    patient_id VARCHAR(42) NOT NULL,
    title VARCHAR(200) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    metadata JSON,  -- 存储诊断 ID、IPFS CID 等
    INDEX idx_patient_id (patient_id),
    INDEX idx_updated_at (updated_at DESC)
);

-- 消息表 (可选，如果 JSON 性能不足)
CREATE TABLE messages (
    id VARCHAR(36) PRIMARY KEY,
    conversation_id VARCHAR(36) NOT NULL,
    role ENUM('user', 'assistant') NOT NULL,
    content TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    context_refs JSON,  -- 引用历史消息 ID
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
    INDEX idx_conversation (conversation_id, timestamp)
);
```

### 3.8 API 接口设计

**新增接口**:

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/api/conversations` | 创建新对话 |
| GET | `/api/conversations` | 获取对话列表 |
| GET | `/api/conversations/{conversationId}` | 获取单个对话详情 |
| POST | `/api/conversations/{conversationId}/messages` | 发送消息 |
| DELETE | `/api/conversations/{conversationId}` | 删除对话 |

**请求/响应示例**:
```json
// POST /api/conversations
{
  "patientId": "0x262Ee58D3e7A782ceC68094A6DACb53D02Fa9d0B",
  "title": "头痛诊断"
}

// Response
{
  "conversationId": "550e8400-e29b-41d4-a716-446655440000",
  "patientId": "0x262Ee58D3e7A782ceC68094A6DACb53D02Fa9d0B",
  "title": "头痛诊断",
  "createdAt": 1724756400
}

// POST /api/conversations/{conversationId}/messages
{
  "content": "我头痛已经 3 天了",
  "contextWindow": 5
}
```

---

## 4. 演示材料规格

### 4.1 演示目标

**面试演示 (3 分钟)**:
- 突出技术亮点
- 展示全栈能力
- 适合技术面试

**产品演示 (5 分钟)**:
- 突出用户体验
- 展示完整流程
- 适合投资人/客户

### 4.2 技术亮点清单

| 亮点 | 展示方式 | 时长 |
|------|----------|------|
| 区块链溯源流程 | 诊断 → 上链 → 验证 | 45 秒 |
| IPFS 报告存储 | 上传 → 下载 → 网关重试 | 30 秒 |
| 多轮对话上下文 | AI 引用历史对话 | 45 秒 |
| 完整端到端流程 | 从诊断到验证 | 60 秒 |

### 4.3 演示脚本

#### 4.3.1 面试演示脚本 (3 分钟)

```
[0:00-0:15] 开场
"大家好，这是 MediTrace - 一个结合 AI 和区块链的医疗诊断溯源系统"

[0:15-1:00] 核心功能演示
1. 输入症状，AI 返回诊断 (15 秒)
2. 展示多轮对话，AI 引用历史 (30 秒)
3. 下载报告，展示 IPFS 存储 (15 秒)

[1:00-2:00] 技术亮点
1. 区块链溯源 - 展示链上记录 (30 秒)
2. 验证功能 - 输入诊断 ID 验证真实性 (30 秒)

[2:00-2:45] 架构说明
- 前端：Next.js + TypeScript + Tailwind
- 后端：FastAPI + Python
- 区块链：Solidity + Sepolia
- AI: DeepSeek API
- 存储：IPFS (Pinata)

[2:45-3:00] 总结
"这个项目展示了 AI + Web3 全栈能力，满足医疗合规审计需求"
```

#### 4.3.2 产品演示脚本 (5 分钟)

```
[0:00-0:30] 问题背景
"医疗 AI 诊断面临数据溯源困难、合规审计缺失的问题"

[0:30-1:30] 解决方案演示
1. 患者输入症状
2. AI 提供诊断建议
3. 多轮追问补充信息
4. 生成完整诊断报告

[1:30-2:30] 溯源功能
1. 展示区块链记录
2. 验证诊断真实性
3. 下载报告永久存储

[2:30-3:30] 历史查询
1. 查看历史记录
2. 切换患者地址
3. 验证历史数据

[3:30-4:30] 技术架构
- 全栈技术栈介绍
- 安全设计
- 扩展性说明

[4:30-5:00] 总结
"MediTrace 为医疗 AI 提供区块链级别的溯源保障"
```

### 4.4 面试 Q&A 准备

#### 4.4.1 技术类问题

**Q1: 为什么选择区块链？**
> A: 医疗数据需要不可篡改的审计轨迹。区块链提供:
> - 不可篡改：一旦上链无法修改
> - 时间戳：精确记录诊断时间
> - 可验证：任何人都能验证真实性

**Q2: IPFS 和传统存储的区别？**
> A: IPFS 提供:
> - 去中心化：数据分布在多个节点
> - 内容寻址：通过哈希定位数据
> - 持久性：不会因单点故障丢失

**Q3: 如何处理隐私问题？**
> A: 我们只存储数据哈希，不存储原始数据:
> - 患者数据加密存储在本地
> - 链上只有哈希值
> - IPFS 报告可设置访问控制

#### 4.4.2 产品类问题

**Q1: 目标用户是谁？**
> A: 三类用户:
> - 患者：获取初步诊断建议
> - 医生：辅助诊断 + 记录存档
> - 监管机构：审查诊断记录

**Q2: 商业价值？**
> A: 满足医疗合规要求:
> - HIPAA 合规审计
> - 医疗纠纷证据
> - 保险理赔依据

---

## 5. 测试覆盖规格

### 5.1 测试框架

**后端**: Pytest  
**前端**: Jest + React Testing Library

### 5.2 测试范围

| 模块 | 测试类型 | 覆盖率目标 |
|------|----------|------------|
| 核心 API | 单元测试 | > 90% |
| 服务层 | 单元测试 | > 80% |
| 前端组件 | 组件测试 | > 70% |
| 端到端流程 | E2E 测试 | 关键路径 |

### 5.3 测试清单

#### 5.3.1 后端测试

```python
# tests/test_diagnosis.py
def test_diagnosis_api_success():
    """测试诊断 API 成功场景"""
    response = client.post("/api/diagnose", json={
        "symptoms": "头痛持续 3 天",
        "userId": "0x123..."
    })
    assert response.status_code == 200
    assert "diagnosisId" in response.json()
    assert "suggestions" in response.json()

def test_diagnosis_api_validation_error():
    """测试诊断 API 参数验证失败"""
    response = client.post("/api/diagnose", json={})
    assert response.status_code == 422

def test_history_query_returns_records():
    """测试历史记录查询"""
    response = client.get("/api/history/0x123...")
    assert response.status_code == 200
    assert "records" in response.json()

def test_conversation_creation():
    """测试多轮对话创建"""
    response = client.post("/api/conversations", json={
        "patientId": "0x123...",
        "title": "头痛诊断"
    })
    assert response.status_code == 200
    assert "conversationId" in response.json()
```

#### 5.3.2 前端测试

```typescript
// __tests__/diagnosis.test.tsx
describe('Diagnosis Page', () => {
  it('renders symptoms input correctly', () => {
    render(<Home />);
    const textarea = screen.getByPlaceholderText(/症状描述/i);
    expect(textarea).toBeInTheDocument();
  });

  it('validates wallet address', () => {
    render(<Home />);
    const input = screen.getByPlaceholderText(/0x/i);
    fireEvent.change(input, { target: { value: 'invalid' } });
    expect(screen.getByText(/必须以 0x 开头/i)).toBeInTheDocument();
  });

  it('displays loading state during diagnosis', async () => {
    render(<Home />);
    fireEvent.click(screen.getByText(/诊断/i));
    expect(screen.getByText(/加载中/i)).toBeInTheDocument();
  });
});
```

### 5.4 测试运行

```bash
# 后端测试
cd src/backend
source venv/bin/activate
pytest tests/ -v --cov=. --cov-report=html

# 前端测试
cd src/frontend
npm test
npm test -- --coverage

# E2E 测试
npm run test:e2e
```

---

## 6. 技术架构设计

### 6.1 系统架构图

```
┌─────────────────────────────────────────────────────────────┐
│                        前端 (Next.js)                        │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐  │
│  │  对话历史列表   │  │  当前对话内容   │  │  输入框     │  │
│  └─────────────────┘  └─────────────────┘  └─────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    后端 (FastAPI)                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ 对话管理 API │  │ 诊断 API     │  │ 区块链客户端        │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │  SQLite DB  │  │ IPFS 服务   │  │ DeepSeek 客户端     │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 6.2 文件结构

```
src/
├── backend/
│   ├── main.py                    # 主应用 (新增对话管理 API)
│   ├── models.py                  # 数据模型 (新增 Conversation 模型)
│   ├── database.py                # 数据库配置 (新增)
│   ├── deepseek_client.py         # AI 客户端
│   ├── blockchain_client.py       # 区块链客户端
│   ├── ipfs_service.py            # IPFS 服务
│   └── tests/                     # 测试文件 (新增)
│       ├── test_diagnosis.py
│       ├── test_conversation.py
│       └── conftest.py
├── frontend/
│   ├── app/
│   │   ├── page.tsx               # 主页 (改造为多轮对话界面)
│   │   ├── history/page.tsx       # 历史记录页
│   │   └── verify/page.tsx        # 验证页
│   ├── lib/
│   │   ├── utils.ts               # 工具函数
│   │   └── api.ts                 # API 客户端 (新增)
│   └── __tests__/                 # 测试文件 (新增)
│       └── diagnosis.test.tsx
└── contracts/
    └── ...                        # 保持不变
```

### 6.3 数据流

```
用户输入症状
    │
    ▼
前端 → POST /api/conversations (创建对话)
    │
    ▼
前端 → POST /api/conversations/{id}/messages (发送消息)
    │
    ▼
后端 → 查询历史对话 (最近 5 轮)
    │
    ▼
后端 → DeepSeek API (携带上下文)
    │
    ▼
后端 → 生成诊断报告 → IPFS 上传
    │
    ▼
后端 → 区块链上链 (包含 IPFS CID)
    │
    ▼
后端 → 返回诊断结果 + 对话历史
    │
    ▼
前端 → 显示 AI 回复 + 更新对话列表
```

---

## 7. 时间规划

### 7.1 任务分解

| 任务 | 子任务 | 预计时间 | 优先级 |
|------|--------|----------|--------|
| **多轮对话实现** | | **4 小时** | P0 |
| - 数据库设计 | 表结构、迁移脚本 | 1 小时 | P0 |
| - 后端 API | 对话管理接口 | 1.5 小时 | P0 |
| - 前端 UI | 左右分栏布局 | 1 小时 | P0 |
| - 上下文集成 | AI 调用携带历史 | 0.5 小时 | P0 |
| **演示材料** | | **3 小时** | P0 |
| - 演示脚本 | 面试 + 产品两套 | 1 小时 | P0 |
| - Q&A 文档 | 技术 + 产品问题 | 1 小时 | P0 |
| - 录屏准备 | 环境配置 + 测试数据 | 1 小时 | P0 |
| **单元测试** | | **2 小时** | P1 |
| - 后端测试 | Pytest + 覆盖率 | 1 小时 | P1 |
| - 前端测试 | Jest + 组件测试 | 1 小时 | P1 |
| **总计** | | **9 小时** | |

### 7.2 时间分配建议

**方案 1: 1 天冲刺**
```
上午 (4 小时):
├── 数据库设计 + 后端 API (2.5 小时)
└── 前端 UI (1.5 小时)

下午 (4 小时):
├── 上下文集成 + 测试 (1 小时)
├── 演示脚本 + Q&A (2 小时)
└── 单元测试 (1 小时)
```

**方案 2: 3 天渐进**
```
Day 1 (3 小时):
└── 多轮对话核心功能

Day 2 (3 小时):
├── 上下文集成
└── 演示材料

Day 3 (3 小时):
└── 单元测试 + 测试数据
```

**方案 3: 1 周随缘**
```
Week 1:
├── Mon: 数据库 + 后端 API
├── Wed: 前端 UI
├── Fri: 上下文集成
└── Weekend: 演示材料 + 测试
```

---

## 8. 验收标准

### 8.1 功能验收

| 标准 | 验证方法 | 通过条件 |
|------|----------|----------|
| 创建新对话 | 调用 API | 返回 conversationId |
| 发送消息 | 调用 API | AI 返回带上下文的回复 |
| 对话历史列表 | 前端展示 | 显示最近 10 条对话 |
| 切换对话 | 点击列表项 | 加载对应对话内容 |
| 刷新持久化 | 刷新浏览器 | 对话历史不丢失 |
| 追问引导 | 触发 AI 回复 | 出现 1-3 个追问问题 |

### 8.2 性能验收

| 标准 | 目标值 | 验证方法 |
|------|--------|----------|
| API 响应时间 | < 3 秒 | 压测工具 |
| 对话加载时间 | < 1 秒 | 浏览器 DevTools |
| 上下文 token 数 | < 10K | API 日志 |

### 8.3 测试验收

| 标准 | 目标值 | 验证方法 |
|------|--------|----------|
| 后端覆盖率 | > 80% | pytest --cov |
| 前端覆盖率 | > 70% | npm test --coverage |
| 关键路径测试 | 100% | E2E 测试 |

### 8.4 演示验收

| 标准 | 目标值 | 验证方法 |
|------|--------|----------|
| 面试演示时长 | 3 分钟 | 计时录制 |
| 产品演示时长 | 5 分钟 | 计时录制 |
| 演示流畅度 | 无卡顿 | 实际演练 |

---

## 📝 附录

### A. 依赖清单

**新增依赖**:
```toml
# backend/requirements.txt
sqlalchemy>=2.0.0  # ORM
alembic>=1.12.0    # 数据库迁移

# frontend/package.json
"@testing-library/react": "^14.0.0"
"jest": "^29.0.0"
```

### B. 环境变量

```env
# .env
DATABASE_URL=sqlite:///./meditrace.db
CONVERSATION_CONTEXT_WINDOW=5
```

### C. 参考文档

- [SPEC.md](../SPEC.md) - 详细规格说明
- [DEVELOPMENT_JOURNEY.md](../DEVELOPMENT_JOURNEY.md) - 开发历程
- [CONTEXT.md](../CONTEXT.md) - 领域模型

---

*文档版本：1.0.0*  
*批准日期：2026-08-27*  
*下一步：开始实现多轮对话功能*
