# MT-16 — 英文入口与免登录固定示例实施证据

日期：2026-10-22。代码已实施并完成离线自动验证；前置 MT-03／13／15 尚未完成全部验收，工单保持 TODO。未部署，未调用模型，未开展独立用户试用。上一批 MT-15 和求职规划调整已提交为 `38b8368`；本票为其后的工作区变更。

## 实现范围

- `/`：英文定位、Try demo / Open workspace、合成与预置标识、作品状态、架构／评估／代码入口。更新默认英文 metadata 和语言。
- `/demo`：身份冲突、缺少声称已附报告、正常资料三例；提示检查证据、处理每项问题、确认和导出，提供身份冲突 60–90 秒主路径与重置。
- `/project`：可直接阅读的架构与评估状态，明确尚无真实模型质量分数、临床验证或独立试用结论。GitHub 仓库链接匿名 HTTP 检查返回 200；本地开发可能领先远端，未执行推送。
- `ReviewTransport`：向同一 ReviewWorkspace / EvidencePanel / ReviewHistory 注入传输接口；真实工作区默认仍使用 workspaceApi。HandoffSummary 共用复制、文本下载及打印呈现。
- 本地会话：每次进入／重置／切换案例新建内存 store；不使用 fetch、localStorage、sessionStorage 或服务端写入。决策有版本检查、幂等键和历史；确认冻结当前事实与人工决定，导出仍显示未解决身份警告和 reviewer supplied 标记。
- 补附件：先 Load prepared revision，将版本 1 结果变为只读；再 Load prepared result，显示版本 2 固定结果。旧历史保留，新结果不继承旧决定，无模型等待动画。
- 演示确认及摘要为本地 `handoff-v1` 投影，不冒充服务端持久化快照、认证审计或服务端 PDF。PDF 使用浏览器 Print / Save PDF；打印对话框由用户操作。

## 资料来源与校验

生成器 `scripts/referral_demo_assets.py` 只读取 MT-03 的 **public development** 资料，未修改原始语料或冻结集：

| 入口 | 来源 | 固定预期 |
| --- | --- | --- |
| 正常 | public/dev-03 | 无清单 finding，保留药物时间语境 |
| 身份冲突 | public/dev-01 | DOB 冲突及缺附件两项；入口明确提示两项 |
| 缺附件 | public/dev-01 的 referral 单文档子集 | 一项 attachment_unmatched |
| 补附件版本 2 | 上述子集 + 明确编写的 Synthetic Echo Report A | 无 attachment_unmatched |

生成时重新执行生产确定性清单 evaluate，校验预期 finding 种类；使用生产 Pydantic 校验 Packet / Revision / Run / Page；验证原文件 SHA-256、页面哈希及证据锚点。源文件以内嵌 data URL 供下载。生成 JSON 不是模型质量评估数据；原标注仍是 provisional_operator_review_pending。

## 自动验证结果

- `src/backend/.venv/bin/python scripts/referral_demo_assets.py --check`：4 个版本契约、原文哈希、规则结果与已提交资产一致。
- `pnpm --dir src/frontend test --runInBand`：12 suites / 60 tests 通过，包含访客隔离、重置、CAS／幂等、确认快照不随后续决定改变、旧版拒绝写入、新版不继承决定、三例 UI 与保留身份警告的复制内容。
- `pnpm --dir src/frontend typecheck`：通过。
- `pnpm --dir src/frontend lint`：0 errors；28 条既有旧页面 warnings，本票文件无 warnings。
- `pnpm --dir src/frontend build`：通过，`/`、`/demo`、`/project` 静态构建成功。
- 默认 Chrome DevTools profile 被其他会话占用；使用本任务专属 headless Chrome + CDP。未启动 Next / FastAPI 服务，未操作其他浏览器会话。
- 浏览器组件测试实际操作了选择问题、键盘选取 Keep unresolved、输入理由、保存两项、确认、复制、下载文本、生成打印 HTML、重置、补附件两步、正常案例确认、刷新恢复初始状态。
- 浏览器记录：0 fetch，0 HTTP(S) 页面请求，localStorage / sessionStorage 均为空。刷新仅读取本地 HTML／JS。三个目标视口 1440×900、1024×768、390×844 无横向溢出；已目视检查首页和移动端双侧证据截图。
- 打印测试拦截 OS 打印对话框，只验证实际生成的 iframe 文档仍含 Identity unresolved；未冒称真实打印机或交互式 Save PDF 已验证。

证据目录：[MT-16](evidence/MT-16/)。包含首页／演示三视口截图、证据面板截图、浏览器审计 JSON，以及真实 Blob 导出的 [confirmed.txt](evidence/MT-16/confirmed.txt)。记录只包含合成资料。

## 复现离线浏览器检查

1. `node scripts/referral_demo_qa.cjs` 构建临时 HTML／JS，打印文件路径。测试环境补充 Next Link 所需 process.env；不是替代生产构建的路由验收。
2. 在专属无界面 Chrome 中使用独立 user-data-dir 与 DevTools 9456 端口，保持后台，不使用他人会话。
3. `node scripts/referral_demo_browser_qa.cjs audit file:///.../index.html` 跑固定演示；将 audit 换为 home 检查首页。只打开后台标签，不触发生成。
4. 测试结束仅关闭本任务的 Chrome。生产路由跳转、真实 HTTP 环境、部署后缓存和正式浏览器打印仍需 MT-22／24 集成验收。

## 验收边界和剩余工作

本票自动覆盖：无需账号的固定核对与本地导出、版本失效、访客隔离、不持久化、共享契约／关键 UI、三例规则结果、身份警告、首页入口与三视口布局。

不能替代的验收：MT-03 操作者标注复核；前置 MT-13／15 完整集成；真实首次使用者无需口头指导完成流程的试用；线上路由与最终部署。工单对应复合验收项保留未勾选，不把自动脚本称作用户反馈。

按调整后的优先级，下一实施项为 **MT-20 离线评估基线**，并非 MT-17。真实模型评估仍须单独满足标注和费用预算条件。
