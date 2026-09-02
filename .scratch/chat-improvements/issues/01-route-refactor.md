# 01 — 路由重构

**What to build:** 聊天页面使用 `/chat` 路径，`/conversations` 路径完全移除

**Blocked by:** None — can start immediately

**Status:** ready-for-agent

- [ ] 确认 `src/frontend/app/chat/` 目录存在
- [ ] 删除或重命名 `src/frontend/app/conversations/` 目录（如果存在）
- [ ] 更新所有内部链接引用（布局、导航等），从 `/conversations` 改为 `/chat`
- [ ] 验证访问 `/chat` 正常工作
- [ ] 验证访问 `/conversations` 返回 404
