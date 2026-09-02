# 02 — URL 参数驱动的对话加载

**What to build:** `/chat/page.tsx` 能够读取 URL 中的 `params.id`，加载对应对话并在左侧菜单中高亮显示。

**Blocked by:** 01 — 统一 Chat 页面路由架构

**Status:** ready-for-agent

## Acceptance criteria

- [ ] 访问 `/chat/{conversationId}` 时，页面从 URL 读取对话 ID
- [ ] 加载对话列表并查找指定对话
- [ ] 找到对话后，在左侧菜单中高亮显示
- [ ] 页面标题显示对应对话的标题
- [ ] 对话消息内容正确显示

## Implementation details

### URL 参数读取逻辑

```typescript
// 第 79-92 行
useEffect(() => {
  const id = params.id as string;
  if (id) {
    setUrlConversationId(id);
    loadConversations(id);  // 加载对话列表并查找指定对话
  } else {
    loadConversations();
    autoCreateConversation();
  }
}, [userId, params]);
```

### 对话加载逻辑

```typescript
// 第 322-350 行
const loadConversations = async (targetId?: string) => {
  setLoading(true);
  try {
    const conversationsList = await getConversations(userId);
    setConversations(conversationsList);
    
    if (targetId) {
      const targetConversation = conversationsList.find(c => c.id === targetId);
      if (targetConversation) {
        setActiveConversation(targetConversation);  // 激活对话
        setPageTitle(targetConversation.title);     // 设置标题
        setIsTempConversation(false);
      } else {
        await autoCreateConversation();  // 对话不存在，创建新对话
      }
    }
  } catch (error) {
    console.error("加载对话列表失败:", error);
    setConversations([]);
  } finally {
    setLoading(false);
  }
};
```

### 侧栏高亮逻辑

左侧菜单通过 `activeConversation` 状态自动高亮：

```typescript
// 第 718-726 行
<div
  onClick={() => {
    setActiveConversation(conv);
    window.history.pushState({}, "", `/chat/${conv.id}`);
  }}
  className={`... ${
    activeConversation?.id === conv.id ? "bg-green-50" : "hover:bg-gray-50"
  }`}
>
```

### 状态管理

- `urlConversationId` - 存储 URL 中的对话 ID
- `activeConversation` - 当前激活的对话（控制侧栏高亮）
- `pageTitle` - 页面标题（同步显示对话标题）

## Test scenarios

1. **正常加载**
   - 访问 `/chat/{existingId}` → 加载对话并高亮侧栏
   - 验证页面标题、消息内容正确显示

2. **对话不存在**
   - 访问 `/chat/{nonExistentId}` → 提示并创建新对话
   - 验证错误处理和用户体验

3. **页面刷新**
   - 在 `/chat/{id}` 页面刷新 → 保持侧栏高亮
   - 验证状态持久化

## Files modified

- `src/frontend/app/chat/page.tsx` - 已有实现，无需修改
