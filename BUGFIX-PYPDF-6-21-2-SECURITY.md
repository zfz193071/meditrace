# 升级 PDF 解析器安全补丁并保留冻结语料来源

日期：2026-10-26。归属：MT-06、MT-20、MT-22。

## 发现与修复

[CI 安全审计](https://github.com/zfz193071/meditrace/actions/runs/40255717095) 报告生产依赖 pypdf 6.21.1 的 CVE-2026-115572、CVE-2026-115585、CVE-2026-115580，修复版本为 6.21.2。依据 [pypdf 6.21.2 发布说明](https://github.com/py-pdf/pypdf/releases/tag/6.21.2)，升级 pyproject 精确版本，通过 uv 更新锁文件及带哈希的运行依赖，仅 pypdf 版本变化。

实际 worker 原先硬编码旧 parser_version，升级依赖后新增回归复现“真实库 6.21.2，但结果记录 6.21.1”。将新解析版本集中为 `PDF_PARSER_VERSION`，父进程、worker 及异常路径共用；真实 PDF 测试同时核对结果版本与安装版本。现有数据库中的旧文档／页不重写。

## 冻结语料

升级后重新生成 30 个资料包仅 manifest 的工具版本声明产生差异，原始 PDF／文本、页面、标注和哈希完全一致。保留已有 manifest、freeze 和评估报告；`--check` 仅允许已知 `synthetic-referral@1` 原工具链声明与当前工具链声明之间的差别，其余 artifact 字节和 manifest 内容仍须逐项相等。未知历史 parser 声明、内容或哈希改变继续失败。`--write` 仍写实际当前工具链，不能用检查模式伪造新产物来源。

测试覆盖新旧工具声明兼容、来源文件改变、manifest 哈希改变、未知来源声明拒绝。

## 本地验证

- 解析版本回归在仅升级依赖后失败：结果仍为 `pypdf-6.21.1/text-v1`，真实库为 6.21.2；统一版本声明后通过。
- `test_parser.py`、`test_documents.py`、`test_fixtures.py`：**86 passed，45.39 秒**，包含实际子进程 PDF 解析、错误／限额、上传保存和完整语料重新生成检查。
- `pip-audit -r src/backend/requirements.txt --no-deps --disable-pip`：**No known vulnerabilities found**。
- `scripts/check_backend_lock.py`：通过；锁文件仅升级 pypdf，requirements 由 uv 生成且一致。
- 冻结语料目录和历史评估报告无改动；`git diff --check` 通过。远程完整回归结果在最终 CI 记录中补充。

## 全链路兼容回归

完整 CI 发现提取契约仍只接受旧解析版本，导致新解析页在进入 Fake 提取前被拒绝，表现为评估中断分母与伪造引用故障测试失败。本地 `test_evaluation.py -k fault_injection_false_quote` 复现同一 `Invalid source page` 错误。补充新旧两版解析来源的参数化提取测试，先确认新版失败、旧版通过，再将 6.21.2 加入显式兼容白名单。保留旧版以继续使用已有不可变文档，并不重新加载旧库解析上传文件；未知版本仍拒绝。

修复后 `test_extraction.py` 与 `test_evaluation.py` 共 **53 passed，61.72 秒**，包括原先失败的中断分母、Fake replay 和伪造引用拒绝路径；未调用真实模型。
