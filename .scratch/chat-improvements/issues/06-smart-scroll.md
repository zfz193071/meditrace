# 06 — 智能滚动行为

**What to build:** 流式回复时自动滚动跟随新内容，但用户手动滚动查看历史时保持位置

**Blocked by:** 05 — AI 回复展示优化

**Status:** ready-for-agent

- [ ] 使用 `shouldAutoScroll` 状态追踪用户滚动意图
- [ ] 用户手动滚动时设置 `shouldAutoScroll = false`
- [ ] 新消息到达时重置 `shouldAutoScroll = true`
- [ ] 流式数据 chunk 更新时不触发滚动
- [ ] 仅通过消息数量变化触发滚动
- [ ] 切换对话时保持当前滚动位置（在底部）
