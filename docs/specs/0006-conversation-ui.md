# MediTrace 多轮对话 UI 规格

> **规范 ID**: SPEC-0006  
> **版本**: 1.0.0  
> **状态**: Ready for Agent  
> **创建日期**: 2026-08-27  
> **基于**: SPEC-0005 多轮对话系统  
> **关联功能**: FT-002 对话 UI 界面

---

## Problem Statement

作为患者，我目前只能看到单次的诊断表单和结果页面，无法：
- 进行多轮连续对话来补充症状信息
- 查看和管理历史诊断会话
- 在对话中追问诊断细节
- 获得类似真实医生问诊的交互体验

这导致诊断体验不完整，用户无法充分利用 AI 诊断系统的价值。

---

## Solution

构建现代化的对话式 UI 界面，支持：
- 左右分栏布局：左侧对话历史，右侧对话内容
- 实时消息流式展示
- 上下文感知的 AI 回复
- 智能追问引导
- 完整的会话管理（创建、切换、删除）

---

## User Stories

### 布局与导航

1. 作为患者，我希望看到左右分栏的对话界面，以便同时查看历史对话和当前内容
2. 作为患者，我希望左侧栏宽度可调整，以便根据个人偏好优化布局
3. 作为患者，我希望在移动端看到单栏布局，以便在小屏幕上正常使用
4. 作为患者，我希望看到清晰的导航标题（如"MediTrace 对话"），以便知道当前位置

### 对话历史列表（左侧栏）

5. 作为患者，我希望在左侧栏看到历史对话列表，以便快速找到之前的诊断
6. 作为患者，我希望每个对话项显示标题（如"头痛诊断"），以便区分不同主题
7. 作为患者，我希望看到对话的最后消息时间，以便了解时效性
8. 作为患者，我希望看到未读消息数量徽章，以便知道是否有新内容
9. 作为患者，我希望点击对话项切换内容，以便查看历史诊断详情
10. 作为患者，我希望当前选中的对话有高亮显示，以便知道正在查看哪个
11. 作为患者，我希望对话列表按时间倒序排列，以便优先看到最新的
12. 作为患者，我希望列表支持滚动加载，以便查看更多历史对话
13. 作为患者，我希望在空列表时看到引导提示，以便知道如何开始

### 新建对话

14. 作为患者，我希望在左侧栏顶部看到"新建对话"按钮，以便开始新的诊断
15. 作为患者，我希望点击后自动创建新对话并清空右侧内容，以便开始独立咨询
16. 作为患者，我希望新建时能输入初始症状描述，以便快速启动对话
17. 作为患者，我希望新建对话自动聚焦到输入框，以便快速输入

### 对话内容区域（右侧主区域）

18. 作为患者，我希望看到对话的消息列表，以便了解问诊过程
19. 作为患者，我希望用户消息显示在右侧，AI 消息显示在左侧，以便区分角色
20. 作为患者，我希望每条消息显示时间戳，以便了解对话时序
21. 作为患者，我希望消息内容支持 Markdown 格式，以便看到结构化的诊断结果
22. 作为患者，我希望 AI 回复支持流式展示，以便看到实时生成过程
23. 作为患者，我希望看到消息的加载状态，以便知道正在处理中
24. 作为患者，我希望错误消息用红色高亮显示，以便注意到问题
25. 作为患者，我希望对话内容自动滚动到最新消息，以便不需要手动滚动

### 输入区域（底部）

26. 作为患者，我希望在底部看到输入框，以便发送消息
27. 作为患者，我希望输入框支持多行文本，以便详细描述症状
28. 作为患者，我希望按 Enter 发送消息，Shift+Enter 换行，以便快速输入
29. 作为患者，我希望输入框为空时禁用发送按钮，防止空消息
30. 作为患者，我希望看到字符计数（如"0/500"），以便控制消息长度
31. 作为患者，我希望发送按钮有 loading 状态，以便知道请求进行中
32. 作为患者，我希望发送后自动清空输入框，以便准备下一条消息

### 追问问题展示

33. 作为患者，我希望 AI 回复后看到追问问题列表，以便快速补充信息
34. 作为患者，我希望追问问题以按钮形式展示，以便一键发送
35. 作为患者，我希望点击追问问题自动填充到输入框，以便确认后再发送
36. 作为患者，我希望追问问题最多显示 3 个，以免界面过于拥挤

### 诊断结果展示

