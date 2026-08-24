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
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

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


# 诊断 API (MVP 版本 - 返回 mock 数据)
@app.post("/api/diagnose", response_model=DiagnosisResponse)
async def diagnose(input: SymptomInput):
    """
    接收症状描述，返回 AI 诊断建议
    
    MVP 版本：返回 mock 数据
    TODO: 集成 DeepSeek API + RAG
    """
    try:
        # 生成数据哈希
        data_string = f"{input.symptoms}:{input.userId}"
        data_hash = hashlib.sha256(data_string.encode()).hexdigest()
        
        # TODO: 调用 DeepSeek API 获取真实诊断
        # 当前返回 mock 数据
        suggestions = [
            {
                "disease": "上呼吸道感染",
                "confidence": 0.75,
                "recommendations": ["血常规检查", "体温监测", "多休息"]
            },
            {
                "disease": "流感",
                "confidence": 0.50,
                "recommendations": ["流感病毒检测", "退烧药", "隔离观察"]
            }
        ]
        
        disclaimer = (
            "重要提示：本系统提供的诊断建议仅供参考，不能替代专业医疗意见。"
            "请咨询合格医疗专业人士获取准确诊断和治疗建议。如有紧急医疗情况，"
            "请立即联系当地急救服务。"
        )
        
        # TODO: 生成 PDF 报告并上传 IPFS
        # TODO: 调用智能合约上链
        
        return {
            "diagnosisId": data_hash[:16],
            "suggestions": suggestions,
            "disclaimer": disclaimer,
            "ipfsCid": None,  # TODO
            "chainTxHash": None  # TODO
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
