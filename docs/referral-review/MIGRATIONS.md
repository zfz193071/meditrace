# Referral Review 数据迁移手册

适用：MT-02 新领域表、MT-06 解析字段、MT-07 草稿元数据、MT-10 费用账本、MT-12 审核历史及 MT-17 支付恢复。初始版本 `rr_0001` 创建 33 张 `rr_` 业务／关联表；`rr_0002` 为 Document 加入解析字段；`rr_0003` 增加 Packet 的合成资料确认时间和独立的非内容草稿表。`rr_0004` 追加价格快照、共享熔断和费用调整表。`rr_0005` 追加不可覆盖的 review_events，保留每次人工处理、草稿修改和确认；保留已有快照，不为旧数据伪造历史。`rr_0006` 追加 checkout_details，保存订单回跳路径、Checkout URL 和固定过期时间，不保存支付个人信息。使用独立 `rr_alembic_version`，旧 conversations、messages 等表不参与迁移。真实 PostgreSQL 验收尚未执行；完成前不要把本迁移用于生产发布。

## 数据模型与事务接口

实现位于 `src/backend/referral_review/persistence/`，采用 SQLAlchemy Core 模型而非再给每张表加 CRUD 包装。模块接口集中处理调用方容易遗漏的归属、版本、证据和账本约束：

| 文件或操作 | 保证与失败行为 |
| --- | --- |
| `models.py` | 独立 metadata、UUID、UTC 时间、外键、唯一约束、状态 CHECK 和查询索引 |
| `database.create_engine(url)` | 必须显式提供连接；不读取 .env、无生产默认连接、无建表；PostgreSQL 使用 NullPool，SQLite 内存库用 StaticPool 仅供顺序测试 |
| `database.transaction(engine)` | 整个事务成功提交，任意异常回滚；不自动重试，不包含外部服务调用 |
| `repository.save_revision` | 归属／删除／到期／ready 校验，expected_revision CAS，生成固定 manifest 和版本成员；失败回滚该操作的 savepoint |
| `repository.advance_review_version` | 同时核对 expected_revision 与 expected_review_version；审核内容追加须由调用方置于同一事务 |
| `repository.add_evidence` | 只接受当前 run 的 revision 成员、精确页、hash 和 Unicode code-point 切片；不创建模型结果 |
| `repository.reserve_usage` | 成员与预算锁定、余额条件更新、单 run 唯一预留、记录原始预算桶；任一步失败回滚全部预留 |
| `migrations.require_current_schema` | 只读检查版本；缺失、未知版本失败，不自动修库 |

仓储要求调用方先开启事务，接收的 owner_id 必须来自已认证会话，不是用户请求参数。这些操作不是业务授权入口：登录在 MT-04，上传／解析在 MT-05/06，完整资料版本 API 与幂等在 MT-07，模型结果批量持久化在 MT-08/11，邀请／会员／日月预算选择／限流／并发槽／结算在 MT-10，审核确认在 MT-12。本工单不注册新的业务 HTTP 路由，也不会开启真实模型或付款。

### 数据关系

`revision_documents` 冗余 packet_id，通过两组复合外键分别约束 Revision 与 Document 必须属于同包。Evidence 冗余 revision_id，与 run、revision 成员、页号和 text_hash 建复合外键，不能引用另一次运行或未纳入版本的文件。Fact、Finding、Resolution 的证据等关联使用正规化关联表，而不是把关系仅存在 JSON UUID 数组中。Finding 的 checklist_version 与 run 相同。

新增 `rr_usage_buckets` 记录预留所属的 UTC 日／月桶，避免跨午夜结算到错的桶；`rr_storage_buckets` 为全站／账号存储共享预留提供后续基础。会员与订单可在清理流程中去标识化，活跃费用预留仍要求 run 和 owner 非空；物理删除与结算流程属于 MT-18／10，不自动级联删除账本。

原文页、资料版本、版本成员、事实、证据、事项、人工处理、审核快照及其关系不允许 UPDATE。已 ready Document 的来源内容字段不可改写，deleted_at 仍可标记删除。DELETE 不由这些触发器禁用，以便 MT-18 在归属／保留规则验证后按外键顺序清理。应用只通过保存新版本改变资料；后续模块不能通过直接修改关联表绕过该接口。

### 加锁与费用

所有新增写路径遵守统一顺序：user → packet → run → order → membership → 按 key 排序的 budget → 按 scope/number 排序的 concurrency slot。只需要后半部分锁时可以跳过前面，但拿到后面的锁后不能再申请更早的锁。数据库事务之外才允许调用模型、Blob 或 Stripe。

金额为整数 micro-USD。预留使用带余额条件的 UPDATE，即使多个账号竞争同一预算桶也必须成功扣住余额才写账本。实际供应商支出可能异常超过原估算，因此 budget 的非负 CHECK 不把真实 spent 强行限制在 limit 内；后续 MT-10 必须记录异常并关闭新真实任务，不能为了满足 CHECK 丢弃已经发生的费用。

## 显式追加迁移

冻结迁移文件：`src/backend/migrations_referral/versions/rr_0001_create_isolated_referral_domain.py`；MT-06 追加 `rr_0002_document_parse_details.py`，MT-07 追加 `rr_0003_packet_drafts.py`，MT-10 追加 `rr_0004_usage_ledger.py`，MT-12 追加 `rr_0005_review_history.py`。已应用的版本不能改写，后续变更新增 revision，并更新审查 allowlist／版本检查；不对旧迁移执行自动 downgrade。

