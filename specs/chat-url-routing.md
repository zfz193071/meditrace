# Chat URL Routing Specification

## Problem Statement

当前 MediTrace 聊天页面存在以下用户体验问题：
1. 侧栏折叠时，"新建对话"按钮仍然显示，占用空间且不符合交互逻辑
2. 对话列表项没有唯一的会话 ID，无法通过 URL 直接访问特定对话
3. 新建对话时没有会话 ID，用户无法分享或 bookmark 特定对话
4. 刷新页面时无法保持当前对话状态（左侧列表高亮和右侧内容）

## Solution

实现基于会话 ID 的 URL 路由系统，支持：
1. 侧栏折叠时隐藏"新建对话"按钮
2. 为每个对话生成唯一 ID 并支持 URL 访问（`/chat/{conversationId}`）
3. 新建对话时自动创建正式会话并生成 ID
4. 页面刷新时自动恢复对话状态

## User Stories

1. 作为用户，我希望点击左上方折叠图标收起侧栏时，"新建对话"按钮也隐藏，so that 侧栏完全收起节省空间
2. 作为用户，我希望左侧列表的每个对话都有唯一 ID，so that 我可以通过 URL 分享特定对话
3. 作为用户，我希望点击对话列表项时，URL 自动更新为 `/chat/{对话 id}`，so that 我可以 bookmark 或分享当前对话
4. 作为用户，我希望新建对话时，一旦有 AI 回复就生成正式会话 ID，so that 对话可以被持久化和访问
5. 作为用户，我希望访问 `/chat/{会话 id}` 时，左侧列表对应项高亮，右侧显示该对话内容，so that 我能快速定位到特定对话
6. 作为用户，我希望刷新 `/chat/{会话 id}` 页面时，状态保持不变，so that 我不会丢失当前对话上下文
7. 作为用户，我希望访问不存在的会话 ID 时自动创建新对话，so that 不会出现错误页面
8. 作为用户，我希望访问 `/chat`（无 ID）时自动创建新对话，so that 我能立即开始新的咨询

## Implementation Decisions

### 1. URL 路由设计
- **基础路由**: `/chat` - 自动创建新对话
- **带 ID 路由**: `/chat/{conversationId}` - 加载指定对话
- 使用 Next.js 动态路由：`app/chat/[id]/page.tsx`

### 2. 会话 ID 生成策略
- **临时会话**: 使用 `temp-{timestamp}-{random}` 格式（仅前端）
- **正式会话**: 后端数据库生成唯一 ID（UUID 格式）
- **转换时机**: 用户发送第一条消息时，临时会话转换为正式会话

### 3. 侧栏折叠逻辑修改
- 当前: `sidebarCollapsed ? 'w-0' : 'w-80'` - 完全隐藏侧栏
- 修改：保持侧栏宽度但折叠内容，或完全隐藏"新建对话"按钮
- 决策：完全隐藏侧栏（保持当前行为），但确保"新建对话"按钮在折叠时不可见

### 4. 对话状态管理
```typescript
// 新增状态
const [urlConversationId, setUrlConversationId] = useState<string | null>(null);
const [isTempConversation, setIsTempConversation] = useState(false);

// URL 同步
useEffect(() => {
  const id = useParams().id;
  if (id) {
    loadConversation(id);
  } else {
    autoCreateConversation();
  }
}, [id]);
```

### 5. 页面刷新恢复逻辑
- 从 URL 读取对话 ID
- 从对话列表查找对应对话
- 找到则激活并高亮，否则创建新对话

### 6. API 接口（现有）
- `GET /api/conversations/{patientId}` - 获取对话列表
- `POST /api/conversations` - 创建对话
- `GET /api/conversations/{conversationId}` - 获取单个对话（需新增）
- `PUT /api/conversations/{conversationId}` - 更新对话

### 7. 前端组件修改
- **主页面**: `app/chat/page.tsx` - 支持 URL 参数解析
- **新增页面**: `app/chat/[id]/page.tsx` - 动态路由页面
- **API 层**: 添加 `getConversationById` 方法

## Testing Decisions

### 测试标准
- 只测试外部行为，不测试实现细节
- 验证 URL 导航、状态恢复、侧栏折叠等用户可感知的功能

### 测试模块
1. **URL 路由测试**
   - 访问 `/chat` 自动创建新对话
   - 访问 `/chat/{id}` 加载指定对话
   - 访问不存在的 ID 时创建新对话

2. **侧栏折叠测试**
   - 点击折叠按钮，侧栏完全隐藏
   - "新建对话"按钮在折叠时不可见

3. **对话 ID 生成测试**
   - 新建对话创建临时会话（temp- 前缀）
   - 发送消息后转换为正式会话
   - URL 自动更新为新 ID

4. **页面刷新恢复测试**
   - 刷新 `/chat/{id}` 保持对话状态
   - 左侧列表对应项高亮
   - 右侧显示正确内容

### 先例参考
- 现有代码中的会话列表加载逻辑
- 临时会话转换机制（已有实现）
- 流式响应处理逻辑

## Out of Scope

1. **对话分享功能** - 本需求仅实现 URL 访问，不包含分享链接生成 UI
2. **权限控制** - 暂不实现对话访问权限验证
3. **SEO 优化** - 对话页面为客户端渲染，不涉及服务端渲染
4. **浏览器历史记录** - 暂不实现 pushState/replaceState 管理历史记录
5. **移动端侧栏抽屉** - 保持当前移动端响应式行为，不优化为抽屉模式

## Further Notes

### 技术实现建议

1. **路由方案选择**
   - 方案 A: 使用 URL 查询参数 `/chat?id={conversationId}`
     - 优点：无需修改路由结构，兼容性好
     - 缺点：URL 不够美观
   - 方案 B: 使用动态路由 `/chat/{conversationId}`
     - 优点：URL 美观，符合 RESTful 规范
     - 缺点：需要创建新路由文件
   
   **推荐方案 B**，因为更符合现代 Web 应用的最佳实践

2. **会话转换时机**
   - 当前实现：发送消息时转换
   - 优化建议：AI 回复完成后转换（确保对话有价值）
   - 决策：保持当前实现（发送消息时转换）

3. **侧栏折叠优化**
   - 当前实现：`w-0` 完全隐藏
   - 需求理解：折叠时"新建对话"按钮隐藏
   - 实现：保持当前行为（侧栏完全隐藏，按钮自然不可见）

4. **错误处理**
   - 对话不存在：自动创建新对话并提示用户
   - 网络错误：显示错误提示，提供重试按钮
   - ID 格式无效：重定向到 `/chat`

### 已知限制

1. **临时会话清理** - 组件卸载时清理无消息的临时会话（现有逻辑）
2. **标题自动生成** - 已有实现，在 AI 回复时自动生成标题
3. **流式响应** - 已有修复，确保流式内容正确显示

### 依赖项

- Next.js 动态路由支持
- 后端 API 支持按 ID 获取对话
- 现有对话列表 API 包含完整对话数据（消息列表）

---

**待确认事项**:
1. 使用哪种 URL 方案？查询参数 vs 动态路由
2. 是否需要实现浏览器历史记录管理（后退/前进）？
3. 是否需要添加"复制分享链接"功能？
