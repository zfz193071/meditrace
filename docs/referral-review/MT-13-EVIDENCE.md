# MT-13 交接摘要与导出验收记录

日期：2026-10-21。导出后端、统一摘要模型、可复用前端组件和离线 PDF 样例已实施。前置 MT-12 未完成全部验收，工单保持 `TODO`；完整工作区及示例页面入口由 MT-15／16 集成，不把独立组件测试当成页面端到端验收。

## 交付

`referral_review/handoff/` 将确认快照投影为 HandoffView。按身份／转诊详情、转诊原因、用药、过敏、报告／附件、未解决项、处理及修正、人工补充、来源索引、确认版本分节。事实保留原始陈述及来源，人工修正作为明确标记的覆盖层呈现，未解决身份不合并；人工补充不伪造引文。缺失字段不推断成“没有”。

GET `/packets/{packet_id}/snapshots/{snapshot_id}/handoff` 返回摘要模型，GET 同路径 `/export?format=pdf|txt` 返回下载。屏幕组件、复制文本、UTF-8 txt、服务端 PDF 使用同一模型；JSON、OpenAPI 与 TypeScript 类型由 Pydantic 生成。确认内容来自固定 payload，并验证 hash；不读取当前草稿替换历史内容。

导出前验证账号／资料包／快照归属、删除及到期，渲染结束后再次验证访问权。渲染期间从当前变为历史会返回冲突，要求重试，避免错误标为当前版本。Historical revision 是派生提示，PDF 每页重复显示；存储 payload/hash 不改变。

无需会员或剩余 AI 额度；导出前调用共享账号限流（每分钟 10 次、每小时 60 次），不创建费用预留。不调用模型、Stripe、IPFS 或区块链，也不保存用户导出到公共目录。响应 private/no-store、attachment、安全文件名、nosniff 和 sandbox。仓库内 output/pdf 仅包含脚本生成的公开合成 QA 材料。

## PDF 与 Unicode

fpdf2 使用已锁定依赖，A4、自动分页、重复页眉／页码、章节标题至少保留两行正文空间；正文左对齐，长词可换行，不以一页为目标裁剪。超过 4,000,000 bytes、200 页或 PDF 输入 500,000 字符时明确返回 EXPORT_TOO_LARGE（413），不返回截断成功文件。

嵌入 Source Sans 3 和原有 Source Han Sans SC 的字形子集，字体及完整 OFL 1.1 许可随仓库保存；来源和文件说明见 `src/backend/fonts/README.md`。测试涵盖 José、Łukasz、王明、Ольга、Δημήτρης。缺少字形（如部分 emoji）或需要尚未启用的复杂文字塑形时，PDF 返回 EXPORT_UNSUPPORTED_TEXT（422），完整 UTF-8 文本仍可下载；不把丢字或方框当作成功。

当前 pypdf 对 CJK 字体提取会附加空字符，但 PDF ToUnicode 映射正确；pypdfium2 提取和实际渲染均显示完整中文。Unicode 断言用 pypdfium2，pypdf 用于页数／页脚及英文语义检查，不通过删除原文中的字符掩盖渲染错误。

## 固定示例与前端

`HandoffSummary` 提供摘要、复制、下载文本、浏览器打印／保存 PDF。打印生成转义后的本地 iframe 文档，不发送业务写入；不将来源内容解释为 HTML。`handoff.ts` 另提供工作区的认证读取和服务器下载 URL。

`demo-handoffs.json` 来自公开 dev-01／02／03 固定结果和示意审核记录，使用同一个 Python view model；明确标注 precomputed／illustrative，不伪称真实审核。生成器 `scripts/referral_handoff_samples.py --check-demo` 检查漂移。没有改写冻结的 MT-03 数据集，也未将测试集用于演示。

## 逐页视觉 QA

使用 PDF 技能；环境没有 pdftoppm，使用已锁定的 pypdfium2 渲染为 PNG。输出位于 `output/pdf/`，PNG 证据位于 `output/pdf/qa/`。长稿是 dev-01 的明确标注 QA 变体，增加人工长字段及单独编写的二页合成来源（`handoff-long-source.txt`），不是原始评估案例的质量结论。

| 样例 | 页 | 检查结果 |
| --- | --- | --- |
| short | 1 | 人工模式、缺失字段、五种 Unicode 名称完整；无方框或底部裁剪 |
| short | 2 | 无来源说明、确认版本／时间／hash 完整，页码 2/2 |
| long | 1 | 顶部身份警示、历史提示、两个 DOB 分别保留 |
| long | 2 | 未解决项、人工修正及理由完整；长字段自然分页 |
| long | 3 | 长字段延续，左对齐后无拉大的词间距，无页脚重叠 |
| long | 4 | 最后一个长字段、Unicode 名称、来源第 2 页索引完整 |
| long | 5 | 余下来源、确认版本／时间／hash 完整，页码 5/5 |

最终版共 7 页均已实际查看。正文中跨页延续的长词不被删除；来源索引与正文编号一致。浏览器原生打印对话框尚未在完整页面集成后验收，留给 MT-15／16／22。

## 自动验证

- 后端专项覆盖三种表示一致、修正／理由／未解决项、历史快照不变、缺失字段、Unicode、非登录／越权／删除／到期拒绝、无额度／会员过期仍可导出、共享限流、渲染中删除、超限、未知格式及 hash 损坏。
- 前端覆盖摘要、复制与 Python 文本一致、复制失败、打印 HTML 转义、认证读取、错误体不泄露；固定示例组件操作不调用业务 API。
- 后端全量：`DATABASE_URL=sqlite:///:memory: src/backend/.venv/bin/python -m pytest -q src/backend/tests/referral_review`，**380 passed、68 skipped、4 项既有弃用警告**（805.29 秒）。其中导出专项 15 项通过；跳过的 PostgreSQL 测试不计为通过。
- 前端全量：`pnpm --dir src/frontend test --runInBand`，**7 suites／30 tests passed**，其中新增摘要专项 6 项通过。
- `pnpm --dir src/frontend typecheck`、修改文件 ESLint、`scripts/referral_contracts.py --check`、`scripts/referral_handoff_samples.py --check-demo` 和 `git diff --cached --check` 均通过。
- 未启动／停止服务，未自动浏览器调用 AI，未产生 API 费用。用户已有 `TASK-PREVISIT-SUMMARY.md` 未修改、未提交。
