# MediTrace 多轮对话系统规范

> **规范 ID**: SPEC-0005  
> **版本**: 1.0.0  
> **状态**: Ready for Agent  
> **创建日期**: 2026-08-27  
> **基于**: SPEC_Scheme_A.md  
> **关联功能**: FT-001 多轮对话系统

---

## Problem Statement

作为患者，我目前只能进行单次诊断对话，无法追问诊断细节或补充信息。这导致：
- 我无法深入了解诊断建议的依据
- AI 无法获取足够的上下文信息来提供更准确的建议
- 我需要重复输入相同的信息，体验不完整
- 历史诊断记录无法管理和追溯

## Solution

构建完整的多轮对话系统，支持：
- 用户与 AI 进行 5 轮以上的连续对话
- AI 引用历史对话内容提供连贯的回答
- AI 主动追问补充信息以提高诊断准确性
- 对话历史持久化存储和管理
- 支持多个患者的独立诊断会话

## User Stories

### 核心对话功能

1. 作为患者，我希望创建新的诊断对话，以便开始一次独立的病情咨询
2. 作为患者，我希望在对话中描述我的症状，以便获得 AI 的诊断建议
3. 作为患者，我希望 AI 能理解我的症状描述并返回初步诊断，以便了解可能的病情
4. 作为患者，我希望追问"这种情况严重吗？"，以便评估病情的紧急程度
5. 作为患者，我希望 AI 引用之前的诊断结果来回答我的追问，以便获得连贯的解释
6. 作为患者，我希望 AI 主动问我"症状持续多久了？"，以便补充重要信息
7. 作为患者，我希望 AI 根据我补充的信息更新诊断建议，以便获得更准确的指导
8. 作为患者，我希望用 1-10 分描述疼痛程度，以便 AI 更精确地评估症状
9. 作为患者，我希望告诉 AI 我是否有既往病史，以便考虑长期健康因素
10. 作为患者，我希望 AI 根据诊断置信度动态选择追问方向，以便获得针对性的问题

### 对话历史管理

11. 作为患者，我希望在左侧栏看到历史对话列表，以便快速找到之前的诊断记录
12. 作为患者，我希望点击历史对话项切换内容，以便查看之前的诊断详情
13. 作为患者，我希望看到对话标题（如"头痛诊断"），以便区分不同的咨询主题
14. 作为患者，我希望看到对话的最后更新时间，以便了解记录的时效性
15. 作为患者，我希望列表显示最近的 10 条对话，以便优先查看最新的诊断
16. 作为患者，我希望滚动查看更多历史对话，以便追溯更早的诊断记录
17. 作为患者，我希望点击"新建对话"按钮开始新的咨询，以便开启独立的诊断会话
18. 作为患者，我希望点击"清空历史"按钮删除所有对话，以便清理不需要的记录
19. 作为患者，我希望刷新页面后对话历史不丢失，以便继续之前的对话
20. 作为患者，我希望同时保存多个患者的诊断记录，以便管理家庭成员的健康咨询

### 上下文处理

21. 作为患者，我希望 AI 在回答时引用之前的对话内容，以便理解回答的依据
22. 作为患者，我希望上下文窗口包含最近 5 轮对话，以便平衡信息完整性和响应速度
23. 作为患者，我希望 AI 能记住我之前的症状描述，以便不需要重复输入
24. 作为患者，我希望 AI 能追踪诊断建议的变化，以便了解病情发展
25. 作为患者，我希望上下文 token 数控制在 10K 以内，以便获得稳定的响应

### 追问引导

26. 作为患者，我希望 AI 在置信度低于 70% 时询问症状持续时间，以便提高诊断准确性
27. 作为患者，我希望 AI 在检测到疼痛时询问疼痛程度 (1-10 分)，以便量化症状
28. 作为患者，我希望 AI 在检测到慢性病时询问既往病史，以便考虑长期因素
29. 作为患者，我希望 AI 最多提出 3 个追问问题，以便不会感到被过度询问
30. 作为患者，我希望 AI 根据诊断结果动态选择追问方向，以便获得针对性的问题

### 多诊断会话

