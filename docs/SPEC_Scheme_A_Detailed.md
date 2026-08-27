# MediTrace 方案 A - 详细技术规格文档

> **版本**: 2.0.0  
> **状态**: 详细规格  
> **最后更新**: 2026-08-27  
> **基于**: SPEC_Scheme_A.md v1.0.0

---

## 📋 文档概览

本文档将 `SPEC_Scheme_A.md` 中的高层需求细化为**可执行的技术规格**，包含：
- ✅ 详细的用户故事列表（50+ 条）
- ✅ 完整的 API 接口定义
- ✅ 数据库 Schema 细节
- ✅ 前端组件规格
- ✅ 测试用例清单
- ✅ 实现决策记录

---

## 1. 问题陈述

### 1.1 当前痛点

从用户视角：

> **作为患者**, 我现在只能进行一次性的诊断问答，无法追问细节，导致：
> 1. 诊断结果不够个性化
> 2. 无法了解病情发展
> 3. 需要重新输入所有症状信息
>
> **作为面试官**, 我现在无法看到完整的项目演示，导致：
> 1. 无法评估用户体验
> 2. 看不到多轮交互能力
> 3. 缺乏工程严谨性证明（测试）

### 1.2 解决方案概述

通过实现**多轮对话系统** + **演示材料** + **单元测试**，让项目达到"可演示、可面试"状态。

---

## 2. 用户故事清单

### 2.1 核心功能 - 多轮对话 (FT-001)

#### 对话管理

1. **作为患者**, 我想创建新的诊断对话，以便开始新的健康咨询
2. **作为患者**, 我想看到所有历史对话列表，以便找到之前的诊断记录
3. **作为患者**, 我想切换不同的对话，以便查看不同时间点的诊断
4. **作为患者**, 我想给对话起标题，以便区分不同的诊断场景
5. **作为患者**, 我想删除不需要的对话，以便清理历史记录
6. **作为患者**, 我想刷新页面后对话历史不丢失，以便继续之前的对话
7. **作为患者**, 我想看到对话创建时间，以便了解诊断的时间点
8. **作为患者**, 我想看到对话最后更新时间，以便知道最近的交互
9. **作为患者**, 我想看到每个对话的简要预览，以便快速识别对话内容
10. **作为患者**, 我想限制对话列表显示数量（最近 10 条），以便界面不会过于拥挤

#### 消息交互

11. **作为患者**, 我想输入症状描述，以便获得 AI 诊断建议
12. **作为患者**, 我想看到 AI 的回复，以便了解诊断结果
13. **作为患者**, 我想在输入框看到占位符提示，以便知道如何描述症状
14. **作为患者**, 我想看到发送按钮，以便提交我的症状描述
15. **作为患者**, 我想在发送时看到加载状态，以便知道系统正在处理
16. **作为患者**, 我想在发送失败时看到错误提示，以便知道问题所在
17. **作为患者**, 我想看到消息的时间戳，以便了解对话的时间线
18. **作为患者**, 我想区分用户消息和 AI 消息（不同样式），以便清晰识别对话角色
19. **作为患者**, 我想复制 AI 的诊断建议，以便保存或分享给医生
20. **作为患者**, 我想滚动查看完整的对话历史，以便回顾之前的交流

#### 上下文感知

21. **作为患者**, 我想 AI 能引用我之前说的症状，以便不需要重复输入
22. **作为患者**, 我想 AI 能记住我的病史信息，以便提供更准确的诊断
23. **作为患者**, 我想 AI 能基于之前的诊断结果回答追问，以便获得连贯的建议
24. **作为患者**, 我想上下文窗口限制在最近 5 轮对话，以便 AI 聚焦最近的交流
25. **作为患者**, 我想看到 AI 引用了哪些历史消息，以便理解回答的依据

#### 追问引导

26. **作为患者**, 我想 AI 主动询问症状持续时间，以便提供更精确的诊断
27. **作为患者**, 我想 AI 主动询问症状严重程度，以便评估紧急程度
28. **作为患者**, 我想 AI 主动询问相关症状，以便发现潜在问题
29. **作为患者**, 我想 AI 主动询问既往病史，以便考虑慢性病史影响
30. **作为患者**, 我想 AI 根据诊断结果智能选择追问方向，以便获得最相关的信息
31. **作为患者**, 我想 AI 最多提出 3 个追问问题，以便不会过于冗长
32. **作为患者**, 我想可以回答追问问题，以便补充诊断所需信息
33. **作为患者**, 我想 AI 根据我的回答更新诊断建议，以便获得更准确的结果

