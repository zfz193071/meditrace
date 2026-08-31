# 01 — 确认后端是否支持更新对话标题的 API

**What to build:** 验证后端是否提供更新对话标题的接口，为前端重命名功能做准备。

**Blocked by:** None — can start immediately

**Status:** ready-for-agent

## Acceptance criteria

- [ ] 检查后端 `src/backend/main.py` 是否存在更新对话标题的 API 端点
- [ ] 如果不存在，记录需要实现的 API 规格（`PUT /api/conversations/{conversation_id}`）
- [ ] 如果存在，记录 API 的请求/响应格式
- [ ] 将验证结果记录在文档中，供后续任务参考

## Technical Notes

根据 `/to-spec.md` 的 Out of Scope 部分：
- 需要确认后端是否提供更新对话标题的 API（`PUT /api/conversations/{id}`）
- 如果不存在，需要后端先实现该接口

## Related Files

- `src/backend/main.py` - 后端 API 实现
- `src/frontend/lib/api.ts` - 前端 API 调用
