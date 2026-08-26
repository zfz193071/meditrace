# ADR 0004: IPFS 服务配置问题修复

## 状态

✅ 已解决 (2024-08-26)

## 背景

在开发过程中发现，所有历史诊断记录都无法下载报告，报错"报告未找到"。进一步排查发现，即使新进行的诊断，返回的 `ipfsCid` 也为 `null`。

## 问题

### 症状

1. 诊断 API 返回 `ipfsCid: null`
2. 下载报告 API 返回 404 "报告未找到"
3. 历史记录中所有记录的报告都无法下载

### 根本原因

经过诊断（使用 `/diagnosing-bugs` 流程），发现以下问题：

#### 1. `pinOptions` 参数格式错误

**文件：** `src/backend/ipfs_service.py`

**错误代码：**
```python
data = {
    "pinOptions": {
        "public": True
    }
}
```

**问题：** Pinata API 要求 `pinOptions` 是 JSON 字符串，而不是 Python 字典。

**错误信息：**
```
Pinata 上传失败：Invalid type for value. Expected primitive type, got <class 'dict'>: {'public': True}
```

#### 2. 后端未使用虚拟环境启动

**问题：** 系统 Python 未安装 `httpx` 依赖，但后端进程未使用 `venv` 中的 Python。

**症状：**
```
ModuleNotFoundError: No module named 'httpx'
```

#### 3. IPFS 网关配置不完整

**问题：** 只配置了 `ipfs.io` 和 `cloudflare-ipfs.com`，这两个网关在某些网络环境下不可达。

**症状：**
```
无法下载报告：所有 IPFS 网关均不可用
```

## 决策

### 1. 修复 `pinOptions` 格式

**解决方案：** 使用 JSON 字符串格式

```python
# 修复后
data = {
    "pinOptions": '{"public":true}'  # JSON 字符串
}
```

**理由：** 符合 Pinata API 规范，确保上传成功。

### 2. 强制使用虚拟环境

**解决方案：** 
1. 在 `DEPLOYMENT.md` 中明确说明必须使用 venv
2. 提供验证命令确认依赖安装
3. 使用 `./venv/bin/python3` 直接启动

```bash
# 推荐方式
./venv/bin/python3 -m uvicorn main:app --host 0.0.0.0 --port 8000

# 或激活后启动
source venv/bin/activate
python3 -m uvicorn main:app
```

**理由：** 确保依赖隔离，避免系统 Python 缺少依赖的问题。

### 3. 添加 `gateway.pinata.cloud` 作为首选网关

**解决方案：** 更新网关优先级

```python
gateways = [
    (f"https://gateway.pinata.cloud/ipfs/{ipfs_cid}", {}, 60, "gateway"),  # 首选
    (f"https://ipfs.io/ipfs/{ipfs_cid}", {}, 60, "gateway"),
    (f"https://cloudflare-ipfs.com/ipfs/{ipfs_cid}", {}, 60, "gateway")
]
```

**理由：** Pinata 官方网关最稳定，成功率最高。

## 后果

### 正面影响

1. ✅ 诊断报告可以正常上传到 IPFS
2. ✅ 下载报告功能恢复正常
3. ✅ 新的诊断记录都有有效的 `ipfsCid`
4. ✅ 减少了部署配置错误

### 负面影响

1. ⚠️ 历史记录的 `ipfsCid` 仍然为空，无法恢复
2. ⚠️ 需要用户重新进行诊断才能下载报告

### 缓解措施

1. 在前端显示"无报告"时提供清晰的提示信息
2. 在文档中详细说明配置要求
3. 添加启动检查脚本验证依赖和环境

## 验证

### 测试脚本

```bash
# 测试 IPFS 上传
/tmp/test_diagnose.sh

# 预期输出
✅ 成功：ipfsCid 有值
✅ 下载报告成功
```

### 日志验证

```bash
tail -f /tmp/backend.log | grep -E "✓|IPFS"

# 成功日志
✓ 报告已上传 IPFS: QmXyz...
✓ 诊断已上链：0xabc...
✓ 成功从 https://gateway.pinata.cloud/ipfs/QmXyz... 下载报告
```

## 相关文档

- [DEPLOYMENT.md](../../DEPLOYMENT.md) - 部署指南（已更新）
- [docs/IPFS_SETUP.md](IPFS_SETUP.md) - IPFS 配置指南（新建）
- [README.md](../../README.md) - 项目概述（已更新）

## 参考

- [Pinata API 文档](https://docs.pinata.cloud/)
- [httpx 文档](https://www.python-httpx.org/)
- Bug 诊断报告（2024-08-26）

## 更新记录

- 2024-08-26: 初始版本，记录问题和解决方案
