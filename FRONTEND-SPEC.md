# MediTrace 前端实现规格说明

> 版本：1.0.0
> 最后更新：2024
> 状态：实施中

---

## 问题陈述

医疗从业者和患者在使用当前 AI 诊断系统时面临以下挑战：

- **缺乏直观的交互界面**: 需要专业工具才能访问诊断功能
- **溯源信息不透明**: 无法直观查看和验证诊断记录的区块链溯源信息
- **历史记录管理困难**: 难以跟踪和管理历史诊断记录
- **合规审计体验差**: 缺乏友好的界面来验证诊断记录的完整性和真实性

## 解决方案

MediTrace 前端通过 Next.js 构建一个现代化、响应式的 Web 应用，提供：

- **直观的对话界面**: 患者可输入症状并获得 AI 诊断建议
- **完整的溯源展示**: 每次诊断自动记录到区块链，并提供可视化溯源信息
- **历史记录管理**: 用户可查询、筛选和下载历史诊断记录
- **链上验证工具**: 监管者可验证诊断记录的真实性和完整性
- **多轮对话支持**: 支持上下文感知的多轮医疗问答

## 用户故事

### 核心功能用户故事

1. 作为患者，我希望输入症状描述，以便获得初步诊断建议
2. 作为患者，我希望看到结构化的诊断结果（疾病列表、置信度、建议检查），以便理解诊断依据
3. 作为患者，我希望每条诊断建议都包含免责声明，以便了解 AI 诊断的局限性
4. 作为患者，我希望查看诊断的溯源信息（诊断 ID、上链状态），以便信任诊断结果
5. 作为患者，我希望输入我的钱包地址，以便诊断记录能正确关联到我的身份
6. 作为患者，我希望系统验证我输入的地址格式，以便避免记录错误
7. 作为患者，我希望在诊断过程中看到加载状态，以便知道系统正在处理
8. 作为患者，我希望诊断失败时有明确的错误提示，以便知道如何重试

### 历史记录用户故事

9. 作为患者，我希望查看我的历史诊断记录，以便跟踪健康状况变化
10. 作为患者，我希望按时间排序历史记录，以便查看最新的诊断
11. 作为患者，我希望看到每条记录的上链状态，以便确认记录已存档
12. 作为患者，我希望点击"验证记录"查看链上详情，以便确认记录真实性
13. 作为患者，我希望下载报告 PDF，以便保存诊断记录用于就医
14. 作为患者，我希望下载报告时看到加载状态，以便知道下载进度
15. 作为患者，我希望切换用户地址查看不同用户的记录，以便管理多个账户
16. 作为患者，我希望刷新历史记录列表，以便获取最新的上链状态
17. 作为患者，我希望在空历史记录时看到引导提示，以便知道如何开始使用

### 链上验证用户故事

18. 作为监管者，我希望输入诊断 ID 验证记录，以便确认诊断的真实性
19. 作为监管者，我希望看到验证通过时的详细链上记录，以便审计诊断数据
20. 作为监管者，我希望看到数据哈希、模型版本、时间戳等信息，以便验证完整性
21. 作为监管者，我希望点击哈希值复制到剪贴板，以便在区块链浏览器中查询
22. 作为监管者，我希望看到区块链浏览器链接，以便深入验证交易
23. 作为监管者，我希望验证失败时有明确提示，以便知道记录可能已被篡改
24. 作为监管者，我希望看到如何验证的说明，以便理解验证流程
25. 作为监管者，我希望从历史记录页面直接进入验证页面，以便快速验证

### 多轮对话用户故事（扩展功能）

26. 作为患者，我希望创建新的诊断对话，以便开始新的健康咨询
27. 作为患者，我希望看到我的对话列表，以便管理多个健康话题
28. 作为患者，我希望在对话中继续提问，以便获得更详细的诊断建议
29. 作为患者，我希望 AI 能记住之前的对话上下文，以便提供更准确的建议
30. 作为患者，我希望看到系统推荐的追问问题，以便获取更多信息
31. 作为医生，我希望查看患者的完整对话历史，以便了解病情发展
32. 作为医生，我希望删除不需要的对话，以便管理存储空间

## 实现决策

### 技术架构决策

- **框架选择**: Next.js 14 (App Router) - 提供 SSR、API Routes 和优秀的 TypeScript 支持
- **样式方案**: Tailwind CSS - 原子化 CSS 实现快速 UI 开发和响应式设计
- **状态管理**: React Hooks (useState, useEffect) - 轻量级，满足当前需求
- **HTTP 客户端**: Fetch API - 原生支持，无需额外依赖
- **路由方案**: Next.js File-based Routing - `/`, `/history`, `/verify`, `/conversations`

### 组件设计决策

