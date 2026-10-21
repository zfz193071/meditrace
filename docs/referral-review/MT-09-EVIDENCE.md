# MT-09 确定性清单离线验收记录

日期：2026-10-21。规则实现与离线验证已完成，前置 MT-08 未完成全部验收，工单保持 `TODO`。本记录不代表真实模型或完整产品通过验收。

## 交付及接口

`src/backend/referral_review/checklist/` 提供纯函数 `evaluate(extraction, manifest, checklist_version, candidates=()) -> ChecklistEvaluation`。不读文件、数据库或网络，不调用模型，不修改输入。调用方传入已验证提取事实及完整不可变版本 manifest；MT-11 负责从持久层加载真实版本和确认归属，不能把客户端自行选取的部分文档当成完整 manifest。

manifest 包含文档 ID、标题、类型、解析状态、预期页数及不可变页。函数复核 revision、重复 ID、连续页码、页数、解析状态、页 hash、证据 offsets/hash、事实引用。解析不完整返回 `PARSE_COVERAGE_INCOMPLETE`，不生成看似完整的 missing 结论；未知清单返回 `CHECKLIST_UNSUPPORTED`；其他输入不一致返回 `CHECKLIST_INPUT_INVALID`。本票选用工单允许的“明确拒绝”路径，不虚构 parse_quality Finding（输入 gate 由后续运行/UI 展示）。

新增契约 `ChecklistManifest`、`ChecklistEvaluation`、`DifferenceCandidate` 已纳入 canonical OpenAPI／JSON Schema／TypeScript 生成。

## 规则与验收

- C01—C07：逐字段检查，C03 必须同时有转诊人和联系方式。缺失项没有伪造 Fact／Evidence，带完整 checked_document_ids、清单版本及文档／页覆盖说明。explicitly_none 属已提供；unknown 单列为需澄清；未提供单列 missing。
- C01 身份：仅空白、首尾及大小写归一；不同姓名产生身份待核对，不归并昵称、音译或不同身份。C02 使用原始日期，支持合法 ISO 和完整英文月份的明确日期；斜线日期不猜 locale，非法／歧义日期不参与身份矛盾比较。
- C06／C07 差异：仅同一明确日期、同字段、非 unknown 的直接相斥陈述。支持同一药名的 currently taking／not taking，以及全局无当前用药／明确正在服用、无已知过敏／明确 allergic to。两边事实和证据均保留；不同日期、未知日期、不同药名或仅剂量数值不同不自动生成矛盾。其余原文事实保留供人审核。
- 差异候选不接受模型消息或医疗评分。候选引用不存在／字段不一致时拒绝；候选不能绕过确定性配对、时间和相斥条件。引擎检查所有合格事实对，候选不会凭空新增 Finding。
- C08 仅对 stated 附件声明做筛查；无声明为 not_applicable。当前明确语法为 `<title> is attached.`，对独立来源文件标题作大小写／空白归一后精确匹配。没有唯一标题匹配、多个匹配、模糊标题或其他措辞均保留人工核对项，不推断没有做过检查。类型仅保留在 manifest，不以“都是 PDF”证明是同一报告。
- 结果按规则、类型、字段、稳定 ID 排序；SHA-256 指纹绑定版本、清单、规则、参与事实／证据及检查范围，UUIDv5 由指纹生成。同输入重复或列表顺序变化得到完全相同结果。指纹用于同版本输入复现；不同运行重新生成的 Fact ID 不保证跨运行同指纹，不据此自动复制人工处理。

## 证据和边界

`tests/referral_review/test_checklist.py` 使用开发集 dev-01—09 的人工编写事实与原文，逐一比较 C01—C08 assessment 及 Finding 的规则／类型／字段。包括缺失、unknown、DOB 差异、同日直接相斥、异日剂量变化、附件有／无匹配、Unicode 和资料内提示注入文字。比较不依赖生成的 Finding ID。开发标注仍待 MT-03 操作者复核。

反例覆盖错误版本、缺页／不可读／失败解析、损坏 hash、跨文档证据、revision 不一致、重复事实、丢失证据、伪候选、不同药物、药名后缀、歧义日期、姓名大小写／别名、重复标题附件与排序复现。没有读取冻结测试集调参，没有运行模型。MT-20 汇总实际提取与规则的端到端准确性，不把这组开发回归称为真实模型评估。

服务保持未启动；没有浏览器 AI 测试、付费请求、部署或生产迁移。规则不是医学判断；保守语法未覆盖的陈述保持原始事实，由人工核对，MT-20 必须按完整分母报告质量。

## 验证命令及结果

- `cd src/backend && DATABASE_URL=sqlite:///:memory: .venv/bin/python -m pytest -q tests/referral_review`：278 passed、32 skipped、4 项既有弃用警告；该轮收集 MT-09 的 31 项测试。外部 PostgreSQL 缺项仍跳过。
- 随后补充 locale 无关日期解析及 4 项测试，最终 `.venv/bin/python -m pytest -q tests/referral_review/test_checklist.py`：35 passed。
- `src/backend/.venv/bin/python scripts/referral_contracts.py --write` 生成，`--check` 无漂移。
- `pnpm --dir src/frontend typecheck` 通过；未改 UI，不重复生产 build。
- `git diff --check` 通过。
