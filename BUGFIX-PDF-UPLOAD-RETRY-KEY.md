# PDF 上传响应丢失后重复导入

日期：2026-10-27。所属工单：MT-14／MT-22，场景 Q09／Q11。

## 问题与复现

后端已经保存 PDF，但浏览器未收到成功响应时，用户重新选择同一文件。原 `PacketWorkspace.uploadFiles` 每次调用 `operationKey()`，因此后端将重试视为新的上传，可能重复保存原件并占用文件名额。文件上传不调用模型，此问题不代表已发生重复模型费用。

新增前端回归先在原代码运行，两个用例均失败：同内容文件重新选择后 key 不一致；同名、同大小文件在更换内容后再选择原内容，也无法复用原 key。

## 修复

`PacketWorkspace.tsx` 在大小／扩展名检查后计算文件字节的 SHA-256，使用 packet ID、NFC 文件名和摘要标识一次上传。组件内存保存其随机幂等 key；重新选择同一内容时复用，内容变化时新建。文件修改时间不作为内容依据，避免复制文件或重新选择产生无意义的新请求。

保留顺序上传、单次操作锁、已有加载及错误处理；不自动重试上传，不启动模型。hash／key 仅在组件内存中，不写 localStorage、URL 或日志。真实文件字节不放入索引。

## 验证

- 新增测试在原实现 **2 failed**，修复后工作区测试 **15 passed**。
- 回归读取实际 File 字节并用 Node Web Crypto 运算，而非固定 hash mock；验证响应丢失后重新选择的新 File 对象复用 key，以及同名同大小、不同内容不会错误合并。
- `pnpm --dir src/frontend typecheck` 通过。
- 受影响组件和测试的 ESLint 检查通过。
- 后端 PDF 重放集成验证同 key／字节只返回原文档，内容改变返回 409，存储原件和业务状态不变；详见 [MT-22](docs/referral-review/tickets/MT-22.md)。
- 修复提交 `08aba8e` 的[完整 CI 40433418902](https://github.com/zfz193071/meditrace/actions/runs/40433418902) 两个 job 全通过：前端 15 suites／71 tests，build／typecheck／lint、前后端依赖审计通过；普通后端 913 passed／179 skipped，独立 PostgreSQL job 384 passed／0 skipped。未启动／停止服务，未进行浏览器 AI 测试或生产发布。

## 边界

索引仅在当前工作区组件生命周期内有效。完整页面刷新或退出后不持久化文件或请求标识，也不会恢复任何自动上传；用户应查看已保存的资料再操作。错误响应仍按原有规则提示读取保存状态；不会在幂等冲突或未知结果时自动换新 key 绕过后端校验。真实 Private Blob 故障往返仍待外部验收。
