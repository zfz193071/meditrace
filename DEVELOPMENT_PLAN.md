# MediTrace + ask-matt 开发计划

> **目标**: 1 个月内完成阶段 1 和部分阶段 2，达到求职展示水平
> **策略**: 两者并行 - MediTrace 作为实际项目，ask-matt 技能作为方法论展示
> **最后更新**: 2025

---

## 📊 整体时间线 (4 周)

```
Week 1:  部署 + 基础完善          ████████░░░░░░░░░░░░  40%
Week 2:  真实 AI 集成 + 错误处理     ████████████░░░░░░░░  60%
Week 3:  多 Agent 系统基础          ████████████████░░░░  80%
Week 4:  评估 + 文档完善           ████████████████████ 100%
```

---

## 🎯 阶段 1: 立即行动 (Week 1-2)

### 目标
- ✅ 部署可访问的 MediTrace demo
- ✅ 集成真实 DeepSeek AI
- ✅ 添加生产级错误处理
- ✅ 实现成本追踪

### Week 1: 部署与基础完善

#### Day 1-2: Cloudflare 部署前端

**任务清单**:
- [ ] 将 Next.js 前端部署到 Cloudflare Pages
- [ ] 配置自定义域名 (可选)
- [ ] 设置环境变量 (API keys)
- [ ] 验证部署后功能正常

**Cloudflare Pages 部署步骤**:

```bash
# 1. 安装 Wrangler CLI
npm install -g wrangler

# 2. 登录 Cloudflare
wrangler login

# 3. 初始化 Pages 项目 (在 src/frontend 目录)
cd src/frontend
npx wrangler pages deploy . --project-name=meditrace-frontend

# 4. 设置环境变量
wrangler secret put DEEPSEEK_API_KEY
wrangler secret put CONTRACT_ADDRESS
```

**预期交付物**:
- 可访问的 URL: `https://meditrace-frontend.pages.dev`
- 部署文档更新

#### Day 3-4: Cloudflare Workers 部署后端

**任务清单**:
- [ ] 将 FastAPI 后端转换为 Cloudflare Worker (或保持 Render 部署)
- [ ] 配置 Workers 路由
- [ ] 设置数据库连接 (如使用 D1)
- [ ] 测试 API 端点

**方案选择**:
- **方案 A (推荐)**: 前端 Pages + 后端 Render (保持 FastAPI 不变)
- **方案 B**: 前端 Pages + 后端 Workers (需要重写为 TypeScript)

```bash
# 方案 A: Render 部署 (推荐，保持现有代码)
# 1. 在 Render.com 创建新服务
# 2. 连接 GitHub 仓库
# 3. 设置构建命令：pip install -r requirements.txt
# 4. 设置启动命令：uvicorn main:app --host 0.0.0.0 --port $PORT
# 5. 添加环境变量

# 方案 B: Cloudflare Workers (需要转换)
cd src/backend
npx wrangler init --type python backend-worker
```

**预期交付物**:
- 后端 API URL: `https://api.meditrace.pages.dev` 或 Render URL
- API 文档可访问

#### Day 5-7: 智能合约部署到测试网

**任务清单**:
- [ ] 配置 Hardhat 部署到 Sepolia 测试网
- [ ] 获取测试 ETH (faucet)
- [ ] 部署合约并验证
- [ ] 更新前端合约地址

```bash
# 1. 配置 hardhat.config.ts
# 2. 获取测试 ETH: https://sepoliafaucet.com/
# 3. 部署到 Sepolia
npx hardhat run scripts/deploy.ts --network sepolia
# 4. 验证合约: https://sepolia.etherscan.io/
```

**预期交付物**:
- 合约地址记录到文档
- Etherscan 验证链接

---

### Week 2: 真实 AI 集成 + 错误处理

#### Day 8-10: DeepSeek API 集成

**任务清单**:
- [ ] 获取 DeepSeek API key
- [ ] 实现诊断 API 调用
- [ ] 实现医学知识库 RAG (使用 ChromaDB)
- [ ] 优化 Prompt 工程

```python
# 示例: DeepSeek 集成
import requests

def diagnose_with_deepseek(symptoms: str) -> dict:
    response = requests.post(
        "https://api.deepseek.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": MEDICAL_PROMPT},
                {"role": "user", "content": symptoms}
            ]
        }
    )
    return parse_diagnosis(response.json())
```

