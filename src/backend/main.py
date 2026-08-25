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
        # 生成数据哈希
        data_string = f"{input.symptoms}:{input.userId}"
        data_hash = hashlib.sha256(data_string.encode()).hexdigest()
        
        # 调用 DeepSeek API 获取真实诊断
        deepseek_client = get_deepseek_client()
        result = await deepseek_client.diagnose(input.symptoms)
        
        suggestions = result.get("suggestions", [])
        disclaimer = result.get("disclaimer", "")
        
        # 验证返回数据
        if not suggestions:
            raise HTTPException(status_code=500, detail="AI 诊断失败：未返回建议")
        
        # 模型版本
        model_version = "deepseek-chat-v1-medkb-2024q1"
        
        # 生成诊断 ID
        diagnosis_id = data_hash[:16]
        
        # 生成 PDF 报告并上传 IPFS
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
        
        # 尝试上链 (异步，不阻塞主流程)
        chain_tx_hash = None
        try:
            blockchain = get_blockchain_client()
            if blockchain:
                # 将患者地址转换为 Web3 格式
                patient_addr = input.userId if input.userId.startswith("0x") else f"0x{input.userId}"
                
                chain_result = await blockchain.record_diagnosis(
                    data_hash=f"0x{data_hash}",
                    model_version=model_version,
                    ipfs_cid=ipfs_cid or "",
                    patient_address=patient_addr
                )
                
                if chain_result.get("success"):
                    chain_tx_hash = chain_result.get("txHash")
                    print(f"✓ 诊断已上链：{chain_tx_hash}")
                else:
                    print(f"⚠️ 上链失败：{chain_result.get('error')}")
                    
        except Exception as e:
            print(f"⚠️ 上链异常：{e}")
            # 上链失败不影响诊断流程
        
        return {
            "diagnosisId": diagnosis_id,
            "suggestions": suggestions,
            "disclaimer": disclaimer,
            "ipfsCid": ipfs_cid,
            "chainTxHash": chain_tx_hash
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"诊断失败：{str(e)}")


# 历史记录查询
@app.get("/api/history/{userId}", response_model=HistoryResponse)
async def get_history(userId: str):
    """
    获取用户的诊断历史记录
    
    MVP 版本：返回 mock 数据
    TODO: 从数据库/区块链查询
    """
    # TODO: 实现真实查询
    return {
        "records": [
            {
                "diagnosisId": "abc12345",
                "timestamp": 1704067200,
                "diseaseTypes": ["上呼吸道感染"],
                "chainStatus": "confirmed"
            }
        ]
    }


# 链上验证
@app.get("/api/verify/{diagnosisId}", response_model=VerificationResponse)
async def verify_diagnosis(diagnosisId: str):
    """
    验证诊断记录的链上状态
    
    MVP 版本：返回 mock 数据
    TODO: 查询智能合约
    """
    # TODO: 实现真实验证
    return {
        "isValid": True,
        "chainRecord": {
            "dataHash": "sha256_hash_here",
            "modelVersion": "deepseek-v2.5-medkb-2024q1",
            "timestamp": 1704067200
        },
        "ipfsCid": "QmTest123456789"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
