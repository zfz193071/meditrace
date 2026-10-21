# 私有原件存储与补偿

MT-05 实现原件存储；PDF 页解析由 MT-06 接入，资料包创建／版本由 MT-07 提供。当前工作区尚不可完成导入流程。capabilities 继续为 false，readiness 继续为 503。

## 配置

默认 `RR_STORAGE_BACKEND=disabled`。启用需要已配置的 MT-04 身份服务、显式迁移后的数据库，以及以下两种存储之一；不会在应用启动时执行 DDL 或创建目录。

- 本地：`RR_STORAGE_BACKEND=local`，`RR_PRIVATE_STORAGE_DIR` 指向仓库之外的绝对私有目录（例如 `$HOME/.local/share/meditrace-private`，由操作者在环境配置中展开为绝对路径）。目录首次使用时创建为 0700，已有目录权限不安全则拒绝，文件为 0600；不能在 public 目录下。生产禁用此 Adapter。
- Vercel：`RR_STORAGE_BACKEND=vercel`，`BLOB_READ_WRITE_TOKEN` 必须来自 **Private** store。密钥仅在后端；不要提交实际值，不使用公开桶或浏览器直传。适配器固定 `access="private"`、禁止覆盖，供应商响应不返回给前端。

使用官方 `vercel-blob==0.5.0` 和同步 SDK 会话，在线程池中运行；通过显式凭据和固定 API 地址隔离环境默认值。SDK 版本、接口与私有访问规则已核对 [Python SDK 文档](https://vercel.com/docs/vercel-blob/python-sdk-reference) 和 [Private Storage 文档](https://vercel.com/docs/vercel-blob/private-storage)。独立 HTTP transport 测试调用实际安装的 SDK，不替代真实供应商验收。

`RR_STORAGE_GLOBAL_BYTES` 默认 1 GiB，账号为 100 MiB。每账号 50 个／全站 5,120 个原件对象；历史原件和待清理对象也计数。全站与账号桶按固定顺序加行锁；文件数查询也在这些锁内。单包当前版本加未入版本的新文件最多 5 份，历史成员不占有效文件槽。新上传预留 PDF 2 MiB 或文本 40,000 bytes，成功后按实际原件字节结算，可能在接近上限时保守拒绝一个最终较小的文件。

配额桶首次使用时写入上限；降低环境上限立即对新预留生效，已占用字节不被改写。提高全站环境上限不会自动扩大已有数据库桶，需操作者核对预算后更新桶上限；不在普通读取中自动提额。

## 接口

- `POST /api/v1/packets/{pid}/documents`：Origin、CSRF、服务端会话和 `Idempotency-Key` 必需；key 是 8—128 位字母、数字、`_` 或 `-`。接收唯一 `file` 字段的 multipart PDF，或 `{text,filename?}` JSON；不接受 owner、URL 或对象路径。当前返回 201 与 `parse_status=parsing`，只是保存原件，MT-06 尚未提供解析结果或后台任务。
- `GET /api/v1/packets/{pid}/documents/{did}`：该资料包下的元数据；无对象键／供应商地址。
- `GET /api/v1/packets/{pid}/documents/{did}/original`：权限校验后代理二进制；校验实际字节和 SHA-256，I/O 后再次检查归属／到期，使用 attachment、private/no-store、nosniff 和 sandbox 响应头。

PDF 按实际接收字节限制整请求（2 MiB + 16 KiB multipart 开销）及文件（2 MiB）。只信服务端计数，不信 Content-Length；有声明时还核对实际长度。限定 MIME 和 `%PDF-` 头，拒绝压缩包和不支持类型；加密、扫描、损坏 PDF 等深入解析在 MT-06 验证。文本最多 10,000 Unicode code points，保留 Unicode 原文；JSON 传输也有固定上限，支持转义后的非 BMP 字符。

文件名拒绝路径分隔、URL、转义路径和控制字符；对象键仅使用服务端 UUID 与随机数。下载只接受 document ID，不接受对象键或重定向。相同 key 相同内容／文件名复用 Document，不重复写对象或扣配额；同 key 不同输入／仍在上传／此前失败返回 409，失败后用新 key 新建 Document。对象本体不可覆盖。

## 失败恢复

预留事务同时写 Document、reservation、幂等记录和 10 分钟后到期的 cleanup intent。存储调用在事务外进行，完成事务再结算字节和取消 intent；解析状态仍待 MT-06。数据库提交回执丢失时先检查已提交状态，不误删成功原件。

接收／存储／结算失败后屏蔽失败文件，并尝试删除确定的对象键；只有删除被确认（或确定未调用写入）才释放额度。删除失败保留 `cleanup_pending`；数据库不可用时原始 intent 留存。崩溃遗留预留在 lease 到期后可显式补偿，补偿不删除 `stored` 文件，也不在 GET 中触发。每个清理任务达到 10 次尝试后停止，等待操作者检查；单次调用最多选择 200 项，45 秒后不再启动新项，当前单项网络操作还可能继续至超时。

在后端目录、已经配置 runtime 环境后手动执行（不加载 dotenv、不启动服务）：

```bash
./.venv/bin/python -m referral_review.documents.maintenance --limit 20
# 仅在检查供应商／数据库恢复后，重新允许达到次数上限的选中任务：
./.venv/bin/python -m referral_review.documents.maintenance --limit 20 --retry-exhausted
```

输出只有选择和成功数量。未成功任务仍保留额度，不将其记作物理删除。每日生产调度、整包／账号删除、历史引用清理和孤立上传 24 小时清理属于 MT-18，本票没有启用任何定时任务。

## 真实供应商验收

当前未配置 Private Blob token，没有实际往返成功记录。操作者须创建／选择私有 store，并通过环境提供 token。以下命令仅写入一个很小的固定合成文本；不访问应用数据库，也不调用模型。请使用新的 receipt 文件路径，脚本拒绝覆盖已有 receipt。

```bash
src/backend/.venv/bin/python scripts/check_private_blob.py roundtrip --receipt /private/tmp/meditrace-blob-receipt.json
# 遇到中断／删除失败时，保留同一 receipt，恢复后执行：
src/backend/.venv/bin/python scripts/check_private_blob.py cleanup --receipt /private/tmp/meditrace-blob-receipt.json
```

receipt 在 PUT 前以 0600 写入，只含随机对象键和 store 指纹。脚本核对私有写入、鉴权读取字节一致、独立无凭据 HTTP 直读被拒绝，以及供应商删除确认。失败不输出原始异常、token 或对象 URL。记录时间、版本、PASS／失败阶段及清理结果；还需用户在实际登录的应用中验证 A/B 归属，不把供应商往返当作 OAuth 验收。

PostgreSQL 使用独立 `TEST_DATABASE_URL`，按 [迁移手册](MIGRATIONS.md) 操作。新增 `test_document_pg.py` 覆盖不同账号全站额度竞争、同包文件数竞争、账号额度失败时全站预留回滚；缺配置时明确 skip，不改用生产库或宣称 SQLite 证明了行锁行为。
