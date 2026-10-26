# 补齐 PostgreSQL CI 验证范围

日期：2026-10-26。归属：MT-02、MT-10、MT-11、MT-12、MT-22。

## 问题

原 PostgreSQL job 只选择持久化和基础双事务测试。后续新增的费用账本、审核快照、跨进程费用竞争和同批次派发测试没有被该 job 收集；普通 foundation job 未配置 TEST_DATABASE_URL，因此相关 PostgreSQL 用例始终跳过。

## 修复

扩展现有临时 PostgreSQL 17 job，包含上述四个现有测试文件，并生成 JUnit 结果。追加检查要求确实收集 PostgreSQL 参数化用例且没有 skipped，避免环境缺失时以绿色 job 冒充数据库验收。job 最长运行 15 分钟。

所有数据仍在测试专属随机 schema；模型使用 Fake Adapter／合成用量，不调用真实供应商、不使用生产数据库。实际 CI 结果在 MT-02 及后续工单证据中记录。

## 退役测试导致整个流水线提前失败

首轮 CI 的 PostgreSQL job 成功，但 foundation 在单独执行 `src/backend/test_database_deployment.py` 时退出 5。该文件在 MT-21 已使用模块级 skip 退役，单独运行没有可执行用例。本地相同命令复现 `1 skipped in 0.05s`、退出 5，与 [CI 失败日志](https://github.com/zfz193071/meditrace/actions/runs/40255134453) 一致。

移除该过时的独立执行步骤；不移除历史文件，不吞掉 pytest 错误。新 `/api/v1` 启动、readiness 和旧接口退役行为仍由完整 referral suite 中的 `test_retired_api.py`、`test_operations.py` 覆盖，持久化由临时 PostgreSQL job 覆盖。此问题已有单命令确定复现和 CI 日志，不需要额外猜测或运行旧业务服务。

扩展数据库 job 在提交 `14519d0` 的 [CI 运行](https://github.com/zfz193071/meditrace/actions/runs/40255313217/job/121355790255) 中通过：**133 passed，零 skipped，32.48 秒**，包含 SQLite／PostgreSQL 参数化用例及真实 PostgreSQL 跨进程竞争；这不是 133 项全部为 PostgreSQL。完整 foundation 结果待移除过时步骤后验证。
