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
from datetime import datetime

# 加载环境变量
load_dotenv(override=True)

# 导入 DeepSeek 客户端
from deepseek_client import get_deepseek_client

# 导入区块链客户端
from blockchain_client import get_blockchain_client

# 导入 IPFS 服务
from ipfs_service import get_ipfs_client, generate_report

# 导入数据模型
from models import DiagnosisMetadata, DiagnosisResult

# 导入工具函数
from utils.hex_utils import to_hex_str


def get_cors_origins() -> list[str]:
    """
    从环境变量获取 CORS 允许的来源列表
    
    环境变量格式：逗号分隔的 URL 列表
    例如：CORS_ORIGINS=http://localhost:3000,http://localhost:8000
    """
    cors_origins_env = os.getenv("CORS_ORIGINS")
    if cors_origins_env:
        return [origin.strip() for origin in cors_origins_env.split(",")]
    
    # 默认开发环境配置
    return [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000",
    ]


# CORS 配置 - 必须在 FastAPI app 创建后立即添加，且在所有其他中间件之前
app = FastAPI(
    title="MediTrace API",
    description="医疗 AI 诊断溯源系统后端 API",
    version="0.1.0"
)

# 添加 CORS 中间件 - 允许前端访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Diagnosis-ID, X-Chain-Tx-Hash"],
    max_age=3600,
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
    chainRecord: Optional[dict]
    ipfsCid: str


# 健康检查
@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "0.1.0"}


# 辅助函数 (提取重复逻辑)
async def _chain_diagnosis(metadata: DiagnosisMetadata, input: SymptomInput):
    """
    将诊断记录上链
    
    Returns:
        tuple: (chain_tx_hash, chain_status, chain_diagnosis_id)
    """
    chain_tx_hash = None
    chain_status = "pending"
    chain_diagnosis_id = None
    
    try:
        blockchain = get_blockchain_client()
        if blockchain:
            # 获取账户地址作为患者地址 (用于测试)
            # 实际生产中应该使用真正的用户钱包地址
            account = blockchain.get_account()
            if account:
                patient_addr = account.address
            else:
                # 如果没有配置私钥，使用 userId 生成的伪地址 (仅用于测试查询)
                patient_addr = input.userId if input.userId.startswith("0x") else f"0x{input.userId}"
            
            # 更新元数据中的患者地址
            metadata.patient_address = patient_addr
            
            # 使用元数据对象的方法获取上链参数
            chain_params = metadata.to_chain_params()
            
            chain_result = await blockchain.record_diagnosis(
                data_hash=f"0x{chain_params[0]}",
                model_version=chain_params[1],
                ipfs_cid=chain_params[2] or "",
                patient_address=patient_addr
            )
            
            if chain_result.get("success"):
                chain_tx_hash = chain_result.get("txHash")
                chain_diagnosis_id = chain_result.get("diagnosisId")
                chain_status = "confirmed"
                print(f"✓ 诊断已上链：{chain_tx_hash}")
                print(f"✓ 链上诊断 ID: {chain_diagnosis_id}")
            else:
                print(f"⚠️ 上链失败：{chain_result.get('error')}")
                chain_status = "failed"
                
    except Exception as e:
        print(f"⚠️ 上链异常：{e}")
        chain_status = "failed"
    
    return chain_tx_hash, chain_status, chain_diagnosis_id


