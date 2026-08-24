// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title DiagnosisRecord
 * @dev 存储医疗 AI 诊断记录的溯源信息
 */
contract DiagnosisRecord {
    struct Record {
        bytes32 dataHash;        // 诊断数据 SHA-256 哈希
        string modelVersion;     // 模型版本
        uint256 timestamp;       // 时间戳
        string ipfsCid;          // IPFS 报告 CID
        address patient;         // 患者地址
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
    
    /**
     * @dev 获取患者的诊断记录数量
     * @param _patient 患者地址
     * @return 记录数量
     */
    function getPatientRecordCount(address _patient)
        external
        view
        returns (uint256)
    {
        return patientRecords[_patient].length;
    }
}