31. 作为患者，我希望为每个患者创建独立的对话会话，以便隔离不同人的健康数据
32. 作为患者，我希望通过患者 ID（钱包地址）查询历史记录，以便追溯特定人的诊断
33. 作为患者，我希望同时管理多个诊断会话，以便对比不同时间点的诊断结果
34. 作为患者，我希望每个会话有独立的标题，以便区分不同的咨询主题

### API 使用

35. 作为前端开发者，我希望调用 `POST /api/conversations` 创建对话，以便初始化会话
36. 作为前端开发者，我希望调用 `GET /api/conversations` 获取对话列表，以便渲染历史
37. 作为前端开发者，我希望调用 `GET /api/conversations/{id}` 获取对话详情，以便展示内容
38. 作为前端开发者，我希望调用 `POST /api/conversations/{id}/messages` 发送消息，以便交互
39. 作为前端开发者，我希望调用 `DELETE /api/conversations/{id}` 删除对话，以便清理数据
40. 作为前端开发者，我希望 API 返回标准化的 JSON 格式，以便解析和展示

### 数据持久化

41. 作为系统，我希望将对话存储在 SQLite 数据库中，以便本地持久化
42. 作为系统，我希望在 conversations 表中存储元数据（如诊断 ID、IPFS CID），以便扩展
43. 作为系统，我希望在 messages 表中存储消息内容和上下文引用，以便完整记录
44. 作为系统，我希望按 updated_at 倒序排列对话列表，以便优先显示最新的
45. 作为系统，我希望通过 patient_id 索引查询历史记录，以便快速过滤

### 测试覆盖

46. 作为开发者，我希望测试对话创建 API 返回 conversationId，以便验证功能正确性
47. 作为开发者，我希望测试发送消息返回带上下文的 AI 回复，以便验证上下文处理
48. 作为开发者，我希望测试对话历史列表显示最近 10 条，以便验证数据查询
49. 作为开发者，我希望测试刷新页面后对话不丢失，以便验证持久化
50. 作为开发者，我希望测试追问引导出现 1-3 个问题，以便验证智能追问逻辑
51. 作为开发者，我希望后端测试覆盖率达到 80% 以上，以便保证代码质量
52. 作为开发者，我希望前端测试覆盖率达到 70% 以上，以便保证 UI 可靠性

### 演示需求

53. 作为演示者，我希望在 3 分钟面试演示中展示多轮对话，以便体现技术深度
54. 作为演示者，我希望 AI 引用历史对话的演示在 45 秒内完成，以便控制时长
55. 作为演示者，我希望在产品演示中展示完整的追问流程，以便体现用户体验
56. 作为演示者，我希望演示数据预先准备好，以便避免等待 AI 响应

## Implementation Decisions

### 模块设计

**后端模块 (FastAPI)**:
- **对话管理模块**: 处理对话的 CRUD 操作
- **消息处理模块**: 处理消息发送和上下文组装
- **上下文引擎**: 组装最近 5 轮对话并调用 DeepSeek API
- **数据库层**: SQLAlchemy ORM 模型定义和会话管理

**前端模块 (Next.js)**:
- **对话列表组件**: 左侧栏显示历史对话
- **对话内容组件**: 主区域显示消息流
- **输入框组件**: 用户消息输入和发送
- **API 客户端**: 封装对话相关 API 调用

### 接口设计

**对话创建接口**:
```
POST /api/conversations
Request: { patientId: string, title: string }
Response: { conversationId: string, patientId: string, title: string, createdAt: number }
```

**消息发送接口**:
```
POST /api/conversations/{conversationId}/messages
Request: { content: string, contextWindow: number = 5 }
Response: { 
  messageId: string, 
  content: string, 
  context: string[],  // 引用历史消息
  followUpQuestions: string[]  // 追问问题 (1-3 个)
}
```

**对话列表接口**:
```
GET /api/conversations?patientId={id}&limit=10&offset=0
Response: { 
  conversations: [
    { id, title, createdAt, updatedAt, messageCount }
  ],
  total: number
}
```

### 数据模型

