# 派发前重新核对执行槽归属

日期：2026-10-26。关联 MT-10／11／20。

## 问题与影响

工作区 `_dispatch` 原先验证 run 状态、run lease、会员和费用预留，但没有重新验证账号／全站执行槽。槽位租约与 run 租约在不同语句中取得时间，边界时刻可能先失去槽位而 run lease 仍有效；恢复或清理后槽位已释放也应拒绝旧请求派发。

## 修复

新增 `usage/slots.py` 统一全站两槽的加锁和可用性判定。工作区在写入派发标记之前，锁定并验证账号槽与全站槽仍属于当前 run、租约未过期，且同编号没有有效评估占用。检查和标记提交处于同一事务；失败返回 RUN_ACTIVE，不写派发标记。

MT-20 评估同时通过该模块领取槽位，`rr_0008` 仅追加带外键的 evaluation_slots。现有 workspace global 行仍是共享锁和槽位编号，旧租约原样保留。终态释放必须匹配持有者 ID，迟到结果不能释放已分配给新任务的槽位；unknown 等待期间租约到期只允许复用应用执行容量，不释放未知费用，也不宣称远端供应商任务已停止。

## 验证与范围

`test_runs.py::test_dispatch_rechecks_live_slot_ownership` 在 run lease 仍有效时分别将账号／全站槽标记过期或释放，确认 `_dispatch` 拒绝、派发标记为空、Fake Adapter 调用次数为零。`test_evaluation_slots.py` 覆盖混合占用、租约到期、迟到结算和事务回滚；PostgreSQL 混合进程竞争由 `test_evaluation_ledger_pg.py` 验证。实际执行结果见 [MT-20 证据](docs/referral-review/MT-20-EVIDENCE.md)。

没有自动浏览器 AI 操作、真实模型调用或生产迁移。真实评估 CLI 仍关闭，操作者授权／合成输入绑定及录制恢复仍待集成。
