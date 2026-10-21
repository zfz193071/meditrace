# Referral 导出限流的 SQLite 写锁

日期：2026-10-21，MT-13 接入导出链路。

`Usage.check_export` 原先使用普通 BEGIN，先读取账号／资料包和窗口计数，再写计数。SQLite 不实现 FOR UPDATE，两个并发请求的读事务同时升级为写事务存在 database locked 风险，可能以服务错误代替稳定的限流结果。

导出计数事务现在在 SQLite 下使用既有 sqlite_immediate 选项，在读之前取得写锁；PostgreSQL 仍使用原行锁与数据库计数，不引入进程内锁。该选项仅用于此短事务，不覆盖 PDF 渲染；会员、预算和执行计费规则未改动。

`test_concurrent_exports_use_persisted_account_limit` 将同一账号计数置为 9，再用两个独立 Handoff 实例同时导出；只允许一个成功，另一个返回 RATE_LIMITED。原有费用及限流测试仍在完整回归范围内。真实 PostgreSQL 竞争依赖独立 TEST_DATABASE_URL，未用 SQLite 结果替代其验收。
