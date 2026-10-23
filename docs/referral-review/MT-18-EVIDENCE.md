# MT-18 实施与验收证据

日期：2026-10-23。状态：代码与离线验证已实施；前置 MT-05／07／11／12／17 未全部验收，工单保留 **TODO**，不代表整票已关闭。

## 改动

- `src/backend/referral_review/lifecycle/`：账号删除、所有会话撤销、包 tombstone、到期和孤立上传、完整历史内容图清除、配额补偿、去标识化、30／90 天保留及有界维护。复用 `rr_0006` 已有表，无新增迁移、未修改用户数据库。
- `documents/service.py`：刷新外部写入 lease；已 ready 文件进入清理时保留不可变解析状态，物理删除后才释放容量。
- `billing/service.py`、`provider.py`、`routes.py`：维护入口移入独立 lifecycle，支付恢复共享批次限额与剩余时间；超出恢复窗口的未绑定 Checkout 订单到期；删除账号的迟到／重复回调不会重建权益。
- `IdentityPanel`、`AccountDeletion`、`PacketList`、`WorkspaceGate`、`PacketWorkspace`：英文保留／备份说明、输入 DELETE 的账号删除、排队反馈、过期和 404 后卸载已加载审核内容、重新可见时只读复查。
- `.github/workflows/referral-maintenance.yml`、`scripts/referral_maintenance.py`：03:17 UTC／手动触发，200 项／45 秒批次预算，最多十批，有积压或失败则 Actions 失败；凭据仅从 secret 环境读取，不跟随重定向。
- OpenAPI 与 TypeScript 生成产物已更新。操作手册见 [LIFECYCLE](LIFECYCLE.md)，既有边界修复见 [BUGFIX](../../BUGFIX-REFERRAL-LIFECYCLE.md)。

MT-18 代码已于 2026-10-23 提交为 `6fd7306`；未推送／部署。用户已有 `TASK-PREVISIT-SUMMARY.md` 未改动。

## 验收逐项

| 工单验收 | 已取得证据 | 未完成部分 |
| --- | --- | --- |
| tombstone 后立即拒绝所有读取，缓存不能恢复 | 原件、页文字、版本、run、审核状态、历史、草稿、快照、handoff、export 均 404 且 private/no-store；前端 404 后移除已加载编辑器及内存输入 | 真实登录页面／多浏览器联调 |
| 删除与 execute／export 并发，没有数据复活；成本结算 | 在模型响应返回后、文本导出渲染中注入删除；结果和导出拒绝，normalized result 不落库；DeepSeek Adapter 的 Mock HTTP usage 仍结算为 2 micro-USD，并保留去标识化统计；失联任务恢复不再调用模型 | PostgreSQL 独立实例竞争、真实供应商返回 |
| Blob／DB 失败持久重试；上限告警 | 本地存储删除失败保持 quota；第十次失败 exhausted；重置并重跑可完成；图清理 DB 故障整笔回滚；对象已删除但配额提交失败仍保留预留，lease 后重试只释放一次 | 真实 Blob 故障与平台通知 |
| 实际删除与每日维护测试，超期不依赖用户访问 | 本地私有文件实际消失；7 天包、24 小时孤立上传与历史保留边界；普通 session／错误 Bearer 被拒；脚本十批、失败退出、不泄漏密钥、不跟随重定向已测试 | **真实 Private Blob 和线上每日／手动 Actions 尚未执行** |
| 删除账号不能被迟到支付恢复 | 全部会话失效、会员撤销、完整账号清理；90 天最小支付去重／过期清理；同 GitHub 再注册拿新 UUID 且无旧会员；签名 Fake 事件在清理前后均不增发权益 | 真实 Stripe 与 PostgreSQL 并发验收 |

## 验证命令与结果

- `src/backend/.venv/bin/python -m pytest -q src/backend/tests/referral_review/test_lifecycle.py src/backend/tests/referral_review/test_billing.py`：**32 passed**；之后新增“对象删除成功但 DB 提交失败”用例，单独执行 **1 passed**。
- `src/backend/.venv/bin/python -m pytest -q src/backend/tests/referral_review/test_maintenance_runner.py src/backend/tests/referral_review/test_lifecycle_pg.py`：**4 passed, 1 skipped**；缺少 `TEST_DATABASE_URL`，不把 SQLite 当 PostgreSQL 并发验收。
- 前端 `AccountDeletion / IdentityPanel / Workspace` 相关测试首次 **36 passed**；补充 404 清除内容用例后 `Workspace.test.tsx` 匹配三个测试文件，**25 passed**。均为 Jest／DOM 测试，没有浏览器模型请求。
- `pnpm --dir src/frontend lint`：0 errors，28 条现有旧页面警告；`build`、`typecheck`：通过。
- `python3 scripts/referral_contracts.py --check`：通过；`git diff --check`：通过。
- 后端全目录首次回归：**434 passed, 69 skipped, 2 failed**。两项失败分别是新增 `/account` 后需要更新已有 OpenAPI 路径集合断言，以及旧入口测试读取本地 PostgreSQL 配置但环境未安装其 psycopg 驱动。已更新路径断言，按仓库 CI 隔离配置执行 `PYTHON_DOTENV_DISABLED=1 DATABASE_URL=sqlite:///:memory: RR_ENVIRONMENT=test REAL_AI_ENABLED=false src/backend/.venv/bin/python -m pytest -q src/backend/tests/referral_review/test_foundation.py src/backend/tests/referral_review/test_lifecycle.py`：**46 passed**（含最新全部 13 项生命周期用例和原两项失败用例）。没有把跳过的 PostgreSQL 验收算作通过；未再次重复全目录执行。

首次误用旧 `src/backend/venv` 时因缺 cryptography 无法收集测试；随后使用项目当前锁定依赖环境 `src/backend/.venv`，未修改系统 Python 或安装新依赖。

## 限制与后续验收

真实 Private Blob、隔离 PostgreSQL、GitHub Actions secrets／调度／失败通知均未验证；没有自动启动／停止本地服务、发起浏览器 AI 测试、调用真实模型或部署。备份及平台日志的实际保留配置尚未取得，说明和手动检查清单在 LIFECYCLE 中；未写未经核实的供应商保留天数。24 小时是清理目标，不是外部平台 SLA，失败队列不能当成“已彻底删除”。

下一可独立实施项：MT-19 可观测性、运行手册和 readiness；上述外部缺项仍属于原工单验收，不因转到下一票而消失。
