# MT-08 离线实现与验收记录

日期：2026-10-21。代码与离线测试已实施；MT-03／06 前置验收未完成，工单保持 `TODO`。没有真实供应商调用或质量成绩。

## 实现

- `src/backend/referral_review/extraction/` 提供 `extract(revision, model_config, adapter)`，独立提示词、输入／模型输出／领域结果 Schema、Fake 和 DeepSeek Adapter。使用既有 Fact／Evidence 与 text-v1 定位规则；通过 `export_contracts.py` 导出输入输出契约及生成 TypeScript。
- 输入是调用方已经鉴权并从不可变版本加载的页快照；提取模块再次检查成员重复、文档／页／文字上限、解析版本和 hash。它不自行查询数据库、不接受文件 URL、不提供公开执行端点。MT-11 必须在调用前验证账号归属／版本、预留 MT-10 额度和费用、持久化 dispatch 标记；配置校验绝不替代这些授权。
- 原文、未知／否定及各个时间陈述分别保留。事实必须是引用的原文子串；药物／报告必须保留完整来源行和识别到的原文日期。V1 规范化只允许 null 或原值，不自动改写日期、姓名或数值单位。非法 ISO DOB、无原文支持的状态、假页码、外部文档、歧义引文和假引文导致整次 `MODEL_INVALID_OUTPUT`，不返回部分成功。
- 完整请求 JSON（含提示词、Schema 和资料）的 UTF-8 字节数加 1,024 framing 余量作为保守 token 上界，限制 16,000；输出限制 1—6,000。超限不截断且不派发。此策略按 byte-level tokenization 上界设计，会拒绝部分原始资料上限内的较长包；更换为非 byte-level tokenizer 的模型前必须重新验证估计器。
- DeepSeek 使用固定 HTTPS 端点、JSON 输出、关闭 thinking、无 stream／tools、一次 HTTP 请求、无重试／重定向／环境代理，120 秒整体 deadline，响应体上限 256 KB。记录请求 model、返回 model、completion ID 与 usage；usage 缺失或不合法为 `None`，绝不当作零费用。截断／无效事实仍携带可用结算元数据；MT-10／11 需消费该元数据并对未知成本保留预留。
- Fake 必须显式传入合成输出；提供非法 JSON、假引用、截断、超时与缺 usage 场景，不冒充实际提取。

## 逐项验收

1. 共用领域结构与输入输出契约：Fake／Mock HTTP 使用同一验证链；生成的 JSON Schema、OpenAPI 与 TypeScript 纳入漂移检查。
2. 假页码、跨文档、重复引用、非法日期及单位改写：离线测试拒绝；相邻上下文消歧及 Unicode offsets 通过。
3. 缺失／未知／否定／时间：未提及字段不生成事实；未知保留；不同日期药物陈述独立；不允许丢失药物行中的剂量、否定或识别到的日期。
4. 错误：`EXTRACTION_INPUT_INVALID`、`MODEL_INPUT_LIMIT`、`MODEL_INVALID_OUTPUT`、`MODEL_TRUNCATED`、`MODEL_TIMEOUT`、`MODEL_UNAVAILABLE`；配置不足使用既有安全 `ConfigurationError`。不存在旧诊断回退。MT-11 接入路由时统一映射 API 错误。
5. HTTP 行为：使用 httpx MockTransport 的合成响应验证请求、解析、供应商失败、重定向、截断、超大响应、工具调用拒绝、总时限和单次派发；没有使用供应商录制结果，不称为真实集成验收。

## 限制与后续验收归属

字符串与状态检查只是最低结构支持，不能证明字段分类或引文语义正确，也不能保证模型找出所有事实。日期识别仅覆盖 ISO、斜线数字日期与英文完整月份表达；原文完整行仍保留，其他时间表达的正确提取由 MT-20 标注评估。提示注入作为数据放在 user 资料 JSON，模型不获得工具能力；模型实际服从程度仍需 MT-20 测量。

MT-20 在完整权限与预算链路完成且获得明确费用授权后验证真实请求、模型 token 上界及质量门槛。MT-11 接入资料加载、费用账本与批次持久化。没有启动服务、浏览器 AI 测试、部署或生产迁移。

请求协议依据：[DeepSeek Chat Completions 官方文档](https://api-docs.deepseek.com/api/create-chat-completion/)（2026-10-21 查阅）。模型名称和价格来自服务端显式配置，不在代码中猜测价格。

## 验证命令

- `cd src/backend && DATABASE_URL=sqlite:///:memory: .venv/bin/python -m pytest -q tests/referral_review`：244 passed、32 skipped、4 项既有弃用警告（该次收集 33 项新增测试）。跳过项主要为 PostgreSQL 集成，未替代外部验收。
- 随后补充总 deadline、失败结算元数据及源 hash 损坏测试；`.venv/bin/python -m pytest -q tests/referral_review/test_extraction.py`：最终 36 passed。
- `src/backend/.venv/bin/python scripts/referral_contracts.py --write` 生成契约，`--check` 无漂移。
- `cd src/frontend && pnpm typecheck` 通过；无 UI 实现变更，未重复生产 build。
- `git diff --check` 通过。
