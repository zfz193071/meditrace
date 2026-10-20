# MT-03 实施与验收证据

日期：2026-10-20。基线提交：`6a85ab4`（MT-02 实现已本地提交，未推送）。本票实现尚未提交。状态：`BLOCKED`，工程检查通过，缺少规范要求的操作者逐包标注复核。不能将代理编写的候选标签称为人工或临床专家验证的 gold。

## 交付范围

资产入口：[合成样本说明](../../fixtures/referral-review/README.md)、[标注规程](../../fixtures/referral-review/ANNOTATION.md)、[复核记录](../../fixtures/referral-review/REVIEW-LOG.md)。

- `fixtures/referral-review/checklist.json`：固定版本的 C01—C08，机器可读、严格 schema 校验及独立哈希锁。
- `dev/`、`test/`：30 包，10 开发／20 测试，47 份源资料；187 个候选 Fact、189 个 Evidence、20 个 Finding。测试集中 6 包无 Finding。7 包属于输入拒绝场景，不产生成功结果或伪造缺失。
- `public/`：仅 dev-01／02／03，分别展示缺附件与身份差异、过敏未知、资料完整但跨日期用药变化。单独保存原文、预计算 run、审核前后状态。完成审核后仍可有未解决事项。
- 19 个 PDF 文件包含 4 个公开副本；15 个独立 PDF 源文件覆盖文字、扫描、混合、损坏、加密、超过 2 MiB 及超过 25 页。普通文字文件可由计划使用的 pypdf 回读，异常文件按预期拒绝。
- `scripts/referral_fixture_data.py`：显式编写的案例与候选标注，不运行模型或未来的规则引擎来生成评判答案。
- `scripts/referral_fixtures.py`：确定性生成、临时目录重生成对比；不加载环境密钥，不访问数据库，不启动服务。
- `scripts/referral_fixture_schema.py`／`referral_fixture_validation.py`：复用 MT-01 契约，并校验页码、code point 跨度、范围、引用、状态、哈希及划分。
- `scripts/referral_fixture_render.py`：后台离线渲染，便于目视检查。预览仅进入被忽略的 `.scratch/referral-pdf-qa/`。
- CI 增加资产漂移检查；现有 pytest 自动发现新测试。`.vercelignore` 排除整个 corpus 和作者脚本，尚未增加任何前端运行时入口。

新依赖仅加入开发组：pypdf 6.21.1、ReportLab 4.5.1、pypdfium2 5.14.0。运行时 requirements 未变化；生产解析模块仍由 MT-06 实施。

## 本地验证

| 命令或检查 | 结果 |
| --- | --- |
| `src/backend/.venv/bin/python scripts/referral_fixtures.py --check` | 所有生成资产逐字节一致；再次生成不会改变 PDF／ID／时间戳 |
| `src/backend/.venv/bin/python -m pytest -q src/backend/tests/referral_review/test_fixtures.py` | 47 passed |
| `PYTHON_DOTENV_DISABLED=1 DATABASE_URL=sqlite:///:memory: src/backend/.venv/bin/python -m pytest -q src/backend/tests/referral_review src/backend/test_database_deployment.py` | 121 passed，31 skipped，5 个既有弃用警告 |
| `python3 scripts/referral_contracts.py --check` | OpenAPI、JSON Schema、TypeScript 契约无漂移 |
| `UV=src/backend/venv/bin/uv UV_CACHE_DIR=.uv-cache python3 scripts/check_backend_lock.py` | 锁文件与运行时 requirements 一致 |
| `python3 scripts/test_deploy_workflow.py` | 10 passed；没有执行部署 |
| `src/backend/.venv/bin/python scripts/referral_fixture_render.py` | 41 页渲染成功；代理检查 4 张总览及 3 张原尺寸图 |
| `src/backend/.venv/bin/pip-audit --local` | 后端虚拟环境（含新增开发依赖）未发现已知漏洞；初次沙箱 DNS 失败后，经授权联网重试通过 |

31 项跳过仍属于 PostgreSQL：24 项新持久化约束、3 项真实双事务竞争、4 项既有部署数据库检查。本票没有新建数据库或使用生产连接，也没有证明 MT-02 的 PostgreSQL 验收通过。

PDF 技能要求的目视检查已执行。系统无 Poppler；Homebrew 安装会涉及大量依赖升级，已在解析／下载阶段中止（退出 130），改用项目虚拟环境的 PDFium。未观察到裁切、重叠、重音字符／µ 缺字或页码错误。损坏 PDF 按设计不渲染；加密样本只为排版检查使用已知合成密码打开，不表示生产解析应接受它。

前端源代码和运行时 API 未变，未重跑前端 build／页面交互测试。没有浏览器 AI 测试、真实供应商调用、模型费用或项目服务启停。

## 失败路径证据

- 错误引文、错位跨度、错误 text hash、越界路径被检测。
- 缺失事项不能借用不存在的原文；完整检查范围必须保留。
- 未知、明确无、未提供保持三种不同语义；不同日期与同日相斥陈述分别校验。
- 重复引文定位到具体 occurrence；跨页事实使用两段页内引文；含 astral 字符的偏移验证 code point 而非 UTF-16。
- 未读页／加密／损坏／超限包不能伪装成成功结果，也不能据此输出普通 missing 标签。
- 清单版本错误、缺项、重复项、测试样本转为公开示例均拒绝。
- 审核仍有 open、unresolved 缺理由、完成时间缺失或状态标记不符均拒绝。
- 独立 `freeze.json` 约束清单与测试包哈希；重生成脚本不改它。

## 验收与剩余门槛

工程交付已具备可检查的原文、候选标注、许可、版本、重生成命令及真实状态记录。复核模板逐包绑定内容哈希，30 项全部 pending，没有虚构审核者或日期。

关闭本票前，真实操作者需要按 [标注规程](../../fixtures/referral-review/ANNOTATION.md) 检查每包全部事实／事项及缺失范围，补齐实际复核记录并处理发现的问题。规范原文要求人工编写／检查 gold；当前代理辅助候选标注不能单独满足这一项。

测试集是“从提示词与公开示例中隔离”，不是“仓库读者不可见”。目前尚无模型评估成绩；后续若依据测试集调参，需要记录暴露情况，不得继续宣传未见测试集结果。样本使用规则较强的模板，不能证明真实医疗资料泛化能力。

MT-16 的公开 UI、MT-20 的基线／真实模型评估、MT-06 的生产解析都未实施。配置接口仍如实报告示例功能不可用，没有因生成这些文件而提前开启功能。
