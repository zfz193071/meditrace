# MT-02 数据持久化验收记录

日期：2026-10-20。状态：**BLOCKED，等待真实 PostgreSQL 迁移与并发验收**。用户确认按没有测试库处理，本次没有连接生产库、启动本地服务、运行真实 AI 或部署。SQLite 结果不用于宣布 PostgreSQL 的锁与事务正确。

## 已实现

- SQLAlchemy Core 33 张领域／关联表，独立 rr_ metadata 和 Alembic 版本表；覆盖身份、资料、不可变版本、运行、证据、审核、支付事件、额度、预算、并发槽、存储预留、限流、幂等、审计和清理。
- 冻结追加迁移 `rr_0001`，迁移版本 allowlist、重复执行保护、失败回滚和禁止数据 downgrade。未知／无版本的已有 rr_ 结构拒绝自动接管。
- 复合外键确保同包成员、同 run/revision 的来源证据和事实关联；支付事件、会员来源订单、批次费用预留、pending Checkout 和活跃同输入批次有唯一约束。
- 默认不连接数据库的 engine factory、事务单元、owner-scoped revision/review CAS、证据源校验与原子费用预留；固定加锁顺序，预算桶按 key 排序。
- 只处理本次随机 schema 的测试初始化／清理工具；没有 TEST_DATABASE_URL 时明确 skip，绝不回退到 DATABASE_URL。
- CI 独立 PostgreSQL 17 job，覆盖相同迁移约束测试及 3 个双连接竞争用例。工作流已编写，尚无实际运行结果。

文件入口：`src/backend/referral_review/persistence/`、`src/backend/migrations_referral/`、`test_persistence.py`、`test_pg_concurrency.py`、`.github/workflows/referral-foundation.yml`。操作和限制见 [迁移手册](MIGRATIONS.md)。

## 已执行的验证

| 检查 | 实际结果 |
| --- | --- |
| 冻结依赖安装 | Alembic 1.20.0、Mako 1.4.3、MarkupSafe 3.0.4 加入 uv.lock 并安装 |
| `PYTHON_DOTENV_DISABLED=1 DATABASE_URL=sqlite:///:memory: src/backend/.venv/bin/python -m pytest -q src/backend/tests/referral_review src/backend/test_database_deployment.py` | **74 passed / 31 skipped / 5 warnings** |
| 新持久化用例贡献 | 35 项通过；24 项 PostgreSQL 迁移／约束用例和 3 项 PostgreSQL 竞争用例未执行 |
| 旧 PostgreSQL 用例 | 另有 4 项因缺 TEST_DATABASE_URL 跳过；没有访问既有线上数据库 |
| PostgreSQL DDL 编译 | 初始迁移可生成 33 个 CREATE TABLE、带时区时间和保护触发器 SQL；没有旧表或 DROP TABLE；仅编译，不是 PostgreSQL 执行 |
| `python3 scripts/test_deploy_workflow.py` | **10 passed**，未改部署脚本／未发真实发布请求 |
| `python3 scripts/referral_contracts.py --check` | 通过，公共 OpenAPI／TS 无变化 |
| `UV=src/backend/venv/bin/uv UV_CACHE_DIR=.uv-cache python3 scripts/check_backend_lock.py` | 通过，锁文件与运行 requirements 一致 |
| `src/backend/.venv/bin/pip-audit -r src/backend/requirements.txt --no-deps --disable-pip` | 无已知漏洞 |
| 迁移和测试 schema CLI `--help`、CI YAML 解析、`git diff --check` | 通过 |

测试仍有 MT-01 已记录的 Starlette httpx 兼容路径及旧 SQLAlchemy／Pydantic／startup 弃用警告。本次没有修改前端，不重复宣称本轮执行了前端 build；MT-01 的构建证据保留。

## 已验证的失败路径

- SQLite 空库与含旧 conversations/messages 的数据库均成功追加迁移；相同迁移再次运行不重复建表，旧行逐值相等。
- 在创建第 4 张表时注入失败，已创建的新表及版本记录全部回滚，旧表及行保持；SQLite 显式 BEGIN，避免驱动默认 DDL 自动提交行为。
- downgrade 拒绝且数据保留；未知迁移目标、未来 schema 版本、未受管理的 rr_ 表均拒绝。
- 非法 state/mode、live 支付环境、超额会员 reserved_units 被拒绝；重复事件／订单权益／费用预留／pending Checkout／同输入活跃运行被拒绝。
- 跨包成员、未纳入运行版本的文档、跨运行 Fact/Evidence、错误清单版本被复合外键拒绝。
- 过期／越权资料无法保存新版本；过期 revision 或 review CAS 失败不覆写现有版本。
- Unicode 摘录与来源页精确匹配；错误摘录／错误身份被拒绝。原文页、ready 文档来源及版本记录不可 UPDATE。
- 后一个预算桶容量不足时，先前桶和会员预留全部回滚，没有残缺账本；整笔事务异常也回滚所有领域写入。
- 无测试库时不使用生产连接；非随机测试 schema 名、错误 receipt／数据库指纹在连接或删除前被拒绝。
- 非整数费用（包括 bool、float、字符串）在查询或写入前被拒绝；测试 schema ownership receipt 在远程 DDL 前持久化，连接异常仍有核对依据。

## 尚待验收

配置独立 TEST_DATABASE_URL，或在获得推送权限后让新增 CI job 使用临时数据库执行测试。必须实际得到以下结果后才能关闭 MT-02：

1. PostgreSQL 新库／旧表升级、失败 DDL 回滚、重复迁移、复合外键、触发器和隔离 schema 清理均通过。
2. 两个真实 PostgreSQL 事务同时保存同一 expected_revision：一个成功，一个冲突，无 lost update。
3. 两个事务竞争最后一个会员额度：只有一个预留成功。
4. 两个账号以相反输入顺序预留相同日／月预算：内部按 key 排序，只有一个成功，失败方无残留预留。

以上测试代码已实现，但未执行。schema 清理工具的实际 PostgreSQL 往返也随这些测试验收；本次没有创建或删除任何 PostgreSQL schema。原文文件上传、完整会员结算、业务 HTTP、真实 readiness 与清理作业仍按各后续工单实现。

## 提交状态

MT-01 已提交为 `e1d64b0`（本地，未推送）。本记录所述 MT-02 改动尚未提交；既有 `TASK-PREVISIT-SUMMARY.md` 未修改、未纳入提交。
