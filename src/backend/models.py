"""
诊断元数据模型
封装诊断相关的元数据，避免参数分散传递
"""

from dataclasses import dataclass
import hashlib
from typing import Optional, List, Dict, Any
from datetime import datetime
import warnings
import uuid
import sqlite3


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


# ============================================================================
# Conversation Models (for multi-turn dialogue system - SPEC-0005)
# ============================================================================

class Conversation:
    """对话 ORM 模型"""
    
    def __init__(
        self,
        patient_id: str,
        title: str,
        id: Optional[str] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.id = id or str(uuid.uuid4())
        self.patient_id = patient_id
        self.title = title
        self.created_at = created_at or datetime.now()
        self.updated_at = updated_at or datetime.now()
        self.metadata = metadata or {}
        self.messages: List['Message'] = []
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "id": self.id,
            "patientId": self.patient_id,
            "title": self.title,
            "createdAt": int(self.created_at.timestamp()),
            "updatedAt": int(self.updated_at.timestamp()),
            "messageCount": len(self.messages)
        }
    
    def to_api_response(self) -> Dict[str, Any]:
        """转换为 API 响应格式"""
        return {
            "conversationId": self.id,
            "patientId": self.patient_id,
            "title": self.title,
            "createdAt": int(self.created_at.timestamp())
        }


class Message:
    """消息 ORM 模型"""
    
    def __init__(
        self,
        conversation_id: str,
        role: str,
        content: str,
        id: Optional[str] = None,
        timestamp: Optional[datetime] = None,
        context_refs: Optional[List[str]] = None
    ):
        self.id = id or str(uuid.uuid4())
        self.conversation_id = conversation_id
        self.role = role  # 'user' or 'assistant'
        self.content = content
        self.timestamp = timestamp or datetime.now()
        self.context_refs = context_refs or []
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "id": self.id,
            "conversationId": self.conversation_id,
            "role": self.role,
            "content": self.content,
            "timestamp": int(self.timestamp.timestamp()),
            "contextRefs": self.context_refs
        }
    
    def to_api_response(self) -> Dict[str, Any]:
        """转换为 API 响应格式"""
        return {
            "messageId": self.id,
            "role": self.role,
            "content": self.content,
            "timestamp": int(self.timestamp.timestamp())
        }
