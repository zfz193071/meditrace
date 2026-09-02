# 04 — 返回按钮逻辑修复

**What to build:** 当通过 URL 访问特定对话时，顶部导航栏显示"←"返回按钮，点击后返回对话列表视图。

**Blocked by:** 02 — URL 参数驱动的对话加载

**Status:** ready-for-agent

## Acceptance criteria

- [ ] 当 URL 包含对话 ID 时（`/chat/{id}`），显示"←"返回按钮
- [ ] 点击返回按钮后，URL 清空为 `/chat`
- [ ] 激活的对话被重置，侧栏显示对话列表
- [ ] 当 URL 不包含对话 ID 时（`/chat`），隐藏返回按钮，显示侧栏折叠按钮

## Implementation details

### 导航栏逻辑修改

```typescript
// 第 806-840 行（修改后的导航栏）
<header className="p-4 border-b bg-white flex items-center gap-2 flex-shrink-0">
  {/* 当 URL 有对话 ID 时显示返回按钮 */}
  {urlConversationId && (
    <button
      onClick={() => {
        // 清空 URL 中的对话 ID，返回对话列表视图
        window.history.replaceState({}, "", "/chat");
        // 重置激活的对话
        setActiveConversation(null);
        setActiveMenuConversationId(null);
      }}
      className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
      title="返回对话列表"
    >
      ←
    </button>
  )}
  
  {/* 侧栏折叠/展开按钮（仅在有对话 ID 时隐藏） */}
  {!urlConversationId && (
    <button
      onClick={toggleSidebar}
      className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
      title={sidebarCollapsed ? "展开侧栏" : "折叠侧栏"}
    >
      {sidebarCollapsed ? '▶' : '◀'}
    </button>
  )}
  
  {/* 返回主页按钮 */}
  <button
    onClick={() => router.push("/")}
    className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
    title="返回主页"
  >
    🏠
  </button>
  
  {/* 页面标题 */}
  <div className="flex-1">
    <h1 className="text-xl font-bold">
      {pageTitle}
    </h1>
  </div>
</header>
```

### 按钮行为说明

| 场景 | URL | 返回按钮 | 侧栏按钮 |
|------|-----|---------|---------|
| 对话列表 | `/chat` | 隐藏 | 显示（◀/▶） |
| 特定对话 | `/chat/{id}` | 显示（←） | 隐藏 |

### 返回按钮功能

1. **清空 URL**: `window.history.replaceState({}, "", "/chat")`
   - 使用 `replaceState` 而非 `pushState`，避免历史记录堆积
   - URL 变为 `/chat`

2. **重置状态**: 
   - `setActiveConversation(null)` - 清空激活对话
   - `setActiveMenuConversationId(null)` - 关闭三点菜单

3. **UI 变化**:
   - 侧栏自动显示（因为 `activeConversation` 为 null）
   - 显示对话列表
   - 返回按钮隐藏，侧栏折叠按钮显示

## Test scenarios

1. **从 URL 返回**
   - 访问 `/chat/{id}` → 点击"←" → 返回 `/chat`
   - 验证侧栏显示，对话列表可见

2. **多次返回**
   - 连续点击返回按钮 → 不应有副作用
   - 验证状态不会重复重置

3. **与侧栏折叠的交互**
   - 在 `/chat` 页面 → 侧栏折叠按钮正常工作
   - 在 `/chat/{id}` 页面 → 侧栏折叠按钮隐藏

## Files modified

- `src/frontend/app/chat/page.tsx` - 第 806-840 行（导航栏逻辑）
