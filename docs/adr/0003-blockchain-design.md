# ADR 0003: 区块链智能合约设计

**状态**: 已接受
**日期**: 2024
**决策者**: 项目团队

---

## 背景

需要设计智能合约来存储诊断记录的溯源信息。关键设计决策包括：存储哪些数据？如何保证隐私？如何支持查询？

## 考虑的方案

### 数据存储方案

#### 方案 A: 完整数据上链

**描述**: 将诊断的完整数据（症状、建议等）直接存储在合约中。

**优点**:
- 数据完全去中心化
- 无需依赖外部存储

**缺点**:
- Gas 费用极高
- 暴露敏感医疗数据
- 合约存储有限

#### 方案 B: 哈希上链 + IPFS 存储

**描述**: 链上仅存数据哈希和 IPFS CID，完整数据存储在 IPFS。

**优点**:
- Gas 费用低
- 数据可加密存储在 IPFS
- 支持大文件（如 PDF 报告）
- 哈希保证完整性

**缺点**:
- 依赖 IPFS 节点持久性
- 需要额外存储层

#### 方案 C: 中心化存储 + 链上哈希

**描述**: 数据存储在传统服务器，链上仅存哈希。

**优点**:
- 成本低
- 性能好

**缺点**:
- 失去去中心化优势
- 单点故障风险

### 身份方案

#### 方案 A: 钱包地址作为身份

**描述**: 用户通过钱包连接，地址作为唯一标识。

**优点**:
- 无需注册
- 隐私保护
- 天然支持签名验证

**缺点**:
- 用户需要钱包
- 地址无法恢复（丢失私钥）

#### 方案 B: 传统账号 + 钱包绑定

**描述**: 邮箱/手机号注册，可选绑定钱包。

**优点**:
- 用户友好
- 支持账号恢复

**缺点**:
- 需要用户系统
- 复杂度增加
- 隐私风险

### 查询方案

#### 方案 A: 映射查询

**描述**: 使用 `mapping(diagnosisId => Record)` 直接查询。

**优点**:
- O(1) 复杂度
- 简单直接

**缺点**:
- 需要知道 diagnosisId

#### 方案 B: 患者记录列表

**描述**: 额外维护 `mapping(patient => diagnosisId[])` 列表。

**优点**:
- 支持按患者查询所有记录
- 便于前端展示历史

**缺点**:
- Gas 成本略高（需维护两个映射）

#### 方案 C: 事件索引查询

**描述**: 通过事件日志查询，不存于合约状态。

**优点**:
- Gas 成本最低

**缺点**:
- 查询复杂
- 历史事件可能丢失

## 决策

### 数据存储：方案 B (哈希上链 + IPFS 存储)

**理由**:
1. **隐私保护**: 链上不存明文数据，符合医疗隐私要求
2. **成本可控**: 仅存储哈希和 CID，Gas 费用可接受
3. **完整性验证**: 哈希保证数据未被篡改
4. **可扩展性**: IPFS 支持任意大小文件（PDF 报告）

**实现细节**:
```solidity
struct Record {
    bytes32 dataHash;        // 诊断数据 SHA-256 哈希
    string modelVersion;     // 模型版本
    uint256 timestamp;       // 时间戳
    string ipfsCid;          // IPFS 报告 CID
    address patient;         // 患者地址
}
```

### 身份方案：方案 A (钱包地址作为身份)

**理由**:
1. **隐私优先**: 无需收集邮箱/手机号
2. **Web3 原生**: 符合项目定位
3. **实现简单**: 无需用户系统
4. **签名验证**: 可验证记录归属

**缓解措施**:
- README 中说明可用测试钱包
- 提供 MetaMask 安装指南

### 查询方案：方案 A + B 组合

**理由**:
1. **直接查询**: `getRecord(diagnosisId)` 用于验证
2. **列表查询**: `getPatientRecords(patient)` 用于历史展示
3. **平衡成本与功能**: 维护两个映射的 Gas 成本可接受

## 最终合约设计

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract DiagnosisRecord {
    struct Record {
        bytes32 dataHash;
        string modelVersion;
        uint256 timestamp;
        string ipfsCid;
        address patient;
    }
    
    // 主映射：diagnosisId => Record
    mapping(bytes32 => Record) public records;
    
    // 患者记录列表：patient => diagnosisId[]
    mapping(address => bytes32[]) public patientRecords;
    
    // 事件：便于 off-chain 索引
    event DiagnosisRecorded(
        bytes32 indexed diagnosisId,
        address indexed patient,
        uint256 timestamp
    );
    
    /**
     * @dev 记录一次诊断
     * @param _dataHash 诊断数据哈希
     * @param _modelVersion 模型版本
     * @param _ipfsCid IPFS 报告 CID
     * @param _patient 患者地址
     * @return diagnosisId 诊断记录 ID
     */
    function recordDiagnosis(
        bytes32 _dataHash,
        string memory _modelVersion,
        string memory _ipfsCid,
        address _patient
    ) external returns (bytes32) {
        bytes32 diagnosisId = keccak256(
            abi.encodePacked(_dataHash, _patient, block.timestamp)
        );
        
        records[diagnosisId] = Record({
            dataHash: _dataHash,
            modelVersion: _modelVersion,
            timestamp: block.timestamp,
            ipfsCid: _ipfsCid,
            patient: _patient
        });
        
        patientRecords[_patient].push(diagnosisId);
        
        emit DiagnosisRecorded(diagnosisId, _patient, block.timestamp);
        
        return diagnosisId;
    }
    
    /**
     * @dev 获取诊断记录
     * @param _diagnosisId 诊断 ID
     * @return 记录详情
     */
    function getRecord(bytes32 _diagnosisId) 
        external 
        view 
        returns (Record memory) 
    {
        return records[_diagnosisId];
    }
    
    /**
     * @dev 获取患者的所有诊断记录 ID
     * @param _patient 患者地址
     * @return diagnosisId 列表
     */
    function getPatientRecords(address _patient)
        external
        view
        returns (bytes32[] memory)
    {
        return patientRecords[_patient];
    }
}
```

## 后果

### 正面后果

- Gas 成本低（仅存储约 150 bytes）
- 隐私保护好（链上无明文）
- 查询功能完整（支持单条和列表）
- 事件日志便于 off-chain 索引

### 负面后果

- 依赖 IPFS 持久性
- 用户需要钱包
- 合约不可升级（简单设计）

### 缓解措施

- 使用 Pinata 等付费 Pin 服务保证 IPFS 持久性
- README 中提供钱包使用指南
- 合约设计简单，易于重新部署

## 验证标准

- [ ] 合约可通过 Hardhat 测试
- [ ] Gas 消耗 < 200,000 per record
- [ ] 支持查询单条记录和患者列表
- [ ] 事件正确触发

## 参考资料

- [Solidity 官方文档](https://docs.soliditylang.org/)
- [IPFS 文档](https://docs.ipfs.io/)
- [ERC 标准参考](https://eips.ethereum.org/)