#### 多患者支持

34. **作为医生**, 我想为不同患者创建对话，以便管理多个病人的诊断记录
35. **作为医生**, 我想通过患者地址区分对话，以便确保数据隔离
36. **作为医生**, 我想查看某个患者的所有对话历史，以便追踪病情发展
37. **作为医生**, 我想在不同患者的对话间切换，以便对比不同病例

### 2.2 演示材料 (DM-001)

#### 面试演示

38. **作为求职者**, 我想有 3 分钟的面试演示脚本，以便在技术面试中展示项目
39. **作为求职者**, 我想演示突出技术亮点，以便展示全栈能力
40. **作为求职者**, 我想演示包含区块链溯源流程，以便展示 Web3 技能
41. **作为求职者**, 我想演示包含多轮对话功能，以便展示用户体验设计
42. **作为求职者**, 我想演示包含 IPFS 存储，以便展示去中心化技术
43. **作为求职者**, 我想准备技术类 Q&A，以便回答面试官的技术问题
44. **作为求职者**, 我想准备产品类 Q&A，以便回答商业价值问题

#### 产品演示

45. **作为产品经理**, 我想有 5 分钟的产品演示脚本，以便向投资人展示
46. **作为产品经理**, 我想演示突出用户体验，以便展示产品价值
47. **作为产品经理**, 我想演示包含完整端到端流程，以便展示系统完整性
48. **作为产品经理**, 我想演示包含历史查询功能，以便展示数据管理

### 2.3 测试覆盖 (TC-001)

#### 后端测试

49. **作为开发者**, 我想有核心 API 的单元测试，以便确保功能正确
50. **作为开发者**, 我想测试诊断 API 成功场景，以便验证正常流程
51. **作为开发者**, 我想测试诊断 API 参数验证失败，以便验证错误处理
52. **作为开发者**, 我想测试历史记录查询，以便验证数据检索
53. **作为开发者**, 我想测试对话创建，以便验证多轮对话功能
54. **作为开发者**, 我想测试消息发送，以便验证上下文传递
55. **作为开发者**, 我想达到 80% 以上的代码覆盖率，以便确保代码质量

#### 前端测试

56. **作为开发者**, 我想有前端组件的单元测试，以便确保 UI 正确
57. **作为开发者**, 我想测试症状输入框渲染，以便验证表单组件
58. **作为开发者**, 我想测试钱包地址验证，以便验证输入校验
59. **作为开发者**, 我想测试加载状态显示，以便验证异步交互
60. **作为开发者**, 我想达到 70% 以上的代码覆盖率，以便确保代码质量

### 2.4 非功能性需求

61. **作为用户**, 我想 API 响应时间小于 3 秒，以便获得流畅体验
62. **作为用户**, 我想对话加载时间小于 1 秒，以便快速查看历史
63. **作为用户**, 我想上下文 token 数小于 10K，以便控制 API 成本
64. **作为系统**, 我想支持并发对话，以便多个用户同时使用
65. **作为系统**, 我想数据库查询有索引，以便保证性能

---

## 3. 实现决策

### 3.1 模块设计

#### 新增模块

**1. 数据库模块 (`database.py`)**

```
职责：数据库连接管理、会话管理、迁移支持
接口:
  - get_db_session() -> Session
  - init_db() -> None
  - migrate_db() -> None
依赖: SQLAlchemy 2.0, Alembic 1.12+
```

**2. 对话管理模块 (`conversation_service.py`)**

```
职责：对话 CRUD、消息管理、上下文检索
接口:
  - create_conversation(patient_id, title) -> Conversation
  - get_conversations(patient_id, limit=10) -> List[Conversation]
  - get_conversation(conversation_id) -> Conversation
  - add_message(conversation_id, role, content) -> Message
  - get_context_messages(conversation_id, window=5) -> List[Message]
  - delete_conversation(conversation_id) -> None
依赖：database.py
```