37. 作为患者，我希望 AI 返回的诊断结果以卡片形式展示，以便清晰阅读
38. 作为患者，我希望看到可能的疾病列表及置信度，以便了解诊断方向
39. 作为患者，我希望看到建议检查项目，以便准备就医
40. 作为患者，我希望看到免责声明，以便理解 AI 建议的局限性
41. 作为患者，我希望诊断结果支持展开/收起，以便控制信息密度

### 会话管理

42. 作为患者，我希望在对话标题处看到"删除"按钮，以便清理不需要的对话
43. 作为患者，我希望删除前弹出确认对话框，防止误删
44. 作为患者，我希望删除后自动切换到其他对话或新建对话，保持界面可用
45. 作为患者，我希望刷新页面后保持当前对话，不丢失上下文

### 响应式设计

46. 作为患者，我希望在平板上看到自适应布局，以便在不同设备上使用
47. 作为患者，我希望在手机上看到汉堡菜单切换历史列表，以便小屏操作
48. 作为患者，我希望触摸设备支持滑动操作，以便更自然的交互

### 性能与体验

49. 作为患者，我希望页面加载时先显示骨架屏，以便知道正在加载
50. 作为患者，我希望消息发送后 1 秒内收到响应，以便获得流畅体验
51. 作为患者，我希望网络错误时看到重试按钮，以便恢复连接
52. 作为患者，我希望长时间对话时支持分页加载，避免卡顿

---

## Implementation Decisions

### 技术栈

- **框架**: Next.js 14 (App Router)
- **语言**: TypeScript
- **UI 组件**: Shadcn/ui + Tailwind CSS
- **状态管理**: React Context + useReducer
- **HTTP 客户端**: fetch API + SWR
- **Markdown 渲染**: react-markdown
- **流式处理**: Server-Sent Events (SSE)

### 模块设计

#### 1. 对话 API 客户端 (`src/frontend/lib/api/conversations.ts`)

封装所有对话相关的 API 调用：

```typescript
interface ConversationAPI {
  createConversation(data: { patientId: string; title: string }): Promise<Conversation>
  getConversations(params: { patientId?: string; limit?: number }): Promise<ConversationList>
  getConversation(id: string): Promise<ConversationDetail>
  sendMessage(conversationId: string, data: { content: string; contextWindow?: number }): Promise<MessageResponse>
  deleteConversation(id: string): Promise<void>
}
```

#### 2. 对话上下文 (`src/frontend/contexts/ConversationContext.tsx`)

管理全局对话状态：

```typescript
interface ConversationState {
  currentConversation: Conversation | null
  conversations: Conversation[]
  messages: Message[]
  isLoading: boolean
  error: string | null
}

interface ConversationContextType {
  selectConversation: (id: string) => void
  createConversation: (title: string) => void
  sendMessage: (content: string) => void
  deleteConversation: (id: string) => void
  refreshConversations: () => void
}
```

#### 3. 主要组件

**ConversationLayout** (`src/frontend/components/conversations/ConversationLayout.tsx`)
- 左右分栏布局容器
- 响应式处理
- 侧栏折叠/展开

**ConversationList** (`src/frontend/components/conversations/ConversationList.tsx`)
- 历史对话列表
- 搜索过滤
- 新建对话按钮

**ConversationItem** (`src/frontend/components/conversations/ConversationItem.tsx`)
- 单个对话项
- 选中状态
- 最后消息预览

**ConversationView** (`src/frontend/components/conversations/ConversationView.tsx`)
- 消息列表
- 输入区域
- 追问问题展示

**MessageBubble** (`src/frontend/components/conversations/MessageBubble.tsx`)
- 用户/AI 消息气泡
- Markdown 渲染
- 时间戳显示

**DiagnosisCard** (`src/frontend/components/conversations/DiagnosisCard.tsx`)
- 诊断结果卡片
- 疾病列表
- 置信度进度条
- 建议检查项目

**FollowUpQuestions** (`src/frontend/components/conversations/FollowUpQuestions.tsx`)
- 追问问题按钮组
- 一键发送

### 页面路由

- `/conversations` - 对话列表页（主入口）
- `/conversations/[id]` - 单个对话详情页

### 数据流

```
用户输入 → ConversationView
         ↓
ConversationContext.sendMessage()
         ↓
API 客户端 (POST /api/conversations/{id}/messages)
         ↓
后端处理 (上下文引擎 + DeepSeek)
         ↓
返回诊断结果 + 追问问题
         ↓
更新状态 → 渲染 MessageBubble + DiagnosisCard + FollowUpQuestions
```

### 样式决策

