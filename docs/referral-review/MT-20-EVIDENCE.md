# MT-20 评估实施证据

## 2026-10-26：晚到费用校正与隔离恢复 CLI

新增 `rr_0009`／`EvaluationLedger.adjust`：原结算保留，追加绝对 usage 及差额，原 batch／日月桶同事务更新，幂等键绑定 token 对；数据库触发器禁止修改／删除校正。晚到录制以内容摘要幂等校正。恢复状态区分原结算、调整和有效合计，始终标为 Fake 演练。

新增 `recover.py`：已有私有 journal 和计划、隔离 PostgreSQL ownership receipt、连接指纹／schema 随机标记／迁移版本均须匹配；默认 PostgreSQL 强制只读，写入需要 `--apply --confirm-plan`。无真实 Adapter、模型密钥读取、环境生产 DB 回退、自动建库／迁移、跨计划扫描或模型重试。具体命令和范围见 [账本手册](EVALUATION-LEDGER.md)。真实授权／gold、真实录制和 usage 来源、生产运维及完整报告仍缺，MT-20 不关闭。

首轮本地定向测试（校正、调度、恢复 CLI、迁移）74 passed／61 skipped／3 failed（193.49 秒）；三项失败均为新增测试 usage 漏填必需的 total_tokens，已补齐测试输入，不放宽产品契约。修正后校正和 CLI 专项 19 passed／14 skipped（19.15 秒），13 项部署脚本回归通过；PostgreSQL 跳过项不视为通过，数据库并发和完整回归交由验证分支 CI 执行。

实现提交 `5aa9a03`。随后复核补充了「释放额度已被重用，晚到校正使总占用超限」的熔断保护，见 [修复记录](../../BUGFIX-EVALUATION-ADJUSTMENT-BUDGET.md)。校正专项 12 passed／12 skipped（17.44 秒），覆盖 batch／全站两种预算重用；最终 CI 结果另补。

## 2026-10-26：隔离事务调度、持久录制与恢复

实现提交：`bdc160d6de59f257b3adb7e73786c9ca4109b084`；槽位断言补充：`90cb281`（验证分支）。

`coordinator.py` 接通计划／用户检查、原子 batch／费用／槽／派发提交、提交后 Fake 调用、先录制后结算，以及不重试模型的恢复。`journal.py` 使用私有目录、排他锁、校验和、fsync 和不可覆盖发布；绑定整个计划。无 Key／数据库的 replay 保留全部所选样本和原／当前实现来源。仅可显式注入隔离测试 engine，必须 test 环境及内置 Fake；未增加 CLI／HTTP 执行入口，没有实际人工授权或真实模型费用。范围与未完成项见 [账本手册](EVALUATION-LEDGER.md)。

