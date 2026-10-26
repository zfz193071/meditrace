# MT-20 独立评估费用账本

2026-10-26。现已完成内部账本和共享并发控制，不开放真实评估。`run.py --provider real` 仍在读取语料或创建输出目录前拒绝；没有新增 HTTP 路由，也没有调用模型或执行生产迁移。

## 已实现的边界

- `evaluation/ledger.py` 为每次评估保留 batch UUID、plan SHA-256、固定美元预算及模型／价格快照。重复打开同一个 UUID 不能提高上限或更换计划／价格。美元预算向下取整至整数 micro-USD，单次成本估算向上取整。
- 每个 batch + sample SHA-256 只能有一次 attempt；输入／输出 token 上限改变会冲突。重放始终返回原状态，不能把成功、失败或 unknown 重新变成可派发任务。
- `usage/budget.py` 同时被工作区 Usage 和评估账本使用。两者锁定相同的 real_ai 熔断行、UTC 日／月桶；评估预留还受自身 batch cap 限制。额度不足或后续写入失败，全部事务回滚。评估不伪造会员、订单或消耗会员次数。
- `record_dispatch` 在同一事务内取得全站执行槽并写入唯一派发标记，不是操作者授权。超时、跨 UTC 日／月、价格变化、配置禁用、熔断或无空闲槽时拒绝。未来调度器仍须验证操作者授权和合成输入，提交标记后才可使用供应商 transport。
- 结算保存实际 tokens 和原始价格计算的成本；已派发且没有 usage 时按上界估计，不能填零。unknown 保留预留，24 小时后转换为 estimated_spent；未派发过期请求才可释放。恢复按批次最多处理 100 项，不派发、不重试模型，等待中的 unknown 不占用本轮可恢复条目的名额。
- 实际费用超过上界时照实记账，并关闭全站新的真实任务。跨月／配置已禁用时仍可按旧桶与旧价格结算。终态重复结算必须 payload 相同，否则拒绝。
- `rr_0007` 仅追加三张表。账本只保存哈希、模型／价格标识、数字和时间，不保存输入原文、模型响应、账号关联或密钥。旧表、旧数据和已应用迁移不改写。

锁顺序为评估 batch → attempt → real_ai control → 排序后的 budget。工作区仍先锁 user／packet／run／membership，再进入相同 control／budget。两条路径都不在持有全站预算锁后倒取对方领域锁。其后依次锁账号槽（仅工作区）、workspace global 行、evaluation_slots 行。

## 共享并发控制（2026-10-26）

`rr_0008` 只追加 `evaluation_slots`。现有 workspace global 的 0／1 两行作为所有路径共同的槽位锁；新表以相同编号保存评估 attempt 外键和租约，任一类型在该编号有有效租约即为占用。所有原工作区行、约束及租约保留，不复制或重写旧任务。工作区 Fake／real 都参与同一全站容量，账号仍最多一项；评估不创建工作区账号槽。

评估费用 reserve 不占执行槽，record_dispatch 才原子取得 240 秒租约并更新 attempt 的过期时间。槽满时维持 reserved，可在未过期且尚未派发时重试领取；已派发不能重试模型。未知结果保留费用及未过期槽，租约到期才允许新任务复用容量；已知终态结算与释放槽在同一事务，迟到结果通过持有者 ID 比对，不能清除新租约。该上限约束本应用有效租约，不承诺终止供应商已接收的请求。

工作区写入派发标记前也重新校验实际账号／全站槽归属，详见 [修复记录](../../BUGFIX-DISPATCH-SLOT-OWNERSHIP.md)。

## 可审阅计划与授权参数预检（2026-10-26）

`evals/referral-review/plan.py` 只生成权限为 0600 的新计划文件和摘要，不连接数据库、不加载密钥、不预留资金、不调用模型。摘要包含样本数、拒绝项、模型／价格、成本上界、预算、输出目录及计划摘要，明确显示 `execution=disabled`、`approval=not_recorded`。它不是授权记录；预览预算是待审阅参数。

计划绑定 batch／操作者 UUID、固定的合成 manifest／freeze、样本集合、实际规范化请求 hash、token 上界、模型／价格／提示／schema／清单／解析器版本、相关 Python 实现及依赖锁摘要及新输出目录。成本使用现有账本的整数规则；失败样本仍在计划中。冻结 test 预览须显式确认暴露，不能声称后续评估仍未见这些样本。