**3. API 客户端模块 (`api_client.ts`)**

```
职责：前端 API 调用封装、错误处理、重试机制
接口:
  - createConversation(data) -> Promise<Conversation>
  - getConversations(patientId) -> Promise<Conversation[]>
  - getConversation(conversationId) -> Promise<Conversation>
  - sendMessage(conversationId, content) -> Promise<Message>
  - deleteConversation(conversationId) -> Promise<void>
依赖：fetch API
```

#### 修改模块

**1. 主应用 (`main.py`)**

```
修改内容:
  - 新增对话管理路由组 /api/conversations/*
  - 修改诊断 API 支持对话 ID 参数
  - 新增上下文注入逻辑
影响：现有诊断流程向后兼容
```

**2. DeepSeek 客户端 (`deepseek_client.py`)**

```
修改内容:
  - 新增 send_with_context 方法
  - 支持历史消息传入
  - 自动计算 token 消耗
影响：现有 diagnose 方法保持不变
```

**3. 主页 (`page.tsx`)**

```
修改内容:
  - 改造为左右分栏布局
  - 新增对话列表组件
  - 新增消息列表组件
  - 新增输入框组件
影响：保留现有诊断功能，增强交互
```

### 3.2 接口定义

#### API 接口规范

**POST /api/conversations**

```typescript
// 请求
interface CreateConversationRequest {
  patientId: string;      // 必填，以太坊地址格式
  title: string;          // 必填，最大 200 字符
}

// 响应
interface CreateConversationResponse {
  conversationId: string; // UUID 格式
  patientId: string;
  title: string;
  createdAt: number;      // Unix 时间戳（秒）
  updatedAt: number;
}

// 错误码
400: "Invalid patientId format"
422: "Validation error"
500: "Internal server error"
```

**GET /api/conversations**

```typescript
// 请求参数
interface GetConversationsQuery {
  patientId: string;      // 必填
  limit?: number;         // 可选，默认 10，最大 50
  offset?: number;        // 可选，默认 0
}

// 响应
interface GetConversationsResponse {
  conversations: ConversationItem[];
  total: number;
  hasMore: boolean;
}

interface ConversationItem {
  conversationId: string;
  title: string;
  createdAt: number;
  updatedAt: number;
  messageCount: number;
  lastMessagePreview: string; // 最后一条消息的前 50 字符
}
```

**POST /api/conversations/{conversationId}/messages**

```typescript
// 请求
interface SendMessageRequest {
  content: string;        // 必填，最大 5000 字符
  contextWindow?: number; // 可选，默认 5，最大 20
}

// 响应
interface SendMessageResponse {
  messageId: string;
  conversationId: string;
  userMessage: Message;
  aiMessage: Message;
  contextUsed: Message[]; // 使用的上下文消息
  followUpQuestions?: string[]; // 追问问题（最多 3 个）
  diagnosisUpdate?: DiagnosisResult; // 诊断更新（如果有）
}

interface Message {
  messageId: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
  references?: string[]; // 引用历史消息 ID
}
```

### 3.3 数据库 Schema

#### conversations 表

```sql
CREATE TABLE conversations (
    -- 主键
    id VARCHAR(36) PRIMARY KEY COMMENT 'UUID 格式',
    
    -- 外键关联
    patient_id VARCHAR(42) NOT NULL COMMENT '以太坊地址',
    
    -- 基本字段
    title VARCHAR(200) NOT NULL COMMENT '对话标题',
    
    -- 时间字段
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    
    -- 元数据（JSON 格式）
    metadata JSON COMMENT '{
      "diagnosisId": "链上诊断 ID",
      "ipfsCid": "IPFS CID",
      "chainTxHash": "链上交易哈希",
      "modelVersion": "AI 模型版本",
      "totalTokens": 1234
    }',
    
    -- 索引
    INDEX idx_patient_id (patient_id),
    INDEX idx_updated_at (updated_at DESC),
    INDEX idx_created_at (created_at DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='对话主表';
```

#### messages 表

