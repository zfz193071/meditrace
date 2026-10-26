# 补齐 PostgreSQL CI 验证范围

日期：2026-10-26。归属：MT-02、MT-10、MT-11、MT-12、MT-22。

## 问题

原 PostgreSQL job 只选择持久化和基础双事务测试。后续新增的费用账本、审核快照、跨进程费用竞争和同批次派发测试没有被该 job 收集；普通 foundation job 未配置 TEST_DATABASE_URL，因此相关 PostgreSQL 用例始终跳过。

## 修复

扩展现有临时 PostgreSQL 17 job，包含上述四个现有测试文件，并生成 JUnit 结果。追加检查要求确实收集 PostgreSQL 参数化用例且没有 skipped，避免环境缺失时以绿色 job 冒充数据库验收。job 最长运行 15 分钟。

所有数据仍在测试专属随机 schema；模型使用 Fake Adapter／合成用量，不调用真实供应商、不使用生产数据库。实际 CI 结果在 MT-02 及后续工单证据中记录。