`validate_approval_binding` 校验显式给定的计划 hash、精确预算、操作者、邀请／开关和价格，并重建当前计划；更换输入、实现、输出或参数后须重新审阅。`bound_request` 校验将发送的规范请求字节。`require_operator` 在调用方事务内锁定仍有效的邀请用户，后续锁顺序应为 user → batch／attempt → control／budget → slots。这些预检已接入下述隔离 Fake 调度演练，尚未与真实供应商入口串联；通过它们不授予供应商调用权限。

固定语料摘要只随经过审查的语料修订手动更新；仍有临时 gold，不能当作人工签核。读取前的路径约束及复读 hash 修复见 [修复记录](../../BUGFIX-EVALUATION-INPUT-PREFLIGHT.md)。

## 事务调度及持久录制演练（2026-10-26）

`referral_eval/coordinator.py` 的内部 `EvaluationSession` 现把操作者锁、batch 身份、费用预留、共享槽和唯一派发标记放入同一个调用方事务；事务成功提交后才执行 Adapter。账本方法新增可选 `connection`，要求同一 engine 的活动事务；原有独立调用语义保持不变。锁顺序仍是 user → batch／attempt → control／budget → slots。任一步失败，新增 batch、资金和标记一起回滚。

当前只接受显式传入的隔离测试数据库、`RR_ENVIRONMENT=test` 和内置 `FakeAdapter`，没有运行 CLI／HTTP 入口，不加载数据库或密钥环境变量。调用方仍须确保传入的是可丢弃测试库；环境名不是数据库隔离证明。这是内部调度链的故障演练，不是真实授权记录或生产就绪 runner。费用、结果和回放明确标为 fake／simulated，不能用作真实成本或质量成绩。

每次派发前重查计划、选择、实际请求字节、配置和事务内有效用户。已有派发、终态或 unknown 标记不会再次调用 Adapter。计划输出目录初次必须不存在；恢复仅在私有目录绑定文件与计划完全一致后允许使用原目录。`journal.py` 使用 0700 目录、0600 文件、独占目录锁、文件及目录 fsync 和原子不覆盖发布；拒绝链接、特殊文件、超大文件、校验和冲突及计划错配。记录只保留合成输出、费用元数据及固定错误码，不记录异常原文或密钥。校验和用于损坏检测，不是对本机文件所有者的数字签名。

逐包录制先落盘，再结算账本。录制后结算前崩溃，可用 `recover_recordings` 幂等补结算；没有录制时，过期已派发任务按 unknown 保留资金，24 小时后估算，绝不重试模型。恢复仅处理所给计划的最多 20 个样本，不扫描或更改其他批次；撤销邀请、禁用模型或更换当前价格不妨碍按旧快照结算。估算已经终结后的晚到 usage 通过下述追加记录校正，不覆盖旧账。损坏／不匹配的录制拒绝恢复，需要调查，不能据此释放预算。

`replay_recordings` 不需要数据库、Key 或 Adapter，重新验证合成输出并计算临时标注指标；未开始、缺录制、失败和拒绝的样本都保留在所选总数内。回放同时记录原实现及当前实现摘要，解析／规则变化可以产生差异。完整真实报告和生产存储保留策略仍缺。

## 晚到 usage 与隔离恢复 CLI（2026-10-26）

追加迁移 `rr_0009` 新建 `evaluation_adjustments`，数据库触发器拒绝 UPDATE／DELETE。`EvaluationLedger.adjust` 接受可信内部来源的绝对 token 总量，使用原 batch 价格计算新成本；以「新成本 − 原结算 − 已有调整合计」为差额，同事务更新原 batch 和原 UTC 日／月桶。原 attempt 的状态、结果、tokens、结算金额和时间全部保留。仅已派发的 settled／estimated_spent 可校正；不能把未知预留或已取消请求当作退款。幂等键绑定完整 token 对，即使四舍五入后成本相同也拒绝不同 payload；重放旧键不撤销后续校正。超出原预留上界照实记账并熔断，后续负差额不自动解除熔断。

录制恢复用录制内容 hash 作为幂等键。状态输出分别保留 `settlement_microusd`、`adjustment_microusd`、合计 `simulated_microusd` 和 `cost_status`；估算经过校正后费用可以是 known，但历史任务状态及 outcome 不改写。所有数值仍为 Fake 演练，不代表供应商实收。

