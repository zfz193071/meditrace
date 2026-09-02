# 01 — 验证后端 API 支持按 ID 获取对话

**What to build:** 确保后端 API 支持通过对话 ID 获取单个对话的完整信息（包括消息列表），为前端 URL 路由提供数据支持。

**Blocked by:** None — can start immediately

**Status:** ready-for-agent

**Acceptance criteria:**
- [ ] 验证 `GET /api/conversations/{conversation_id}` 接口存在并返回完整的对话数据（包含 messages 数组）
- [ ] 测试接口返回的数据格式与前端期望的 Conversation 类型匹配
- [ ] 测试访问不存在的对话 ID 时返回适当的 HTTP 错误状态码（404）
- [ ] 在 `.scratch/chat-url-routing/test-results/` 目录下创建 API 测试报告

**技术备注:**
- 后端代码位于 `src/backend/main.py` 第 618-656 行
- 需要验证返回的 JSON 结构包含：id, patientId, title, createdAt, updatedAt, messages
- messages 数组应包含完整的消息历史（role, content, timestamp）
