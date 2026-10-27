# 离线测试开关与产品配置前缀冲突

日期：2026-10-27。

新增 Python 网络保护的首版 `ab2809f` 使用 `RR_TEST_NETWORK_GUARD`。
产品配置加载器有意拒绝未知 `RR_` 开关，因此完整回归中的默认 app 创建、
旧 API 退役用例报 `ConfigurationError: Unknown referral configuration option`。
单独的网络探针不创建默认 app，未暴露该冲突。

修正为测试专用的 `MEDITRACE_TEST_NETWORK_GUARD`，同步 conftest、Python
子进程 bootstrap、CI 独立命令和文档。产品配置校验、网络阻断以及真实 AI
授权条件保持原样；没有把测试开关加入生产 Settings。

回归覆盖 `test_offline_network.py`、`test_foundation.py` 和 `test_retired_api.py`；
完整 CI 及实际通过数记录在 [MT-22](docs/referral-review/tickets/MT-22.md)。
首轮失败不计为验收通过，未执行生产部署或真实模型请求。