新 `recover.py` 默认预览，PostgreSQL 强制 `SET TRANSACTION READ ONLY`。只接受 `TEST_DATABASE_URL` 及 `referral_review.persistence.test_database create` 生成的私有 ownership receipt，核对连接指纹、随机 schema、数据库内随机标记和当前迁移版本；不回退到 `DATABASE_URL`，不创建／迁移／删除数据库，不读取模型密钥。CLI 当前仅支持已有隔离 PostgreSQL 演练库；SQLite 继续由内部测试 API 覆盖。恢复允许使用原计划及原价格，不要求当前实现 hash 相同，也不授权再次执行。

在仓库根目录、已有隔离演练数据及 journal 的前提下运行（占位路径须替换）：

```bash
PYTHONPATH=src/backend src/backend/.venv/bin/python evals/referral-review/recover.py \
  --plan /private/path/plan.json --database-receipt /private/path/test-db.json
```

核对输出中的 `plan_sha256` 后，同一命令追加 `--apply --confirm-plan <精确摘要>` 才写账；这不是模型预算授权。最多处理计划内 20 个样本，逐样本独立事务；中途失败可能已有样本完成结算，修复问题后用相同命令恢复，不会重复扣费或调用模型。缺失／不匹配的目录锁直接拒绝，不创建或修补 journal。错误输出固定文本，不打印数据库连接、录制原文或异常参数。schema 回收仍使用既有测试库工具和精确确认，不由恢复命令代办。

## 尚未实现，真实入口继续关闭

1. 补齐实际人工授权及 gold 签核来源，将已在隔离演练验证的调度事务接入受控真实入口；预览和合成授权参数不能开启真实执行。
2. 接入真实 Adapter；共享两槽、240 秒派发租约和单次标记已实现，但该内部方法不验证邀请用户或人工预算授权，不能单独使用它调用模型。
3. 已有私有 Fake 逐包录制、隔离库恢复 CLI、无 Key 回放及晚到费用追加校正；仍须接入真实录制、可信 usage 来源、生产恢复运维和完整报告。账本内部 recover 未注册到现有每日维护任务。
4. 操作者复核 gold，配置模型／核实价格并明确授权预算，再执行真实冻结集和至少 20 次延迟测量。

因此 MT-20 保持 TODO；这些前置条件没有因为账本测试通过而满足。本轮不要求用户提供 Key 或预算。

## 验证

`test_evaluation_ledger.py` 同时参数化 SQLite／隔离 PostgreSQL，覆盖 cap、共享预算、幂等、终态冲突、未知保留、崩溃恢复、跨月价格快照、熔断、事务回滚及从 rr_0006 追加升级。`test_evaluation_ledger_pg.py` 使用独立进程竞争 batch cap、全站预算、派发标记和结算，并包含评估与工作区同时竞争同一预算。

`test_evaluation_slots.py` 补充混合占用、未知租约、迟到释放、领取／结算回滚及从 rr_0007 保留旧占用的升级测试；PostgreSQL 进程测试同时竞争评估与 Fake／real 工作区槽。

CI 的 PostgreSQL job 已加入以上文件并要求零 skipped。具体运行结果见 [MT-20 实施证据](MT-20-EVIDENCE.md)；不得把本机跳过的 PostgreSQL 用例称为通过。既有真实入口 fail-closed 测试继续覆盖给定正预算仍不派发、也不生成输出目录。

`test_evaluation_planning.py` 覆盖预算／价格／邀请／输出／实现／请求变更、路径越界与符号链接、重复键、源文件篡改、私有且不可覆盖的预览 CLI，以及 SQLite／PostgreSQL 的事务内有效用户检查。测试价格、用户及凭据均为合成值，不代表真实预算获批。

`test_evaluation_coordinator.py` 在 SQLite／隔离 PostgreSQL 上验证提交后调用、原子回滚、撤销／变更检查、单次派发、磁盘写失败、录制后结算崩溃、超时／取消／usage 缺失、私有目录锁、防覆盖及无数据库回放。账本进程测试补充操作者锁与组合事务的并发竞争／回滚；CI 不允许跳过 PostgreSQL 验收。

`test_evaluation_adjustments.py` 验证跨月／停用后的旧价格校正、原结算保留、幂等冲突、旧键重放、超额熔断、回滚、数据库不可覆盖及追加升级。PostgreSQL 进程测试覆盖相同／不同键并发校正；`test_evaluation_recovery.py` 验证默认预览、精确确认、数据库 ownership 和实际只读事务、拒绝不安全 receipt 及错误脱敏。
