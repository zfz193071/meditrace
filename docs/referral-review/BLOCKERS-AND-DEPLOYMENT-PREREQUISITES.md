# Referral Review V1：当前阻碍与解除条件

更新：2026-10-23。供新会话回答“遇到的阻碍有？”、“完成工单／部署还缺什么”时使用。**本页的实测状态是日期快照，不是永久结论。**回答前重新检查工单 front matter、最新证据、仓库状态、部署预检和只读线上探测；不要把代码已实施、离线通过或旧站可访问写成 V1 已验收／已部署。需求与关闭规则以 [开发基线](README.md)、[质量发布门槛](QUALITY-AND-RELEASE.md) 和各工单为准。

## 2026-10-23 已核实状态

- `MT-01` 为 `DONE`；`MT-02` 因真实 PostgreSQL 迁移／并发验收为 `BLOCKED`；`MT-03` 因操作者尚未逐包签核候选标注为 `BLOCKED`。`MT-04`—`MT-24` 的 front matter 仍为 `TODO`；其中 04—21 和 23 已有不同程度代码／离线证据，不能据此提前关闭。
- `MT-21` 代码提交为 `2e4339f`：旧 HTTP API 返回 410、旧页面转退役说明、只读 readiness 和安全回退保护已有离线测试。缺前置 `MT-11`／`MT-17`／`MT-19`、真实 PostgreSQL、首次安全生产基线及线上验收。详见 [MT-21 证据](MT-21-EVIDENCE.md)。
- 对当前生产域名作过**不读取旧资料**的只读 GET：`/api/v1/readiness` 返回 **404**，`/api/diagnose` 返回 **405**。这只证明生产尚未运行 MT-21 代码，不证明其他旧路径的数据内容或权限。
- 本机 Vercel CLI 和 `.vercel/project.json` 存在，项目 ID 与部署脚本一致；`./deploy-vercel.sh --check` 因保存的 Vercel 登录失效，在 `vercel whoami` 阶段停止。尚不能确认平台的实际环境变量、套餐或权限。需要操作者交互运行 `vercel login`，或在受控环境提供 `VERCEL_TOKEN`；不要在聊天中发送令牌。
- 当前 shell 的 `TEST_DATABASE_URL`、`DATABASE_URL`、`DEEPSEEK_API_KEY`、`VERCEL_TOKEN` 均未设置。**本机缺失不等于 Vercel／GitHub 平台缺失**，新会话需重新检查存在性，绝不打印值。
- 本地 `main` 有未推送提交，远端 CI 的临时 PostgreSQL job 未有本批次运行证据。已有未跟踪 `TASK-PREVISIT-SUMMARY.md` 是用户文件，保持不动。

## 关闭 MT-21 的条件

1. 按依赖规则先完成 `MT-11`、`MT-17`、`MT-19`；它们的阻碍又追溯到 `MT-02`、`MT-03` 以及 OAuth、存储、支付和真实数据库验收。依赖未关闭时 MT-21 仍为 `TODO`。
2. 在隔离 PostgreSQL 上验证追加迁移、旧表／行保留、并发、费用预留及回滚。可以使用仓库 CI 的临时 PostgreSQL 或独立 `TEST_DATABASE_URL`；不拿生产库当测试库。生产 `DATABASE_URL` 和备份／恢复条件必须在迁移前单独核实。
3. 首次从旧生产版本切换时，建立**已封闭旧公开接口且兼容 `rr_` schema 的安全基线**。当前 `deploy-vercel.sh` 会拒绝把旧生产版本作为自动回退候选，因此普通发布脚本不能直接完成首次切换。设计、实现并离线验证一次性安全切换流程是代理的工程工作；禁止为求快回滚到恢复旧公开读取的版本。
4. 上线后直接测试旧读、写、流式、诊断、报告、验证路径的受支持方法均为 410；新配置无钱包／RPC／Pinata 仍能运行；`GET /api/v1/readiness` 的数据库、迁移、清单均 `ready`；旧数据未删改；只读 verify 和失败回退证据齐全。才逐项勾选 [MT-21](tickets/MT-21.md)。

