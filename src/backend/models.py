"""
诊断元数据模型
封装诊断相关的元数据，避免参数分散传递
"""

from dataclasses import dataclass
import hashlib
from typing import Optional
from datetime import datetime


@dataclass
class DiagnosisMetadata:
    """诊断元数据值对象"""
    
    user_id: str
    symptoms: str
    model_version: str
    ipfs_cid: str = ""
    patient_address: str = ""
    
    def generate_data_hash(self) -> str:
        """生成诊断数据哈希"""
        data_string = f"{self.symptoms}:{self.user_id}"
        return hashlib.sha256(data_string.encode()).hexdigest()
    
    def generate_diagnosis_id(self) -> str:
        """
        生成诊断 ID (已废弃，改用合约生成的 ID)
        
        注意：此方法已废弃，诊断 ID 现在由智能合约生成
        以确保全局唯一性和不可篡改性。
        保留此方法仅用于向后兼容。
        """
        import warnings
        warnings.warn(
            "generate_diagnosis_id() is deprecated. Use the diagnosisId returned by the blockchain contract.",
            DeprecationWarning,
            stacklevel=2
        )
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        data_hash = self.generate_data_hash()
        return f"{timestamp}_{data_hash[:16]}"
    
    def to_chain_params(self) -> tuple:
        """返回上链所需的参数元组"""
        return (
            self.generate_data_hash(),
            self.model_version,
            self.ipfs_cid,
            self.patient_address or self.user_id
        )


@dataclass
class DiagnosisResult:
    """诊断结果封装"""
    
    diagnosis_id: str
    suggestions: list
    disclaimer: str
    metadata: DiagnosisMetadata
    ipfs_cid: str = ""
    chain_tx_hash: str = ""
    chain_status: str = "pending"
    
    def to_api_response(self) -> dict:
        """转换为 API 响应格式"""
        return {
            "diagnosisId": self.diagnosis_id,
            "suggestions": self.suggestions,
            "disclaimer": self.disclaimer,
            "modelVersion": self.metadata.model_version,
            "dataHash": self.metadata.generate_data_hash(),
            "ipfsCid": self.ipfs_cid,
            "chainTxHash": self.chain_tx_hash if self.chain_tx_hash else None,
            "chainStatus": self.chain_status,
            "timestamp": int(datetime.now().timestamp())
        }
