# Refactor: Rename conversations to chat, fix scroll animation and menu display

## Problem Statement

用户在使用 MediTrace 对话页面时面临以下三个问题：
1. URL 路径为 `/conversations`，但用户希望改为 `/chat` 以更符合语义
2. 左侧对话列表中的标题过长时无法完整显示，需要滚动动画来查看完整内容
3. 鼠标悬停时，时间位置显示了两个"三点"菜单按钮（一个在时间处，一个在右侧），造成冗余

## Solution

1. 将对话页面路由从 `/conversations` 迁移到 `/chat`
2. 实现智能文本滚动动画：仅在文本溢出时从右向左滚动，滚动结束后保留 20px 间距后再次滚动
3. 修复三点菜单显示问题，只在鼠标悬停时显示一个三点按钮

## User Stories

1. As a user, I want to access `/chat` instead of `/conversations`, so that the URL is more intuitive and meaningful
2. As a user, I want to see the complete conversation title when it's too long, so that I don't miss important information
3. As a user, I want the scroll animation to stop after the text is fully displayed with a visual gap, so that it looks more natural
4. As a user, I want no scroll animation when the title fits completely, so that there's no visual distraction
5. As a user, I want only one three-dot menu button when hovering, so that the interface is cleaner
6. As a user, I want the three-dot menu button to appear only on the current row without duplicate buttons, so that the UI is consistent
7. As a user, I want all existing conversation features (create, delete, rename) to work correctly under the new route
8. As a user, I want the page to load normally when refreshing on `/chat` path
9. As a user, I want to bookmark or share `/chat` links that open the page correctly

## Implementation Decisions

### Route Migration
- Rename `src/frontend/app/conversations/` directory to `src/frontend/app/chat/`
- Next.js file-based routing will automatically map the directory name to the URL path
- No code logic changes needed, just rename the directory

### Scroll Animation Implementation
- Use CSS animations for right-to-left scroll effect
- Dynamically calculate text width and container width via JavaScript, apply animation only when overflow occurs
- Animation keyframes design:
  - 0%: `translateX(0)` - start position
  - 100%: `translateX(calc(-100% - 20px))` - scroll to text end with 20px gap
- Use `whitespace-nowrap` to prevent text wrapping
- Use `overflow-hidden` to hide overflow
- Animation triggers on `hover`, plays with `linear` timing

### Three-Dot Menu Fix
- Current code has two three-dot displays:
  1. Line 422-425: Three dots at time position (`group-hover:inline`)
  2. Line 426-433: Independent three-dot button (`group-hover:opacity-100`)
- Remove the three-dot display at time position (lines 422-425)
- Keep the independent three-dot button with correct hover display logic
- Simplify HTML structure to avoid duplication

### Technical Details
```tsx
// Scroll animation style (exists, needs enhancement)
@keyframes title-scroll-right-to-left {
  0% {
    transform: translateX(0);
  }
  100% {
    transform: translateX(calc(-100% - 20px)); // extra 20px gap
  }
}

// Conditional animation application (needs to be added)
const shouldScroll = textWidth > containerWidth;
```

## Testing Decisions

### Test Criteria
- Test only externally visible behavior, not implementation details
- Verify route is correctly mapped
- Verify scroll animation behavior when overflow/no-overflow
- Verify three-dot menu appears only once

### Test Items
1. **Route Test**: 
   - Access `/chat` displays conversation page normally
   - Access `/conversations` returns 404
   - Internal links and redirects use the new path

2. **Scroll Animation Test**:
   - Long title conversation: text scrolls right-to-left on hover
   - Short title conversation: no scroll animation on hover
   - After scrolling ends, text end maintains approximately 20px gap from container right edge
   - Animation stops when mouse leaves

3. **Three-Dot Menu Test**:
   - On hover, only one three-dot button appears per row
   - Clicking the three-dot button displays the menu popup correctly
   - Menu functions (rename, delete) work correctly

### Prior Art
- Reference the existing streaming response display bug fix record (`BUGFIX-STREAMING-RECORD.md`)
- Follow project testing standards: manual browser verification

## Out of Scope

1. Backend API path changes (backend still uses `/api/conversations`)
2. Database schema changes
3. Other page route changes
4. Automated browser conversation testing (per project rules, manual verification required)
5. Mobile responsive optimization (already has basic support)
6. Animation performance optimization (e.g., using `will-change`)

## Further Notes

### Modification Steps
1. Rename directory: `src/frontend/app/conversations/` → `src/frontend/app/chat/`
2. Modify scroll animation CSS, add 20px gap
3. Add JavaScript logic to determine if scrolling is needed
4. Remove duplicate three-dot display at time position
5. Restart frontend service (HMR should apply automatically)
6. Manually verify all functionality

### Notes
- Frontend changes apply automatically via HMR, no full restart needed
- Per project rules, automatic browser conversation testing is prohibited
- User needs to provide manual verification steps
- All modifications should preserve existing functionality integrity

### Files to Modify
- `src/frontend/app/conversations/page.tsx` → rename to `src/frontend/app/chat/page.tsx`
  - Modify CSS animation (add 20px gap)
  - Add scroll condition logic
  - Remove duplicate three-dot display

### Verification Steps (User Manual Execution)
1. Start frontend: `cd src/frontend && pnpm dev`
2. Access `http://localhost:3000/chat` to confirm page displays normally
3. Try accessing `http://localhost:3000/conversations` to confirm 404
4. Create a long-title conversation, hover to check scroll animation
5. Create a short-title conversation, hover to confirm no scroll animation
6. Hover on any conversation row, confirm only one three-dot button appears
7. Test three-dot menu rename and delete functions