```sql
CREATE TABLE messages (
    -- 主键
    id VARCHAR(36) PRIMARY KEY COMMENT 'UUID 格式',
    
    -- 外键关联
    conversation_id VARCHAR(36) NOT NULL COMMENT '关联对话 ID',
    
    -- 消息内容
    role ENUM('user', 'assistant') NOT NULL COMMENT '消息角色',
    content TEXT NOT NULL COMMENT '消息内容',
    
    -- 上下文引用
    context_refs JSON COMMENT '引用的历史消息 ID 数组',
    
    -- AI 元数据
    ai_metadata JSON COMMENT '{
      "tokens": 234,
      "model": "deepseek-v4-flash",
      "followUpQuestions": ["问题 1", "问题 2"],
      "diagnosisUpdate": {...}
    }',
    
    -- 时间字段
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '消息时间',
    
    -- 索引
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
    INDEX idx_conversation_time (conversation_id, timestamp)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='消息表';
```

### 3.4 前端组件规格

#### ConversationList 组件

```typescript
interface ConversationListProps {
  patientId: string;
  onSelectConversation: (conversationId: string) => void;
  onNewConversation: () => void;
  selectedConversationId?: string;
}

// 状态管理
interface ConversationListState {
  conversations: ConversationItem[];
  loading: boolean;
  error: string | null;
  hasMore: boolean;
  offset: number;
}

// 交互行为
- 初始化时加载最近 10 条对话
- 滚动到底部时加载更多（分页）
- 点击对话项触发 onSelectConversation
- 点击新建按钮触发 onNewConversation
- 下拉刷新重新加载
- 高亮显示当前选中的对话
```

#### MessageList 组件

```typescript
interface MessageListProps {
  messages: Message[];
  isLoading?: boolean;
  followUpQuestions?: string[];
}

// 样式规范
- 用户消息：右侧对齐，蓝色背景
- AI 消息：左侧对齐，灰色背景
- 时间戳：消息下方，小字号，灰色
- 引用高亮：被引用的历史消息用特殊边框标识
- 追问问题：可点击的按钮样式

// 交互行为
- 自动滚动到底部（新消息到达时）
- 支持复制消息内容
- 支持点击查看引用详情
```

#### ConversationInput 组件

```typescript
interface ConversationInputProps {
  onSubmit: (content: string) => void;
  disabled?: boolean;
  placeholder?: string;
}

// 状态管理
interface ConversationInputState {
  content: string;
  isSubmitting: boolean;
  error: string | null;
}

// 交互行为
- Enter 键发送（Shift+Enter 换行）
- 内容验证（非空、长度限制）
- 发送时禁用输入框
- 显示字符计数（0/5000）
- 错误提示悬浮显示
```

### 3.5 上下文传递逻辑

#### 上下文构建算法

```python
def build_context_messages(
    conversation_id: str,
    window_size: int = 5
) -> List[Dict]:
    """
    构建 AI 上下文消息列表
    
    策略:
    1. 获取最近 window_size 轮对话（用户+AI 各半）
    2. 按时间正序排列
    3. 添加系统提示词
    4. 计算总 token 数，不超过 10K
    """
    
    # 1. 查询最近消息
    messages = db.query(
        "SELECT * FROM messages WHERE conversation_id = ? ORDER BY timestamp DESC LIMIT ?",
        [conversation_id, window_size * 2]
    )
    
    # 2. 反转成正序
    messages = messages[::-1]
    
    # 3. 构建上下文
    context = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT  # 医疗诊断助手提示词
        }
    ]
    
    for msg in messages:
        context.append({
            "role": msg.role,
            "content": msg.content,
            "timestamp": msg.timestamp
        })
    
    # 4. Token 检查
    total_tokens = estimate_tokens(context)
    if total_tokens > 10000:
        # 截断最旧的上下文
        context = truncate_to_token_limit(context, 10000)
    
    return context
```

#### 追问生成逻辑

