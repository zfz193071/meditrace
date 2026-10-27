# Referral Review V1 验收报告（部分）

状态：**未通过最终验收，禁止据此宣称 V1 已完成或已部署。** 本报告汇总当前分支可复现的代码与自动化证据，并单独列出尚未执行的外部／人工验收。更新日期：2026-10-27。

## 被测版本与环境

- 最新被测代码：`4d19aec719c87ef165a956b69ef9a29390ae2fdb`；[完整 CI 40441851253](https://github.com/zfz193071/meditrace/actions/runs/40441851253) 的 `foundation`、`postgres-persistence` 均成功。普通后端 **934 passed／179 skipped**；独立 PostgreSQL 17 job **405 passed／0 skipped**，通过零跳过断言；前端 **17 suites／93 tests**、build／typecheck／lint、前后端依赖审计、契约／fixture 检查及 18 项部署脚本测试通过。普通 job 的 skipped 不计验收通过。
- 初版闭环代码为 `2b967eda50a8d33b5586a38f934508fbc9d729f6`，证据文档提交 `ed9973e`；[历史 CI 40310916116](https://github.com/zfz193071/meditrace/actions/runs/40310916116) 的两个 job 均成功。
- CI 环境由仓库 workflow 固定：Python 3.12、Node.js 22、PostgreSQL 17。后端普通 job 使用 SQLite；独立数据库 job 使用临时 PostgreSQL 和随机隔离 schema。
- 自动测试仅使用合成资料、Fake／replay 或模拟供应商；不配置付费模型密钥，不访问生产数据库，不发起浏览器 AI 对话。
- Python 测试现已默认阻断 DNS／IPv4／IPv6 socket 联网，普通 Python 子进程继承启动保护；吞掉联网异常也会使当前测试失败。21 项探针包含无 Mock 的真实 adapter（仅合成假密钥），未发出真实请求。原生 libpq、Node／外部程序和清除环境的进程不在该测试层保护范围；详见 [边界说明](../../src/backend/tests/offline/README.md)。首版开关命名冲突已修复，本地受影响回归 **139 passed**，首轮失败及最终 CI 证据见 [MT-22](tickets/MT-22.md#python-离线测试网络保护2026-10-27)。
- MT-22 新增 API 闭环见 [`test_workflow_integration.py`](../../src/backend/tests/referral_review/test_workflow_integration.py)：本地 SQLite HTTP／HTTPS 两种配置 2 passed；无本地 `TEST_DATABASE_URL`，PostgreSQL 两个参数化用例本地跳过；远端 PostgreSQL job 已成功执行并通过零跳过检查。
- 随后新增同一工作流的双账号资源隔离矩阵，见同一测试文件：另一账号的 packet、draft、revision、run、review、document metadata/page/original、snapshot、history、handoff 和 export 读取均返回 404；执行他人 run 和删除他人 packet 也均返回 404，且没有二次 Fake 派发。CI [run 40312565916](https://github.com/zfz193071/meditrace/actions/runs/40312565916) 的 `foundation` 与 `postgres-persistence` 均通过，PostgreSQL job 的零跳过门槛通过；本机没有 `TEST_DATABASE_URL`，本地 PG 参数仍跳过。
- 2026-10-27 增补：同一文件将跨账号矩阵扩至 15 个读取／12 个写入变体，增加同账号跨包 ID 混用和删除／到期在维护前后的读写拒绝，并逐次核对业务数据库、私有文件及 Fake 调用次数不变。对应 Q09／Q16／Q17；本地 HTTP／HTTPS SQLite 合计 **10 passed**，PostgreSQL **10 skipped**（未配置测试连接）；该轮 [CI 40431376009](https://github.com/zfz193071/meditrace/actions/runs/40431376009) 的独立数据库 job 已执行当时该文件全部 20 个参数化用例。详细边界见 [MT-22](tickets/MT-22.md#权限与生命周期矩阵增补2026-10-27)。

## Q01—Q20 证据与剩余工作

| 场景 | 当前自动化证据 | 当前结论与未完成项 |
| --- | --- | --- |
| Q01 无登录固定示例 | 固定案例／fixture 测试；相关前端代码和构建检查 | 代码证据部分具备；独立首次使用者和浏览器键盘／窄屏验收未完成 |
| Q02 正常资料包 | `test_workflow_integration.py`、`test_parser.py`、`test_extraction.py` | Fake API 路径可从导入走到导出；真实模型与用户工作区验收未完成 |
| Q03 unknown 与明确 none | `test_checklist.py`、`test_extraction.py`、`test_evaluation.py` | 离线语义回归已覆盖；冻结集与人工 gold 尚未签核 |
| Q04 DOB 冲突 | `test_checklist.py`、`test_reviews.py`、`test_handoff.py` | 规则及未解决事项导出有离线证据；人工资料复核未完成 |
| Q05 未找到附件 | `test_checklist.py`、`test_fixtures.py`、`test_handoff.py` | 合成案例和规则有离线证据；独立用户可用性验收未完成 |
| Q06 药物时间差异 | `test_checklist.py`、`test_evaluation.py` | 规则／固定集回归有离线证据；最终质量评估未完成 |
| Q07 引用边界与 Unicode | `test_parser.py`、`test_extraction.py`、`test_documents.py` | offsets、hash 与证据验证有离线测试；真实扫描材料不在自动验收范围 |
| Q08 受限 PDF | `test_parser.py`、`test_documents.py`、`test_document_pg.py` | 解析失败和 PostgreSQL 存储路径有测试；托管 Blob 往返与浏览器错误呈现未验收 |
| Q09 上传／版本／审核竞争 | `test_document_pg.py`、`test_runs_pg.py`、`test_reviews_persistence.py`、`test_workflow_integration.py`、`ReviewWorkspace.test.tsx` | 隔离 PostgreSQL 并发及一条完整流程通过；补充审核写入期间保持当前上下文、成功／失败后恢复操作的组件回归。完整外部／人工验收未完成 |
| Q10 重复执行与预算竞争 | `test_runs.py`、`test_runs_pg.py`、`test_usage_pg.py`、`test_evaluation_slots.py` | Fake 多进程和账本竞争已通过；真实供应商派发未开放 |
| Q11 断网、超时与未知费用 | `test_runs.py`、`test_operations.py`、`test_evaluation_recovery.py`、`test_evaluation_adjustments.py`、`Workspace.test.tsx`、`ManualDraft.test.tsx` | 离线故障／恢复证据存在；PDF 重选复用 key，以及手工备注冲突／断网后保留输入、读取一致版本并明确重试均已修复并通过回归。真实供应商超时与线上告警未验收 |
| Q12 无效输出及越权证据 | `test_extraction.py`、`test_documents.py`、`test_runs.py` | Fake 无效输出与归属验证有离线覆盖；真实模型防护与人工审查未验收 |
| Q13 改版后重跑 | `test_workflow_integration.py`、`test_runs.py`、`test_reviews.py`、`ReviewHistory.test.tsx` | 旧快照保留、新版本重跑通过；历史刷新／分页的迟到结果隔离及保留当前编辑通过组件回归。更广泛的历史 UI 人工检查未完成 |
| Q14 会员／额度限制 | `test_usage.py`、`test_runs.py`、`test_handoff.py`、`test_billing.py` | Fake 权益和额度边界已测；真实 Stripe 测试购买与真实模型阻断未验收 |
| Q15 重复／乱序／退款支付 | `test_billing.py`、`test_billing_pg.py` | 假 Stripe 签名及 PostgreSQL 竞争通过；真实 Stripe test Checkout／webhook 往返未完成 |
| Q16 跨账号隔离 | `test_packets.py`、`test_documents.py`、`test_runs.py`、`test_reviews.py`、`test_handoff.py`、`test_workflow_integration.py` | 集成工作流 15 个读取／12 个写入变体、同账号跨包资源绑定及拒绝写入无副作用通过；新增 PDF multipart／分块上传和旧 key 重放的跨账号拒绝，SQLite 与 PostgreSQL CI 通过。真实 Blob／托管权限及浏览器人工验收仍未完成 |
| Q17 删除与运行竞争 | `test_lifecycle.py`、`test_lifecycle_pg.py`、`test_workflow_integration.py` | Fake／PostgreSQL 清理竞争与补偿有证据；新增删除／到期在维护前后的读写隔离通过。Vercel Blob 删除及托管调度未验收 |
| Q18 无 AI／人工导出 | `test_handoff.py`、`test_fixtures.py` | Fake／人工导出路径有测试；示例页面无登录浏览器验收未完成 |
| Q19 PDF 分页与 Unicode | `test_handoff.py` | 本地 PDF 解析／渲染测试通过；长文档多视口浏览器检查未完成 |
| Q20 旧入口退役 | `test_retired_api.py`、`scripts/test_deploy_workflow.py` | 离线 410 与发布保护测试存在；生产旧路径全量只读复核待首次安全切换后执行 |

本表“有测试”表示当前仓库存在相应离线证据，不表示该 Q 场景的所有验收条件均通过。尤其 UI、供应商、真实模型质量、生产路由及操作者流程不能由 Fake 或后端测试替代。

2026-10-27 后续增量补充 Q08／Q09／Q13／Q16：新增 PDF multipart／分块上传的重放和内容冲突、跨账号及删除／到期拒绝、扫描件解析失败后保留审核与新文档替换闭环。分块拒绝验证没有读取正文；私有原件字节和业务状态保持不变。定向本地 **12 passed／12 PostgreSQL skipped**；提交 `abdacc5` 的[完整 CI](https://github.com/zfz193071/meditrace/actions/runs/40432785865) 及最新修复提交的完整 CI 均通过，独立数据库 job 执行集成文件全部 **44 个参数化用例**。前端同时修复了重新选择 PDF 时丢失幂等 key 的问题，两个新增回归验证同内容复用／不同内容分离；记录见 [BUGFIX](../../BUGFIX-PDF-UPLOAD-RETRY-KEY.md)。详见 [MT-22](tickets/MT-22.md#pdf-上传重放和解析失败闭环2026-10-27)；仍不替代真实 Blob 往返和浏览器失败呈现验收。

2026-10-27 历史列表增量对应 Q09／Q11／Q13：独立刷新历史后忽略旧分页的结果、错误、游标和加载状态；资料包切换时清空旧列表。常驻刷新入口可以在保留手工备注／人工修正的情况下发现新确认记录，不自动写入或打开快照。新增 6 项组件和 2 项工作区回归，本地前端 **17 suites／88 tests passed**；边界与远端证据见 [修复记录](../../BUGFIX-REVIEW-HISTORY-REQUESTS.md)。不是实际断网、浏览器或外部供应商验收。

2026-10-27 手工备注增量对应 Q09／Q11／Q18：在不丢弃本地输入的情况下读取已保存备注及其他人工字段，读取前后资料／审核版本一致才允许再次保存；可明确采用服务器备注并确认。新增 9 项回归包含写入已成功但响应丢失、确认失败不显示导出成功、初次／恢复读取失败、并发变化和卸载后迟到错误；本地与上述完整 CI 通过。没有浏览器 AI 操作、自动写入或本地持久化。刷新及资料版本变化的边界见 [修复记录](../../BUGFIX-MANUAL-NOTE-RECOVERY.md)；不作为三视口、真实断网或人工验收证据。

2026-10-27 审核写入增量对应 Q09／Q11／Q13：保存／确认未结束时禁用事项切换、丢弃编辑和历史导航；同步标记拦截同一次更新中的连续点击。只读历史刷新保持可用，失败保留输入，确认成功正常展示快照。新增 5 项回归，本地前端 **17 suites／93 tests passed**；命令、远端证据和页面关闭等边界见 [修复记录](../../BUGFIX-REVIEW-PENDING-NAVIGATION.md)。未执行浏览器 AI 操作或真实模型调用。

## 外部验收与阻碍

- MT-03：30 份合成资料的 gold 标注仍需人工逐包复核并签核。
- MT-04：本地 OAuth 真实往返已完成；托管 Vercel 日志验收仍待执行。
- 私有文件：尚无 Vercel Private Blob 配置及真实授权读／越权拒绝／删除往返证据。
- 支付：尚无 Stripe test key、固定 test Price 和真实 test webhook 往返。
- 模型：真实 runner 派发／录制尚未完成；真实评估须等待操作者明确授权费用上限、价格及测试账号。
- UI：三种视口、键盘／焦点、固定 demo 的首次使用者体验尚未形成完整 MT-22 报告证据。
- MT-21／24：代码已有首次安全切换流程，但生产 `/api/v1/readiness` 上次只读检查返回 404；生产备份／恢复核验、迁移授权、首次安全基线、线上旧路径验证及实际发布均未执行。
- 维护与告警：生产维护凭据、调度、失败通知到达和供应商备份保留策略仍未验收。

## 结论

MT-22 仍为 `TODO`。本报告是部分证据索引，尚未完成其要求的全场景验收报告。MT-24 的上线门槛也未满足；禁止执行生产首次切换、迁移或发布，直到依赖工单、人工签核、外部配置和备份／恢复条件经逐项确认。