**预期交付物**:
- 真实的 AI 诊断功能
- Prompt 文档

#### Day 11-14: 错误处理与成本追踪

**任务清单**:
- [ ] 添加重试逻辑 (指数退避)
- [ ] 实现熔断器模式
- [ ] Token 计数和成本日志
- [ ] 添加健康检查端点

```python
# 错误处理示例
from tenacity import retry, stop_after_attempt, exponential_backoff

@retry(stop=stop_after_attempt(3), wait=exponential_backoff())
def call_deepseek_with_retry(symptoms: str):
    # API 调用
    pass

# 成本追踪
class CostTracker:
    def __init__(self):
        self.total_tokens = 0
        self.total_cost = 0
    
    def record(self, prompt_tokens: int, completion_tokens: int):
        self.total_tokens += prompt_tokens + completion_tokens
        self.total_cost += (prompt_tokens + completion_tokens) * 0.000001
```

**预期交付物**:
- 错误处理文档
- 成本追踪 dashboard (简单 JSON 日志即可)

---

## 🚀 阶段 2: 中期增强 (Week 3-4)

### 目标
- ✅ 多智能体系统基础
- ✅ 自定义评估框架
- ✅ 完整文档体系

### Week 3: 多 Agent 系统

#### Day 15-18: LangGraph 集成

**任务清单**:
- [ ] 设计 3 个 Agent 角色
- [ ] 实现 LangGraph 工作流
- [ ] 添加状态管理
- [ ] 记录决策日志

**Agent 角色设计**:

```
┌─────────────────────────────────────────────────────────┐
│                    MediTrace Agent System                │
├─────────────────────────────────────────────────────────┤
│                                                          │
│   ┌──────────────┐     ┌──────────────┐                │
│   │  Grill Agent │────>│  RAG Agent   │                │
│   │  (需求梳理)  │     │ (医学检索)   │                │
│   └──────────────┘     └──────┬───────┘                │
│                                │                         │
│                                ▼                         │
│                       ┌──────────────┐                  │
│                       │Diagnosis     │                  │
│                       │Agent         │                  │
│                       │(诊断生成)    │                  │
│                       └──────┬───────┘                  │
│                              │                           │
│                              ▼                           │
│                       ┌──────────────┐                  │
│                       │Blockchain    │                  │
│                       │Agent         │                  │
│                       │(上链记录)    │                  │
│                       └──────────────┘                  │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

**预期交付物**:
- LangGraph 工作流代码
- Agent 决策日志示例

#### Day 19-21: IPFS 报告存储

**任务清单**:
- [ ] 生成 PDF 诊断报告
- [ ] 集成 Pinata IPFS
- [ ] 存储 CID 到合约
- [ ] 添加报告查看功能

```python
# IPFS 集成示例
import requests

def upload_to_pinata(pdf_bytes: bytes) -> str:
    url = "https://api.pinata.cloud/pinning/pinFileToIPFS"
    response = requests.post(
        url,
        headers={"Authorization": f"Bearer {PINATA_JWT}"},
        files={"file": ("report.pdf", pdf_bytes)}
    )
    return response.json()["IpfsHash"]