```python
def generate_follow_up_questions(
    diagnosis_result: DiagnosisResult,
    conversation_history: List[Message]
) -> List[str]:
    """
    根据诊断结果生成追问问题
    
    规则:
    1. 置信度低 (<0.7) → 询问持续时间
    2. 包含疼痛 → 询问严重程度
    3. 可能慢性病 → 询问病史
    4. 症状复杂 → 询问其他并发症状
    5. 最多返回 3 个问题
    """
    
    questions = []
    
    # 规则 1: 置信度低
    if diagnosis_result.confidence < 0.7:
        questions.append("这种情况持续多久了？")
    
    # 规则 2: 包含疼痛
    if any(keyword in diagnosis_result.symptoms for keyword in ["痛", "疼", "难受"]):
        questions.append("如果用 1-10 分评分，您觉得有多严重？")
    
    # 规则 3: 可能慢性病
    if diagnosis_result.has_potential_chronic:
        questions.append("您之前有过类似的情况吗？是否有相关病史？")
    
    # 规则 4: 症状复杂
    if len(diagnosis_result.suggestions) > 3:
        questions.append("还有其他不舒服的地方吗？")
    
    # 规则 5: 限制数量
    return questions[:3]
```

---

## 4. 测试决策

### 4.1 测试原则

**只测试外部行为，不测试实现细节**

```python
# ✅ 好的测试
def test_diagnosis_api_returns_suggestions():
    """验证 API 返回诊断建议"""
    response = client.post("/api/diagnose", json={...})
    assert response.status_code == 200
    assert "suggestions" in response.json()

# ❌ 坏的测试
def test_diagnosis_calls_deepseek_client():
    """不应该测试内部调用"""
    with patch("deepseek_client.call") as mock:
        ...
```

### 4.2 测试清单

#### 后端测试文件

```
tests/
├── conftest.py                    # 测试配置和 fixture
├── test_diagnosis.py              # 诊断 API 测试
│   ├── test_diagnosis_success
│   ├── test_diagnosis_validation_error
│   ├── test_diagnosis_ipfs_failure
│   └── test_diagnosis_chain_failure
├── test_conversation.py           # 对话管理测试
│   ├── test_create_conversation
│   ├── test_get_conversations
│   ├── test_get_conversation
│   ├── test_add_message
│   ├── test_get_context_messages
│   └── test_delete_conversation
├── test_follow_up.py              # 追问生成测试
│   ├── test_follow_up_low_confidence
│   ├── test_follow_up_pain_symptom
│   ├── test_follow_up_chronic_condition
│   └── test_follow_up_max_3_questions
└── integration/
    └── test_full_diagnosis_flow.py # 端到端流程测试
```

#### 前端测试文件

```
__tests__/
├── diagnosis.test.tsx             # 诊断页面测试
│   ├── test_symptoms_input_render
│   ├── test_wallet_address_validation
│   ├── test_loading_state_display
│   └── test_diagnosis_result_display
├── conversation_list.test.tsx     # 对话列表测试
│   ├── test_conversation_list_render
│   ├── test_conversation_selection
│   ├── test_new_conversation_button
│   └── test_conversation_pagination
├── message_list.test.tsx          # 消息列表测试
│   ├── test_message_render
│   ├── test_user_vs_ai_styling
│   ├── test_follow_up_questions_display
│   └── test_auto_scroll_to_bottom
└── conversation_input.test.tsx    # 输入框测试
    ├── test_input_render
    ├── test_enter_key_submit
    ├── test_character_counter
    └── test_error_display
```

### 4.3 测试数据

#### Fixture 数据

```python
# conftest.py

@pytest.fixture
def sample_patient_id():
    return "0x262Ee58D3e7A782ceC68094A6DACb53D02Fa9d0B"

@pytest.fixture
def sample_conversation_data():
    return {
        "patientId": "0x262Ee58D3e7A782ceC68094A6DACb53D02Fa9d0B",
        "title": "头痛诊断"
    }

@pytest.fixture
def sample_message_data():
    return {
        "content": "我头痛已经 3 天了，伴有轻微发烧",
        "contextWindow": 5
    }

@pytest.fixture
def sample_diagnosis_result():
    return {
        "confidence": 0.65,
        "symptoms": "头痛、发烧",
        "has_potential_chronic": False
    }
```

---

## 5. 范围边界

### 5.1 包含范围

✅ **本次实现**

| 模块 | 功能点 | 完成标准 |
|------|--------|----------|
| 数据库 | Schema 设计 + 迁移脚本 | 表创建成功 |
| 后端 API | 5 个对话管理接口 | 所有接口通过测试 |
| 前端 UI | 左右分栏布局 + 3 个组件 | 页面可交互 |
| 上下文 | 最近 5 轮对话传递 | AI 能引用历史 |
| 追问 | 5 种场景 + 最多 3 个问题 | 追问正确触发 |
| 测试 | 后端 + 前端单元测试 | 覆盖率达标 |
| 演示 | 2 套脚本 + Q&A 文档 | 可流畅演示 |

