# Chat Timestamp Display Behavior Specification

## Problem Statement

在聊天页面 (`/chat`)，当 AI 正在流式回复消息时，时间戳会立即显示在消息下方。这导致用户体验不佳，因为：
- 用户看到时间戳时，AI 内容还在加载中
- 时间戳应该在 AI 回复完成后才显示，表示"这条消息已完成"
- 当前行为让用户误以为消息已经回复完毕

## Solution

修改时间戳显示逻辑：
- **AI 消息正在流式回复时**：不显示时间戳
- **AI 消息回复完成后**：显示时间戳
- **用户消息**：保持当前行为，发送后立即显示时间戳

## User Stories

1. As a chat user, I want to see the timestamp only after the AI finishes responding, so that I know the message is complete
2. As a chat user, I want to see the timestamp immediately after I send my message, so that I know when I sent it
3. As a chat user, I want the timestamp to appear smoothly when the AI response completes, so that the UI feels polished
4. As a chat user, I want to distinguish between streaming and completed AI messages visually, so that I know when to wait and when to read

## Implementation Decisions

### Modified Module
- `src/frontend/app/chat/page.tsx` - Chat interface component

### UI Behavior Changes

**Current Logic (Line 868-876)**:
```tsx
{/* 时间戳 */}
<p
  className={`text-xs mt-2 ${
    msg.role === "user" ? "text-green-100" : "text-gray-500 dark:text-gray-400"
  }`}
>
  {formatTime(msg.timestamp)}
</p>
```

**New Logic**:
- Add conditional rendering for timestamp based on message role and streaming state
- For AI messages: only show timestamp when `!isAiStreaming`
- For user messages: always show timestamp

**Key Variables**:
- `isLastMessage` - identifies if this is the last message in the list
- `isAiStreaming` - identifies if AI message is currently streaming (Line 837)
  ```tsx
  const isAiStreaming = msg.role === "assistant" && isLastMessage && sending;
  ```

**Implementation**:
```tsx
{/* 时间戳 - 只在非流式状态或用户消息时显示 */}
{(!isAiStreaming || msg.role === "user") && (
  <p
    className={`text-xs mt-2 ${
      msg.role === "user" ? "text-green-100" : "text-gray-500 dark:text-gray-400"
    }`}
  >
    {formatTime(msg.timestamp)}
  </p>
)}
```

### State Management
- No changes to state management required
- Leverages existing `sending` state (Line 58) which tracks message sending status
- Leverages existing `isAiStreaming` computed variable (Line 837)

## Testing Decisions

### What Makes a Good Test
- Test external UI behavior, not implementation details
- Verify timestamp visibility based on message state
- Test both user and AI message scenarios

### Modules to Test
- `src/frontend/app/chat/page.tsx` - Chat interface

### Test Scenarios
1. **User message timestamp**: User sends a message → timestamp appears immediately
2. **AI streaming timestamp**: AI starts streaming → timestamp is NOT visible
3. **AI complete timestamp**: AI finishes streaming → timestamp appears
4. **Mixed messages**: Multiple messages with different states → each shows correct timestamp behavior

### Prior Art
- Similar UI conditional rendering patterns exist in the codebase
- Streaming state management follows existing patterns (see Ticket 06 scroll behavior)

## Out of Scope

- Timestamp formatting changes (keeps existing `formatTime` function)
- Date display changes (keeps existing `formatDate` function)
- Message content rendering changes
- Streaming behavior changes (existing stream handling remains unchanged)
- Backend API changes

## Further Notes

### Implementation Simplicity
This is a simple UI conditional rendering change that:
- Requires minimal code modification (one conditional wrapper)
- No state management changes
- No backend changes
- No new dependencies

### User Experience Impact
- Improves perceived responsiveness of the chat interface
- Provides clearer visual feedback about message completion state
- Maintains consistency with common chat UI patterns (e.g., WhatsApp, iMessage)

### Edge Cases Handled
- Multiple AI messages in sequence
- Rapid message sending
- Network delays during streaming
- Component unmount during streaming (existing cleanup handles this)

### Related Code
- Line 58: `sending` state declaration
- Line 837: `isAiStreaming` computation
- Line 868-876: Current timestamp rendering (to be modified)
- Line 646-648: `formatTime` function (unchanged)
