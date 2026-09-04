# 自动滚动修复记录

## 问题描述

在 AI 自动回答（流式响应）时，纵向滚动条不会自动跟随新内容往下滚动，导致用户需要手动滚动才能看到最新的回复内容。

## 根本原因

当前代码的滚动逻辑存在以下问题：

1. **滚动触发条件过于严格**：代码仅在消息数量增加时触发滚动（第 332-342 行的 `useEffect`），但流式响应时消息数量不会变化，只是消息内容在更新。

2. **流式更新未触发滚动**：在 `handleSendMessage` 的流式回调中（第 723-756 行），每次收到 chunk 只更新消息内容，不会触发滚动。

3. **滚动检测时机不正确**：当前的滚动逻辑依赖于 `activeConversation?.messages?.length` 的变化，但流式响应时消息数组长度不变，只有内容变化。

## 解决方案

### 修复策略

1. **在流式响应时持续滚动**：每次收到新的 chunk 内容时，如果用户没有手动滚动，则自动滚动到底部。

2. **保持用户手动滚动权限**：当用户手动滚动时，设置 `shouldAutoScrollRef.current = false`，停止自动滚动。

3. **使用平滑滚动体验**：在流式响应时使用 `behavior: "smooth"`，在用户发送新消息时使用 `behavior: "auto"`。

### 具体实现

#### 修改 `scrollToBottom` 函数

添加参数控制滚动行为：
- 流式响应时：`behavior: "smooth"`
- 新消息发送时：`behavior: "auto"`

#### 修改流式响应回调

在 `sendMessageStream` 的 chunk 处理中：
1. 更新消息内容后，检查 `shouldAutoScrollRef.current`
2. 如果允许自动滚动，调用 `scrollToBottom(true)`（true 表示流式响应）

#### 保持现有用户交互逻辑

- 用户手动滚动时禁用自动滚动（现有逻辑保留）
- 切换会话时重置滚动状态（现有逻辑保留）

## 文件变更

### src/frontend/app/chat/[id]/page.tsx

**修改位置 1：`scrollToBottom` 函数（第 380 行附近）**

```typescript
// 修改前
const scrollToBottom = () => {
  messagesEndRef.current?.scrollIntoView({ behavior: "auto" });
};

// 修改后
const scrollToBottom = (isStreaming: boolean = false) => {
  messagesEndRef.current?.scrollIntoView({
    behavior: isStreaming ? "smooth" : "auto",
  });
};
```

**修改位置 2：流式响应回调（第 723-756 行附近）**

在 chunk 处理的 `setTimeout` 回调末尾添加滚动逻辑：

```typescript
// 修改前
// 修复：流式更新时不主动滚动，让消息数量变化 useEffect 处理

// 修改后
// 流式响应时自动滚动（如果用户没有手动滚动）
if (shouldAutoScrollRef.current) {
  scrollToBottom(true); // true 表示流式响应，使用平滑滚动
}
```

## 测试步骤

1. 启动前端服务：
   ```bash
   cd src/frontend && pnpm dev
   ```

2. 测试自动滚动功能：
   - 访问 `http://localhost:3000/chat/{conversation-id}`
   - 发送一条需要较长回复的消息
   - 观察 AI 回复时，滚动条是否自动跟随新内容往下滚动

3. 测试用户手动滚动：
   - 在 AI 回复过程中，手动向上滚动查看历史消息
   - 确认自动滚动已停止，不再强制滚动到底部

4. 测试切换会话：
   - 切换到另一个对话
   - 确认切换后滚动位置在底部

## 注意事项

- 前端代码修改后 HMR 会自动应用
- 验证时需用户手动在浏览器测试
- 禁止自动在浏览器中向 AI 发送消息进行测试（会消耗 API token）

## 相关代码

- 第 88 行：`shouldAutoScrollRef` 定义
- 第 332-342 行：消息数量变化时的滚动逻辑
- 第 380 行：`scrollToBottom` 函数
- 第 699 行：发送消息时重置自动滚动标志
- 第 723-756 行：流式响应回调
- 第 1005-1010 行：用户手动滚动时禁用自动滚动

## 修复日期

2026-09-02