## 正式部署完整 V1 的条件

`MT-24` 要求 `MT-01`—`MT-23` **全部 DONE**、[Q01—Q20](QUALITY-AND-RELEASE.md) 和发布门槛全通过。尤其 `MT-20` 还缺独立真实评估账本与全站费用预留接入；当前真实 runner 主动拒绝派发，Fake／replay 不能替代真实成绩。`MT-22` 还须完成整条任务链、双账号权限、PostgreSQL 并发、故障、三视口／键盘／PDF、依赖审计并写 `acceptance-report.md`。`MT-23` 求职材料初稿需按最终实测复核。

| 外部条件 | 需要的内容与实际验收 | 谁需参与 |
| --- | --- | --- |
| Vercel | 恢复 CLI 登录；核对当前项目权限、Services、Hobby、生产域名 HTTPS、函数时限、实际环境和部署输入。`./deploy-vercel.sh --check` 成功后仍不代表可以发布。 | 操作者完成登录；代理检查和记录 |
| PostgreSQL | 隔离测试 schema 或 CI 临时 PostgreSQL；生产 `DATABASE_URL`、追加迁移记录、备份／恢复条件。真实测试覆盖迁移、竞争、回滚、权限和幂等。 | 操作者确认生产资源；代理可建立临时测试环境 |
| GitHub OAuth | `RR_SITE_ORIGIN`、client ID／secret、精确 callback `https://meditrace.baozaolaoba.top/api/v1/auth/github/callback`、session encryption key；实际登录、consent、退出和错误回跳。 | 操作者配置 OAuth App 并完成一次 consent；代理验证 |
| 私有文件 | 私有 Vercel Blob store、`RR_STORAGE_BACKEND=vercel`、最小权限 `BLOB_READ_WRITE_TOKEN`；真实写／授权读／越权拒绝／删除和孤立清理。 | 操作者提供资源；代理验证 |
| 支付测试 | 仅 Stripe **test** key、固定 Price／金额／货币及 webhook secret；真实 test Checkout→签名 webhook→一次权益、重复／乱序／退款和多实例竞争。禁止 live 配置。 | 操作者配置测试账号；代理验证 |
| 真实模型 | DeepSeek Key、模型 ID、经核实的价格版本和输入／输出单价、受邀内部 user UUID、正数日／月预算；先完成评估账本，再由操作者明确授权具体 `--max-cost-usd` 上限，使用合成资料进行真实测量。 | 代理先补实现；操作者给预算授权与受邀账号 |
| 维护与告警 | 后端 `RR_MAINTENANCE_TOKEN`，仓库 `RR_MAINTENANCE_SITE_ORIGIN`／同名 token secrets；每日 03:17 UTC、手动触发、失败通知接收者和实际到达测试；核对供应商备份及日志保留。 | 操作者确认接收者／平台设置；代理演练 |
| 人工验收 | 30 份合成资料的 gold 标注逐项复核并留签核记录；一次真实受邀核对、人工修改、确认及导出；三例 demo 的独立首次使用者试用；最终作品文字／视频的本人贡献声明复核。 | 用户或指定操作者实际完成并留证据 |

自动浏览器不得发送 AI 消息。真实模型评估只在受控 CLI、费用上限和明确授权下进行；完整工作区的真实核对由用户手动触发。所有密钥在平台或受控环境配置，不粘贴在聊天、工单或日志。

## 新会话应如何更新此页

1. 读工单 front matter、最新 `MT-*-EVIDENCE.md` 和 `git status`，核对依赖是否真的关闭。只读查看环境变量**是否存在**，不输出内容。
2. 需要判断线上状态时，先做不读取旧资料的 GET 探测；Vercel 登录可用后运行 `./deploy-vercel.sh --check`，保留失败原因。不要把 `--check` 当成发布。
3. 分开报告：**当前已验证阻碍**、**代理可继续完成的工程工作**、**必须由操作者提供的配置／预算／人工验收**。每解决一项，更新日期、证据链接和剩余条件；以工单及发布门槛判定是否可关闭／部署。
