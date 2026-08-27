# 多轮对话系统 - 任务分解

> **关联规范**: SPEC-0005  
> **预计总工时**: 9 小时  
> **优先级**: P0

---

## 阶段一：数据库设计 (1 小时)

### Task 1.1: 设计数据库表结构
- [x] 定义 conversations 表结构
- [x] 定义 messages 表结构
- [x] 添加必要索引
- [ ] 编写 SQL 迁移脚本

**产出**: 
- `src/backend/migrations/001_conversations.sql`

### Task 1.2: 创建 SQLAlchemy 模型
- [ ] 定义 Conversation ORM 模型
- [ ] 定义 Message ORM 模型
- [ ] 添加关系定义 (一对多)
- [ ] 添加序列化方法

**产出**:
- `src/backend/models.py` (新增 Conversation, Message 类)

---

## 阶段二：后端 API 实现 (1.5 小时)

### Task 2.1: 对话管理 API
- [ ] `POST /api/conversations` - 创建新对话
  - 验证 patientId 格式
  - 生成 UUID
  - 保存到数据库
  - 返回对话信息

- [ ] `GET /api/conversations` - 获取对话列表
  - 支持 patientId 过滤
  - 支持分页 (limit/offset)
  - 按 updated_at 倒序

- [ ] `GET /api/conversations/{id}` - 获取对话详情
  - 验证对话存在
  - 返回完整消息列表

- [ ] `DELETE /api/conversations/{id}` - 删除对话
  - 级联删除消息
  - 返回删除结果

**产出**:
- `src/backend/routes/conversations.py`

### Task 2.2: 消息处理 API
- [ ] `POST /api/conversations/{id}/messages` - 发送消息
  - 验证对话存在
  - 保存到数据库
  - 调用上下文引擎
  - 返回 AI 回复 + 追问问题

**产出**:
- `src/backend/routes/messages.py` (或集成到 conversations.py)

### Task 2.3: 上下文引擎
- [ ] 实现上下文组装逻辑
  - 查询最近 N 轮对话
  - 组装为 API 调用格式
  - 限制 token 数量

- [ ] 实现追问引导逻辑
  - 根据诊断结果生成问题
  - 最多返回 3 个问题

**产出**:
- `src/backend/context_engine.py`

---

## 阶段三：前端 UI 实现 (1 小时)

### Task 3.1: 左右分栏布局
- [ ] 创建主布局组件
  - 左侧栏 300px 固定
  - 主内容区自适应

**产出**:
- `src/frontend/src/components/ConversationLayout.tsx`

### Task 3.2: 对话列表组件
- [ ] 显示对话列表项
  - 标题
  - 最后更新时间
  - 消息数量
- [ ] 点击切换对话
- [ ] 新建对话按钮
- [ ] 清空历史按钮

**产出**:
- `src/frontend/src/components/ConversationList.tsx`

### Task 3.3: 对话内容组件
- [ ] 显示消息列表
  - 用户消息 (右侧)
  - AI 消息 (左侧)
  - 追问问题展示
- [ ] 加载状态
- [ ] 错误处理

**产出**:
- `src/frontend/src/components/ConversationView.tsx`

### Task 3.4: 输入框组件
- [ ] 文本输入区域
- [ ] 发送按钮
- [ ] 输入验证
- [ ] 回车发送

**产出**:
- `src/frontend/src/components/MessageInput.tsx`

### Task 3.5: API 客户端
- [ ] 封装对话相关 API 调用
- [ ] 错误处理
- [ ] Loading 状态管理

**产出**:
- `src/frontend/src/lib/api.ts`

---

## 阶段四：上下文集成 (0.5 小时)

### Task 4.1: 连接 DeepSeek 客户端
- [ ] 修改 deepseek_client.py
  - 支持多轮对话上下文
  - 添加 system prompt

- [ ] 集成到消息处理流程
  - 调用上下文引擎
  - 处理流式响应

**产出**:
- `src/backend/deepseek_client.py` (修改)

### Task 4.2: 区块链/IPFS 集成
- [ ] 对话完成后生成诊断报告
- [ ] 上传到 IPFS
- [ ] 记录到区块链
- [ ] 更新 conversation.metadata

**产出**:
- `src/backend/main.py` (修改诊断流程)

---

## 阶段五：演示材料 (2 小时)

