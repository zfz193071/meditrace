# 01 — 确认后端是否支持更新对话标题的 API

**What to build:** 验证后端是否提供更新对话标题的接口，为前端重命名功能做准备。

**Blocked by:** None — can start immediately

**Status:** ✅ **COMPLETED**

## Acceptance criteria

- [x] 检查后端 `src/backend/main.py` 是否存在更新对话标题的 API 端点
- [x] 如果不存在，记录需要实现的 API 规格（`PUT /api/conversations/{conversation_id}`）
- [x] 如果存在，记录 API 的请求/响应格式
- [x] 将验证结果记录在文档中，供后续任务参考

## Implementation Details

### API 规格（已实现）

**端点**: `PUT /api/conversations/{conversation_id}`

**请求**:
```json
{
  "title": "新的对话标题"
}
```

**响应**:
```json
{
  "success": true,
  "message": "Conversation updated",
  "conversationId": "uuid",
  "title": "新的对话标题"
}
```

**错误处理**:
- `400 Bad Request`: 缺少 title 字段
- `404 Not Found`: 对话不存在

### 修改的文件

1. **后端**: `src/backend/main.py`
   - 添加了 `update_conversation` 函数
   - 位置：在 `delete_conversation` 之前

2. **前端**: `src/frontend/lib/api.ts`
   - 添加了 `updateConversation` 函数
   - 导出供组件使用

## Technical Notes

根据 `/to-spec.md` 的 Out of Scope 部分：
- ✅ 后端已提供更新对话标题的 API（`PUT /api/conversations/{id}`）
- ✅ 前端已添加对应的 API 调用函数

## Related Files

- `src/backend/main.py` - 后端 API 实现 ✅
- `src/frontend/lib/api.ts` - 前端 API 调用 ✅

## Next Steps

此 ticket 已完成，可以开始实现依赖此功能的后续 ticket：
- Ticket 05: 实现三点菜单和右下弹框功能（包含重命名功能）
