# MT-15 双栏证据与人工审核 UI 证据

日期：2026-10-22。代码与离线验证已实施；MT-12／14 前置验收未关闭，本票保持 TODO。当前变更尚在工作区，不能将本记录解释为线上发布或真实供应商集成通过。

## 实施

- 工作台接入事项类型／状态筛选、清单要求、检查范围、关联事实和双侧证据；缺失项明确没有可引用的“缺失原文”。所有提取事实可展开核对。
- 引用依赖 run 的不可变来源版本，按 Unicode code point 半开区间切片，验证文档成员、解析版本、页号、quote、页哈希并重算 SHA-256。不用字符串搜索猜测位置，不匹配时停止高亮。
- 展示局部摘录和可展开完整规范化页；React 文本渲染不解释来源 HTML／Markdown。原 PDF 采用已有鉴权 attachment 下载接口并标明对应页，选择安全下载路径，不嵌入／执行原 PDF，也不宣称像素级框选。
- 支持 resolve、dismiss、defer、reopen；dismiss／defer 要求理由，纠正值注明 Reviewer supplied，引用关联只能选本结果已有证据。原始事实和引文不覆写。
- 审核写入携带 review_version 和幂等键；409／不确定响应保留输入并停止继续写入，先显式重新读取、对比，再由用户保存。字段及事项切换有未保存提醒。
- 当前 run 成功、来源未过期、无 open 事项且没有未保存编辑时，才可二次确认生成快照。未解决／被忽略的身份差异持续显示警告。接入 MT-13 摘要、复制、文本下载、打印及服务端 txt／PDF 导出链接。
- 分页显示审核历史、人工更正与确认记录，可以查看对应 run 或确认交接；旧版本只读，旧决定不自动应用到新 run。
- 新增 `GET /runs/{run_id}/review`：在同一事务内按 owner 校验资料包，返回该 run 的来源 manifest、当前审核版本、stale 和每项最新决定；不修改状态、不派发模型、不预留费用。解决仅从一页审核历史无法得到完整最新决定的问题。
- 运行状态组件将新读取的完成结果传回工作台，用户完成／恢复批次后可进入证据审核；有未保存审核编辑时不允许另开核对或切换来源版本。

主要文件：`ReviewWorkspace.tsx`、`EvidencePanel.tsx`、`ReviewHistory.tsx`、`PacketWorkspace.tsx`、`RunPanel.tsx`、`lib/referral-api/{workspace,evidence}.ts`，以及后端 `reviews/{contracts,routes,service}.py` 和生成契约。

## 检查结果

| 检查 | 结果 |
| --- | --- |
| `cd src/backend && DATABASE_URL=sqlite:///:memory: .venv/bin/python -m pytest tests/referral_review/test_reviews.py tests/referral_review/test_foundation.py -q` | 57 passed；4 条既有弃用 warning |
| `cd src/backend && DATABASE_URL=sqlite:///:memory: .venv/bin/python -m pytest tests/referral_review -q` | 384 passed，68 skipped，4 warnings；包括审核、确认及原有导出回归；跳过不代表 PostgreSQL 验收通过 |
| `pnpm --dir src/frontend test --runInBand` | 11 suites／56 tests passed |
| `pnpm --dir src/frontend typecheck` | 通过 |
| 修改范围 ESLint | 通过 |
| `pnpm --dir src/frontend build` | 生产构建通过，workspace 及动态 packet 路由正常生成 |
| `python3 scripts/referral_contracts.py --check` | OpenAPI／TypeScript 与 Pydantic 一致 |
| `git diff --check` | 通过 |

初次后端检查遇到环境默认 PostgreSQL 驱动缺失；最终命令显式固定临时内存 SQLite，未访问生产库，也未把这次 SQLite 通过当作 PostgreSQL 证据。新删除隔离测试最初缺少 DELETE 幂等头，已补头并断言 202，再检查读取 404。

新增自动测试覆盖：双侧 DOB 引用、恶意 HTML 只显示文本、缺失检查范围、篡改哈希拒绝高亮、Unicode／组合字符／重复引用／长页、来源成员／页／解析版本不符、人工决定到确认导出、必须理由、409 保留修改与对比、历史只读、dismiss 后身份警告、reopen、筛选不清空编辑、历史分页与历史快照。后端新增最新决定覆盖、不可变历史 manifest、只读无费用、匿名／他人／删除隔离。

## 后台浏览器验证

使用 chrome-devtools-pages 技能。默认 DevTools profile 被另一会话占用，未关闭或修改它；使用本工单独立 headless Chrome，通过 CDP 后台检查，未切换用户窗口或标签。没有启动／停止项目服务。

`node scripts/referral_review_qa.cjs` 将实际 Workspace／ReviewWorkspace 组件与合成 fixtures 打包成临时离线 HTML。响应层预载成功结果，模拟人工决定／确认持久化；任何创建或执行模型批次请求都拒绝。这个 harness 是组件浏览器 QA，不是真实 Next／FastAPI／OAuth 往返。

- [1440×900 截图](evidence/MT-15/desktop.png)、[1024×768 截图](evidence/MT-15/tablet.png)、[390×844 截图](evidence/MT-15/mobile.png)：已查看，双侧引文正确，窄屏可切换事项／证据，宽度无溢出。截图截取工作台审核区域，非整个长页面。
- [桌面审计](evidence/MT-15/desktop-audit.json)、[窄屏审计](evidence/MT-15/mobile-audit.json)：仅合成数据；页宽等于 scrollWidth，localStorage 为零。
- [人工操作审计](evidence/MT-15/interact-audit.json)：原生键盘选择 Keep unresolved、输入理由、Space 保存、选择下一项；补充人工联系人后显式确认。只发生读取、resolution 和 confirm 请求，无 create run／execute。
- [实际生成的文本 Blob 内容](evidence/MT-15/confirmed.txt)：浏览器触发 Download text，保留 Reviewed — unresolved items remain 和 Identity unresolved。该文件由合成快照视图生成；服务端 PDF／txt 的真实 API 回归由后端既有 handoff 测试验证，本轮未新增 PDF 排版。
- [版本切换审计](evidence/MT-15/stale-audit.json)：预置 source version 2 后重新加载，旧 source version 1 的双侧证据和决定仍可读，修改／确认禁用。

自动浏览器没有点击任何生成按钮，包括模拟生成。初次键盘驱动缺少字符事件、初次 DOM 等待返回了元素对象，修正驱动后从全新离线案例完成闭环，最终审计来自通过的运行。

## 验收边界

本票的核心交互、失败边界、三种视口和预载结果到确认／文本导出的离线证据已齐；相关实现不等于整票可关闭。真实 OAuth、Private Blob、PostgreSQL 并发及 MT-12／14 前置验收仍未完成，完整服务端页面往返及发布归 MT-22／24。

人工后续步骤：手动启动服务并登录；使用合成材料导入并保存来源，手动完成核对；在同一工作台核验 DOB 双侧引用，分别保存处理／保留未解决项，确认并下载 PDF；替换资料后核验旧结果只读与历史导出。真实模型费用须按既定授权执行。
