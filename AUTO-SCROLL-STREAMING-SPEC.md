# Auto-Scroll During AI Streaming Response - Specification

## Problem Statement

When the AI is automatically responding with streaming content, the vertical scrollbar does not automatically scroll down to follow the new content, forcing users to manually scroll to see the latest response content.

## Solution

Implement automatic scrolling behavior during AI streaming responses that:
1. Automatically scrolls to show new content as it arrives
2. Uses smooth scrolling for better user experience during streaming
3. Respects user's manual scroll actions (stops auto-scrolling when user scrolls)
4. Maintains proper scroll behavior when switching conversations

## User Stories

1. As a user, I want the chat to automatically scroll down as the AI types its response, so that I can see the latest content without manual scrolling.

2. As a user, I want smooth scrolling animation during AI responses, so that the scrolling feels natural and not jarring.

3. As a user, I want to be able to scroll up to review previous messages while the AI is responding, so that I can read the conversation history without being forced to the bottom.

4. As a user, I want the chat to scroll to the bottom when I send a new message, so that I can see the AI's response area immediately.

5. As a user, I want the chat to scroll to the bottom when I switch to a different conversation, so that I can see the most recent messages.

6. As a user, I want the auto-scroll to stop when I manually scroll up, so that I have control over my viewing position.

7. As a user, I want the auto-scroll to resume when I scroll back to the bottom, so that I can continue receiving updates.

8. As a user, I want different scroll behaviors for different scenarios (smooth for streaming, instant for new messages), so that each interaction feels appropriate.

9. As a mobile user, I want touch scrolling to also disable auto-scroll, so that the behavior is consistent across input methods.

10. As a user, I want the scroll behavior to work reliably when switching between conversations, so that I don't lose my place.

## Implementation Decisions

### Modules Modified

- **Frontend Chat Page**: `src/frontend/app/chat/[id]/page.tsx`
  - Main chat interface with message display and streaming response handling

### Interfaces Modified

- **`scrollToBottom` function**: Added optional `isStreaming` parameter
  - `isStreaming: boolean` - When true, uses smooth scrolling; when false (or undefined), uses auto scrolling

### Technical Decisions

1. **Scroll Trigger Points**:
   - Stream chunks arriving: Trigger scroll if `shouldAutoScrollRef.current` is true
   - New message sent: Trigger scroll with `behavior: "auto"`
   - Conversation switch: Trigger scroll to bottom

2. **Scroll Behavior Differentiation**:
   - Streaming responses: Use `behavior: "smooth"` for gentle, readable scrolling
   - New messages/conversation switch: Use `behavior: "auto"` for immediate positioning

3. **User Control Mechanism**:
   - `shouldAutoScrollRef` tracks whether auto-scroll is enabled
   - Set to `false` when user manually scrolls (wheel or touch events)
   - Set to `true` when user sends a new message

4. **Event Listeners for Manual Scroll Detection**:
   - `onWheel` on message container: Detects mouse wheel scrolling
   - `onTouchStart` on message container: Detects touch scrolling on mobile

5. **State Management**:
   - Use `useRef` for `shouldAutoScroll` to avoid re-renders
   - Use `useRef` for tracking previous message count
   - Use `useRef` for initial mount detection

### Architecture

The solution follows the existing pattern in the codebase:
- Uses React refs for scroll state management
- Integrates with existing message update flow
- Maintains separation between streaming and non-streaming scroll behaviors
- Preserves user interaction preferences

### Code Changes Summary

1. **Modified `scrollToBottom` function** (line ~380):
   ```typescript
   const scrollToBottom = (isStreaming: boolean = false) => {
     messagesEndRef.current?.scrollIntoView({
       behavior: isStreaming ? "smooth" : "auto",
     });
   };
   ```

2. **Added scroll trigger in streaming callback** (line ~756):
   ```typescript
   // 流式响应时自动滚动（如果用户没有手动滚动）
   if (shouldAutoScrollRef.current) {
     scrollToBottom(true); // true 表示流式响应，使用平滑滚动
   }
   ```

## Testing Decisions

### What Makes a Good Test

- Test external behavior only: verify that scrolling happens (or doesn't) based on user actions
- Do NOT test implementation details (ref values, function calls)
- Test should cover both auto-scroll and manual scroll scenarios

### Modules to Test

- **Chat Page UI** (`/chat/{id}` route)
  - Message display area
  - Scrolling behavior
  - User interaction handling

### Test Scenarios

1. **Streaming Auto-Scroll**:
   - Send a message that triggers a long AI response
   - Verify that the view automatically scrolls down as content arrives
   - Verify that scrolling is smooth (not jarring)

2. **Manual Scroll Override**:
   - During AI response, manually scroll up
   - Verify that auto-scroll stops
   - Verify that user can read historical messages without interruption

3. **New Message Scroll**:
   - Send a new message
   - Verify that the view scrolls to bottom immediately (auto behavior)
   - Verify that AI response area is visible

4. **Conversation Switch Scroll**:
   - Switch to a different conversation
   - Verify that the view scrolls to bottom
   - Verify that most recent messages are visible

5. **Mobile Touch Scroll**:
   - On mobile device, touch and scroll during AI response
   - Verify that auto-scroll stops on touch interaction

### Prior Art

- Existing scroll behavior tests in the codebase (if any)
- Pattern from Ticket 06 (scroll behavior when sending messages)
- Similar streaming UI patterns in other chat applications

## Out of Scope

1. **Backend Changes**: No backend modifications required; this is purely a frontend UI enhancement

2. **API Changes**: The streaming API interface remains unchanged

3. **New Components**: No new React components are created; changes are within existing chat page

4. **Performance Optimization**: This spec does not address potential performance concerns with frequent scroll calls during high-frequency streaming (optimization can be added later if needed)

5. **Accessibility Improvements**: While the feature improves UX, specific accessibility enhancements (ARIA labels, keyboard navigation) are out of scope

6. **Cross-browser Testing**: The implementation uses standard `scrollIntoView` API which has broad browser support; specific cross-browser testing is not included

7. **Animation Customization**: The smooth scrolling uses browser default easing; custom animation curves are out of scope

## Further Notes

### User Experience Considerations

- **Smooth vs Auto**: The distinction between smooth (streaming) and auto (new messages) scrolling provides appropriate feedback for different user actions
- **User Control**: Allowing users to override auto-scroll is critical for good UX - users should never feel "trapped" at the bottom
- **Mobile Support**: Touch events are handled separately from wheel events to ensure consistent behavior across devices

### Technical Notes

- **Ref vs State**: Using `useRef` for scroll state avoids unnecessary re-renders during rapid streaming updates
- **Event Delegation**: Scroll detection is attached to the message container, not individual messages, for better performance
- **Timing**: Scroll calls are made synchronously after state updates to ensure content is rendered before scrolling

### Future Enhancements

Potential improvements that could be added later:
- Debouncing scroll calls during very high-frequency streaming
- "Jump to bottom" button that appears when user has scrolled up
- Scroll position memory (remember where user was when switching back to a conversation)
- Animated scroll indicator when new content arrives while user is scrolled up

### Related Issues

- Ticket 06: Original scroll behavior implementation for new messages
- Streaming response bug fix (2026-08-28): Related to streaming display mechanism

### Deployment Notes

- Frontend changes apply via HMR (Hot Module Replacement)
- No backend restart required
- User should manually test in browser (do not auto-test with AI messages to save API tokens)
