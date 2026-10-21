# MT-07 离线实现与验收记录

日期：2026-10-21。状态：后端代码已实施，工单仍为 `TODO`；MT-02／04／06 前置验收未完成，真实 PostgreSQL 并发验证也未执行。

实现：`POST/GET /packets` 创建及稳定 cursor 分页，创建必须显式确认合成资料；账号行锁保护 10 个未删除、未到期资料包限额。资料包详情和标题更新只使用会话归属；到期与 tombstone 立即对读写隐藏。`POST /packets/{pid}/revisions` 对 expected_revision 作事务内比较，校验文件归属、ready 状态、重复成员和合计页数／文字长度；新集合产生新的 manifest，旧版本和页内容不改写。提交最后一份文件的移除也产生空集合历史版本。`GET` 可读取旧版本及其 derived `is_current`。写入接口使用归属范围的 `Idempotency-Key`。

服务端 `rr_packet_drafts` 仅存候选 document ID、最近位置枚举、基础版本和草稿版本；不存患者原文，也不把原文放入 URL／浏览器本地存储。登出后同账号重新登录，使用只含 packet ID 的回跳路径恢复草稿。`DELETE` 立即写 tombstone 和持久 packet cleanup intent，物理删除由 MT-18 负责。

测试使用真实签名会话、SQLite 事务和合成文字上传，覆盖创建确认／配额、分页、越权、幂等、版本冲突、替换与清空历史、草稿恢复、删除屏蔽和待清理任务。PostgreSQL 对应测试在独立 `TEST_DATABASE_URL` 缺失时明确跳过；SQLite 不能代替跨实例行锁证据。MT-14 工作区 UI 与支付页面尚未实现，因此浏览器刷新及支付回跳的端到端验收留待对应工单。不调用模型或自动在浏览器发送 AI 对话。

本地验证：后端完整 `DATABASE_URL=sqlite:///:memory: .venv/bin/python -m pytest -q tests/referral_review` 为 211 passed、32 skipped（主要为真实 PostgreSQL）；前端 `pnpm test --runInBand` 为 24 passed，`pnpm typecheck` 和 `pnpm build` 通过。`pnpm lint` 无错误，保留 28 项旧页面警告。契约生成后漂移检查、后端锁文件检查和 `git diff --check` 通过。`rr_0002 → rr_0003` 数据保留用例在 SQLite 通过、PostgreSQL 跳过；新迁移的 PostgreSQL SQL 离线编译通过。未启动服务、未部署或执行生产迁移。
