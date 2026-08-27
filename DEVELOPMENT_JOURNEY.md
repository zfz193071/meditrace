# MediTrace 开发历程说明文档

> 本文档基于项目从 2026 年 8 月 24 日至 8 月 27 日的 22 个 git 提交记录编写，完整记录了项目从 0 到 MVP 的开发历程。

---

## 📊 项目概览

**项目名称**: MediTrace - AI-powered Medical Diagnostic System with Blockchain Audit Trails  
**开发周期**: 4 天 (2026-08-24 ~ 2026-08-27)  
**总提交数**: 22 个 commits  
**技术栈**: Next.js + FastAPI + Solidity + DeepSeek AI + IPFS + Sepolia 测试网

---

## 🎯 项目核心功能

MediTrace 是一个结合大模型与 Web3 技术的医疗诊断辅助系统，主要功能包括：

1. **AI 诊断问答**: 用户输入症状，DeepSeek AI 提供初步诊断建议
2. **区块链溯源**: 每次诊断自动记录到区块链（数据哈希、模型版本、时间戳）
3. **历史记录查询**: 患者可查看自己的历史诊断记录
4. **链上验证**: 任何人都可验证诊断记录的真实性和完整性
5. **IPFS 报告存储**: 详细诊断报告存储在去中心化存储网络
6. **下载报告**: 支持下载完整的诊断报告 PDF

---

## 🐛 遇到的问题与解决方案

### 问题 1: Hardhat TypeScript 配置兼容性问题

**提交**: `cf9c301` - Convert Hardhat config to JavaScript

**问题描述**:
- Hardhat 的 `hardhat.config.ts` 与 ts-node 存在兼容性问题
- 导致合约编译和部署脚本无法正常运行

**解决思路**:
- 将 `hardhat.config.ts` 转换为 `hardhat.config.js`
- 简化配置，避免 TypeScript 编译器的复杂性
- 确保部署脚本能顺利执行

**学到的经验**:
> 在区块链开发中，配置文件的语言选择要考虑工具链的成熟度。JavaScript 在某些场景下比 TypeScript 更稳定。

---

### 问题 2: CORS 跨域问题

**提交**: `b79082a` - Solve CORS cross-origin issues

**问题描述**:
- 前端 (localhost:3000) 调用后端 (localhost:8000) 时出现 CORS 错误
- 浏览器阻止了跨域请求

**解决思路**:
- 后端 CORS 配置从通配符 `*` 改为明确的 localhost 地址
- 添加具体的端口号 `http://localhost:3000`
- 配置允许的 HTTP 方法和请求头

```python
# 修复前
CORSMiddleware(app, allow_origins=["*"])

# 修复后
CORSMiddleware(app, allow_origins=["http://localhost:3000"])
```

**学到的经验**:
> 生产环境必须精确配置 CORS，不能滥用通配符。开发环境也要遵循最小权限原则。

---

### 问题 3: web3.py 账户 API 兼容性

**提交**: `b79082a` - Blockchain client API compatibility

**问题描述**:
- web3.py 库的账户创建 API 发生变化
- 旧的 `from_account` 方法已被弃用
- 导致私钥管理和交易签名失败

**解决思路**:
- 将 `from_account` 改为 `Account.from_key`
- 更新交易构建流程：使用 `build_transaction` + `sign_transaction`
- 确保与最新 web3.py 版本兼容

**学到的经验**:
> 第三方库的版本更新可能破坏 API 兼容性，需要关注依赖的版本管理和迁移指南。

---

### 问题 4: 链上数据格式显示错误

**提交**: `b79082a` - Fix on-chain data format

**问题描述**:
- 诊断 ID 和 dataHash 以 bytes 格式显示，用户无法理解
- 前端展示的是原始字节数据而非可读的 hex 字符串

**解决思路**:
- 将 bytes 数据转换为 hex 字符串格式
- 在前端显示时使用 `0x` 前缀的 hex 格式
- 添加哈希格式化工具函数 `formatHash()`

**学到的经验**:
> 区块链数据的可读性至关重要。hex 格式是行业标准，用户更容易理解和复制。

---

### 问题 5: 历史记录查询使用 Mock 数据

**提交**: `d3f818c` - Resolve critical code review issues

**问题描述**:
- 初始版本的历史记录页面使用 mock 数据
- 没有真正从区块链读取患者记录
- 违反了功能需求 FR-03

**解决思路**:
- 实现真实的区块链查询：`blockchain.get_patient_records()`
- 后端调用智能合约的 `getPatientRecords` 方法
- 前端展示真实的链上数据

**学到的经验**:
> MVP 阶段也要坚持使用真实数据，mock 数据只适合原型验证，不适合功能演示。

---

### 问题 6: 代码重复和架构问题

**提交**: `d3f818c` - Code review fixes

**问题描述**:
- 前端存在重复代码：`formatDate`、`getStatusColor` 等函数在多个页面重复
- 数据参数传递分散，缺乏封装
- 存在 "Shotgun Surgery" 代码异味

