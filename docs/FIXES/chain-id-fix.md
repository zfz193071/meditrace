# 链上诊断 ID 验证失败修复

## 问题描述

使用本地生成的诊断 ID (如 `20260826102152_a137e7af1a3412ad`) 在链上验证时返回"未找到该诊断记录"。

## 根本原因

**诊断 ID 生成方式不一致**:

| 位置 | ID 生成方式 | 示例 |
|------|------------|------|
| **后端本地** (`models.py`) | `timestamp + "_" + data_hash[:16]` | `20260826102152_a137e7af1a3412ad` |
| **智能合约** (`DiagnosisRecord.sol`) | `keccak256(dataHash, patient, timestamp)` | `0x8f3a...` (32 字节哈希) |

当使用本地 ID 查询链上记录时，合约中不存在该 ID，因为真正的链上 ID 是通过 `keccak256` 计算出来的完全不同的值。

## 解决方案

**方案 1: 统一使用合约生成的 ID** (已实施)

### 修改内容

1. **`blockchain_client.py`** - 修改 `record_diagnosis` 方法
   - 从合约事件日志中提取合约返回的 `diagnosisId`
   - 在返回结果中添加 `diagnosisId` 字段

```python
# 从事件日志中提取 diagnosisId
event_logs = self.contract.events.DiagnosisRecorded().get_logs(tx_receipt)
if event_logs and len(event_logs) > 0:
    diagnosis_id = self.w3.to_hex(event_logs[0]['args']['diagnosisId'])

return {
    "success": True,
    "txHash": self.w3.to_hex(tx_hash),
    "diagnosisId": diagnosis_id,  # 新增
    ...
}
```

2. **`models.py`** - 标记本地 ID 生成为废弃
   - `generate_diagnosis_id()` 方法添加 `DeprecationWarning`
   - 保留方法仅用于向后兼容

3. **`main.py`** - 调整诊断流程
   - **先上链**，获取合约生成的 `diagnosisId`
   - 使用链上 ID 生成 IPFS 报告文件名
   - 返回时优先使用链上 ID，上链失败时使用本地临时 ID

```python
# 先上链获取 diagnosisId
chain_result = await blockchain.record_diagnosis(...)
chain_diagnosis_id = chain_result.get("diagnosisId")

# 使用链上 ID 生成报告
report_id = chain_diagnosis_id if chain_diagnosis_id else f"temp_{timestamp}"

# 返回时优先使用链上 ID
final_diagnosis_id = chain_diagnosis_id if chain_diagnosis_id else f"offline_{timestamp}..."
```

### 优势

- ✅ 完全去中心化，ID 由合约保证唯一性
- ✅ 验证时直接使用返回的 ID，无需映射表
- ✅ 简化架构，减少状态同步问题

### 测试步骤

1. 启动后端服务:
   ```bash
   cd src/backend
   source venv/bin/activate
   python3 main.py
   ```

2. 调用诊断 API:
   ```bash
   curl -X POST http://localhost:8000/api/diagnose \
     -H "Content-Type: application/json" \
     -d '{"symptoms": "fever and headache", "userId": "user123"}'
   ```

3. 检查返回的 `diagnosisId` 格式 (应为 `0x...` 开头的 32 字节哈希)

4. 验证链上记录:
   ```bash
   curl http://localhost:8000/api/verify/{diagnosisId}
   ```

## 相关文件

- `src/backend/blockchain_client.py` - 区块链客户端
- `src/backend/models.py` - 诊断元数据模型
- `src/backend/main.py` - API 主逻辑
- `src/contracts/contracts/DiagnosisRecord.sol` - 智能合约

## 注意事项

1. **上链失败降级**: 如果区块链不可用，系统会使用本地临时 ID，但此时无法进行链上验证
2. **事件日志解析**: 确保 Web3.py 版本兼容，使用正确的 API (`get_logs` vs `process_receipt`)
3. **患者地址**: 当前使用账户地址作为患者地址，生产环境应使用真正的用户钱包地址

## 后续改进

- [ ] 添加本地 ID 到链上 ID 的映射缓存 (Redis)
- [ ] 支持用户自定义钱包地址
- [ ] 添加批量验证 API
- [ ] 实现离线诊断记录的后续上链同步