**Conversation 模型**:
```typescript
interface Conversation {
  id: string;              // UUID
  patientId: string;       // 患者钱包地址
  title: string;           // 对话标题 (如"头痛诊断")
  createdAt: number;       // 创建时间戳
  updatedAt: number;       // 最后更新时间戳
  metadata: object;        // 诊断 ID、IPFS CID 等扩展数据
}
```

**Message 模型**:
```typescript
interface Message {
  id: string;              // 消息 ID
  conversationId: string;  // 关联对话
  role: 'user' | 'assistant';
  content: string;         // 消息内容
  timestamp: number;       // 时间戳
  contextRefs: string[];   // 引用历史消息 ID
}
```

### 上下文窗口设计

**窗口大小**: 最近 5 轮对话 (10 条消息)

**原因**:
- 平衡 token 消耗和上下文完整性
- 医疗诊断通常 3-5 轮即可完成
- 避免上下文过长导致 AI 注意力分散

**组装逻辑**:
```
1. 查询 conversation 的最近 10 条消息
2. 过滤掉超过 contextWindow 的消息
3. 组装为 [system, user, assistant, user, assistant...] 格式
4. 附加当前用户消息
5. 调用 DeepSeek API
```

### 追问引导逻辑

**触发条件**:
```python
def generate_follow_up_questions(diagnosis_result):
    questions = []
    
    # 置信度低时询问持续时间
    if diagnosis_result.confidence < 0.7:
        questions.append("症状持续多久了？")
    
    # 检测到疼痛时询问程度
    if "疼痛" in diagnosis_result.symptoms:
        questions.append("疼痛程度 1-10 分是多少？")
    
    # 检测到慢性病时询问病史
    if diagnosis_result.has_chronic_conditions:
        questions.append("您有既往病史吗？")
    
    # 通用追问
    if len(questions) < 3:
        questions.append("还有其他不舒服的地方吗？")
    
    return questions[:3]  # 最多 3 个
```

### 数据库设计

**混合存储方案**: 主表 + JSON 字段

**conversations 表**:
```sql
CREATE TABLE conversations (
    id VARCHAR(36) PRIMARY KEY,
    patient_id VARCHAR(42) NOT NULL,
    title VARCHAR(200) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    metadata JSON,
    INDEX idx_patient_id (patient_id),
    INDEX idx_updated_at (updated_at DESC)
);
```

**messages 表**:
```sql
CREATE TABLE messages (
    id VARCHAR(36) PRIMARY KEY,
    conversation_id VARCHAR(36) NOT NULL,
    role ENUM('user', 'assistant') NOT NULL,
    content TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    context_refs JSON,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
    INDEX idx_conversation (conversation_id, timestamp)
);
```

**选择原因**:
- 支持未来扩展 (图片、附件等)
- 查询灵活 (通过 JSON 字段)
- 开发效率高 (无需过度规范化)

### UI 布局

**左右分栏布局**:
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

### 技术栈

**后端**:
- FastAPI (API 框架)
- SQLAlchemy (ORM)
- SQLite (开发) / PostgreSQL (生产)
- Pytest (测试)

**前端**:
- Next.js 14 (App Router)
- TypeScript
- Tailwind CSS
- Jest + React Testing Library (测试)

### 与现有系统集成

**区块链溯源**: 诊断完成后，将诊断 ID 存入 conversation.metadata
**IPFS 存储**: 报告 CID 存入 conversation.metadata
**DeepSeek 调用**: 在消息处理时携带上下文窗口

## Testing Decisions

### 测试原则

**只测试外部行为，不测试实现细节**:
- ✅ 测试 API 响应格式和内容
- ✅ 测试数据库读写正确性
- ✅ 测试上下文组装逻辑
- ❌ 不测试 SQLAlchemy 内部调用
- ❌ 不测试 DeepSeek API 内部实现

### 后端测试

**测试框架**: Pytest

**测试模块**:
1. **test_conversation.py** - 对话 CRUD 测试
   - test_create_conversation_returns_id
   - test_get_conversations_filters_by_patient
   - test_get_conversation_returns_messages
   - test_delete_conversation_cascades

2. **test_message.py** - 消息处理测试
   - test_send_message_returns_ai_response
   - test_send_message_includes_context
   - test_send_message_generates_follow_ups