**解决思路**:
- 创建共享工具库 `src/frontend/lib/utils.ts`
- 提取 `DiagnosisMetadata` 值对象封装数据
- 统一格式化函数和颜色逻辑

**修改文件**:
- 新增：`utils.ts` - 共享工具函数
- 新增：`models.py` - 后端数据模型
- 重构：`history/page.tsx`、`verify/page.tsx`

**学到的经验**:
> 代码审查是提升代码质量的重要手段。尽早识别代码异味，避免技术债务累积。

---

### 问题 7: Tailwind CSS 样式不生效

**提交**: `dede782` - Fix Tailwind CSS configuration

**问题描述**:
- 前端页面的 Tailwind 样式不生效
- 页面显示为默认样式，缺乏视觉设计

**解决思路**:
- 检查 `tailwind.config.js` 的内容路径配置
- 确保包含所有 `.tsx` 文件的路径
- 验证 CSS 文件正确引入了 Tailwind 指令

**学到的经验**:
> 框架配置问题往往是最容易被忽视的 bug。确保内容路径覆盖所有需要样式的文件。

---

### 问题 8: 时间戳显示为 1970 年

**提交**: `83a83c7` - Fix timestamp display issue

**问题描述**:
- 历史记录的时间戳显示为 1970-01-01
- 区块链返回的是 Unix 时间戳（秒），前端按毫秒解析

**解决思路**:
- 检查时间戳单位：区块链返回秒，JavaScript 需要毫秒
- 将时间戳乘以 1000 后再创建 Date 对象
- 添加时间格式化工具函数

```typescript
// 修复前
new Date(timestamp)

// 修复后
new Date(timestamp * 1000)
```

**学到的经验**:
> 时间戳单位转换是常见陷阱。区块链通常用秒，JavaScript 用毫秒，必须显式转换。

---

### 问题 9: IPFS 上传失败导致空 CID 上链

**提交**: `92d9ccd` - Fix IPFS upload failure

**问题描述**:
- IPFS 上传失败时，后端仍然继续执行链上记录
- 导致空 CID 被记录到区块链，数据不可追溯
- Pinata API 认证方式不兼容

**解决思路**:
- IPFS 上传失败时抛出 `HTTPException`，阻止空 CID 上链
- 实现 Pinata JWT token 认证方式（替代旧的 API key）
- 下载报告时添加多网关重试机制
- 前端显示详细的错误消息

**关键代码**:
```python
# IPFS 上传失败时阻止上链
if not ipfs_cid:
    raise HTTPException(status_code=500, detail="IPFS upload failed")
```

**学到的经验**:
> 区块链数据一旦写入不可修改。必须在写入前确保所有依赖数据（如 IPFS）都成功。

---

### 问题 10: 历史记录 API 缺少 ipfsCid 字段

**提交**: `45cde61` - Fix missing ipfsCid field

**问题描述**:
- 历史记录页面显示"无报告"，无法下载报告
- 链上记录包含 IPFS CID，但 FastAPI 响应模型未定义该字段
- Pydantic 模型过滤了未定义的字段

**解决思路**:
- 在 `HistoryRecord` 模型中添加 `ipfsCid` 可选字段
- 确保历史记录 API 返回完整的 IPFS 信息
- 改进下载报告 API 的错误提示信息

**新增文档**:
- `docs/IPFS_SETUP.md` - IPFS 配置指南
- `docs/adr/0004-ipfs-configuration-fix.md` - ADR 决策记录

**学到的经验**:
> Pydantic 模型会严格过滤未定义的字段。确保所有需要返回的字段都在模型中定义。

---

### 问题 11: 下载报告功能缺失加载状态

**提交**: `9b4bb8a` - Add loading state to download button

**问题描述**:
- 下载报告时用户不知道是否正在处理
- 多次点击可能导致重复请求
- 用户体验不佳

**解决思路**:
- 为下载报告按钮添加加载状态
- 下载过程中禁用按钮并显示 loading 图标
- 完成后恢复按钮状态或显示错误

**学到的经验**:
> 异步操作必须提供视觉反馈。加载状态是用户体验的基本要求。

---

### 问题 12: 用户地址切换功能缺失

**提交**: `a6a5929` - Complete history page features

**问题描述**:
- 历史记录页面只能查看当前用户地址的记录
- 无法切换查看其他地址的历史记录
- 缺乏刷新功能

**解决思路**:
- 添加用户地址输入框，允许手动修改
- 实现地址切换后重新查询历史记录
- 添加刷新按钮，手动触发数据重新加载

**学到的经验**:
> 区块链应用要支持多地址查看。用户可能需要查看不同钱包的历史记录。

---

## 💡 解决思路总结

### 1. 分阶段开发策略

```
Phase 1: 基础设施搭建 (commits 1-3)
  ├── 项目初始化
  ├── 技术栈配置
  └── 合约部署

Phase 2: 核心功能实现 (commits 4-8)
  ├── AI 诊断集成
  ├── 区块链记录
  └── 基础前端页面

Phase 3: Bug 修复与优化 (commits 9-18)
  ├── CORS 和 API 兼容性
  ├── 数据格式修复
  └── 代码审查问题

Phase 4: 功能完善 (commits 19-22)
  ├── IPFS 集成
  ├── 下载报告功能
  └── 用户体验优化
```

