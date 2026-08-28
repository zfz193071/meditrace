# 流式响应显示 Bug 修复记录

## 问题描述

**日期**: 2026-08-28  
**问题 ID**: stream-display-bug-001

### 症状
在 `http://localhost:3000/conversations` 页面上，`/api/conversations/{conversationId}/messages/stream` 接口已返回流式数据，但页面上一次性显示所有内容，而不是逐字打印输出（打字机效果）。

### 影响
- 用户体验差，无法看到 AI 逐步生成的过程
- 无法区分流式接口和普通接口的效果差异

---

## 问题根源分析

通过代码审查和测试脚本验证，发现了两个问题：

### 1. 后端问题 (`src/backend/main.py` 第 796 行)

**原代码**:
```python
# 发送完成信号
yield f"data: {json.dumps({'content': full_content, 'complete': True})}\n\n"
yield "data: [DONE]\n\n"
```

**问题**:
- `complete: true` 的 chunk 发送了完整的 `full_content`，而不是增量内容
- 前端在累加时会重复添加完整内容，导致显示异常

### 2. 前端问题 (`src/frontend/app/conversations/page.tsx` 第 119-133 行)

**原代码**:
```typescript
await sendMessageStream(
  {
    conversationId: activeConversation.id,
    message: newMessage,
  },
  (chunk) => {
    // 更新 AI 消息内容
    setActiveConversation((prev) => {
      if (!prev) return prev;
      const messages = [...prev.messages];
      if (messages[aiMessageIndex]) {
        messages[aiMessageIndex] = {
          ...messages[aiMessageIndex],
          content: messages[aiMessageIndex].content + chunk.content,
        };
      }
      return {
        ...prev,
        messages,
      };
    });
  }
);
```

**问题**:
- React 的批量更新机制可能导致多个 chunk 的状态更新被合并
- UI 不会在每个 chunk 到来时都重新渲染，看起来像"一次性显示"

---

## 修复方案

### 1. 后端修复

**修改位置**: `src/backend/main.py` 第 795-797 行

**修改后代码**:
```python
# 发送完成信号（content 为空，避免重复累加）
yield f"data: {json.dumps({'content': '', 'complete': True})}\n\n"
yield "data: [DONE]\n\n"
```

**说明**:
- `complete: true` 的 chunk 现在发送空内容
- 前端只负责累加增量 chunk，不再重复添加完整内容

### 2. 前端修复

**修改位置**: `src/frontend/app/conversations/page.tsx` 第 113-142 行

**修改后代码**:
```typescript
// 流式发送消息
await sendMessageStream(
  {
    conversationId: activeConversation.id,
    message: newMessage,
  },
  (chunk) => {
    // 使用 setTimeout 确保每个 chunk 都能触发 UI 更新
    // 避免 React 批量更新导致的显示延迟
    setTimeout(() => {
      // 更新 AI 消息内容
      setActiveConversation((prev) => {
        if (!prev) return prev;
        const messages = [...prev.messages];
        if (messages[aiMessageIndex]) {
          messages[aiMessageIndex] = {
            ...messages[aiMessageIndex],
            content: messages[aiMessageIndex].content + chunk.content,
          };
        }
        return {
          ...prev,
          messages,
        };
      });
      
      // 滚动到底部
      scrollToBottom();
    }, 0);
  }
);
```

**说明**:
- 使用 `setTimeout(..., 0)` 将状态更新放入事件队列，确保每个 chunk 触发独立的 UI 更新
- 在每次更新后调用 `scrollToBottom()` 确保滚动到最新消息

---

## 验证方法

### 1. 后端验证（测试脚本）

创建测试脚本验证流式响应：

```javascript
// test-stream.js (已删除)
const response = await fetch(`${baseUrl}/api/conversations/${conversationId}/messages/stream`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ content: "测试流式响应" }),
});

// 验证结果:
// - 75 个 chunk 在 2.1 秒内返回
// - 每个 chunk 约 29ms
// - 最后一个 chunk (complete=true) 内容为空
```

### 2. 前端验证

1. 启动后端服务：`cd src/backend && python main.py`
2. 启动前端服务：`cd src/frontend && pnpm dev`
3. 访问 `http://localhost:3000/conversations`
4. 选择一个对话，发送消息
5. 观察 AI 回复是否逐字显示（打字机效果）

---

## 修改的文件

| 文件 | 修改内容 | 行号 |
|------|----------|------|
| `src/backend/main.py` | 修复流式响应完成信号 | 795-797 |
| `src/frontend/app/conversations/page.tsx` | 修复 UI 更新机制 | 113-142 |

---

## 注意事项

1. **服务管理**: 启动和停止服务需要手动操作，不再自动测试
2. **浏览器测试**: 禁止自动在浏览器发起对话测试，需手动验证
3. **HMR 热更新**: Next.js 的 HMR 会自动应用前端代码更改，但后端代码修改需要重启服务

---

## 后续改进建议

1. 考虑添加流式响应的加载状态指示器（如闪烁的光标）
2. 添加性能监控，记录每个 chunk 的接收时间
3. 考虑使用 WebSocket 替代 SSE，获得更好的实时性
4. 添加错误重试机制，处理网络中断情况

---

## 相关文档

- [SSE (Server-Sent Events) 规范](https://html.spec.whatwg.org/multipage/server-sent-events.html)
- [React 批量更新机制](https://react.dev/reference/react/useEffect#batching-updates)
- [Next.js HMR 配置](https://nextjs.org/docs/app/building-your-application/rendering/client-components)

---

**修复完成时间**: 2026-08-28 17:16  
**修复者**: AI Agent (diagnosing-bugs skill)  
**状态**: ✅ 已修复，待手动验证
