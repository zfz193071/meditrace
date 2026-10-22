# MediTrace：产品定位、新西兰求职与工单调整

整理日期：2026-10-22。本文整理本轮讨论，不是客户需求验证报告、招聘承诺或个人签证资格评估。招聘与签证信息是本轮查阅时的快照，实际投递／申请前需重新核查官方来源。

## 1. 当前在做什么

MediTrace Referral Review Copilot 面向诊所转诊接收人员，辅助核对一次门诊转诊资料包，生成经人工确认、可以追溯来源的交接摘要。

典型任务：导入转诊信、检查报告和用药记录；检查姓名／出生日期差异、转诊原因及联系方式、用药／过敏状态、声称已附却未找到的报告；查看原文证据，人工处理，再确认导出。系统不推断诊断、不推荐治疗、不自动拒收转诊。

当前主要目标是英文 AI 应用／全栈求职作品。V1 只接受合成资料，使用单人工作区和测试支付；没有确定商业价格、客户、具体目标专科或获客渠道。MT-14 已提交 `3c9ea95`，实现导入与状态 UI；核心证据审核界面属于 MT-15。代码完成与前置验收完成是不同状态。

规格来源：[PRODUCT](PRODUCT.md)、[开发基线与实际状态](README.md)。

## 2. 市场与真实需求：什么有证据，什么仍是假设

转诊资料不完整、需要补充及人工跟进，是有公开业务证据的问题。NHS 指南描述了需要更多信息时将转诊退回转诊方的流程，也说明行政支持人员会跟踪待办。它们证明业务问题存在，不证明客户愿意购买 MediTrace，更不能直接代表新西兰市场已验证。

