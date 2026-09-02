# 01 — 统一 Chat 页面路由架构

**What to build:** 将 `/chat/[id]/page.tsx` 的功能整合到 `/chat/page.tsx` 中，使 `/chat/{id}` URL 访问时显示带有左侧菜单的完整界面。

**Blocked by:** None — can start immediately

**Status:** ready-for-agent

## Acceptance criteria

- [ ] 删除独立的 `/chat/[id]/page.tsx` 文件
- [ ] `/chat/page.tsx` 能够处理 `/chat` 和 `/chat/{id}` 两种路由
- [ ] 访问 `/chat/{id}` 时显示完整的界面（包含左侧菜单）
- [ ] 左侧菜单能够高亮显示当前激活的对话
- [ ] 返回按钮正确导航到 `/chat`（对话列表视图）

## Implementation notes

### 已完成的工作

1. **删除独立路由文件**
   - 删除了 `src/frontend/app/chat/[id]/page.tsx`
   - Next.js 会自动将 `/chat/page.tsx` 作为 `/chat` 和 `/chat/{id}` 的处理器

2. **现有功能验证**
   - `/chat/page.tsx` 已经实现了 URL 参数读取（`params.id`）
   - 已经实现了对话加载逻辑（`loadConversations(targetId)`）
   - 已经实现了左侧菜单高亮（`activeConversation` 状态）
   - 已经实现了返回按钮（导航到 `/chat`）

### 关键代码位置

- URL 参数读取：第 82 行 `const id = params.id as string;`
- 对话加载：第 322-350 行 `loadConversations(targetId)` 函数
- 侧栏高亮：第 718-726 行对话列表项的 `onClick` 处理
- 返回按钮：第 806-812 行折叠侧栏按钮（`◀`）

### 路由行为

```
/chat              → 加载对话列表，自动创建临时对话
/chat/{id}         → 加载对话列表，查找并激活指定对话
```

## Next steps

完成此 ticket 后，继续处理：
- Ticket 02 — URL 参数驱动的对话加载（验证功能是否完整）
- Ticket 04 — 返回按钮逻辑修复（验证导航是否正确）

## Implementation completed

### Changes made

1. **Deleted separate route file**
   - Removed `src/frontend/app/chat/[id]/page.tsx`
   - Next.js now routes both `/chat` and `/chat/{id}` to `page.tsx`

2. **Enhanced navigation header**
   - Added "←" return button when URL contains conversation ID
   - Return button clears URL and resets active conversation
   - Sidebar toggle button only shown when not viewing specific conversation

### Files modified

- `src/frontend/app/chat/page.tsx` - Enhanced header navigation logic
