# MT-20 离线评估基线实施证据

日期：2026-10-22。前一票 MT-16 已提交：`0bfb26d`。本票完成离线 runner、指标、开发集报告、replay 和 `/evaluation` 展示；**没有完成整张 MT-20 的真实评估验收**。前置尚未关闭，front matter 保留 TODO；真实阶段受阻，缺项详见下方。

## 交付文件

- `evals/referral-review/referral_eval/metrics.py`：多重集合 TP／FP／FN、分字段／类型、负例误报、引用存在和标注支持性分开计分；失败包不从召回分母消失。
- `evals/referral-review/referral_eval/runner.py`、`run.py`：无模型字段基线、脚本 Fake 输出经过生产解析／提取验证／清单、无 Adapter replay；语料／文件／冻结 hash 校验、版本和运行环境、报告／录制／状态文件、逐包回归比较与门槛命令。
- [使用及指标定义](../../evals/referral-review/README.md)、[失败与限制分析](../../evals/referral-review/FAILURES.md)。
- 三套完整 [开发集报告](../../evals/referral-review/reports/)，每套均含 JSON、Markdown、录制与状态。报告记录 base commit `0bfb26d` + dirty worktree，并以实现 SHA-256 绑定本票评估源码；不谎称本票已在该 commit 内。
- `scripts/referral_evaluation_summary.py`：显式公开汇总投影，只从开发集报告提取指标／版本／限制，不包含原文、gold 或录制。`.vercelignore` 排除整个 evals 目录。
- `/evaluation`：英文指标说明、完整分母、Fake／baseline／replay 区分、四个失败／限制条目、JSON 下载和版本 manifest。首页、demo、project 页面链接已更新。

## 实测结果（仅开发集、临时标注）

| 项目 | 简单基线 | Fake 当前校验流程 | Fake 录制 replay |
| --- | --- | --- | --- |
| 总包数 | 10 | 10 | 10 |
| 成功／拒绝／失败 | 9／1／0 | 9／1／0 | 9／1／0 |
| Fact TP／FP／FN | 69／5／4 | 71／3／2 | 71／3／2 |
| Finding TP／FP／FN | 9／1／1 | 10／1／0 | 10／1／0 |
| 采纳事实引用完整性 | 74／74 | 74／74 | 74／74 |
| 负例包有误报 | 1／2 | 1／2 | 1／2 |

以上不是模型准确率。Fake 输出来自简单源码行读取器，没有读取 gold 生成答案；生产校验器／规则被实际调用，但没有语言模型参与。人工引用支持性、真实 tokens／成本／模型延迟全部为 null。假 Adapter 的 token 常量不用于计费报告。数值／单位暂以完整事实保守比较，未宣称已完成细粒度临床语义审计。

可复现的观察：

1. baseline dev-06 丢失日期上下文，漏一项同日药物陈述差异。
2. dev-08 把历史模板中的 Unknown 过敏行当作当前事实，产生额外 C07；引用位置正确但语义上下文不成立。
3. dev-10 扫描件被 PDF_UNREADABLE_PAGE 明确拒绝，保留在总数中。
4. dev-03 报告日期／dev-06 特定药物否定状态与临时标注存在分歧，仍计 FP／FN，等待实际操作者复核，没有为了改善成绩修改 gold。

## 验证命令与结果

- baseline／fake：在 README 所列命令实际运行，10 个开发包全部保留。
- replay：`--provider replay --recording ...fake-dev/recording.json --compare ...fake-dev/report.json` 成功；每个包的结果、诊断和汇总指标与原报告相同。无需模型 Key，不调用 Adapter。
- `python3 scripts/referral_evaluation_summary.py --check`：公开展示与报告一致。
- `DATABASE_URL=sqlite:///:memory: .venv/bin/python -m pytest tests/referral_review -q`（src/backend）：**398 passed / 68 skipped / 4 warnings**；跳过项为现有 PostgreSQL／外部集成条件，不能据此宣称真实集成通过。全量运行后另补模式／录制来源和包级原文哈希校验；评估专项 15 项通过，最后新增原文哈希防篡改用例单独通过，共 16 个评估测试。
- 手算样例覆盖重复事实、TP／FP／FN、空分母、缺引用／假引用／支持不足、字段／日期／单位不被猜测、关键字段错值、负例身份误报。
- 异常测试覆盖错误录制 hash／拆分／漏包／重复包、Fake 缺引用拒绝、注入中断后的分母与 replay、真实入口对未给／0／负／NaN／正数 cap 全部 fail closed，冻结 split 需要显式暴露确认。
- 前端 DemoWorkspace 回归 4 项通过；typecheck 通过；lint 0 errors，28 条既有旧页面 warnings；生产 build 通过并包含静态 `/evaluation`。
- 后台独立 headless Chrome + CDP：1440×900、1024×768、390×844，三个比较卡、四个限制案例和阻断标识均存在，版本详情可展开，0 fetch，无横向溢出。已目视检查截图。仅离线组件 harness，未启动 Next／FastAPI，未调用 AI，未做线上路由验收。

截图和审计：[MT-20 evidence](evidence/MT-20/)。浏览器工具：扩展的 `scripts/referral_demo_qa.cjs` 加载 `#evaluation`，`scripts/referral_evaluation_browser_qa.cjs <file-URL>` 做只读检查。静态报告 metadata 更新后重新生成了公开汇总，计数与页面结构不变。

## 未完成项及验收状态

- 30 份语料／10–20 划分已存在，但人工 gold 复核仍缺；本次只跑 dev，未执行冻结集质量评估，也不重新声称冻结材料对开发者未见。
- 真实 runner 的**独立评估账本与全站预留集成尚未实现**。真实模式现在明确拒绝所有派发，包含给了 cap 的情况；这是安全关闭而非“费用上限已完整实现”。后续须复用 MT-10／11 预留、派发 CAS、结算／unknown 保留，另加评估独立额度和异常恢复测试，不能直接调用 DeepSeek Adapter。
- 完成上述实现后，还须操作者授权明确预算、配置模型与价格、完成真实合成评估录制／支持性复核、冻结集指标及至少 20 次真实延迟测量。
- fake/replay 输出和故障注入不可替代真实模型记录，公开质量门槛保持 BLOCKED；没有宣传临床验证或效率改善。
- 前置 MT-03／08／09／12／13 仍未全部验收；票内复合验收项不提前勾选。没有推送或部署。

按既定优先级，下一可独立实施项为 **MT-23 求职材料初稿**。MT-20 的上述缺项继续保留在原票，不能因进入下一票而视为完成。
