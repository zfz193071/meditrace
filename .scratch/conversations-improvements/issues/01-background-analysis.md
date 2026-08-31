# 01 — 对话页面改进背景分析

**What to build:** 完成对话页面当前实现的分析，明确需要修改的代码位置和实现方案，为后续实现提供技术蓝图。

**Blocked by:** None — can start immediately

**Status:** ready-for-agent

**技术分析任务:**

1. **当前实现分析**
   - 阅读 `src/frontend/app/conversations/page.tsx` 完整代码
   - 理解当前的状态管理：`activeConversation`、`messages`、`showNewConversation` 等
   - 理解当前的滚动逻辑：`useEffect` 监听 `activeConversation?.messages` 并调用 `scrollToBottom()`
   - 理解当前的新建会话流程：`showNewConversation` 状态控制输入框显示

2. **需要修改的关键点**
   - **新建会话流程**：移除 `showNewConversation` 状态和输入框 UI，点击按钮直接调用 `createConversation` 使用默认标题
   - **滚动行为**：修改 `useEffect` 的依赖和逻辑，区分"切换会话"和"新消息到达"两种场景
   - **默认标题策略**：确定使用固定默认标题（如"新的诊断对话"）

3. **需要保留的功能**
   - 流式消息显示逻辑（之前的 Bug 修复）
   - 消息发送时的自动滚动到底部
   - 会话删除、列表加载等现有功能

4. **实现方案**
   - 方案 A（推荐）：简单直接实现
     - 删除 `showNewConversation` 和 `newTitle` 状态
     - 删除新建输入框 UI 代码
     - 修改 `handleCreateConversation` 为 `handleNewConversation`，直接使用默认标题
     - 添加 `messagesEndRef` 的依赖跟踪，只在消息内容变化时滚动
     - 使用 `useRef` 标记是否为首次渲染或会话切换

5. **验收标准**
   - [ ] 完成当前代码的完整分析
   - [ ] 明确需要修改的每一处代码位置
   - [ ] 确定实现方案并记录决策理由
   - [ ] 输出详细的技术实现步骤
   - [ ] 识别潜在的边界情况和风险点
