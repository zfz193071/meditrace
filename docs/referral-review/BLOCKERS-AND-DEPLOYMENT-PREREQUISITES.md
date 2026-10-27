# Referral Review V1：当前阻碍与解除条件

## 当前范围调整：求职 MVP（2026-10-27）

用户已明确收缩为 Discord 求职最小 MVP。当前只推进[开发基线中的 4 个收尾包](README.md#当前优先目标discord-求职-mvp2026-10-27-用户调整)：公开前端演示、核心流程验收、求职文案、现有视频复核。
下文支付、真实模型评估、私有存储和生产运维等阻碍属于完整 V1，现阶段暂缓，
不再全部作为隔离的公开前端作品展示前置。尚未核实公开新版 demo 链接；已有
三个固定案例和约 80 秒字幕粗剪可以复用。旧生产服务的安全切换与数据保护
约束仍适用，本次不替换旧服务、不部署、不发送消息。

本次重新核对工单状态为 2 DONE、2 BLOCKED、20 TODO；22 项未关闭是原完整
产品的验收状态，不是剩余开发量。以下平台／生产信息仍为各自注明日期的
历史快照，本次未重新探测，不能据此声称线上当前配置已通过。

更新：2026-10-26（已执行远端 CI 和真实隔离 PostgreSQL 验收；线上完整验收未执行）。供新会话回答“遇到的阻碍有？”、“完成工单／部署还缺什么”时使用。**本页的实测状态是日期快照，不是永久结论。**回答前重新检查工单 front matter、最新证据、仓库状态、部署预检和只读线上探测；不要把代码已实施、离线通过或旧站可访问写成 V1 已验收／已部署。需求与关闭规则以 [开发基线](README.md)、[质量发布门槛](QUALITY-AND-RELEASE.md) 和各工单为准。

## 2026-10-26 Vercel、CI 与工单复核

- 操作者完成 `vercel login` 浏览器授权，CLI 退出 0 并确认已登录；此前的登录失效阻碍已解除。
- `./deploy-vercel.sh --check` 退出 0：已核对目标项目访问权限、前后端 Services、Hobby 套餐、生产 `DATABASE_URL` 变量存在及 231 个部署输入文件。证据：[本地预检日志](../../.vercel/deploy-20261026-092810.log)（本机文件，不随仓库提交）。预检未验证数据库连接或迁移状态。
- 生产 `DEEPSEEK_API_KEY` 仍未配置。本次未发布、未迁移；MT-02 已通过隔离 CI 验收，线上功能及下方其他发布条件仍需逐项复核。
- 首次 `git fetch origin` 后确认的 24 个本地提交及本次修复，现已推送到 `codex/referral-postgres-validation` 验证分支；远端生产 `main` 未更新。未跟踪的用户文件 `TASK-PREVISIT-SUMMARY.md` 保持不动。
- 初次生产变量名称检查没有任何 `RR_*`、`BLOB_READ_WRITE_TOKEN` 或 `DEEPSEEK_API_KEY`。本轮已创建 [GitHub OAuth App](https://github.com/settings/applications/3964320)，精确回调为 `https://meditrace.baozaolaoba.top/api/v1/auth/github/callback`，没有开启 wildcard 或 device flow。Vercel production 已保存 `RR_GITHUB_CLIENT_ID`、`RR_SITE_ORIGIN`、`RR_GITHUB_CALLBACK_URL`、`RR_SESSION_ENCRYPTION_KEY` 与 `RR_MODE=sandbox`。`RR_GITHUB_CLIENT_SECRET` 已通过浏览器表单保存；Vercel API 已复核六项 production 配置均存在，client secret 类型为 `sensitive`。聊天中曾暴露的密钥均已撤销，替代密钥未写入本地文件或本文档。其他存储、测试支付、真实模型及维护配置仍缺。
- HTTPS 只读 GET `/api/v1/readiness` 仍返回 **404**（仅检查状态码，不读取旧资料），当前生产未通过新 readiness 验证，首次安全切换阻碍未解除。
- 临时 PostgreSQL 17 [扩展数据库 job](https://github.com/zfz193071/meditrace/actions/runs/40255313217/job/121355790255) 为 **133 passed／0 skipped**（包含 SQLite／PostgreSQL 参数化），MT-02 的全部验收通过并改为 `DONE`；MT-10／11／12 的账本、跨进程和审核持久化证据同步补充。未使用生产数据库，本机 shell 仍无 `TEST_DATABASE_URL`，不再因此把 MT-02 记为受阻。
- 当前工单状态：MT-01／02 `DONE`、MT-03／04 `BLOCKED`、MT-05—24 `TODO`。MT-03 缺人工标注签核，MT-04 已完成本地真实 OAuth 往返及用户 consent，仍缺托管平台日志验收；MT-20 真实 runner 派发／录制集成、MT-21 首次安全生产基线及 MT-22 完整验收仍未完成。
- MT-04 本地验收资源已准备：独立 [Local OAuth App](https://github.com/settings/applications/3964380)、loopback 精确 callback、0700 私有目录及 0600 凭据／SQLite 库，迁移 `rr_0006`，就绪检查通过。新增手动启动脚本和 OAuth access log 脱敏修复，75 项后端定向测试及 1 项前端日志回归通过；后续已获用户明确授权启动服务，用户亲自完成 consent；修复 GitHub `iss` 兼容问题后真实登录／回跳／刷新／退出通过，最新身份回归 86 passed。操作及环境边界见 [认证手册](AUTHENTICATION.md)。此环境不启用存储、支付或真实模型，不替代 Vercel 线上验收。
- Vercel 项目开启了 Git 自动部署且生产分支为 main。为防止推送绕过发布门槛，验证分支已设置 `git.deploymentEnabled: false`，实际推送后最近部署记录仍为既有生产版本。远端 main 尚未包含该保护，不向其推送未包含保护的提交。见 [修复记录](../../BUGFIX-VERCEL-GIT-AUTO-DEPLOY.md)。
- 历史 CI 经退役测试步骤、pypdf 安全补丁及解析版本兼容修复后，在提交 `ef5d9e5` [全部通过](https://github.com/zfz193071/meditrace/actions/runs/40257964496)：后端 564 passed／69 skipped，另一个 PostgreSQL job 137 passed／0 skipped，前端 68 tests、构建／类型检查／前后端依赖审计均通过。详见 [最终 CI 证据](CI-2026-10-26.md)，不将普通 job 的 skipped 当作验收通过。

- OAuth 修复提交 `381850a` 的 [完整 CI](https://github.com/zfz193071/meditrace/actions/runs/40264116229) 全通过：后端 767 passed／73 skipped；独立 PostgreSQL job 141 passed／0 skipped；前端 15 suites／69 tests、构建、类型检查及依赖审计通过。共享认证 fixture 的 HTTP／HTTPS 参数化也扩展了下游 API 用例覆盖，计数不能视为新增功能数。

## 2026-10-26 MT-20 工程推进

最新增量追加 `rr_0009` 实现晚到 usage 校正，保留原结算并幂等更新原 batch／日月桶；新增隔离 PostgreSQL 恢复 CLI，默认强制只读，写入需精确计划确认及测试 schema ownership receipt。真实入口、实际人工授权／gold、真实录制来源、生产恢复运维和完整报告仍缺。验证结果见 [MT-20 证据](MT-20-EVIDENCE.md)；本次没有生产迁移或更新下方线上快照。

继续补充 MT-17 支付回调的隔离 PostgreSQL 多进程竞争：不同成功事件同单竞态只授一份会员；退款与成功并发最终保持撤销。Fake Stripe，不替代真实支付验收；本机没有 TEST_DATABASE_URL，结果须等本次 CI。实现仅在验证分支，未更新生产。

MT-17 的[最新完整 CI](https://github.com/zfz193071/meditrace/actions/runs/40297989217)已通过：后端 891 passed／157 skipped，PostgreSQL 17 job 340 passed／0 skipped，前端 69 tests、build／typecheck／audit 通过。支付回调和不同幂等键 Checkout 竞争补充均通过；真实 Stripe 往返与托管 OAuth 日志仍未完成，MT-17 保持 TODO。

MT-21 首次安全切换流程提交 `46dcc8c` 的[完整 CI](https://github.com/zfz193071/meditrace/actions/runs/40299944166) 中 `foundation` 与 `postgres-persistence` 均通过，部署工作流 18 项离线测试通过。仅实现并验证代码路径；未做生产备份、迁移、发布或线上验收，首次安全基线仍未建立。

MT-22 新增 API 级完整闭环测试及 PostgreSQL 参数化提交 `2b967ed` 的[完整 CI](https://github.com/zfz193071/meditrace/actions/runs/40310916116) 中 `foundation` 与 `postgres-persistence` 均通过，PostgreSQL job 零跳过门槛通过。该项仅覆盖一条 Fake 工作流，不等于 MT-22 的全场景验收报告。

MT-22 已新增[部分验收报告](acceptance-report.md)，逐项列出 Q01—Q20 的自动化证据和待执行条件；新增核心工作流跨账号读取／写入拒绝矩阵，并在 SQLite 与 PostgreSQL CI 通过。报告明确不是最终验收结论；浏览器人工验收、真实供应商往返、人工 gold 签核及生产发布证据仍未完成。

2026-10-27 MT-22 增补 `defca4c` 的[完整 CI](https://github.com/zfz193071/meditrace/actions/runs/40431376009) 已通过：跨账号 15 个读取／12 个写入变体、同账号跨包绑定，以及删除／到期在维护前后拒绝读写，逐次核对业务状态／文件／Fake 次数无副作用。普通后端 901 passed／167 skipped；独立 PostgreSQL 17 job 360 passed／0 skipped，前端 69 tests、build／typecheck／lint／audit 及部署脚本 18 tests 通过。仅更新工程证据，不更新生产探测或外部配置快照；MT-22 仍为 TODO。

同日继续完成 PDF 表单／分块上传的幂等、跨账号、删除／到期及解析失败后替换闭环，并修复前端响应丢失后重选同一 PDF 会生成新 key 的重复上传问题。最终代码 `08aba8e` 的[完整 CI](https://github.com/zfz193071/meditrace/actions/runs/40433418902) 全通过：普通后端 913 passed／179 skipped，独立 PostgreSQL 384 passed／0 skipped（集成文件 44 个参数化用例），前端 71 tests 及构建／类型检查／lint／审计通过。见 [修复记录](../../BUGFIX-PDF-UPLOAD-RETRY-KEY.md)及 [MT-22](tickets/MT-22.md)。未更新外部或线上状态，前置及真实／人工验收条件仍不变。

同日 MT-22 增加 Python 离线测试网络保护，防止漏配 Mock 时访问真实模型；普通 Python 子进程继承保护，CI 测试 job 显式清空模型密钥。首版测试开关与产品 `RR_` 配置前缀冲突，已修正且保留失败记录。最终 `3789672` 的[完整 CI 40437026849](https://github.com/zfz193071/meditrace/actions/runs/40437026849) 通过：普通后端 **934 passed／179 skipped**、独立 PostgreSQL **405 passed／0 skipped**、前端 **71 tests** 及构建／类型检查／lint／审计、契约／fixture 和部署脚本检查通过。此为 Python socket 层保护，不覆盖原生 libpq／Node 等；边界见 [说明](../../src/backend/tests/offline/README.md)。只更新工程证据，不更新生产配置或探测快照，不解除外部／人工验收及部署门槛。

同日继续修复手工备注在 409／响应丢失后只能整包重载的恢复问题，保留本地输入并对照一致的服务器版本；读取期间出现并发变更则保持写入阻断。代码 `851e6a3` 的[完整 CI 40438487348](https://github.com/zfz193071/meditrace/actions/runs/40438487348) 通过：前端 **16 suites／80 tests**，普通后端 **934 passed／179 skipped**，独立 PostgreSQL **405 passed／0 skipped**，构建／类型检查／lint／审计、契约／fixture 和部署脚本检查通过。见 [修复记录](../../BUGFIX-MANUAL-NOTE-RECOVERY.md)。仍未执行生产部署、真实模型调用或外部／人工验收；MT-22 保持 TODO。

同日继续修复历史分页的迟到响应污染：刷新／上下文变更／卸载后忽略旧结果、错误、游标和加载状态，并支持保留当前编辑的独立历史刷新。代码 `6fcdecf` 的[完整 CI 40439750785](https://github.com/zfz193071/meditrace/actions/runs/40439750785) 通过：前端 **17 suites／88 tests**，普通后端 **934 passed／179 skipped**，独立 PostgreSQL **405 passed／0 skipped**，构建／类型检查／lint／审计、契约／fixture 和部署脚本检查通过。见 [修复记录](../../BUGFIX-REVIEW-HISTORY-REQUESTS.md)。只补充工程证据；外部配置、生产探测和人工验收状态未更新，MT-22 继续 TODO。

同日继续保护审核写请求期间的界面上下文：保存／确认未结束时禁止切换事项、丢弃编辑和历史导航，只读历史刷新仍可用；成功／失败后恢复查看，失败保留输入，确认成功正常显示快照。代码 `4d19aec` 的[完整 CI 40441851253](https://github.com/zfz193071/meditrace/actions/runs/40441851253) 通过：前端 **17 suites／93 tests**，普通后端 **934 passed／179 skipped**，独立 PostgreSQL **405 passed／0 skipped**，构建／类型检查／lint／审计、契约／fixture 和部署脚本检查通过。见 [修复记录](../../BUGFIX-REVIEW-PENDING-NAVIGATION.md)。仍未执行生产发布、真实模型调用或外部／人工验收，MT-22 保持 TODO。

实现 `5aa9a03`、预算补充 `e568b9e`、PostgreSQL 汇总类型修复 `ad48bf2` 的[最终完整 CI](https://github.com/zfz193071/meditrace/actions/runs/40290077756) 全通过：后端 891 passed／154 skipped；独立数据库 job 337 passed／0 skipped（含两种数据库参数化），前端 69 项测试、构建／类型检查／审计通过。先前 CI 暴露的 JSON 类型问题及预算重用保护已记录，不能据此将 MT-20 或完整 V1 记为已验收。

事务调度与持久录制恢复现已接通隔离 Fake 演练：操作者检查、费用预留及派发标记同事务，录制先于结算，恢复不重复调用；无数据库／Key 回放保留缺失及失败样本。仅 test 环境和内置 Fake，未开启真实供应商入口，也未记录实际预算授权。此轮无迁移或线上操作。实现 `bdc160d`／测试修正 `90cb281` 的[完整 CI](https://github.com/zfz193071/meditrace/actions/runs/40282732849) 全通过：后端 870 passed／136 skipped，独立数据库 job 298 passed／0 skipped（含 SQLite／PostgreSQL 参数化），前端 69 项及构建／审计通过；首轮查询顺序断言误判的原因和修复保留在 [MT-20 证据](MT-20-EVIDENCE.md)。

新增可审阅计划和授权参数预检：只处理固定合成语料，输出样本／预算／版本／目录及 hash，未记录实际人工授权，不连接供应商。源码与路径复读校验已加强。真实 runner 仍关闭，事务派发／录制恢复及人工 gold／预算条件不变。提交 `8272a1f`／`e2277bc` 的[完整 CI](https://github.com/zfz193071/meditrace/actions/runs/40279569965) 全通过：后端 849 passed／113 skipped；独立数据库 job 254 passed／0 skipped（含 SQLite／PostgreSQL 参数化）；前端 69 项、构建及审计通过。本机原有离线回归曾出现 PDF_TIMEOUT，未提高超时；详见 [MT-20 证据](MT-20-EVIDENCE.md)。本段不更新上方线上探测快照。

独立评估账本及共享日月费用预留已实施（`d45d810`），详见 [账本范围](EVALUATION-LEDGER.md)。本地后端 798 passed／97 skipped；[独立 PostgreSQL 17 job](https://github.com/zfz193071/meditrace/actions/runs/40267092317/job/121391749549) 196 passed／0 skipped，包含评估与工作区多进程竞争。[完整 CI](https://github.com/zfz193071/meditrace/actions/runs/40267092317) 全通过：前端 69 tests、构建／类型检查及前后端审计通过，后端 CI 同为 798 passed／97 skipped。真实 CLI 仍拒绝派发，共享并发槽现已实现，仍缺授权与合成输入绑定、真实录制／恢复及晚到费用校正。未请求或消耗真实模型预算，未应用生产迁移，MT-20 不关闭。

共享执行槽增量 `1efa200` 的[该增量 CI](https://github.com/zfz193071/meditrace/actions/runs/40276376704) 全通过：后端 818 passed／112 skipped；独立 PostgreSQL 17 job 223 passed／0 skipped（含两种数据库参数化），包含 Fake／real 工作区和评估四进程争用全站两槽、过期完成与新派发竞争。前端 69 tests、构建／类型检查及前后端审计通过。新增迁移 rr_0008 仅在隔离测试库验证，未应用生产。

2026-10-27 支付返回页增量：切换订单、刷新或轮询失败时撤下旧订单信息，隔离迟到响应，避免显示上一订单已支付或错误返回链接。代码 `6acbf86` 的[完整 CI 40445193439](https://github.com/zfz193071/meditrace/actions/runs/40445193439) 两个 job 均成功：前端 **17 suites／98 tests**，普通后端 **934 passed／179 skipped**，独立 PostgreSQL **405 passed／0 skipped**，构建／类型检查／lint、契约／fixture、18 项部署脚本测试和依赖审计通过。见 [修复记录](../../BUGFIX-PAYMENT-RETURN-STATE.md)。没有访问 Stripe、调用真实模型或生产部署；不更新线上配置快照，MT-17／MT-22 保持 TODO。

2026-10-27 核对状态增量：旧轮询不再覆盖取消／恢复／执行／主动查询的新结果，终态清理定时读取。代码 `6c3a3bd` 的[完整 CI 40446782653](https://github.com/zfz193071/meditrace/actions/runs/40446782653) 两个 job 均通过：前端 **18 suites／107 tests**，普通后端 **934 passed／179 skipped**，独立 PostgreSQL **405 passed／0 skipped**，构建／类型检查／lint、契约／fixture、部署脚本及依赖审计通过。见 [修复记录](../../BUGFIX-RUN-STATUS-POLLING.md)。未执行浏览器 AI 操作、真实模型调用或生产部署，不更新外部配置快照；MT-22 保持 TODO。

2026-10-27 资料包列表增量：删除已确认但刷新失败时不再显示旧入口，创建输入保留；同步锁与请求代次隔离连续提交和卸载后迟到响应。代码 `14b382e` 的[完整 CI 40454849223](https://github.com/zfz193071/meditrace/actions/runs/40454849223) 两个 job 均通过：前端 **19 suites／114 tests**，普通后端 **934 passed／179 skipped**，独立 PostgreSQL **405 passed／0 skipped**，构建／类型检查／lint、契约／fixture、部署脚本及依赖审计通过。见 [修复记录](../../BUGFIX-PACKET-LIST-RECOVERY.md)。无实际删除、模型调用或部署，不更新外部配置快照；MT-22 保持 TODO。

2026-10-27 会话恢复增量：临时会话／配置读取失败不再卸载仍有效的当前编辑区；账号变化、退出、拒绝与到期保持隔离。代码 `512689a` 的[完整 CI 40457437815](https://github.com/zfz193071/meditrace/actions/runs/40457437815) 两个 job 均通过：前端 **20 suites／127 tests**，普通后端 **934 passed／179 skipped**，独立 PostgreSQL **405 passed／0 skipped**，构建／类型检查／lint、契约／fixture、部署脚本与审计通过。本地既有 Demo 超时在旧代码对照也复现，未改时限，CI 原用例通过；见 [修复记录](../../BUGFIX-WORKSPACE-SESSION-RECOVERY.md)。无真实登录、模型调用或部署，不更新外部配置快照；MT-22 保持 TODO。

## 2026-10-23 已核实状态（历史快照，登录状态已由上方复核更新）

- `MT-01` 为 `DONE`；`MT-02` 因真实 PostgreSQL 迁移／并发验收为 `BLOCKED`；`MT-03` 因操作者尚未逐包签核候选标注为 `BLOCKED`。`MT-04`—`MT-24` 的 front matter 仍为 `TODO`；其中 04—21 和 23 已有不同程度代码／离线证据，不能据此提前关闭。
- `MT-21` 代码提交为 `2e4339f`：旧 HTTP API 返回 410、旧页面转退役说明、只读 readiness 和安全回退保护已有离线测试。缺前置 `MT-11`／`MT-17`／`MT-19`、真实 PostgreSQL、首次安全生产基线及线上验收。详见 [MT-21 证据](MT-21-EVIDENCE.md)。
- 对当前生产域名作过**不读取旧资料**的只读 GET：`/api/v1/readiness` 返回 **404**，`/api/diagnose` 返回 **405**。这只证明生产尚未运行 MT-21 代码，不证明其他旧路径的数据内容或权限。
- 本机 Vercel CLI 和 `.vercel/project.json` 存在，项目 ID 与部署脚本一致；`./deploy-vercel.sh --check` 因保存的 Vercel 登录失效，在 `vercel whoami` 阶段停止。尚不能确认平台的实际环境变量、套餐或权限。需要操作者交互运行 `vercel login`，或在受控环境提供 `VERCEL_TOKEN`；不要在聊天中发送令牌。
- 当前 shell 的 `TEST_DATABASE_URL`、`DATABASE_URL`、`DEEPSEEK_API_KEY`、`VERCEL_TOKEN` 均未设置。**本机缺失不等于 Vercel／GitHub 平台缺失**，新会话需重新检查存在性，绝不打印值。
- 本地 `main` 有未推送提交，远端 CI 的临时 PostgreSQL job 未有本批次运行证据。已有未跟踪 `TASK-PREVISIT-SUMMARY.md` 是用户文件，保持不动。

## 关闭 MT-21 的条件

1. 按依赖规则先完成 `MT-11`、`MT-17`、`MT-19`；它们的阻碍又追溯到 `MT-02`、`MT-03` 以及 OAuth、存储、支付和真实数据库验收。依赖未关闭时 MT-21 仍为 `TODO`。
2. 在隔离 PostgreSQL 上验证追加迁移、旧表／行保留、并发、费用预留及回滚。可以使用仓库 CI 的临时 PostgreSQL 或独立 `TEST_DATABASE_URL`；不拿生产库当测试库。生产 `DATABASE_URL` 和备份／恢复条件必须在迁移前单独核实。
3. 首次从旧生产版本切换时，建立**已封闭旧公开接口且兼容 `rr_` schema 的安全基线**。`--first-cutover` 一次性流程已实现并通过 18 项部署 mock 测试：迁移和暂存验证后才 promote，线上验证失败不回滚到旧公开接口版本。仍须等依赖及 MT-24 发布条件、生产备份／恢复核验和操作者授权；该流程尚未在线上执行。
4. 上线后直接测试旧读、写、流式、诊断、报告、验证路径的受支持方法均为 410；新配置无钱包／RPC／Pinata 仍能运行；`GET /api/v1/readiness` 的数据库、迁移、清单均 `ready`；旧数据未删改；只读 verify 和失败回退证据齐全。才逐项勾选 [MT-21](tickets/MT-21.md)。

## 正式部署完整 V1 的条件

`MT-24` 要求 `MT-01`—`MT-23` **全部 DONE**、[Q01—Q20](QUALITY-AND-RELEASE.md) 和发布门槛全通过。尤其 `MT-20` 独立账本及全站日月费用预留已实施，共享派发槽也已实现，计划检查、事务派发及持久录制恢复已接通隔离 Fake 演练，隔离测试库恢复 CLI 和晚到费用校正也已实现；仍缺实际授权／gold 来源、真实入口、生产恢复运维及完整报告；当前真实 runner 主动拒绝派发，Fake／replay 不能替代真实成绩。`MT-22` 还须完成整条任务链、双账号权限、PostgreSQL 并发、故障、三视口／键盘／PDF、依赖审计并写 `acceptance-report.md`。`MT-23` 求职材料初稿需按最终实测复核。

| 外部条件 | 需要的内容与实际验收 | 谁需参与 |
| --- | --- | --- |
| Vercel | 2026-10-26 已恢复 CLI 登录并通过 `--check`，核实项目访问权限、Services、Hobby、生产数据库变量存在及部署输入；生产域名 HTTPS、函数时限和完整 V1 环境配置仍需核对。`./deploy-vercel.sh --check` 成功后仍不代表可以发布。 | 登录已完成；代理继续检查和记录 |
| PostgreSQL | MT-02 隔离 PostgreSQL 17 验收已通过，账本／运行竞争及审核持久化也补充了 CI 证据。生产 `DATABASE_URL` 实际连接、追加迁移、备份／恢复及其他业务的完整集成验收仍需核实。 | 无需用户提供测试库；操作者确认生产资源和备份，代理验证 |
| GitHub OAuth | OAuth App 已创建，站点／client ID／callback／session key／sandbox 模式已存 Vercel；客户端 secret 已保存并核实为 production sensitive。本地真实登录、用户 consent、刷新、退出及非法回跳已验收；托管平台日志仍待检查。 | 本地参与已完成；代理推进托管环境验收 |
| 私有文件 | 私有 Vercel Blob store、`RR_STORAGE_BACKEND=vercel`、最小权限 `BLOB_READ_WRITE_TOKEN`；真实写／授权读／越权拒绝／删除和孤立清理。 | 操作者提供资源；代理验证 |
| 支付测试 | 仅 Stripe **test** key、固定 Price／金额／货币及 webhook secret；真实 test Checkout→签名 webhook→一次权益、重复／乱序／退款和多实例竞争。禁止 live 配置。 | 操作者配置测试账号；代理验证 |
| 真实模型 | DeepSeek Key、模型 ID、经核实的价格版本和输入／输出单价、受邀内部 user UUID、正数日／月预算；先完成账本到真实 runner 的派发／录制集成，再由操作者明确授权具体 `--max-cost-usd` 上限，使用合成资料进行真实测量。 | 代理继续 runner 集成；操作者给预算授权与受邀账号 |
| 维护与告警 | 后端 `RR_MAINTENANCE_TOKEN`，仓库 `RR_MAINTENANCE_SITE_ORIGIN`／同名 token secrets；每日 03:17 UTC、手动触发、失败通知接收者和实际到达测试；核对供应商备份及日志保留。 | 操作者确认接收者／平台设置；代理演练 |
| 人工验收 | 30 份合成资料的 gold 标注逐项复核并留签核记录；一次真实受邀核对、人工修改、确认及导出；三例 demo 的独立首次使用者试用；最终作品文字／视频的本人贡献声明复核。 | 用户或指定操作者实际完成并留证据 |

自动浏览器不得发送 AI 消息。真实模型评估只在受控 CLI、费用上限和明确授权下进行；完整工作区的真实核对由用户手动触发。所有密钥在平台或受控环境配置，不粘贴在聊天、工单或日志。

## 新会话应如何更新此页

1. 读工单 front matter、最新 `MT-*-EVIDENCE.md` 和 `git status`，核对依赖是否真的关闭。只读查看环境变量**是否存在**，不输出内容。
2. 需要判断线上状态时，先做不读取旧资料的 GET 探测；Vercel 登录可用后运行 `./deploy-vercel.sh --check`，保留失败原因。不要把 `--check` 当成发布。
3. 分开报告：**当前已验证阻碍**、**代理可继续完成的工程工作**、**必须由操作者提供的配置／预算／人工验收**。每解决一项，更新日期、证据链接和剩余条件；以工单及发布门槛判定是否可关闭／部署。
