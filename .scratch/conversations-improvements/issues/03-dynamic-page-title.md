# 03 — 实现动态标题展示逻辑

**What to build:** 根据对话状态动态调整页面标题，新对话显示"MediTrace 对话"，选择已有对话显示"有效提取用户的问题"。

**Blocked by:** 02 — 实现页面默认进入新对话逻辑

**Status:** ready-for-agent

## Acceptance criteria

- [ ] 新对话状态（刚创建，无历史消息）时，页面标题显示 "MediTrace 对话"
- [ ] 选择已有对话（从列表选择，有历史消息）时，页面标题显示 "有效提取用户的问题"
- [ ] 使用条件渲染根据 `activeConversation` 状态和消息数量判断标题
- [ ] 切换对话时标题正确更新
- [ ] 页面标题显示在顶部导航栏的标题位置

## User Stories

- 作为用户，我希望新对话时页面标题显示"MediTrace 对话"，这样我能清楚知道当前处于新建对话状态
- 作为用户，我希望选择已有对话时页面标题显示"有效提取用户的问题"，这样我能清楚知道当前处于历史对话状态

## Technical Decisions

- 判断逻辑：`activeConversation?.messages?.length === 0` 为新对话
- 使用条件表达式设置标题：`activeConversation?.messages?.length === 0 ? "MediTrace 对话" : "有效提取用户的问题"`
- 在顶部导航栏的 `<h1>` 元素中应用动态标题

## Related Files

- `src/frontend/app/conversations/page.tsx` - 主要修改文件
