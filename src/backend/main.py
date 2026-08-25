"""
MediTrace Backend API
医疗 AI 诊断溯源系统后端服务
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import hashlib
import os
import json
from dotenv import load_dotenv
import asyncio

# 加载环境变量
load_dotenv()

# 导入 DeepSeek 客户端
from deepseek_client import get_deepseek_client

# 导入区块链客户端
from blockchain_client import get_blockchain_client

# 导入 IPFS 服务
from ipfs_service import get_ipfs_client, generate_report

# 导入数据模型
from models import DiagnosisMetadata, DiagnosisResult

app = FastAPI(
    title="MediTrace API",
    description="医疗 AI 诊断溯源系统后端 API",
    version="0.1.0"
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 数据模型
class SymptomInput(BaseModel):
    symptoms: str
    userId: str


class DiagnosisSuggestion(BaseModel):
    disease: str
    confidence: float
    recommendations: List[str]


class DiagnosisResponse(BaseModel):
    diagnosisId: str
    suggestions: List[DiagnosisSuggestion]
    disclaimer: str
    ipfsCid: Optional[str] = None
    chainTxHash: Optional[str] = None


class HistoryRecord(BaseModel):
    diagnosisId: str
    timestamp: int
    diseaseTypes: List[str]
    chainStatus: str


class HistoryResponse(BaseModel):
    records: List[HistoryRecord]


class VerificationResponse(BaseModel):
    isValid: bool
    chainRecord: dict
    ipfsCid: str


# 健康检查
@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "0.1.0"}


# 诊断 API (集成 DeepSeek + 区块链)
@app.post("/api/diagnose", response_model=DiagnosisResponse)
async def diagnose(input: SymptomInput):
    """
    接收症状描述，返回 AI 诊断建议
    
    集成 DeepSeek API + 医学知识库 RAG + 区块链溯源
    """
    try:
        # 创建元数据对象（解决 Data Clumps 问题）
        metadata = DiagnosisMetadata(
            user_id=input.userId,
            symptoms=input.symptoms,
            model_version="deepseek-chat-v1-medkb-2024q1"
        )
        
        # 调用 DeepSeek API 获取真实诊断
        deepseek_client = get_deepseek_client()
        result = await deepseek_client.diagnose(input.symptoms)
        
        suggestions = result.get("suggestions", [])
        disclaimer = result.get("disclaimer", "")
        
        # 验证返回数据
        if not suggestions:
            raise HTTPException(status_code=500, detail="AI 诊断失败：未返回建议")
        
        # 生成诊断 ID
        diagnosis_id = metadata.generate_diagnosis_id()
        
        # 生成报告并上传 IPFS
        ipfs_cid = ""
        try:
            report_bytes = generate_report(
                symptoms=input.symptoms,
                suggestions=suggestions,
                disclaimer=disclaimer,
                diagnosis_id=diagnosis_id
            )
            
            ipfs = get_ipfs_client()
            if ipfs:
                ipfs_cid = await ipfs.upload_report(report_bytes, f"{diagnosis_id}_report.txt")
                if ipfs_cid:
                    print(f"✓ 报告已上传 IPFS: {ipfs_cid}")
                else:
                    print("⚠️ IPFS 上传失败，继续流程")
            else:
                print("⚠️ IPFS 客户端未初始化，跳过上传")
                
        except Exception as e:
            print(f"⚠️ 报告生成/上传异常：{e}")
        
        # 更新元数据中的 IPFS CID
        metadata.ipfs_cid = ipfs_cid
        
        # 尝试上链 (异步，不阻塞主流程)
        chain_tx_hash = None
        chain_status = "pending"
        try:
            blockchain = get_blockchain_client()
            if blockchain:
                # 将患者地址转换为 Web3 格式
                patient_addr = input.userId if input.userId.startswith("0x") else f"0x{input.userId}"
                metadata.patient_address = patient_addr
                
                # 使用元数据对象的方法获取上链参数
                data_hash, model_version, ipfs_cid_param, patient_addr = metadata.to_chain_params()
                
                chain_result = await blockchain.record_diagnosis(
                    data_hash=f"0x{data_hash}",
                    model_version=model_version,
                    ipfs_cid=ipfs_cid_param or "",
                    patient_address=patient_addr
                )
                
                if chain_result.get("success"):
                    chain_tx_hash = chain_result.get("txHash")
                    chain_status = "confirmed"
                    print(f"✓ 诊断已上链：{chain_tx_hash}")
                else:
                    print(f"⚠️ 上链失败：{chain_result.get('error')}")
                    chain_status = "failed"
                    
        except Exception as e:
            print(f"⚠️ 上链异常：{e}")
            chain_status = "failed"
            # 上链失败不影响诊断流程
        
        # 使用结果对象封装返回数据
        diag_result = DiagnosisResult(
            diagnosis_id=diagnosis_id,
            suggestions=suggestions,
            disclaimer=disclaimer,
            metadata=metadata,
            ipfs_cid=ipfs_cid,
            chain_tx_hash=chain_tx_hash,
            chain_status=chain_status
        )
        
        return diag_result.to_api_response()
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"诊断失败：{str(e)}")


# 历史记录查询
@app.get("/api/history/{userId}", response_model=HistoryResponse)
async def get_history(userId: str):
    """
    获取用户的诊断历史记录
    
    从区块链查询用户的诊断记录 ID，然后获取详细信息
    """
    blockchain = get_blockchain_client()
    if not blockchain:
        raise HTTPException(status_code=500, detail="区块链服务不可用")
    
    try:
        # 使用 userId 作为患者地址查询记录
        # 注意：实际生产中应该使用真正的钱包地址
        diagnosis_ids = blockchain.get_patient_records(userId)
        
        records = []
        for diag_id in diagnosis_ids:
            # 获取每条记录的详细信息
            record = blockchain.verify_diagnosis(str(diag_id))
            if record:
                records.append({
                    "diagnosisId": str(diag_id),
                    "timestamp": record.get("timestamp", 0),
                    "diseaseTypes": [],  # 疾病类型需要从诊断数据中解析
                    "chainStatus": "confirmed" if record else "pending"
                })
        
        return {"records": records}
        
    except Exception as e:
        # 区块链查询失败时返回空列表，不影响用户体验
        print(f"⚠️ 历史记录查询失败：{e}")
        return {"records": []}


# 链上验证
@app.get("/api/verify/{diagnosisId}", response_model=VerificationResponse)
async def verify_diagnosis(diagnosisId: str):
    """
    验证诊断记录的链上状态
    
    查询智能合约获取真实记录
    """
    blockchain = get_blockchain_client()
    if not blockchain:
        raise HTTPException(status_code=500, detail="区块链服务不可用")
    
    try:
        # 查询智能合约
        record = blockchain.verify_diagnosis(diagnosisId)
        
        if record:
            return {
                "isValid": True,
                "chainRecord": {
                    "dataHash": record.get("dataHash", ""),
                    "modelVersion": record.get("modelVersion", ""),
                    "timestamp": record.get("timestamp", 0)
                },
                "ipfsCid": record.get("ipfsCid", "")
            }
        else:
            # 记录不存在
            return {
                "isValid": False,
                "chainRecord": None,
                "ipfsCid": ""
            }
            
    except Exception as e:
        print(f"⚠️ 链上验证失败：{e}")
        raise HTTPException(status_code=500, detail=f"验证失败：{str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