async def _upload_ipfs_report(symptoms: str, suggestions: list, disclaimer: str, chain_diagnosis_id: Optional[str]):
    """
    生成诊断报告并上传 IPFS
    
    Returns:
        ipfs_cid: IPFS CID 字符串
    """
    ipfs_cid = ""
    try:
        # 优先使用链上 diagnosisId，如果没有则使用时间戳临时 ID
        report_id = chain_diagnosis_id if chain_diagnosis_id else f"temp_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        report_bytes = generate_report(
            symptoms=symptoms,
            suggestions=suggestions,
            disclaimer=disclaimer,
            diagnosis_id=report_id
        )
        
        ipfs = get_ipfs_client()
        if ipfs:
            ipfs_cid = await ipfs.upload_report(report_bytes, f"{report_id}_report.txt")
            if ipfs_cid:
                print(f"✓ 报告已上传 IPFS: {ipfs_cid}")
            else:
                print("⚠️ IPFS 上传失败，继续流程")
        else:
            print("⚠️ IPFS 客户端未初始化，跳过上传")
            
    except Exception as e:
        print(f"⚠️ 报告生成/上传异常：{e}")
    
    return ipfs_cid


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
        
        # 先生成报告并上传 IPFS（需要先有 CID 再上链）
        # 使用时间戳临时 ID 上传
        ipfs_cid = await _upload_ipfs_report(
            input.symptoms, suggestions, disclaimer, None
        )
        
        # IPFS 上传失败时阻止上链
        if not ipfs_cid:
            raise HTTPException(
                status_code=500, 
                detail="报告上传失败：IPFS 服务不可用，请检查配置（Pinata 密钥或本地 IPFS 节点）"
            )
        
        # 更新元数据中的 IPFS CID
        metadata.ipfs_cid = ipfs_cid
        
        # 尝试上链 (异步，不阻塞主流程)
        # 此时 metadata 已包含 ipfs_cid，上链时会一起提交
        chain_tx_hash, chain_status, chain_diagnosis_id = await _chain_diagnosis(
            metadata, input
        )
        
        # 使用结果对象封装返回数据
        # 优先使用链上 diagnosisId，如果上链失败则使用本地临时 ID
        final_diagnosis_id = chain_diagnosis_id if chain_diagnosis_id else f"offline_{datetime.now().strftime('%Y%m%d%H%M%S')}_{metadata.generate_data_hash()[:16]}"
        
        diag_result = DiagnosisResult(
            diagnosis_id=final_diagnosis_id,
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
        print(f"🔍 查询用户 {userId} 的历史记录...")
        # 使用 userId 作为患者地址查询记录
        # 注意：实际生产中应该使用真正的钱包地址
        diagnosis_ids = blockchain.get_patient_records(userId)
        print(f"✓ 找到 {len(diagnosis_ids)} 条记录")
        
        records = []
        for i, diag_id_bytes in enumerate(diagnosis_ids):
            # 将 bytes 转换为 hex 字符串
            diag_id_hex = to_hex_str(diag_id_bytes)
            
            # 获取每条记录的详细信息
            record = blockchain.verify_diagnosis(diag_id_bytes)
            if record:
                records.append({
                    "diagnosisId": diag_id_hex,
                    "timestamp": record.get("timestamp", 0),
                    "diseaseTypes": [],  # 疾病类型需要从诊断数据中解析
                    "chainStatus": "confirmed" if record else "pending"
                })
        
        print(f"✓ 返回 {len(records)} 条记录")
        return {"records": records}
        
    except Exception as e:
        # 区块链查询失败时返回空列表，不影响用户体验
        print(f"⚠️ 历史记录查询失败：{e}")
        import traceback
        traceback.print_exc()
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
            # 将 bytes 类型的 dataHash 转换为 hex 字符串
            data_hash = record.get("dataHash", b"")
            if isinstance(data_hash, bytes):
                data_hash = to_hex_str(data_hash)
            
            return {
                "isValid": True,
                "chainRecord": {
                    "dataHash": data_hash,
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


# 下载报告
@app.get("/api/report/{diagnosisId}")
async def download_report(diagnosisId: str):
    """
    下载诊断报告
    
    从 IPFS 获取报告文件并返回给前端
    """
    # 首先从区块链获取记录的 IPFS CID
    blockchain = get_blockchain_client()
    if not blockchain:
        raise HTTPException(status_code=500, detail="区块链服务不可用")
    
    record = blockchain.verify_diagnosis(diagnosisId)
    if not record:
        # 诊断记录不存在于区块链
        raise HTTPException(status_code=404, detail=f"诊断记录不存在：{diagnosisId}")
    
    ipfs_cid = record.get("ipfsCid", "")
    
    if not ipfs_cid:
        # 记录存在但没有 IPFS CID，可能是上链时 IPFS 上传失败
        raise HTTPException(
            status_code=404, 
            detail=f"报告未找到：该诊断记录尚未生成报告 (IPFS CID 为空)。请重新进行诊断以生成报告。"
        )
    
    # 从 IPFS 下载报告
    import httpx
    import os
    
    # 使用 Pinata API 直接下载（使用 JWT token）
    jwt_token = os.getenv("PINATA_JWT_TOKEN")
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        # 使用 Pinata API 下载文件
        headers = {"Authorization": f"Bearer {jwt_token}"} if jwt_token else {}
        
        # 尝试多个网关，提高成功率
        gateways = [
            f"https://{ipfs_cid}.ipfs.pinata.cloud",
            f"https://ipfs.io/ipfs/{ipfs_cid}",
            f"https://cloudflare-ipfs.com/ipfs/{ipfs_cid}"
        ]
        
        response = None
        for gateway_url in gateways:
            try:
                print(f"尝试下载：{gateway_url}")
                response = await client.get(gateway_url, headers=headers)
                if response.status_code == 200:
                    print(f"✓ 成功从 {gateway_url} 下载报告")
                    break
                else:
                    print(f"⚠️ {gateway_url} 返回 {response.status_code}")
                    response = None
            except Exception as e:
                print(f"⚠️ {gateway_url} 连接失败：{e}")
                response = None
        
        if not response:
            raise HTTPException(
                status_code=500, 
                detail=f"无法下载报告：所有 IPFS 网关均不可用，请稍后重试"
            )
        
        if response.status_code == 404:
            raise HTTPException(status_code=404, detail=f"IPFS 报告不存在：{ipfs_cid}")
        
        response.raise_for_status()
        
        # 返回报告文件
        from fastapi.responses import Response
        return Response(
            content=response.content,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=diagnosis-report-{diagnosisId}.pdf"
            }
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