- 首轮新调度专项：18 passed／18 skipped；后续组合 `test_evaluation_coordinator.py test_evaluation_ledger.py test_evaluation_planning.py`：80 passed／40 skipped（96.55 秒）。跳过仅因本机未配置 PostgreSQL，不能当作通过。
- 补充晚到 usage 保留估算、恢复不涉及其他 batch、合法校验和但错误 attempt 绑定及价格变更检查：3 passed／3 skipped。
- 数据库进程用例新增用户锁及组合派发事务竞争／回滚；新调度模块已加入 PostgreSQL CI，首轮 [PostgreSQL CI](https://github.com/zfz193071/meditrace/actions/runs/40282363008/job/121438257984) 为 297 passed／1 failed：新测试错误地依赖未排序的槽位行序，已改为验证唯一占用、对应持有者及有效租约，见 [修复记录](../../BUGFIX-EVALUATION-POSTGRES-SLOT-ASSERTION.md)。修正后本机定向 1 passed／1 skipped；[最终 PostgreSQL 17 job](https://github.com/zfz193071/meditrace/actions/runs/40282732849/job/121439391929) 已通过：298 passed／0 skipped（120.14 秒，含 SQLite／PostgreSQL 参数化）。用户锁与组合事务的多进程竞争、回滚及持久恢复均已实际执行；[完整 CI](https://github.com/zfz193071/meditrace/actions/runs/40282732849) 全通过：后端 870 passed／136 skipped（187.64 秒）；前端 15 suites／69 tests、lint／build／typecheck、前后端生产依赖审计和 13 项部署脚本回归均通过。
- 没有新增迁移、启停服务、操作生产数据、真实模型调用或改动历史评估报告。MT-20 保持 TODO；后续仍须实际授权与 gold、真实 Adapter 入口、恢复 CLI／完整报告及追加费用校正。

## 2026-10-26：可审阅计划与授权参数预检

实现提交：`8272a1f`，同字节 manifest 固定校验补充提交：`e2277bc5360af8e3938e43daa627157c9ffc0499`（验证分支）。

新增 `plan.py`、`planning.py` 与有界文件读取：只预览固定合成语料，展示样本数、拒绝项、模型价格、预算和输出目录。计划绑定实际请求字节摘要、输入上界、版本、实现／依赖锁及操作者。授权参数预检会重建计划，拒绝旧参数、旧代码、变动输入和超过 cap 的选择；事务检查锁定有效邀请用户。文件明确未记录授权、执行禁用，不读凭据、不连数据库、不预留费用。

这不是已集成的真实 runner：实际人工授权、每次派发与账本事务串联、真实录制／恢复仍待完成。人工 gold 和真实预算尚未授权，MT-20 维持 TODO。修复详情见 [读取前路径约束及解析器版本](../../BUGFIX-EVALUATION-INPUT-PREFLIGHT.md)。

本地首轮预检专项 28 passed／1 skipped（PostgreSQL 未配置）；随后新增祖先目录替换回归，路径／复读专项 8 passed；固定摘要消费字节补充后专项 9 passed。解析恢复回放故障注入 1 passed。原有离线评估本机首轮 15 passed／1 failed，单独复跑 14 passed／2 failed，实际观察到 PDF_TIMEOUT 和逐包计数差异；未修改断言或提高解析超时。另修复其暴露的空输出回放异常，追加解析拒绝录制及确定性恢复测试。[独立 PostgreSQL 17 job](https://github.com/zfz193071/meditrace/actions/runs/40279569965/job/121429638552) 已通过：254 passed／0 skipped（105.85 秒，包含 SQLite／PostgreSQL 参数化）。[完整 CI](https://github.com/zfz193071/meditrace/actions/runs/40279569965) 全通过：后端 849 passed／113 skipped（228.09 秒）；前端 15 suites／69 tests，lint／build／typecheck、前后端生产依赖审计、13 项部署脚本回归均通过。CI 中原有离线回放和新增规划测试全部通过，本机 PDF 超时记录仍保留。

## 2026-10-26：共享执行槽

实现提交：`1efa200d35813a40841a51c7c6c95b4e1fdec4d5`（验证分支）。新增 `usage/slots.py`、追加迁移 `rr_0008`，评估和工作区 Fake／real 共用全站两个槽。评估派发标记和 240 秒租约原子提交，终态结算与释放同事务；unknown 保留未过期租约及费用，迟到结果不会释放新持有者。工作区派发前重查账号／全站槽，见 [修复记录](../../BUGFIX-DISPATCH-SLOT-OWNERSHIP.md)。

- 既有账本及迁移回归 `test_usage.py test_evaluation_ledger.py test_persistence.py`：97 passed／74 skipped。
- 首轮新槽位及工作区派发测试 `test_evaluation_slots.py test_runs.py`：77 passed／11 skipped；另补工作区迟到结算不得释放评估槽的对称用例后，`test_evaluation_slots.py test_evaluation.py` 为 28 passed／12 skipped，包含真实入口继续 fail-closed。部署脚本离线回归 13 项通过。以上跳过均为本机缺少隔离 PostgreSQL。
- [完整 CI](https://github.com/zfz193071/meditrace/actions/runs/40276376704) 全通过：后端 818 passed／112 skipped（186.44 秒）；前端 15 suites／69 tests、lint／build／typecheck、前后端生产依赖审计通过。
- [独立 PostgreSQL 17 job](https://github.com/zfz193071/meditrace/actions/runs/40276376704/job/121419890311) 223 passed／0 skipped（76.96 秒，包含 SQLite／PostgreSQL 参数化）。已实际执行 Fake／real 工作区与评估四进程同时竞争两个槽，以及过期评估完成与新派发竞争；零跳过检查通过。
- 真实评估 CLI 保持关闭，剩余是授权／合成输入绑定、真实 Adapter／录制与恢复接入、晚到费用校正及人工／预算验收；MT-20 保持 TODO。无真实模型调用、生产迁移或部署。

## 2026-10-26：独立费用账本基础层

实现提交：`d45d810f510025fc6d734c0d28e282cb6a530b09`（验证分支）。新增 `evaluation/ledger.py`、共享 `usage/budget.py`、追加迁移 `rr_0007` 及 SQLite／PostgreSQL 参数化、多进程竞争测试。评估 cap、原子共享日月预留、单次派发财务标记、幂等结算、unknown 保留与有界恢复已实施。实现及未完成边界见 [账本手册](EVALUATION-LEDGER.md)。

- 定向测试 `test_evaluation_ledger.py test_usage.py test_persistence.py`：97 passed／74 skipped；跳过的是本机未配置的 PostgreSQL，不计为通过。
- [完整 CI](https://github.com/zfz193071/meditrace/actions/runs/40267092317) 全通过：后端 798 passed／97 skipped；前端 15 suites／69 tests、lint／build／typecheck、前后端审计通过。详情见 [CI 记录](CI-2026-10-26.md)。
- 完整本地后端回归：798 passed／97 skipped，489.10 秒；PostgreSQL 由独立 CI 验证。部署脚本离线回归 13 项通过，公开评估汇总与历史开发集报告一致。
- [PostgreSQL 17 CI](https://github.com/zfz193071/meditrace/actions/runs/40267092317/job/121391749549)：196 passed／0 skipped，64.33 秒（包含 SQLite／PostgreSQL 参数化）。已实际执行评估与工作区混合竞争、同一 batch 预算竞争及重复派发／结算；零跳过检查通过。
- `--provider real` 继续拒绝，正数 cap 也不能打开；无供应商调用、模型费用、线上发布或生产迁移。
- 剩余工程工作：真实 CLI 的授权／合成输入绑定、共享并发槽、录制与报告／恢复接入、晚到 usage 的追加校正；仍须人工 gold、明确预算和真实冻结集测量。前置未关闭，MT-20 仍为 TODO。

## 2026-10-22：离线报告历史证据

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

## 2026-10-22 当时未完成项（账本进度以上方更新为准）

- 30 份语料／10–20 划分已存在，但人工 gold 复核仍缺；本次只跑 dev，未执行冻结集质量评估，也不重新声称冻结材料对开发者未见。
- 真实 runner 的**独立评估账本与全站预留集成尚未实现**。真实模式现在明确拒绝所有派发，包含给了 cap 的情况；这是安全关闭而非“费用上限已完整实现”。后续须复用 MT-10／11 预留、派发 CAS、结算／unknown 保留，另加评估独立额度和异常恢复测试，不能直接调用 DeepSeek Adapter。
- 完成上述实现后，还须操作者授权明确预算、配置模型与价格、完成真实合成评估录制／支持性复核、冻结集指标及至少 20 次真实延迟测量。
- fake/replay 输出和故障注入不可替代真实模型记录，公开质量门槛保持 BLOCKED；没有宣传临床验证或效率改善。
- 前置 MT-03／08／09／12／13 仍未全部验收；票内复合验收项不提前勾选。没有推送或部署。

按既定优先级，下一可独立实施项为 **MT-23 求职材料初稿**。MT-20 的上述缺项继续保留在原票，不能因进入下一票而视为完成。
