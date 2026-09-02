# 02 — 前端 API 层添加对话查询和 URL 导航方法

**What to build:** 在前端 API 层添加获取单个对话和 URL 导航的方法，支持基于对话 ID 的路由操作。

**Blocked by:** 01 — 验证后端 API 支持按 ID 获取对话

**Status:** ready-for-agent

**Acceptance criteria:**
- [ ] 在 `src/frontend/lib/api.ts` 中添加 `getConversationById(conversationId: string)` 方法
  - 调用后端 `GET /api/conversations/{conversation_id}` 接口
  - 返回完整的 Conversation 对象
  - 处理 404 错误并抛出适当的异常
- [ ] 在 `src/frontend/lib/api.ts` 中添加 `navigateToConversation(conversationId: string)` 方法
  - 使用 Next.js 的 `router.push()` 导航到 `/chat/{conversationId}`
  - 处理导航失败的情况
- [ ] 添加 TypeScript 类型定义，确保返回类型与现有 Conversation 类型一致
- [ ] 在 `src/frontend/lib/api.test.ts` 中添加单元测试（如果测试文件不存在则创建）
  - 测试成功获取对话
  - 测试对话不存在时的错误处理

**技术备注:**
- 参考现有的 `getConversations` 和 `createConversation` 方法实现
- API 基础 URL 使用 `http://localhost:8000`（开发环境）
- 使用 Next.js 的 `router` 进行导航
