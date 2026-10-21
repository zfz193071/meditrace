# MT-12 人工审核与确认快照验收记录

日期：2026-10-21。后端实现及离线验证已实施；前置 MT-11 尚未完成全部验收，真实 PostgreSQL 竞争未实际运行，工单保持 `TODO`。本票不包含 MT-15 审核页面和 MT-13 导出。

## 交付与边界

`referral_review/reviews/` 提供事项处理、交接草稿读写、确认、历史分页和快照读取。所有写入要求已认证会话、Origin／CSRF、Idempotency-Key；归属／到期／删除检查共用 MT-04／07，越权资源统一 404。无需会员，不调用模型或账本。

resolve／dismiss／defer／reopen 分别追加 resolved／dismissed／unresolved／open。dismiss/defer 必须填写非空理由；记录操作者、时间、审核版本、理由、人工修正和关联证据。人工修正不修改 Fact／Evidence，来源固定标为 `Reviewer supplied`。关联证据不能跨 run，客户端不能传入来源标记伪装成证据。

交接草稿为整份字段映射替换，每次保存追加不可修改的历史事件，并更新当前草稿指针。确认仅使用同 revision/run 的草稿。新批次不继承旧决定或草稿；资料变更后旧 run 不可继续写入，历史仍可读。

assisted 确认要求当前版本 succeeded run 且没有 open。defer 保留未解决状态；身份差异除 resolve 外均在顶部保留 `Identity unresolved`。manual 显式不绑定 run，保留 `Not automatically checked`，所有人工字段仍标明来源，不构造机器事实或评分。

确认将原始结果图、最新处理覆盖层、事项状态、交接字段、资料版本及 manifest hash、确认者和时间固化到 payload，生成 canonical JSON SHA-256。确认本身递增审核版本；确认后再编辑递增新版本，旧快照内容／hash 不变。historical 根据当前资料和审核版本派生，不能写回快照。

## 事务与追加迁移

版本 CAS、人工处理／草稿／快照、历史和幂等记录在同一事务提交；任何一步失败全部回滚。PostgreSQL 遵循 user／session → packet → run 的锁顺序；SQLite 审核写事务显式选择 BEGIN IMMEDIATE，在第一次读之前取得写锁，避免两个 tab 同时读后升级写锁导致 database locked。该选项不改变其他事务默认行为，不用进程内锁冒充多实例保障。

`rr_0005_review_history.py` 仅增加 `rr_review_events`、约束、索引和拒绝 UPDATE 的触发器。既有快照不改写，不对旧表中的记录补造操作者／时间。历史事件按 packet/review_version 唯一，防止一个版本写入两个决定。旧资料／结果／处理／快照继续沿用数据库不可变触发器；删除留给 MT-18 的受控清理。

## 验证

- 审核接口专项覆盖状态转换、理由必填、open 阻止确认、身份警示、人工来源、引用隔离、幂等、分页、越权、CSRF、非成功批次、资料变更、新批次不继承、确认后编辑及快照不变。
- 两线程竞争同版本草稿，以及两个独立 spawn 进程竞争草稿／确认，只有一次提交，另一个为 REVIEW_CONFLICT。
- 故障注入在历史及幂等写入后抛错，验证 resolution／draft／confirmation 各路径的版本、内容和 key 全部回滚。
- 迁移测试验证已有快照 payload 保留、模型与迁移一致、SQLite／PostgreSQL DDL 编译、不可变触发器；PostgreSQL 实测只使用 TEST_DATABASE_URL，没有配置时明确跳过。
- 测试直接种入合成结果图，未调用 Fake 或真实模型；未启动／停止服务、部署或操作浏览器。

最终结果：

- `DATABASE_URL=sqlite:///:memory: src/backend/.venv/bin/python -m pytest -q src/backend/tests/referral_review`：**365 passed、68 skipped、4 项既有弃用警告**。新增审核专项 22 项通过，持久化专项 SQLite 2 项通过、PostgreSQL 2 项跳过；没有 TEST_DATABASE_URL 的测试不计为通过。
- `src/backend/.venv/bin/python scripts/referral_contracts.py --check`：生成契约与 Pydantic 一致，无漂移。
- `pnpm --dir src/frontend typecheck`：通过。本票无页面改动，未重复生产构建。
- `git diff --check`：通过。用户已有的 `TASK-PREVISIT-SUMMARY.md` 保留未修改、未提交。