**主页组件 (page.tsx)**:
- 采用单页滚动设计，包含英雄区域、诊断表单、功能特性和导航卡片
- 诊断表单集成用户地址输入和验证
- 诊断结果以卡片形式展示，包含疾病建议、免责声明和溯源信息
- 使用渐变背景和卡片阴影创建现代化视觉风格

**历史记录页面 (history/page.tsx)**:
- 用户信息卡片显示当前地址和切换功能
- 记录列表采用时间倒序排列，每条记录包含诊断 ID、时间戳、疾病类型和状态徽章
- 操作按钮包括"验证记录"和"下载报告"
- 空状态引导用户开始新诊断
- 全局 loading 遮罩层处理下载报告时的等待状态

**验证页面 (verify/page.tsx)**:
- 输入框支持直接输入诊断 ID 或从历史记录跳转
- 验证结果分为"验证通过"和"验证失败"两种状态
- 通过时展示详细的链上记录（数据哈希、模型版本、时间戳、患者地址、IPFS CID）
- 哈希值支持点击复制，提供区块链浏览器链接
- 底部包含"如何验证"说明卡片

**共享组件模式**:
- 所有页面使用统一的头部横幅设计（渐变背景、返回按钮、标题）
- 统一的卡片样式（card-modern, history-card-bg, card-shadow-xl）
- 统一的状态徽章（badge-success, badge-warning, badge-error, badge-info）
- 统一的按钮样式（btn-primary, btn-secondary）
- 统一的输入框样式（input-modern）

### API 集成决策

**后端 API 端点**:
```typescript
// 诊断 API
POST /api/diagnose
- 请求：{ symptoms: string, userId: string }
- 响应：{ diagnosisId, suggestions[], disclaimer, ipfsCid, chainTxHash }

// 历史记录 API
GET /api/history/:userId
- 响应：{ records: [{ diagnosisId, timestamp, diseaseTypes[], chainStatus, ipfsCid }] }

// 验证 API
GET /api/verify/:diagnosisId
- 响应：{ isValid, chainRecord: { dataHash, modelVersion, timestamp }, ipfsCid }

// 下载报告 API
GET /api/report/:diagnosisId
- 响应：PDF 文件二进制流

// 对话 API（扩展）
POST /api/conversations
GET /api/conversations
GET /api/conversations/:id
POST /api/conversations/:id/messages
DELETE /api/conversations/:id
```

**环境变量配置**:
```bash
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
```

### 数据模型决策

**前端类型定义**:
```typescript
interface DiagnosisSuggestion {
  disease: string;
  confidence: number;  // 0-1
  recommendations: string[];
}

interface DiagnosisResult {
  diagnosisId: string;
  suggestions: DiagnosisSuggestion[];
  disclaimer: string;
  ipfsCid?: string;
  chainTxHash?: string;
}

interface HistoryRecord {
  diagnosisId: string;
  timestamp: number;
  diseaseTypes: string[];
  chainStatus: "pending" | "confirmed" | "failed";
  ipfsCid?: string;
}

interface VerificationResult {
  isValid: boolean;
  chainRecord?: {
    dataHash: string;
    modelVersion: string;
    timestamp: number;
    patient: string;
    ipfsCid: string;
  };
  ipfsCid: string;
}
```

### UI/UX 设计决策

**视觉风格**:
- 主色调：绿色（医疗、健康）+ 蓝色（科技、信任）+ 紫色（创新）
- 渐变背景：`gradient-bg` - 从绿色到蓝色的渐变
- 卡片设计：圆角 2xl，阴影 xl，悬停时有轻微上浮效果
- 响应式布局：移动端优先，桌面端使用多列网格

**交互模式**:
- 加载状态：使用旋转 spinner 图标 + 文字提示
- 错误提示：红色文字 + 警告图标
- 成功提示：绿色徽章 + 对勾图标
- 空状态：大图标 + 引导文字 + 操作按钮
- 复制功能：点击哈希值复制到剪贴板，弹出提示

**动画效果**:
- 页面加载：fade-in 淡入动画
- 卡片悬停：hover-lift 轻微上浮
- 按钮点击：transition-all 平滑过渡

### 错误处理决策

**用户地址验证**:
- 必须以 0x 开头
- 长度必须为 42 字符
- 0x 后必须为 40 个十六进制字符
- 验证失败时显示红色错误提示

**API 调用失败**:
- 诊断失败：弹出 alert 提示"诊断失败，请稍后重试"
- 历史记录加载失败：显示空状态，但允许用户刷新
- 验证失败：显示"验证失败"卡片，提示记录可能不存在
- 下载报告失败：显示错误详情，包含诊断 ID 便于排查

**上链失败处理**:
- 不影响诊断流程，继续返回诊断结果
- 在溯源信息中显示"待上链"或"上链失败"状态
- 用户可在历史记录中刷新查看最新状态

