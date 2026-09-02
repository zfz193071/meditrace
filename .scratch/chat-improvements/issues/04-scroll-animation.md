# 04 — 滚动动画优化

**What to build:** 对话标题仅在溢出时显示平滑滚动动画，滚动结束后有 20px 空白间隔

**Blocked by:** 01 — 路由重构

**Status:** ready-for-agent

- [ ] 改进 CSS 动画关键帧（添加 20px 间隔）
- [ ] 使用 `animation-fill-mode: forwards` 确保正确结束位置
- [ ] 鼠标移开后动画停止
- [ ] 验证短标题不触发动画
