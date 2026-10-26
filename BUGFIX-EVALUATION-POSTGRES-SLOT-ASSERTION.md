# PostgreSQL 调度验收按持有者校验执行槽

日期：2026-10-26。

首轮事务调度 CI 的 PostgreSQL job 为 297 passed／1 failed。失败的是新测试读取未排序的槽位查询后，假定第一行就是占用行；PostgreSQL 对更新后的行不保证这种返回顺序。派发标记和费用预留已经可见，其他并发／回滚用例通过。

修正为检查恰好一个槽被占用、其持有者等于本次 attempt，且租约仍有效。该断言仍在 Adapter 调用之前，通过另一个数据库连接执行，继续验证完整事务已提交；没有放宽槽位数量、归属或时限要求，也没有修改生产调度逻辑。

对应测试：`test_commit_before_transport_single_dispatch_and_keyless_replay`，同时运行 SQLite／PostgreSQL。最终 CI 证据见 [MT-20 实施记录](docs/referral-review/MT-20-EVIDENCE.md)。