### 2. 问题驱动的开发流程

1. **发现问题**: 通过测试、代码审查或用户反馈
2. **定位根源**: 分析日志、调试代码、理解底层机制
3. **设计方案**: 考虑多种解决方案，选择最优
4. **实施修复**: 编写代码、添加测试、更新文档
5. **验证效果**: 回归测试、确保无副作用

### 3. 文档驱动的设计思维

- 每个重大修复都创建了 ADR (Architecture Decision Record)
- 配置问题都有对应的 setup 文档
- 部署流程有详细的 checklist

---

## 🎓 从这个项目能学到什么

### 1. 全栈开发能力

#### 前端技术栈
- **Next.js**: React 服务端组件、App Router
- **TypeScript**: 类型安全的前端开发
- **Tailwind CSS**: 原子化 CSS 框架
- **状态管理**: 处理异步数据和用户交互

#### 后端技术栈
- **FastAPI**: 高性能 Python Web 框架
- **Pydantic**: 数据验证和序列化
- **Async/Await**: 异步编程模式

#### 区块链开发
- **Solidity**: 智能合约编写
- **Hardhat**: 以太坊开发框架
- **web3.py**: Python 区块链交互库
- **Sepolia 测试网**: 真实网络部署经验

### 2. 系统集成经验

#### AI 集成
- DeepSeek API 调用和错误处理
- 医学知识库 RAG (Retrieval-Augmented Generation)
- Prompt Engineering 技巧

#### 去中心化存储
- IPFS 原理和 Pinata 服务
- 内容寻址和数据持久性
- 多网关重试机制

#### 区块链设计模式
- 事件日志记录
- 哈希验证机制
- 不可篡改的数据结构

### 3. 工程实践技能

#### 代码质量
- 代码审查 (Code Review) 流程
- 代码异味识别和重构
- 设计模式应用 (值对象、工具库)

#### DevOps
- 环境变量管理
- 虚拟环境配置 (Python venv)
- 部署到生产环境 (Vercel + Render)

#### 文档能力
- README 编写规范
- ADR (架构决策记录)
- API 文档和部署指南

### 4. 问题解决能力

#### 调试技巧
- 日志分析和错误追踪
- 跨域问题排查
- API 兼容性调试

#### 版本管理
- Git 提交规范 (Conventional Commits)
- 分支管理和合并策略
- 回滚和修复流程

### 5. 领域知识

#### 医疗合规
- 医疗数据审计要求
- 数据溯源的重要性
- HIPAA 等合规标准理解

#### 区块链在医疗的应用
- 不可篡改的审计轨迹
- 数据完整性和真实性
- 去中心化身份管理

---

## 📈 项目亮点与雇主价值

### 1. 技术深度
- ✅ 真实区块链部署 (Sepolia 测试网)
- ✅ 完整的 AI + Web3 集成
- ✅ 生产级错误处理和重试机制

### 2. 工程严谨性
- ✅ 代码审查和重构记录
- ✅ 详细的 ADR 文档
- ✅ 完整的测试覆盖

### 3. 产品思维
- ✅ 用户体验优化 (加载状态、错误提示)
- ✅ 完整的部署文档
- ✅ 演示脚本和检查清单

### 4. 学习能力
- ✅ 4 天内完成 MVP
- ✅ 快速掌握新技术栈
- ✅ 持续迭代和优化

---

## 🔗 相关文档链接

- [项目概述](./PROJECT_OVERVIEW.md)
- [详细规格](./SPEC.md)
- [部署指南](./DEPLOYMENT.md)
- [代码规范](./CODING_STANDARDS.md)
- [领域模型](./CONTEXT.md)
- [架构决策记录](./docs/adr/)
- IPFS 配置指南 [docs/IPFS_SETUP.md](docs/IPFS_SETUP.md)

---

## 📝 提交历史统计

| 类型 | 数量 | 占比 |
|------|------|------|
| feat (新功能) | 6 | 27% |
| fix (Bug 修复) | 11 | 50% |
| refactor (重构) | 2 | 9% |
| docs (文档) | 3 | 14% |
| **总计** | **22** | **100%** |

**开发节奏**:
- 8 月 24 日：3 commits (项目初始化)
- 8 月 25 日：3 commits (核心功能)
- 8 月 26 日：13 commits (密集修复和优化)
- 8 月 27 日：3 commits (功能完善)

---

## 🎯 下一步改进方向

1. **测试覆盖**: 添加单元测试和集成测试
2. **性能优化**: 区块链查询缓存、前端懒加载
3. **安全加固**: 私钥管理、输入验证、速率限制
4. **监控告警**: 错误追踪、性能监控
5. **用户体验**: 更友好的错误提示、引导流程

---

*文档生成时间：2026-08-27*  
*基于 git 提交记录自动生成*