3. **test_context_engine.py** - 上下文引擎测试
   - test_context_window_limits_to_5_rounds
   - test_context_assembles_correct_format
   - test_context_handles_empty_history

**覆盖率目标**: > 80%

**运行命令**:
```bash
cd src/backend
pytest tests/ -v --cov=. --cov-report=html
```

### 前端测试

**测试框架**: Jest + React Testing Library

**测试模块**:
1. **ConversationList.test.tsx** - 对话列表组件
   - renders conversation items correctly
   - handles click to switch conversation
   - shows loading state

2. **ConversationView.test.tsx** - 对话内容组件
   - displays user and assistant messages
   - shows follow-up questions
   - handles empty state

3. **MessageInput.test.tsx** - 输入框组件
   - validates input not empty
   - disables button during loading
   - clears input after send

**覆盖率目标**: > 70%

**运行命令**:
```bash
cd src/frontend
npm test -- --coverage
```

### E2E 测试

**测试框架**: Playwright

**关键路径**:
1. 创建新对话 → 发送消息 → 查看 AI 回复
2. 切换对话 → 验证内容加载
3. 刷新页面 → 验证历史不丢失

## Out of Scope

以下功能不在本规范范围内:

1. **医学知识库 RAG** (方案 B 内容)
   - 医学文献检索
   - 专业知识库构建
   - 语义搜索增强

2. **性能优化** (方案 B 内容)
   - 数据库查询优化
   - 缓存策略
   - 并发处理

3. **安全加固** (方案 B 内容)
   - 身份认证
   - 权限控制
   - 数据加密

4. **生产环境部署**
   - Docker 容器化
   - Kubernetes 编排
   - CI/CD 流水线

5. **移动端适配**
   - 响应式布局
   - 触摸交互
   - 离线支持

6. **语音输入**
   - 语音识别
   - 语音合成
   - 语音对话

## Further Notes

### 时间规划

**总计**: 9 小时

| 任务 | 时间 | 优先级 |
|------|------|--------|
| 数据库设计 + 迁移 | 1 小时 | P0 |
| 后端 API 实现 | 1.5 小时 | P0 |
| 前端 UI 实现 | 1 小时 | P0 |
| 上下文集成 | 0.5 小时 | P0 |
| 演示脚本 + Q&A | 2 小时 | P0 |
| 单元测试 | 2 小时 | P1 |

### 验收标准

**功能验收**:
- ✅ 创建新对话返回 conversationId
- ✅ 发送消息返回带上下文的 AI 回复
- ✅ 对话历史列表显示最近 10 条
- ✅ 切换对话加载对应对话内容
- ✅ 刷新页面对话历史不丢失
- ✅ 追问引导出现 1-3 个问题

**性能验收**:
- API 响应时间 < 3 秒
- 对话加载时间 < 1 秒
- 上下文 token 数 < 10K

**测试验收**:
- 后端覆盖率 > 80%
- 前端覆盖率 > 70%
- 关键路径 E2E 测试通过

### 依赖清单

**新增依赖**:
```toml
# backend/requirements.txt
sqlalchemy>=2.0.0
alembic>=1.12.0

# frontend/package.json
"@testing-library/react": "^14.0.0"
"jest": "^29.0.0"
"react-testing-library": "^14.0.0"
```

**环境变量**:
```env
DATABASE_URL=sqlite:///./meditrace.db
CONVERSATION_CONTEXT_WINDOW=5
```

### 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 上下文过长导致 API 超时 | 高 | 限制 5 轮窗口，监控 token 数 |
| 数据库性能瓶颈 | 中 | 添加索引，考虑分页 |
| AI 追问质量不稳定 | 中 | 预设问题模板，动态选择 |
| 前端状态管理复杂 | 低 | 使用 Zustand 简化 |

### 后续迭代

**V2.0 可能功能**:
- 对话导出为 PDF
- 对话分享功能
- 对话标签分类
- 对话搜索功能
- 语音输入支持

---

*规范版本：1.0.0*  
*创建日期：2026-08-27*  
*下一步：开始实现对话管理 API*