### Task 5.1: 面试演示脚本 (3 分钟)
- [ ] 编写演示脚本
  - 开场介绍 (15 秒)
  - 核心功能演示 (45 秒)
  - 技术亮点 (60 秒)
  - 架构说明 (45 秒)
  - 总结 (15 秒)

- [ ] 准备演示数据
  - 预设对话历史
  - 测试症状列表

**产出**:
- `docs/DEMO_SCRIPT_INTERVIEW.md`

### Task 5.2: 产品演示脚本 (5 分钟)
- [ ] 编写演示脚本
  - 问题背景 (30 秒)
  - 解决方案 (60 秒)
  - 溯源功能 (60 秒)
  - 历史查询 (60 秒)
  - 技术架构 (60 秒)
  - 总结 (30 秒)

**产出**:
- `docs/DEMO_SCRIPT_PRODUCT.md`

### Task 5.3: 面试 Q&A 文档
- [ ] 技术类问题准备
  - 为什么选择区块链
  - IPFS vs 传统存储
  - 隐私处理方案

- [ ] 产品类问题准备
  - 目标用户
  - 商业价值
  - 合规性

**产出**:
- `docs/INTERVIEW_QA.md`

---

## 阶段六：单元测试 (2 小时)

### Task 6.1: 后端测试
- [ ] 配置 Pytest
  - 安装依赖
  - 配置 fixtures
  - 配置覆盖率

- [ ] test_conversation.py
  - test_create_conversation
  - test_get_conversations
  - test_delete_conversation

- [ ] test_message.py
  - test_send_message
  - test_context_assembly
  - test_follow_up_questions

- [ ] test_api.py
  - test_api_endpoints
  - test_error_handling

**产出**:
- `src/backend/tests/test_conversation.py`
- `src/backend/tests/test_message.py`
- `src/backend/tests/test_api.py`

### Task 6.2: 前端测试
- [ ] 配置 Jest + RTL
  - 安装依赖
  - 配置测试环境

- [ ] ConversationList.test.tsx
  - renders correctly
  - handles click
  - shows loading

- [ ] ConversationView.test.tsx
  - displays messages
  - shows follow-ups
  - handles empty state

- [ ] MessageInput.test.tsx
  - validates input
  - handles send
  - disables during loading

**产出**:
- `src/frontend/__tests__/ConversationList.test.tsx`
- `src/frontend/__tests__/ConversationView.test.tsx`
- `src/frontend/__tests__/MessageInput.test.tsx`

### Task 6.3: E2E 测试
- [ ] 配置 Playwright
- [ ] 编写关键路径测试
  - 创建对话 → 发送消息 → 查看回复
  - 切换对话 → 验证内容
  - 刷新页面 → 验证持久化

**产出**:
- `src/frontend/e2e/conversation.spec.ts`

---

## 验收检查清单

### 功能验收
- [ ] 创建新对话返回 conversationId
- [ ] 发送消息返回带上下文的 AI 回复
- [ ] 对话历史列表显示最近 10 条
- [ ] 切换对话加载对应对话内容
- [ ] 刷新页面对话历史不丢失
- [ ] 追问引导出现 1-3 个问题

### 性能验收
- [ ] API 响应时间 < 3 秒
- [ ] 对话加载时间 < 1 秒
- [ ] 上下文 token 数 < 10K

### 测试验收
- [ ] 后端覆盖率 > 80%
- [ ] 前端覆盖率 > 70%
- [ ] 所有 E2E 测试通过

### 演示验收
- [ ] 面试演示脚本完成
- [ ] 产品演示脚本完成
- [ ] Q&A 文档完成

---

## 时间分配建议

### 方案 A: 1 天冲刺
```
上午 (4 小时):
├── 数据库设计 (1h)
├── 后端 API (1.5h)
└── 前端 UI (1.5h)

下午 (4 小时):
├── 上下文集成 (0.5h)
├── 演示材料 (2h)
└── 单元测试 (1.5h)
```

### 方案 B: 3 天渐进
```
Day 1 (3 小时):
└── 多轮对话核心功能 (数据库 + 后端 + 前端)

Day 2 (3 小时):
├── 上下文集成 (0.5h)
└── 演示材料 (2.5h)

Day 3 (3 小时):
└── 单元测试 + 测试数据
```

---

## 依赖关系

```
数据库设计 → 后端 API → 前端 UI → 上下文集成
                                    ↓
                            演示材料 ← 单元测试
```

---

*创建日期：2026-08-27*  
*最后更新：2026-08-27*