### 5.2 排除范围

❌ **本次不实现**

| 功能 | 原因 | 后续计划 |
|------|------|----------|
| 医学知识库 RAG | 属于方案 B | 方案 B Day 1 |
| 图片/附件上传 | 超出 MVP 范围 | 方案 B 扩展 |
| 实时通知 | 非核心功能 | 方案 C |
| 用户认证系统 | 超出范围 | 方案 C |
| 性能优化 (Redis 缓存) | 当前性能足够 | 方案 B Day 3 |
| 安全加固 (私钥加密) | 开发环境优先 | 方案 B Day 4 |
| 生产环境部署 | 本次不部署 | 单独任务 |

---

## 6. 实现优先级

### 6.1 阶段 1: 基础设施 (2 小时)

```
优先级：P0 (阻塞后续)
任务:
  1. 创建数据库表 (30 分钟)
  2. 创建 database.py 模块 (30 分钟)
  3. 创建 conversation_service.py (1 小时)
验收标准:
  - 数据库表创建成功
  - 服务层方法可调用
  - 基础测试通过
```

### 6.2 阶段 2: 后端 API (1.5 小时)

```
优先级：P0 (阻塞前端)
任务:
  1. 创建对话管理路由 (45 分钟)
  2. 修改诊断 API 支持对话 ID (30 分钟)
  3. 实现追问生成逻辑 (15 分钟)
验收标准:
  - 所有 API 接口可调用
  - API 测试通过
  - 文档更新
```

### 6.3 阶段 3: 前端 UI (1 小时)

```
优先级：P0 (用户可见)
任务:
  1. 改造主页为左右分栏 (30 分钟)
  2. 实现 3 个核心组件 (30 分钟)
验收标准:
  - 页面可交互
  - 样式正确
  - 组件测试通过
```

### 6.4 阶段 4: 上下文集成 (0.5 小时)

```
优先级：P0 (核心功能)
任务:
  1. 实现上下文构建逻辑 (30 分钟)
验收标准:
  - AI 能引用历史消息
  - Token 数控制在 10K 内
```

### 6.5 阶段 5: 测试补充 (1 小时)

```
优先级：P1 (质量保障)
任务:
  1. 补充后端测试 (30 分钟)
  2. 补充前端测试 (30 分钟)
验收标准:
  - 后端覆盖率 > 80%
  - 前端覆盖率 > 70%
```

### 6.6 阶段 6: 演示材料 (1 小时)

```
优先级：P0 (面试必备)
任务:
  1. 完善演示脚本 (30 分钟)
  2. 整理 Q&A 文档 (30 分钟)
验收标准:
  - 脚本可流畅演示
  - Q&A 覆盖常见问题
```

---

## 7. 风险与缓解

### 7.1 技术风险

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|----------|
| 数据库性能问题 | 中 | 中 | 添加索引，监控查询速度 |
| Token 数超限 | 低 | 中 | 实现截断逻辑，提前计算 |
| AI 上下文理解错误 | 中 | 低 | 优化系统提示词，A/B 测试 |
| 前端状态管理复杂 | 低 | 低 | 使用简化状态管理 |

### 7.2 进度风险

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|----------|
| 时间不足 | 中 | 高 | 优先实现 P0 功能 |
| 需求变更 | 低 | 中 | 保持文档更新 |
| 技术难点卡住 | 中 | 中 | 准备简化方案 |

---

## 8. 参考文档

- [SPEC_Scheme_A.md](./SPEC_Scheme_A.md) - 高层需求规格
- [SPEC.md](../SPEC.md) - 完整项目规格
- [CONTEXT.md](../CONTEXT.md) - 领域模型
- [CODING_STANDARDS.md](../CODING_STANDARDS.md) - 代码规范
- [DEPLOYMENT.md](../DEPLOYMENT.md) - 部署指南

---

*文档版本：2.0.0*  
*创建日期：2026-08-27*  
*下一步：开始阶段 1 实现*