应用启动不导入该迁移文件、不建新表。MT-21 已移除原 main.py 的旧启动建表逻辑，旧数据库数据未修改。MT-19 readiness 对数据库／迁移／清单执行只读检查，未迁移时返回 503。

迁移命令在 `src/backend` 下用 `./.venv/bin/python` 执行。默认只读取版本，必须给出 `--apply --target rr_0006` 才升级到当前版本；已有 `rr_0001`／`rr_0002`／`rr_0003`／`rr_0004` 数据库可追加升级。`upgrade` 共享调用方事务；PostgreSQL 额外获取事务级 advisory lock，防止同库同时执行两个部署迁移。未知版本或没有版本记录但已有 rr_ 表时直接拒绝，不猜测／接管现有结构。

## 独立测试库与清理

当前没有 TEST_DATABASE_URL，按用户要求不使用生产 DATABASE_URL 代替。可以选择：

1. 后续在 GitHub Actions 运行 `postgres-persistence` job。它启动自己的临时 PostgreSQL 17 服务，不需要 Neon 凭据；本次只添加了工作流，没有推送或执行远程 CI。
2. 开发者提供独立 PostgreSQL 数据库，把连接串配置在终端的 TEST_DATABASE_URL 中。不要把连接串写进聊天、命令行参数或提交文件；测试代码不读取 .env 作为隐式连接来源。

自动测试会为每个用例生成 `rr_test_` 加 32 位随机十六进制值的 schema，设置独立 search_path（没有 public 回退），写入随机 ownership marker。结束时只在 schema 名、数据库指纹和随机 marker 全部匹配后删除本次 schema。失败的清理会让测试失败，不会尝试删除 public 或其他 schema。

```bash
# 仓库根目录；预先在终端安全配置 TEST_DATABASE_URL
PYTHON_DOTENV_DISABLED=1 src/backend/.venv/bin/python -m pytest -q \
  src/backend/tests/referral_review/test_persistence.py \
  src/backend/tests/referral_review/test_pg_concurrency.py
```

如果需要单独查看迁移后的 schema，提供了显式初始化与清理工具。以下在 `src/backend` 执行；先确认 receipt 文件路径未被使用。把命令中的 `rr_test_REPLACE_WITH_RECEIPT_VALUE` 替换为实际 receipt.schema，不能替换成 public／用户 schema：

```bash
./.venv/bin/python -m referral_review.persistence.test_database create \
  --receipt /tmp/meditrace-test-schema.json

./.venv/bin/python -m referral_review.persistence.migrate \
  --database-env TEST_DATABASE_URL --schema rr_test_REPLACE_WITH_RECEIPT_VALUE \
  --target rr_0006 --apply

# 重复执行相同命令仅核对版本，不重复创建表。
# 完成检查后，仅删除该 receipt 对应的临时 schema；其中测试数据不可恢复。
./.venv/bin/python -m referral_review.persistence.test_database drop \
  --receipt /tmp/meditrace-test-schema.json \
  --confirm-schema rr_test_REPLACE_WITH_RECEIPT_VALUE
```

receipt 只含随机 schema、marker 和不含密码的数据库标识指纹，权限为 0600；独占创建，不覆盖已有 receipt，并在发出数据库 DDL 前写入磁盘，以便提交确认丢失时核对。保留它直到确认清理完成。若创建失败，先核对数据库操作结果；清理工具遇到缺失／不匹配 marker 一律停止，不提供 force-drop。

## 生产迁移与应用回滚

只有 PostgreSQL 用例全部通过、迁移文件完成审查、备份／恢复条件确认且用户授权发布后，才执行以下生产步骤；本工单没有执行它们：

```bash
# src/backend；DATABASE_URL 由安全环境注入
./.venv/bin/python -m referral_review.persistence.migrate --database-env DATABASE_URL
./.venv/bin/python -m referral_review.persistence.migrate \
  --database-env DATABASE_URL --target rr_0006 --apply --confirm-production
```

第二条命令仍只执行 allowlist 的追加版本，不会运行旧 migrations 目录中的 SQL。事务内 SQL 失败回滚；如果连接在提交确认时丢失，先重新只读检查版本，不假定服务端必然回滚。未知状态停止后人工检查，禁止自动 stamp 修饰失败。成功后应用回滚仅切回已封闭旧公开接口的兼容代码，不能删除新表／新数据。Alembic downgrade 明确拒绝执行。MT-21 已将 `deploy-vercel.sh --migrate` 接入审核过的 `rr_` revision allowlist；真实 PostgreSQL 与发布验证仍属 MT-24 门槛。

实现依据：共享显式事务采用 [Alembic connection sharing](https://alembic.sqlalchemy.org/en/latest/cookbook.html#sharing-a-connection-across-one-or-more-programmatic-migration-commands)；跨行／跨表约束使用外键和唯一键，而不是依赖跨表 CHECK，符合 [PostgreSQL constraints 文档](https://www.postgresql.org/docs/current/ddl-constraints.html)。这些依据不替代本项目尚待执行的 PostgreSQL 集成测试。
