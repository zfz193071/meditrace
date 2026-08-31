# 06 — 移除冗余的对话信息头部

**What to build:** 移除右侧内容区域的第二个头部（对话信息栏），扩大聊天内容展示空间。

**Blocked by:** None — can start immediately

**Status:** ready-for-agent

## Acceptance criteria

- [ ] 删除 `<div className="p-4 border-b bg-gray-50 flex-shrink-0">` 元素（对话信息栏）
- [ ] 保留顶部导航栏（侧栏折叠按钮、返回主页按钮、页面标题）
- [ ] 验证聊天内容区域空间增大
- [ ] 验证整体布局正常，无样式问题

## User Stories

- 作为用户，我希望移除右侧内容区域的第二个头部（对话信息栏），这样我能获得更大的聊天内容展示空间

## Technical Decisions

- 直接删除对话信息头部 `<div>` 元素及其内容
- 保留顶部导航栏的 `<header>` 元素
- 确保消息列表的父容器正确设置 `flex-1 overflow-y-auto`

## Related Files

- `src/frontend/app/conversations/page.tsx` - 主要修改文件
