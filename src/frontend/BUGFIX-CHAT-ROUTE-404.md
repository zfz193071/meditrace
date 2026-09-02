# 路由 404 修复记录

## 问题描述

访问 `http://localhost:3000/chat/{conversation-id}` 页面刷新时报 404 错误。

## 根本原因

在 Next.js App Router 中，当同时存在 `/chat/page.tsx` 和 `/chat/[id]/page.tsx` 时：

- `/chat/page.tsx` 应该处理 `/chat` 路由（无参数）
- `/chat/[id]/page.tsx` 应该处理 `/chat/{id}` 路由（有动态参数）

之前两个文件内容完全相同，都依赖 `params.id`，导致：
1. `/chat` 路由访问时，`params.id` 为 `undefined`
2. 路由匹配可能产生冲突
3. 页面刷新时 Next.js 无法正确匹配路由

## 修复方案

### 修改 `/chat/page.tsx`

1. **移除 `useParams` 导入**：不再使用 URL 参数
2. **移除 `urlConversationId` 状态**：不需要追踪 URL 中的对话 ID
3. **简化 `useEffect`**：只加载对话列表并自动创建新对话
4. **移除返回按钮逻辑**：`/chat` 路由不需要返回按钮

### `/chat/[id]/page.tsx` 保持不变

保留完整的 `params.id` 依赖逻辑，用于处理动态路由。

## 文件变更

### src/frontend/app/chat/page.tsx

**移除的内容：**
- `useParams` 导入
- `urlConversationId` 状态
- URL 参数依赖的 `useEffect` 逻辑
- 返回按钮（←）及其逻辑

**保留的功能：**
- 对话列表展示
- 新建对话
- 消息发送
- 流式响应显示
- 对话标题自动生成

### src/frontend/app/chat/[id]/page.tsx

**保持不变**：完整保留动态路由逻辑

## 路由结构

```
src/frontend/app/chat/
├── page.tsx          # 处理 /chat 路由
└── [id]/
    └── page.tsx      # 处理 /chat/{id} 路由
```

## 测试步骤

1. 启动前端服务：
   ```bash
   cd src/frontend && pnpm dev
   ```

2. 测试 `/chat` 路由：
   - 访问 `http://localhost:3000/chat`
   - 应该显示对话列表和新建的临时对话
   - 不应报 404 错误

3. 测试 `/chat/{id}` 路由：
   - 在对话列表中选择一个对话
   - URL 应该变为 `http://localhost:3000/chat/{conversation-id}`
   - 刷新页面，应该正常显示该对话内容
   - 不应报 404 错误

## 注意事项

- 前端代码修改后 HMR 会自动应用
- 验证时需用户手动在浏览器测试
- 禁止自动在浏览器中向 AI 发送消息进行测试（会消耗 API token）

## 修复日期

2026-09-02
