# 演示事项选择后的键盘焦点

日期：2026-10-27。范围：求职 MVP 核心演示验收，共享 `ReviewWorkspace`。

## 复现与原因

在独立后台 Chrome 中打开静态演示，使用 390px 窄屏和 Tab／Enter 选择事项。
界面已切换到证据面板，但焦点落回 `body`，无法从刚选择的证据继续键盘操作。
原实现先更新 React 状态，再用 `requestAnimationFrame` 转移焦点；动画帧与
面板提交没有绑定，后台页面的帧调度也不能作为焦点转移的可靠时机。

## 修改

每次有效选择事项递增焦点请求，在 React 提交后由 effect 聚焦证据区域。
选择同一事项也生效；初次加载、保存决定和普通重渲染不自动移动焦点。
保留现有未保存编辑确认和写入期间禁用规则。

## 验证

- 新回归暂停动画帧调度，检查首次选择及再次选择同一事项的焦点。旧实现失败。
- `NEXT_PUBLIC_PORTFOLIO_ONLY=true pnpm --dir src/frontend test --runInBand __tests__/components/DemoWorkspace.test.tsx __tests__/components/ReviewWorkspace.test.tsx`：19 passed。
- 修改文件的 ESLint（零警告）及独立静态构建（含 TypeScript、链接／资源检查）通过。
- 浏览器复验及边界见 [MVP 静态演示说明](docs/portfolio/STATIC-DEMO.md)。这不代表完整 V1 或生产上线验收。

测试工具首轮还遗漏了 CDP Enter 的文本事件；补齐后面板切换正常，随后独立
复现上述产品焦点问题。没有为测试改成鼠标点击，也没有触发任何 AI 请求。