### 性能优化决策

**前端优化**:
- 使用 React.memo 优化列表渲染（历史记录）
- 使用 useCallback 优化事件处理函数
- 图片使用懒加载（如果添加图标图片）
- CSS 使用 Tailwind 的 PurgeCSS 自动移除未使用样式

**API 优化**:
- 历史记录自动刷新：切换用户地址时自动重新获取
- 验证页面自动验证：从历史记录跳转时自动触发验证
- 下载报告使用流式传输，避免大文件阻塞

### 安全考虑

**数据保护**:
- 链上仅存储数据哈希，不存储明文症状和诊断结果
- 用户地址作为伪匿名标识符，不关联真实身份
- IPFS 报告使用加密存储（如果启用 Pinata 加密功能）

**输入验证**:
- 用户地址格式验证（前端 + 后端双重验证）
- 症状描述长度限制（建议 1000 字符以内）
- SQL 注入防护（后端使用参数化查询）

**CORS 配置**:
- 允许的来源列表通过环境变量配置
- 默认允许 localhost:3000 和 localhost:8000
- 生产环境应限制为正式域名

## 测试决策

### 测试标准

**测试原则**:
- 只测试外部行为，不测试实现细节
- 优先测试用户可见的功能
- 模拟后端 API 响应，不依赖真实服务

### 测试范围

**主页测试**:
- 症状输入框可编辑
- 用户地址输入框可编辑
- 地址格式验证（有效/无效地址）
- 诊断按钮点击触发 API 调用
- 加载状态显示
- 诊断结果正确渲染（疾病列表、置信度、建议）
- 免责声明显示
- 溯源信息显示（诊断 ID、上链状态）

**历史记录测试**:
- 用户地址显示正确
- 地址切换触发重新加载
- 历史记录列表按时间倒序排列
- 状态徽章正确显示（已上链/待上链/上链失败）
- 验证按钮点击跳转到验证页面
- 下载报告按钮触发下载
- 空状态显示引导
- 刷新按钮重新获取数据

**验证页面测试**:
- 诊断 ID 输入框可编辑
- 验证按钮点击触发验证
- 验证通过显示详细链上记录
- 验证失败显示错误提示
- 哈希值点击复制功能
- 区块链浏览器链接正确打开
- 从历史记录跳转时自动验证

### 先例参考

**现有测试模式**:
- 后端使用 pytest 测试 API 端点
- 智能合约使用 Hardhat + Chai 测试
- 前端可借鉴使用 React Testing Library

**测试工具推荐**:
- Jest - 测试运行器
- React Testing Library - 组件测试
- MSW (Mock Service Worker) - API 模拟
- Playwright - E2E 测试

## 超出范围

以下功能不在当前前端实现范围内：

- **用户认证系统**: 当前使用手动输入的钱包地址，未集成 MetaMask 或其他钱包连接
- **实时通知**: 上链状态变化不推送通知，用户需手动刷新
- **数据导出**: 仅支持下载报告 PDF，不支持批量导出
- **多语言支持**: 当前仅支持中文，未实现 i18n
- **高级分析**: 不提供诊断数据统计和可视化图表
- **医生后台**: 不提供医生专用的患者管理界面
- **移动端 App**: 仅支持 Web 响应式，不提供原生 App
- **语音输入**: 症状描述仅支持文本输入

## 进一步说明

### 当前实现状态

**已完成**:
- ✅ 主页诊断界面（症状输入、结果展示、溯源信息）
- ✅ 历史记录页面（列表展示、状态徽章、下载报告）
- ✅ 验证页面（链上查询、详情展示、区块链浏览器链接）
- ✅ 响应式设计（移动端 + 桌面端）
- ✅ 统一 UI 组件库（卡片、按钮、输入框、徽章）
- ✅ 错误处理和加载状态
- ✅ 后端 API 集成（诊断、历史、验证、报告下载）

**待实现**:
- ⏳ 多轮对话界面（对话列表、聊天界面、上下文管理）
- ⏳ 钱包连接集成（MetaMask、WalletConnect）
- ⏳ 前端单元测试和 E2E 测试
- ⏳ 性能优化（代码分割、懒加载）
- ⏳ PWA 支持（离线使用、添加到主屏幕）

### 已知限制

1. **地址管理**: 当前用户需手动输入钱包地址，生产环境应集成钱包连接
2. **疾病类型解析**: 历史记录中的 diseaseTypes 字段为空数组，需后端补充
3. **IPFS 依赖**: 下载报告依赖 IPFS 网关可用性，可能受网络影响
4. **区块链查询**: 历史记录从区块链查询，本地链数据可能不完整

### 未来扩展方向

1. **对话系统增强**:
   - 实现完整的对话界面（类似聊天应用）
   - 支持语音输入和输出
   - 添加情感分析和紧急程度评估

