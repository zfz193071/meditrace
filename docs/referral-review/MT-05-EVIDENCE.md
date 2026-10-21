# MT-05 私有原件存储验收证据

日期：2026-10-21。MT-04 已先提交为 `1316b51`；本票对应其后的工作区变更，尚未提交或推送。前置 MT-04 未完成，按依赖规则保留 `TODO`，不能关闭；真实 PostgreSQL／Private Blob 验收尚缺配置。

## 实现与边界

- `src/backend/referral_review/documents/`：本地私有／Vercel Private Blob Adapter，受限 multipart 和 Unicode 文本输入，元数据／同源鉴权下载，事务配额和幂等，持久清理 intent 与显式补偿 CLI。
- `app.py`、`config.py`、`schemas/__init__.py`、`errors.py`：路由接入、默认禁用的存储配置、安全错误与元数据契约；OpenAPI 和 TypeScript 由源生成。
- `scripts/check_private_blob.py`：固定合成原件的真实供应商往返工具，写入前保存 0600 cleanup receipt；失败保留可重试清理入口，不输出原始供应商异常。
- 后端依赖锁定官方 `vercel-blob==0.5.0`；审计发现并定向修复 certifi 版本，见 [修复记录](../../BUGFIX-REFERRAL-CERTIFI-AUDIT.md)。
- 使用既有 storage buckets／reservations／cleanup_jobs，无新增或自动执行迁移。资料版本历史原件计存储配额，但不占当前版本 5 份有效文件槽。存储对象上限账号 50、全站 5,120，与字节配额一并在锁内检查。

PDF 当前只完成 MIME、头及实际字节限制，不宣称已经验证扫描／损坏／加密 PDF。原件保存返回 `parsing`，没有后台解析 worker；MT-06 接入当前请求内解析后才能达到 `201 ready`。资料包创建属于 MT-07，上传页面属于 MT-14，日常生命周期调度属于 MT-18。

## 逐项验收

| MT-05 条件 | 证据及结果 |
| --- | --- |
| 2 MiB、长度谎报、并发超额、恶意文件名 | 精确 2 MiB 成功、超一字节拒绝；谎报／缺失 Content-Length、分块输入、MIME／ZIP／路径攻击、多文件及额外字段均覆盖。PostgreSQL 三项竞争测试已写但 skip，此项不整体勾选 |
| 账号隔离、对象键和缓存 | 实际身份模块 + 隔离 SQL + 本地对象测试：未登录 401，另一账号与未知 ID 都 404；错包、已删／到期、读取中到期拒绝。仅同源代理返回原件，private/no-store、nosniff、attachment、sandbox；响应无对象键／token |
| 跨存储／DB 故障恢复 | PUT 失败、PUT 成功后 DB 失败、DELETE 失败、补偿时 DB 失败、进程中断遗留、提交成功回执丢失均覆盖；删除失败保留预留，恢复后恰好释放一次；已提交原件不被误删 |
| 实际 Private Blob 往返 | 未执行。只检查本地配置是否存在，未输出密钥；`BLOB_READ_WRITE_TOKEN` 缺失。HTTP transport 测试调用实际 SDK，仅证明适配器协议，不证明真实 store 配置 |
| 本地存储不公开／不进仓库 | 本地路径必须在仓库之外且不含 public 路径段；权限 0700／0600，拒绝路径／URL 键、软链接读取和覆盖；生产配置拒绝 local |

`test_documents.py` 24 项、`test_private_blob.py` 6 项、`test_storage_tools.py` 2 项，均离线通过。`test_document_pg.py` 3 项（全站跨账号竞争、单包数量竞争、账号额度失败全站回滚）因缺独立测试库 skip。测试没有发起 OAuth、模型或真实 Blob 请求。

## 验证命令

在仓库根目录执行，使用后端 Python 3.12 虚拟环境：

| 命令 | 实测结果 |
| --- | --- |
| `PYTHON_DOTENV_DISABLED=1 DATABASE_URL=sqlite:///:memory: src/backend/.venv/bin/python -m pytest -q src/backend/tests/referral_review src/backend/test_database_deployment.py` | 188 passed、34 skipped、4 个现有弃用警告；此轮在补充 CLI receipt 测试之前 |
| `PYTHON_DOTENV_DISABLED=1 src/backend/.venv/bin/python -m pytest -q src/backend/tests/referral_review/test_storage_tools.py` | 补充 CLI receipt 2 项通过 |
| `python3 scripts/referral_contracts.py --write`、`--check` | 生成及漂移检查通过 |
| `UV=src/backend/venv/bin/uv UV_CACHE_DIR=.uv-cache python3 scripts/check_backend_lock.py` | 锁文件／生成 requirements 一致 |
| `python3 scripts/test_deploy_workflow.py` | 10 项通过，只验证部署脚本，未部署 |
| `pnpm --dir src/frontend typecheck` | 通过 |
| `pnpm --dir src/frontend build` | 生产构建通过 |
| `pnpm --dir src/frontend lint` | 0 errors，28 个旧代码 warnings |
| `pnpm --dir src/frontend test --runInBand` | 5 suites、23 tests 通过 |
| `python3 -m py_compile scripts/check_private_blob.py src/backend/referral_review/documents/maintenance.py` | 通过 |
| `src/backend/.venv/bin/pip-audit -r src/backend/requirements.txt --no-deps --disable-pip` | certifi 定向升级后，无已知漏洞 |
| `src/backend/.venv/bin/pip-audit --local` | 实际安装环境无已知漏洞 |
| `git diff --check` | 通过 |

## 剩余验收与操作

1. MT-04 的前置 MT-02 PostgreSQL 以及真实 GitHub OAuth 仍未验收。
2. 配置独立 `TEST_DATABASE_URL` 后运行 PostgreSQL 集成；没有使用已有生产库，SQLite 结果不等同于行锁验收。
3. 配置 Private store 后按 [存储手册](STORAGE.md) 运行实际合成往返、无凭据直读拒绝和删除，保留脱敏记录；没有用 transport 成功替代此项。
4. 手动启动／重启服务仍由操作者完成。自动浏览器 AI 测试、真实模型调用、生产迁移和部署均未执行。

capabilities 保持 false，readiness 保持 503；V1 未交付，MT-05 不记 DONE。