```

**预期交付物**:
- IPFS 报告存储功能
- Pinata 集成文档

---

### Week 4: 评估 + 文档完善

#### Day 22-25: 自定义评估框架

**任务清单**:
- [ ] 定义评估指标
- [ ] 实现评估脚本
- [ ] 创建 metrics dashboard
- [ ] 记录基线性能

**评估指标**:

| 指标 | 说明 | 目标 |
|------|------|------|
| 诊断准确率 | 与医学标准对比 | >70% |
| 响应时间 | API 调用延迟 | <5s |
| 上链成功率 | 成功上链比例 | >95% |
| 成本/查询 | 单次诊断成本 | <$0.01 |

**预期交付物**:
- `evaluation/` 目录下的评估脚本
- 性能基准文档

#### Day 26-28: 完整文档体系

**任务清单**:
- [ ] 编写 ADRs (架构决策记录)
- [ ] 创建架构图解 (使用 archify 技能)
- [ ] 录制演示视频
- [ ] 优化 README

**ADR 清单**:

```
docs/adr/
├── 0001-project-vision.md      ✅ 已存在
├── 0002-tech-stack.md          ✅ 已存在
├── 0003-blockchain-design.md   ✅ 已存在
├── 0004-deployment-strategy.md  [ ] 新增
├── 0005-agent-architecture.md   [ ] 新增
└── 0006-evaluation-metrics.md   [ ] 新增
```

**预期交付物**:
- 完整的 docs/ 目录
- 演示视频 (5-10 分钟)
- 优化的 GitHub README

---

## 📋 交付物清单

### 技术交付物

| 交付物 | 状态 | 说明 |
|--------|------|------|
| 前端部署 URL | [ ] | Cloudflare Pages |
| 后端 API URL | [ ] | Render 或 Workers |
| 智能合约地址 | [ ] | Sepolia 测试网 |
| 完整功能 demo | [ ] | 可演示的诊断流程 |
| 多 Agent 系统 | [ ] | LangGraph 工作流 |
| 评估框架 | [ ] | metrics 和 dashboard |

### 文档交付物

| 文档 | 状态 | 说明 |
|------|------|------|
| README.md | [ ] | 项目介绍 + 快速开始 |
| DEPLOYMENT.md | [ ] | 部署指南 |
| SPEC.md | [ ] | 规格说明 |
| CONTEXT.md | [ ] | 领域模型 |
| ADRs | [ ] | 架构决策记录 (5+ 篇) |
| 演示视频 | [ ] | 5-10 分钟录屏 |
| 案例研究 | [ ] | 开发过程总结 |

### 求职材料

| 材料 | 状态 | 说明 |
|------|------|------|
| GitHub 仓库 | [ ] | 整理 commits + README |
| LinkedIn 更新 | [ ] | 添加项目经历 |
| 技术博客 | [ ] | 可选，分享经验 |
| Discord 社区 | [ ] | 分享项目求反馈 |

---

## ⚠️ 风险评估

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| Cloudflare 部署问题 | 中 | 高 | 准备 Render 作为备选 |
| DeepSeek API 限制 | 低 | 中 | 准备多个模型备选 |
| 合约 Gas 费用过高 | 中 | 中 | 使用测试网，优化合约 |
| 时间不足 | 高 | 高 | 优先完成 P0 任务 |
| 技术学习曲线 | 中 | 中 | 预留缓冲时间 |

---

## 🎯 成功标准

### 最低可行 (Week 2 完成)
- [ ] 前端可访问的 URL
- [ ] 真实 AI 诊断功能
- [ ] 合约部署到测试网
- [ ] 基础错误处理

### 理想目标 (Week 4 完成)
- [ ] 多 Agent 系统工作
- [ ] 评估框架和 metrics
- [ ] 完整文档体系
- [ ] 演示视频

### 超出预期
- [ ] 技术博客文章
- [ ] Discord 社区反馈
- [ ] 开源贡献
- [ ] 获得面试机会

---

## 🚀 阶段 3: 长期目标 (Month 2-3) - 达到高级/专家水平

### 目标
- ✅ 领域专业化
- ✅ 开源贡献
- ✅ 社区影响力

### Month 2: 领域专业化

#### Week 5-6: 医疗领域深化

**任务清单**:
- [ ] 构建医学知识图谱
- [ ] 实现更精准的 RAG 检索
- [ ] 添加医疗合规检查 (HIPAA/GDPR)
- [ ] 优化诊断准确率到 >80%

**预期交付物**:
- 医学知识图谱
- 合规检查文档
- 性能基准报告

#### Week 7-8: 性能优化

**任务清单**:
- [ ] 实现缓存策略 (Redis)
- [ ] 优化检索延迟 (<2s)
- [ ] 添加流式输出
- [ ] 成本优化 (<$0.005/查询)

**预期交付物**:
- 性能基准文档
- 成本优化报告

---

### Month 3: 社区影响力

#### Week 9-10: 开源贡献

**任务清单**:
- [ ] 向 LangGraph 提交 PR
- [ ] 向 CrewAI 提交 PR
- [ ] 编写技术博客 (3-5 篇)
- [ ] 在 Discord 社区分享

**预期交付物**:
- GitHub PR 记录
- 技术博客链接
- 社区贡献记录

#### Week 11-12: 求职准备

**任务清单**:
- [ ] 整理 GitHub 仓库
- [ ] 更新 LinkedIn 简历
- [ ] 准备面试演示
- [ ] 开始投递职位

**预期交付物**:
- 优化的 GitHub README
- LinkedIn 更新
- 演示 PPT

---

## 📊 完整阶段汇总

| 阶段 | 时间 | 目标 | 关键交付物 | 求职等级 |
|------|------|------|-----------|---------|
| **阶段 1** | Week 1-2 | 部署 + 基础完善 | 可访问的 demo + 真实 AI | 入门级 ($75-110/hr) |
| **阶段 2** | Week 3-4 | 多 Agent + 评估 | LangGraph + metrics | 中级 ($120-165/hr) |
| **阶段 3** | Month 2-3 | 专业化 + 社区 | 开源贡献 + 技术博客 | 高级/专家 ($180-350/hr) |

---

## 📊 各阶段详细任务对照表

### 阶段 1: 立即行动 (Week 1-2) - 入门级门槛

| 优先级 | 任务 | 状态 | 交付物 |
|--------|------|------|--------|
| **P0** | 前端部署到 Vercel | [ ] | https://meditrace.baozaolaoba.top |
| **P0** | 后端部署到 Render | [ ] | https://meditrace-api.onrender.com |
| **P0** | 智能合约部署到 Sepolia | [x] | 0x860418e7713A346c829Bc539C93c7A2d576897C5 |
| **P0** | DeepSeek API 集成 | [ ] | 真实 AI 诊断 |
| **P1** | 错误处理 (重试 + 熔断) | [ ] | 生产级代码 |
| **P1** | Token 成本追踪 | [ ] | 成本日志 |
| **P2** | 健康检查端点 | [ ] | /health 端点 |

**成功标准**:
- ✅ 前端可访问
- ✅ 真实 AI 诊断
- ✅ 合约已部署
- ✅ 基础错误处理

---

### 阶段 2: 中期增强 (Week 3-4) - 中级水平

| 优先级 | 任务 | 状态 | 交付物 |
|--------|------|------|--------|
| **P0** | LangGraph 多 Agent 系统 | [ ] | 4 Agent 工作流 |
| **P0** | 自定义评估框架 | [ ] | metrics dashboard |
| **P1** | IPFS 报告存储 | [ ] | PDF + CID |
| **P1** | 历史记录查询 | [ ] | 用户历史页面 |
| **P1** | 链上验证组件 | [ ] | 验证 UI |
| **P2** | ADRs (5+ 篇) | [ ] | 架构文档 |
| **P2** | 演示视频 | [ ] | 5-10 分钟 |

**成功标准**:
- ✅ 多 Agent 系统工作
- ✅ 评估框架和 metrics
- ✅ 完整文档体系
- ✅ 演示视频

---

### 阶段 3: 长期目标 (Month 2-3) - 高级/专家水平

| 优先级 | 任务 | 状态 | 交付物 |
|--------|------|------|--------|
| **P0** | 医学知识图谱 | [ ] | RAG 优化 |
| **P0** | 性能优化 (<2s) | [ ] | 基准报告 |
| **P1** | 开源贡献 (LangGraph) | [ ] | PR 合并 |
| **P1** | 技术博客 (3-5 篇) | [ ] | 博客链接 |
| **P2** | Discord 社区分享 | [ ] | 社区声誉 |
| **P2** | 领域专业化 | [ ] | 案例研究 |

**成功标准**:
- ✅ 开源贡献
- ✅ 技术博客
- ✅ 社区影响力
- ✅ 获得面试机会

---

## 📞 立即开始

### 今天需要完成:

1. **Cloudflare DNS 配置** ← 你现在在这里
   - 添加 CNAME 记录: `meditrace.baozaolaoba.top` → `cname.vercel-dns.com`

2. **安装 Vercel CLI**
   ```bash
   npm install -g vercel
   ```

3. **登录 Vercel**
   ```bash
   vercel login
   ```

### 明天开始:

- 部署前端到 Vercel
- 部署后端到 Render
- 验证完整流程

---

有任何问题随时沟通！🚀
