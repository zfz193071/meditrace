# IPFS 服务配置指南

本文档介绍 MediTrace 项目的 IPFS 服务配置和故障排查。

## 概述

MediTrace 使用 [Pinata](https://www.pinata.cloud) 作为 IPFS 存储服务，用于存储和分发诊断报告 PDF 文件。

## 环境配置

### 必需的环境变量

在 `src/backend/.env` 中配置：

```bash
# Pinata IPFS 配置
PINATA_API_KEY=your_api_key
PINATA_SECRET_API_KEY=your_secret_api_key
PINATA_JWT_TOKEN=your_jwt_token
```

### 获取 Pinata 凭证

1. **注册 Pinata 账号**
   - 访问 https://app.pinata.cloud 注册
   - 免费额度：1GB 存储，3000 次/月上传

2. **创建 API Key**
   - 登录 Pinata 控制台
   - 进入 "API Keys" 页面
   - 点击 "Create New API Key"
   - 复制 `API Key` 和 `Secret Access Key`

3. **生成 JWT Token**（推荐）
   - 在 "API Keys" 页面点击 API Key 右侧的 "..."
   - 选择 "Generate JWT"
   - 复制 JWT Token（只显示一次，请妥善保管）

## IPFS 工作流程

### 1. 上传报告

```python
# ipfs_service.py
async def upload_report(report_bytes: bytes, filename: str) -> Optional[str]:
    """
    上传诊断报告到 IPFS
    
    返回:
        IPFS CID (如 "QmXyz...")
        失败返回 None
    """
```

**请求示例：**
```bash
curl -X POST https://api.pinata.cloud/pinning/pinFileToIPFS \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -F "file=@report.pdf;filename=diagnosis_report.pdf" \
  -F 'pinOptions={"public":true}'
```

**响应示例：**
```json
{
  "IpfsHash": "QmXyz123...",
  "PinSize": 245678,
  "Timestamp": "2024-01-15T10:30:00.000Z"
}
```

### 2. 下载报告

从 IPFS 下载报告文件，支持多个网关：

```python
# 网关优先级
1. gateway.pinata.cloud  # 首选，最稳定
2. ipfs.io               # 公共网关
3. cloudflare-ipfs.com   # 备用网关
```

**下载示例：**
```bash
CID="QmXyz123..."
curl "https://gateway.pinata.cloud/ipfs/$CID" -o report.pdf
```

## 常见问题

### 问题 1: 上传失败 - Invalid type for value

**错误信息：**
```
Pinata 上传失败：Invalid type for value. Expected primitive type, got <class 'dict'>: {'public': True}
```

**原因：** `pinOptions` 参数格式错误

**解决方案：** 使用 JSON 字符串而不是 Python 字典

```python
# ❌ 错误
data = {"pinOptions": {"public": True}}

# ✅ 正确
data = {"pinOptions": '{"public":true}'}
```

### 问题 2: 下载报告超时

**错误信息：**
```
无法下载报告：所有 IPFS 网关均不可用
```

**原因：** 网络问题或网关不可达

**解决方案：**

1. **检查网关连通性：**
```bash
CID="your_cid"
curl -I --connect-timeout 10 "https://gateway.pinata.cloud/ipfs/$CID"
```

2. **使用 Pinata 网关（带认证）：**
```python
headers = {"Authorization": f"Bearer {jwt_token}"}
response = await client.get(
    f"https://{cid}.ipfs.pinata.cloud",
    headers=headers
)
```

3. **增加超时时间：**
```python
async with httpx.AsyncClient(timeout=120.0) as client:
    # 下载逻辑
```

### 问题 3: 历史记录显示"无报告"

**原因：** 历史记录的 `ipfsCid` 字段为空

**可能的原因：**
1. 诊断时 IPFS 上传失败
2. 上链时未正确存储 `ipfsCid`
3. 使用旧版本代码（未包含 `ipfsCid` 字段）

**解决方案：**
- **新诊断：** 确保 IPFS 配置正确，重启后端
- **历史记录：** 无法恢复，需要重新诊断

### 问题 4: IPFS 客户端未初始化

**错误信息：**
```
⚠️ IPFS 客户端未初始化，跳过上传
```

**原因：** Pinata 凭证未配置或无效

**解决方案：**

1. 检查 `.env` 文件：
```bash
cd src/backend
grep PINATA .env
```

2. 验证凭证有效性：
```bash
JWT_TOKEN=$(grep PINATA_JWT_TOKEN .env | cut -d'=' -f2)
curl -X POST https://api.pinata.cloud/pinning/pinFileToIPFS \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -F "file=@/dev/null"
```

如果返回 `401 Unauthorized`，说明凭证无效，需要重新生成。

## 测试脚本

### 测试 IPFS 上传

```bash
#!/bin/bash
# test_ipfs_upload.sh

cd src/backend
JWT_TOKEN=$(grep "^PINATA_JWT_TOKEN=" .env | cut -d'=' -f2)

echo "测试 IPFS 上传..."
curl -s -X POST https://api.pinata.cloud/pinning/pinFileToIPFS \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -F "file=@/tmp/test.pdf;filename=test_report.pdf" \
  -F 'pinOptions={"public":true}' \
  | python3 -m json.tool
```

### 测试 IPFS 下载

```bash
#!/bin/bash
# test_ipfs_download.sh

CID="QmYourCIDHere"

echo "测试 IPFS 下载..."
echo "1. gateway.pinata.cloud:"
curl -s -w "\nHTTP: %{http_code}\n" "https://gateway.pinata.cloud/ipfs/$CID" | head -5

echo -e "\n2. ipfs.io:"
curl -s -w "\nHTTP: %{http_code}\n" "https://ipfs.io/ipfs/$CID" | head -5
```

## 监控和日志

### 查看上传日志

```bash
# 后端日志中的 IPFS 相关日志
tail -f /tmp/backend.log | grep -E "IPFS|Pinata|upload"
```

**成功日志示例：**
```
✓ 报告已上传 IPFS: QmXyz123...
✓ 诊断已上链：0xabc...
```

**失败日志示例：**
```
⚠️ IPFS 上传失败，继续流程
Pinata 上传失败：Invalid type for value
```

### 检查 Pinata 使用量

登录 Pinata 控制台查看：
- 存储使用量
- 上传次数
- 带宽使用情况

## 最佳实践

### 1. 使用 JWT Token

**推荐：** 使用 `PINATA_JWT_TOKEN` 而不是 `PINATA_API_KEY`/`PINATA_SECRET_API_KEY`

**原因：**
- JWT Token 更安全，有效期更长
- 无需手动生成签名
- 代码更简洁

### 2. 设置公开访问

上传时设置 `pinOptions.public = true`，使文件可以通过公共网关访问：

```python
data = {"pinOptions": '{"public":true}'}
```

### 3. 添加超时和重试

```python
async with httpx.AsyncClient(timeout=60.0) as client:
    for attempt in range(3):
        try:
            response = await client.post(url, files=files, timeout=60)
            break
        except httpx.TimeoutException:
            if attempt == 2:
                raise
            await asyncio.sleep(1)
```

### 4. 验证 CID 格式

上传成功后验证 CID：
```python
import re

def validate_cid(cid: str) -> bool:
    """验证 IPFS CID 格式（CIDv0）"""
    pattern = r'^Qm[1-9A-Za-z]{44}$'
    return bool(re.match(pattern, cid))
```

## 安全建议

1. **不要提交 .env 文件到 Git**
   ```bash
   echo ".env" >> .gitignore
   ```

2. **使用环境变量管理凭证**
   ```python
   jwt_token = os.getenv("PINATA_JWT_TOKEN")  # ✅ 推荐
   jwt_token = "eyJhbGc..."  # ❌ 不推荐
   ```

3. **定期轮换密钥**
   - 每 6-12 个月更换一次 API Key
   - 泄露时立即撤销并重新生成

4. **限制 API Key 权限**
   - 在 Pinata 控制台设置合适的权限
   - 仅授予必要的操作权限

## 相关资源

- [Pinata 官方文档](https://docs.pinata.cloud/)
- [IPFS 文档](https://docs.ipfs.io/)
- [httpx 文档](https://www.python-httpx.org/)

## 更新日志

- 2024-08-26: 添加网关故障排查和测试脚本
- 2024-08-26: 修复 pinOptions 格式问题文档
- 2024-08-24: 初始版本
