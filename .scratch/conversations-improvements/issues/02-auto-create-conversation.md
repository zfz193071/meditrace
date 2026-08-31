# 02 — 实现页面默认进入新对话逻辑

**What to build:** 用户访问 `/conversations` 页面时，自动创建新对话并直接进入聊天状态，无需手动选择或创建。

**Blocked by:** None — can start immediately

**Status:** ready-for-agent

## Acceptance criteria

- [ ] 页面加载时自动调用 `createConversation` 创建新对话
- [ ] 添加状态标记防止重复创建（如 `hasAutoCreated`）
- [ ] 新对话创建成功后自动设置为 `activeConversation`
- [ ] 处理创建失败的异常情况（显示错误提示）
- [ ] 确保只在组件首次挂载时执行一次自动创建
- [ ] 如果用户已有对话列表，不影响现有功能

## User Stories

- 作为用户，我希望进入 `/conversations` 页面时直接进入新对话状态，这样我可以立即开始医疗咨询而无需额外操作

## Technical Decisions

- 使用 `useEffect` 在组件挂载时自动调用 `createConversation`
- 添加状态标记（如 `isAutoCreating` 或 `hasAutoCreated`）防止重复创建
- 处理创建失败的异常情况，显示友好提示
- 保持与现有 `handleNewConversation` 函数的兼容性

## Related Files

- `src/frontend/app/conversations/page.tsx` - 主要修改文件
- `src/frontend/lib/api.ts` - `createConversation` API
