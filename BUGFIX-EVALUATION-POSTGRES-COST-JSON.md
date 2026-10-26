# PostgreSQL 评估费用汇总 JSON 输出

2026-10-26，MT-20 隔离恢复 CLI。

首次 [PostgreSQL 17 CI](https://github.com/zfz193071/meditrace/actions/runs/40289119119/job/121459747618) 执行 333 项，332 passed／1 failed。CLI 的真实隔离库预览在 JSON 输出时报错；数据库只读保护、迁移和账本测试均通过。原因是 PostgreSQL 的 `SUM(bigint)` 返回 numeric，驱动将其表示为 Decimal；即使没有调整记录，coalesce 后的 0 也是 Decimal。SQLite 返回 int，因此本机未复现。

在领域数据边界把整数列的汇总无损转换为 Python int：`coordinator.attempts` 对外返回整数 micro-USD，`EvaluationLedger.adjust` 的差额也保持整数。没有使用浮点数或通用 JSON default=str，因此没有精度损失，也没有把金额字段悄悄变成字符串。原查询、原账和数据库预算约束保持不变。

原有 PostgreSQL CLI 集成测试继续覆盖空调整预览、实际恢复和重复恢复；晚到非零调整的测试新增 JSON 往返和整数类型断言，账本也验证新建差额类型。最终结果见 [MT-20 证据](docs/referral-review/MT-20-EVIDENCE.md)。