2. **数据可视化**:
   - 健康趋势图表（疾病频率、症状变化）
   - 诊断统计面板（总次数、上链成功率）
   - 时间线视图（健康状况演变）

3. **社交功能**:
   - 匿名分享诊断经验
   - 医生评价和推荐
   - 健康社区讨论

4. **合规增强**:
   - GDPR 数据删除请求
   - 审计日志导出
   - 合规报告生成

### 部署建议

**前端部署**:
- 平台：Vercel（推荐）或 Netlify
- 环境变量：设置 `NEXT_PUBLIC_BACKEND_URL` 为后端 API 地址
- 自定义域名：配置正式域名和 SSL 证书
- CI/CD：Git push 自动部署

**后端部署**:
- 平台：Render、Railway 或 AWS Elastic Beanstalk
- 环境变量：配置 DeepSeek API Key、Pinata JWT、区块链节点 URL
- 数据库：SQLite（开发）或 PostgreSQL（生产）

**监控和日志**:
- 前端：Sentry 错误追踪
- 后端：Logtail 或 CloudWatch 日志
- API 监控：Pingdom 或 Uptime Robot

---

## 附录

### A. 文件结构

```
src/frontend/
├── app/
│   ├── layout.tsx           # 根布局（HTML 结构、元数据）
│   ├── page.tsx             # 主页（诊断界面）
│   ├── globals.css          # 全局样式（Tailwind 指令、自定义类）
│   ├── history/
│   │   └── page.tsx         # 历史记录页面
│   ├── verify/
│   │   └── page.tsx         # 链上验证页面
│   └── conversations/       # （待实现）对话列表页面
│       └── page.tsx
├── components/              # （建议创建）共享组件目录
│   ├── Header.tsx
│   ├── DiagnosisForm.tsx
│   ├── ResultCard.tsx
│   └── StatusBadge.tsx
├── types/                   # （建议创建）类型定义目录
│   └── index.ts
├── lib/                     # （建议创建）工具函数目录
│   └── api.ts
├── package.json
├── tsconfig.json
├── tailwind.config.js
└── .env.local.example
```

### B. 关键样式类

```css
/* 渐变背景 */
.gradient-bg {
  background: linear-gradient(135deg, #10b981 0%, #3b82f6 100%);
}

/* 卡片样式 */
.card-modern {
  background: white;
  border-radius: 1rem;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.1);
  padding: 2rem;
}

/* 历史卡片背景 */
.history-card-bg {
  background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
}

/* 主按钮 */
.btn-primary {
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
  color: white;
  border-radius: 0.75rem;
  font-weight: 600;
}

/* 次级按钮 */
.btn-secondary {
  background: white;
  color: #10b981;
  border: 2px solid #10b981;
  border-radius: 0.75rem;
  font-weight: 600;
}

/* 状态徽章 */
.badge-success { background: #d1fae5; color: #065f46; }
.badge-warning { background: #fef3c7; color: #92400e; }
.badge-error { background: #fee2e2; color: #991b1b; }
.badge-info { background: #dbeafe; color: #1e40af; }
```

### C. API 响应示例

**诊断响应**:
```json
{
  "diagnosisId": "1234567890abcdef",
  "suggestions": [
    {
      "disease": "上呼吸道感染",
      "confidence": 0.85,
      "recommendations": ["血常规检查", "胸部 X 光", "病毒检测"]
    }
  ],
  "disclaimer": "本系统提供的诊断建议仅供参考，不能替代专业医疗意见...",
  "ipfsCid": "QmXoypizjW3WknFiJnKLwHCnL72vedxjQkDDP1mXWo6uco",
  "chainTxHash": "0x1234...abcd"
}
```

**历史记录响应**:
```json
{
  "records": [
    {
      "diagnosisId": "1234567890abcdef",
      "timestamp": 1704067200,
      "diseaseTypes": ["上呼吸道感染", "发热"],
      "chainStatus": "confirmed",
      "ipfsCid": "QmXoypizjW3WknFiJnKLwHCnL72vedxjQkDDP1mXWo6uco"
    }
  ]
}
```

**验证响应**:
```json
{
  "isValid": true,
  "chainRecord": {
    "dataHash": "0xabcd1234...",
    "modelVersion": "deepseek-chat-v1-medkb-2024q1",
    "timestamp": 1704067200,
    "patient": "0x262Ee58D3e7A782ceC68094A6DACb53D02Fa9d0B",
    "ipfsCid": "QmXoypizjW3WknFiJnKLwHCnL72vedxjQkDDP1mXWo6uco"
  },
  "ipfsCid": "QmXoypizjW3WknFiJnKLwHCnL72vedxjQkDDP1mXWo6uco"
}
```

---

**文档结束**
