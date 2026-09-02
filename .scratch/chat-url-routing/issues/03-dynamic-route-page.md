# 03 — 创建动态路由页面 app/chat/[id]/page.tsx

**What to build:** 创建 Next.js 动态路由页面，支持通过 URL 访问特定对话，实现刷新页面时保持对话状态。

**Blocked by:** 02 — 前端 API 层添加对话查询和 URL 导航方法

**Status:** ready-for-agent

**Acceptance criteria:**
- [ ] 创建 `src/frontend/app/chat/[id]/page.tsx` 动态路由页面组件
- [ ] 页面从 URL 参数中读取对话 ID（使用 Next.js `useParams` hook）
- [ ] 页面加载时调用 `getConversationById` 获取对话数据
- [ ] 对话加载成功：
  - 在左侧对话列表中高亮当前对话
  - 在右侧显示完整的对话内容（消息列表）
  - 更新页面标题为对话标题
- [ ] 对话不存在或加载失败：
  - 显示友好的错误提示
  - 提供"返回对话列表"或"创建新对话"的按钮
  - 自动重定向到 `/chat`（可选）
- [ ] 支持响应式布局（移动端和桌面端）
- [ ] 复用现有的 UI 组件（LoadingSpinner, MarkdownRenderer 等）
- [ ] 保持与现有聊天页面一致的样式和交互体验

**技术备注:**
- 使用 Next.js App Router 的动态路由语法
- 使用 `useParams()` hook 获取 URL 参数
- 使用 `useState` 和 `useEffect` 管理加载状态
- 复用 `src/frontend/app/chat/page.tsx` 中的消息展示逻辑
- 考虑代码复用：将消息展示逻辑提取为公共组件

**UX 细节:**
- 加载中显示 LoadingSpinner
- 错误状态显示友好的提示信息
- 对话标题显示在页面顶部
- 消息列表自动滚动到底部