- **配色**: 基于现有 Tailwind 主题
  - 用户消息：蓝色背景
  - AI 消息：灰色背景
  - 选中对话：浅蓝色高亮
  - 错误消息：红色边框

- **间距**: 使用 Tailwind 标准间距
  - 消息间距：`gap-4`
  - 卡片内边距：`p-4`
  - 布局边距：`px-6 py-4`

- **响应式断点**:
  - Mobile: `< 768px` (单栏)
  - Tablet: `768px - 1024px` (可折叠侧栏)
  - Desktop: `> 1024px` (双栏)

### API 集成点

| 前端组件 | API 端点 | 用途 |
|----------|---------|------|
| ConversationList | GET /api/conversations | 加载历史对话 |
| ConversationView | GET /api/conversations/{id} | 加载对话详情 |
| ConversationView | POST /api/conversations/{id}/messages | 发送消息 |
| ConversationLayout | POST /api/conversations | 创建新对话 |
| ConversationItem | DELETE /api/conversations/{id} | 删除对话 |

---

## Testing Decisions

### 测试原则

- **只测试外部行为**：不测试内部实现细节
- **测试公共接口**：组件的 props 和事件
- **模拟 API 调用**：使用 MSW (Mock Service Worker)

### 测试范围

#### 1. 组件测试 (Jest + React Testing Library)

**测试文件**: `src/frontend/__tests__/components/conversations/`

- `ConversationList.test.tsx`
  - 空列表显示引导提示
  - 列表项正确渲染
  - 点击切换对话
  - 新建对话按钮

- `ConversationView.test.tsx`
  - 消息列表渲染
  - 输入框功能
  - 发送消息
  - 追问问题按钮

- `MessageBubble.test.tsx`
  - 用户/AI 消息样式
  - Markdown 渲染
  - 时间戳显示

- `DiagnosisCard.test.tsx`
  - 疾病列表展示
  - 置信度进度条
  - 展开/收起

#### 2. API 客户端测试

**测试文件**: `src/frontend/__tests__/lib/api/conversations.test.ts`

- 创建对话返回正确结构
- 获取对话列表分页
- 发送消息处理响应
- 错误处理

#### 3. E2E 测试 (Playwright)

**测试文件**: `src/frontend/__tests__/e2e/conversations.spec.ts`

- 完整对话流程
- 历史对话管理
- 响应式布局
- 性能测试

### 先例参考

参考现有测试：
- `src/frontend/__tests__/` (如有)
- 其他项目的对话组件测试

---

## Out of Scope

以下功能不在本次规格范围内：

### 用户认证

- MetaMask 钱包连接
- 用户登录/注册
- 权限管理

### 高级功能

- 语音输入
- 图片上传
- 文件附件
- 实时翻译
- 语音输出

### 数据导出

- PDF 报告生成（已有，但不在对话 UI 中集成）
- 对话历史导出
- 数据同步到云端

### 社交功能

- 分享对话
- 评论/点赞
- 公共诊断库

### 管理功能

- 对话审核
- 敏感词过滤
- 使用统计

---

## Further Notes

### 优先级划分

**P0 - 必须完成**
- 左右分栏布局
- 对话列表
- 消息发送/接收
- 输入框
- 诊断结果卡片

**P1 - 建议完成**
- 追问问题按钮
- 流式展示
- Markdown 渲染
- 响应式设计
- 错误处理

**P2 - 可选**
- 骨架屏加载
- 消息编辑
- 对话搜索
- 主题切换

### 技术债务

- 目前使用 fetch API，未来可迁移到 SWR 或 React Query
- Markdown 渲染未做安全过滤，需添加 DOMPurify
- 未实现 WebSocket/SSE 流式传输

### 依赖项

需要安装的 npm 包：

```json
{
  "dependencies": {
    "react-markdown": "^9.0.0",
    "remark-gfm": "^4.0.0",
    "clsx": "^2.0.0",
    "tailwind-merge": "^2.0.0"
  },
  "devDependencies": {
    "@testing-library/react": "^14.0.0",
    "@testing-library/jest-dom": "^6.0.0",
    "msw": "^2.0.0",
    "playwright": "^1.40.0"
  }
}
```

### 设计资源

- Shadcn/ui 组件库：https://ui.shadcn.com
- Tailwind CSS 文档：https://tailwindcss.com
- React Testing Library：https://testing-library.com

---

*规格创建时间：2026-08-27*  
*下一步：/to-tickets 拆分为可执行的 tickets*
