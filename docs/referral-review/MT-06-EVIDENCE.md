# MT-06 离线实现与验收记录

日期：2026-10-21。状态：代码已实施，工单仍为 `TODO`；MT-05 尚未完成真实 Private Blob／PostgreSQL 验收，不能关闭前置依赖。

实现：`text-v1` 将 CRLF／CR 统一为 LF，再做 NFC；offset 是 Unicode code point。PDF 由固定的 pypdf 6.21.1 子进程提取，20 秒墙钟上限、18 秒 CPU 上限、最多 25 页、每页 12,000 code point、每文件 30,000 code point、每页内容流 1 MB、子进程响应 200 KB。Linux 使用 512 MB 地址空间上限；macOS 拒绝该 rlimit 时依靠解压、内容流、CPU、墙钟和响应边界。解析失败保存 `rejected`、错误代码和可用的页号；原件和实际字节配额保持已结算。页面 API 仅对归属者开放，证据只可引用 ready 文档的 ready 页和精确 hash／code point 切片。

逐项验证：合成语料覆盖正常双页、扫描页、损坏、加密、26 页、真正空白页、压缩膨胀内容流；超时测试验证只终止所建子进程。Python／TypeScript 共用 `fixtures/referral-review/offsets-golden.json`，覆盖中文、emoji、组合字符、换行和重复短句消歧。上传集成测试覆盖逐页查询、错误页、包文字限额、幂等、删除／过期权限、存储失败补偿。所有测试不调用模型，也不自动在浏览器发起 AI 会话。

待验收：真实 PostgreSQL 并发与 `rr_0001 → rr_0002` 升级、生产 Private Blob。真实环境未执行迁移或部署；旧 `text-v1` 页不会被新解析器重写。错误页有提取出的部分文字时也不会被当作可核对的正常来源。

离线命令结果：后端全套 `DATABASE_URL=sqlite:///:memory: .venv/bin/python -m pytest -q tests/referral_review` 为 201 passed、30 skipped（PostgreSQL 未配置）；新增 SQLite `rr_0001 → rr_0002` 测试与 ready 不可变检查另跑通过，PostgreSQL 对应用例跳过。前端 `pnpm test --runInBand` 为 24 passed；`pnpm typecheck`、`pnpm build`、契约漂移检查、后端锁文件检查均通过。`pnpm lint` 无错误，有 28 项旧页面警告。`pip-audit` 对生成的生产 requirements 报告无已知漏洞。混合图像／文字页、空白页、压缩内容流和权限路径的新增定向测试为 38 passed。
