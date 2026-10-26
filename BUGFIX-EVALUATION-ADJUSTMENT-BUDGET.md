# 评估费用校正后的预算熔断

2026-10-26，MT-20 晚到费用校正增量的复核补充。

原实现仅在新实际费用超过原预留上界时熔断。如果较低的原结算已经释放预算，并被另一个任务预留，后来向上校正即使不超过原上界，仍可能使 batch 或共享日月桶的「预留 + 已花费」超过预算。仅拒绝后续 reserve 不足以阻止已有预留继续派发。

`EvaluationLedger.adjust` 现在在原有 batch／attempt／全站 control／budget 锁内，照实追加差额并检查 batch cap 和原日月桶限额；超过时以 `ADJUSTMENT_EXCEEDS_BUDGET` 熔断，已有未派发请求也被 dispatch 拒绝。不会撤销已发生费用、删除历史或因后续退款自动解禁。超过原预留上界的原有原因码保持不变。

回归分别复现 batch 和全站预算被重用：原预留 3 micro-USD、结算 2、新预留 3，再把原结算校正为 3；总占用 6 超过限额 5，原记录保持不变，待派发任务被拒绝。测试在 SQLite／隔离 PostgreSQL 参数化执行，结果见 [MT-20 证据](docs/referral-review/MT-20-EVIDENCE.md)。无生产迁移或模型调用。
