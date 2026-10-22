# MT-14 工作区、导入与执行状态证据

日期：2026-10-22。代码与离线验证已实施；依赖 MT-04／07／11 未关闭，工单保持 TODO。本记录不代表真实 OAuth、存储、数据库或整站上线验收通过。

## 改动

- `/workspace` 资料包列表、创建、分页、保留期限、删除确认；packet 工作台支持重命名、删除和空／失败状态。
- PDF 单个顺序上传、文件大小和格式限制、文本显式导入、解析错误展示；候选资料与当前不可变版本分开显示。选择草稿和来源版本分别显式保存，409 保留编辑值，重新加载需确认丢弃未保存内容。
- 生成契约类型驱动 API client，附加 CSRF／必要幂等键；普通请求 20 秒、上传 75 秒、execute 185 秒上限。原文仅暂存在 React 内存；没有 localStorage、URL 或 analytics 原文持久化。
- 会话失效、回到页面及账号切换重新核验身份；登录后读取最后保存的选择和版本。新增 owner 限定的 `GET /packets/{pid}/runs/latest`，只读恢复，不派发模型、不结算账本。
- 显示会员次数、fake／real／unavailable、服务端阶段及 elapsed。创建 pending 与执行分开，必须明确点击启动。执行失败转 GET 查询；轮询 4 秒一次，读取失败或 5 分钟截止后暂停，提供手动查询／恢复／取消。
- 无额度仍可保存手工备注、手工确认及下载确认版本。保存备注保留其他已有人工字段；标记 Reviewer supplied / Not automatically checked，并明确只对应已保存来源版本。完整双栏证据审核和历史展示归 MT-15。
- capabilities 仅反映配置与服务接线；个人邀请、额度、费用预算及限流仍由执行服务验证。完整 readiness 仍返回 not_ready。

主要文件：`src/frontend/app/workspace/`、`components/referral/{Workspace,WorkspaceGate,PacketList,PacketWorkspace,RunPanel,ManualDraft}.tsx`、`lib/referral-api/workspace.ts`；后端 `runs/{routes,service}.py`、`app.py` 与生成契约。测试 fixture 位于 `src/frontend/test-support/workspace.ts`，不被生产页面导入。

## 验证结果

| 检查 | 结果 |
| --- | --- |
| `cd src/backend && .venv/bin/python -m pytest tests/referral_review -q` | 382 passed，68 skipped，4 条既有弃用 warning；跳过项不是 PostgreSQL 验收通过 |
| `pnpm --dir src/frontend test --runInBand` | 9 suites，46 tests passed |
| `pnpm --dir src/frontend typecheck` | 通过 |
| 修改范围 ESLint | 通过；手工字段保留调整后重新检查 |
| `pnpm --dir src/frontend build` | 通过，含静态 workspace 与动态 packet 路由；之后手工备注字段保留小改通过类型及测试复查 |
| `python3 scripts/referral_contracts.py --check` | 生成契约一致 |
| 桌面 1440×1000／窄屏 390×844 | 实际生产组件离线渲染；无横向溢出，解析失败、来源版本、模式及 unknown 恢复文字可见 |

新增组件／API 测试覆盖：选择恢复、候选解析失败、草稿与版本写入分离、409 不清空编辑、文本显式提交且不写浏览器存储、逐个 PDF 与超大文件拒绝、无会员手工入口、已有人工字段保留、离开提醒、创建重试复用幂等键、删除确认、session 失效、预载 unknown 恢复、预载 running 查询失败停止轮询、CSRF／幂等头、execute 网络失败不重试、请求截止及 multipart boundary。

### 背景浏览器证据

构建命令 `node scripts/referral_workspace_qa.cjs` 输出临时离线 HTML，直接打包真实 Workspace 组件及合成 fixtures。fetch 由本地合成返回替代，任何创建／执行批次请求都被拒绝。预载一个 unknown 批次和一个解析失败候选，没有点击准备或启动核对。

Chrome DevTools MCP 的默认 profile 被其他会话占用；未关闭或修改它。改用本工单独立 profile 的 headless Chrome，在后台通过 CDP 验证，不切换用户前台。本地项目页面连接被拒绝，未启动项目服务，因此这是组件浏览器 QA，不是运行中 Next／FastAPI 的端到端验收。

截图：[桌面](evidence/MT-14/desktop.png)、[窄屏](evidence/MT-14/mobile.png)。键盘非生成交互：输入合成文本、Space 激活导入、Space 选择、Space 激活保存选择草稿；请求仅涉及 mock 读取、导入和草稿保存，localStorage 为零。

## 逐项结论与限制

1. 操作边界、解析失败、409：组件测试及预载页面验证通过；真实 Private Blob／PostgreSQL 待前置验收。
2. 刷新恢复、断网、session 失效、unknown：有只读恢复和有限截止的测试；真实 OAuth 往返仍需配置与人工集成验收。支付回跳依赖尚未实现的 MT-17，不能宣称已经验证。
3. 原文不写浏览器持久存储：代码检查、Storage spy、浏览器存储检查通过；请求使用生成类型。
4. 桌面／窄屏、键盘与状态文本：离线实际组件通过；完整辅助技术验收和浏览器兼容性属于后续集成验收。
5. UI 自动化只做预载状态与非生成动作；没有真实模型或支付调用，也未自动进行 fake 模型运行。实际核对须用户手动触发。

人工后续步骤：按项目手册手动启动服务，配置并完成真实登录；创建合成资料包，依次导入、选择、保存版本，离开／返回核验草稿；仅在明确看到模式和额度后手动准备并启动核对，测试刷新／断网恢复；最后验证手工确认和授权导出。完整审核界面待 MT-15。