- [NHS：转诊处理及补充信息](https://digital.nhs.uk/services/e-referral-service/document-library/managing-and-minimising-appointment-slot-issues)
- [NHS：转诊工作列表与人员职责](https://digital.nhs.uk/services/e-referral-service/joint-guidance-on-the-use-of-the-nhs-e-referral-service)

商业化仍需验证：目标人员每天核对多少材料、最耗时的步骤、能否接受额外上传流程、误报复查是否抵消节省时间、谁采购，以及需要哪些系统集成。当前不支持扫描件／OCR、团队协作或院内系统集成，可能限制真实采用，但这些仍不在 V1 范围内。

如果目标是求职，完成可体验且可解释的闭环有价值；如果目标转为商业化，应先选择一个具体专科，访谈接收人员，并用经授权的脱敏样例比较人工／辅助核对的耗时、漏项和误报。这是待验证建议，不是已经发生的客户访谈或提效结果。

## 3. 对新西兰求职有什么帮助

判断：值得作为 AI 应用工程或全栈岗位作品继续完善。吸引力来自完整任务、证据链、人工决策、版本管理、权限、成本和失败恢复，以及候选人能解释为什么这样设计。不能只展示框架列表、页面截图或测试数量。

以下是本轮查阅的具体岗位样本，不是市场统计，也不是经过确认适合从中国申请的职位清单：

| 公司／岗位样本 | 技术与产品相关性 | 海外申请边界 | 来源 |
| --- | --- | --- | --- |
| Sentry AI，Auckland AI Engineer | Next.js、TypeScript、Python、FastAPI、Postgres；重视个人项目和开发经历 | 广告要求新西兰工作资格及到办公室；未确认支持无现有资格的海外申请人 | [官方岗位](https://sentrysolutions.ai/careers/artificial-intelligence-engineer-eng-001) |
| Elixir，Christchurch 全栈 | React、TypeScript、Python、API；医疗领域经验加分 | 页面明确列出居民／公民资格，不作为目前需要新办签证者的优先目标 | [官方招聘](https://www.elixir.nz/careers/) |
| KPMG NZ，Senior AI Engineer | Python／TypeScript、评估、监控、成本和生产可靠性 | 本轮未确认岗位签证支持；高级岗位的生产经验不能由作品替代 | [官方招聘系统](https://jobs.lever.co/kpmgnz/c363bad1-e357-4de5-82ac-3e4f40ce2108) |

本地相关性也有边界：新西兰存在 HealthLink 电子转诊流程，但本项目尚未对接或验证适配。可以解释未来集成位置，不应将此写成既有能力。[HealthLink CareSelect 资料](https://www.healthlink.co.nz/wp-content/uploads/2023/09/CareSelect-eReferrals-for-GPs.pdf)

目前短板：核心双栏审核与公开演示未交付；尚无足以支持提效声明的用户数据；离线回归测试不等于模型准确性；真实外部集成和部分人工验收未完成。此前已通过的 382 项后端／46 项前端测试仅对应 MT-14 当时的回归运行，不是当前或未来版本的永久质量证明。

建议英文定位：

> An evidence-linked referral review copilot, built with Next.js and FastAPI, with human approval, versioned records, and controlled AI execution.

这是一份预期定位文案，公开使用时须核对当时实际交付状态，注明合成资料作品。

## 4. 四项建议与原工单审查

| 建议 | 原覆盖 | 本次补齐 |
| --- | --- | --- |
| 完整且清晰的核心案例 | MT-15 审核、MT-13 导出，但 MT-15 没有明确将整条展示路径作为验收 | MT-15 增加来源到确认／导出、stale 和历史的连贯案例 |
| 无需注册即可体验 | MT-16 已要求三例、无登录、共用真实 UI | 明确正常／缺附件／身份冲突三例、英文首屏和首访操作路径 |
| 60—90 秒英文视频 | MT-23 已要求成片，但完整依赖 MT-22，容易到最后才开始准备 | 提前做脚本／粗剪；完整验收后修订并交付最终视频 |
| 英文技术讲解 | 原 MT-23 有 README、架构和求职文案，缺明确面试材料 | 增加 90 秒介绍、5—10 分钟讲解、至少 6 个技术追问、代码证据及 AI 辅助开发说明 |

结论：原范围大体符合，不需要推倒重做；需要调整实施优先级，补齐实际可检查的交付物。MT-20 的评估和失败案例也应提前准备，支撑视频及简历中的质量声明。

实施顺序：

1. MT-15：完成核心证据审核、人工处理、确认与导出。
2. MT-16：完成三个免登录固定案例和英文首页。
3. MT-20：先完成离线评估工具及报告；满足标注复核和明确费用授权后做真实评估。
4. MT-23 初稿：英文 README、演示粗剪、技术讲解、两种岗位方向的简历要点及岗位筛选模板。
5. MT-17、18、19、21：补齐测试支付、数据生命周期、运维及旧入口退役；完成 MT-22 全流程验收。
6. MT-23 最终材料，再 MT-24 部署及线上交付。

已有前置票的外部验收穿插推进。以上是实施顺序，未改变依赖关系：MT-20／23 的提前产物不表示票已 DONE；真实预算未授权不调用模型；最终发布仍受 QUALITY 和 MT-24 全部门槛约束。没有新增提前发布或真实支付授权。

调整计划时下一张为 MT-15；本轮 MT-15 代码与离线验证已实施，下一张实施 MT-16。前置未验收仍不关闭工单，最新状态与详细顺序以 [README](README.md) 为准。

## 5. 什么是“已有新西兰工作资格”

它是允许从事相应工作的新西兰身份或签证，例如公民、居民，或工作条件适用的有效签证；具体需看签证限制。“能够申请签证”不等于“已经有工作资格”。[Employment New Zealand](https://www.employment.govt.nz/starting-employment/hiring/hiring-temporary-migrants)

| 广告表述 | 求职时如何理解 |
| --- | --- |
| Must have existing NZ work rights | 通常要求已具备资格；不能默认愿意支持新办签证 |
| No visa sponsorship | 明确不提供相关支持，降低投递优先级 |
| Overseas applicants welcome / visa support available | 优先核查是否适用于该具体岗位；不保证录用或签证 |
| 未写签证条件 | 信息未知，可以询问，不能推断支持或拒绝 |

人在中国、没有新西兰工作签证，不等于没有机会。AEWV 是一条可从海外申请的路径：先面试并获得符合要求的认证雇主 offer；雇主完成岗位等相关流程、提供申请链接；本人申请签证，获批后按条件赴新西兰工作。签证由移民局审批，公司不能保证获批。雇主获得认证不代表每个岗位都支持海外招聘。

- [移民局：AEWV 要求及流程](https://www.immigration.govt.nz/visas/accredited-employer-work-visa/)
- [移民局：从新西兰境外招聘](https://www.immigration.govt.nz/work/for-employers/hiring-people-from-overseas/hiring-people-from-overseas-not-in-new-zealand/)

前面的岗位例子说明技术匹配，不足以证明适合需要签证支持的海外申请人。实际应同时筛选“技术匹配、接受海外候选人、愿意支持签证”。工作年限、可证明的商业经验、英语面试能力也需要单独判断；这些个人信息目前未知。

英文询问模板：

> I’m currently based in China and would require employer support for a New Zealand work visa. Is this role open to offshore candidates requiring AEWV support?

岗位筛选模板（由 MT-23 交付材料扩充，未知项不推断）：

| 公司／岗位／链接 | 技术匹配证据 | 接受海外申请？ | 签证支持及来源 | 核查日期 | 下一步 |
| --- | --- | --- | --- | --- | --- |
| 待填写 | 待填写 | 是／否／未知 | 明确说明／待询问 | 待填写 | 投递／询问／暂缓 |

作品帮助雇主判断技术能力，签证支持决定岗位是否适合当前申请条件，两者都需要核查。本文件不承诺录用概率，不代用户申请职位或联系雇主。
