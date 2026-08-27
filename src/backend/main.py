"""
MediTrace Backend API
医疗 AI 诊断溯源系统后端服务
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional
import hashlib
import os
import json
from dotenv import load_dotenv
import asyncio
from datetime import datetime


def camel_case_generator(value: str) -> str:
    """将 snake_case 转换为 camelCase"""
    parts = value.split('_')
    return parts[0] + ''.join(word.capitalize() for word in parts[1:])


# Pydantic v2 配置基类
class BaseApiModel(BaseModel):
    """API 模型基类，自动将字段名转换为 camelCase"""
    model_config = {
        'populate_by_name': True,
    }
    
    # Pydantic v2 使用 model_dump 时的别名配置
    @classmethod
    def model_dump_json(cls, *args, **kwargs):
        # 使用别名输出 JSON
        if 'by_alias' not in kwargs:
            kwargs['by_alias'] = True
        return super().model_dump_json(*args, **kwargs)

# 加载环境变量
load_dotenv(override=True)

# 导入 DeepSeek 客户端
from deepseek_client import get_deepseek_client

# 导入区块链客户端
from blockchain_client import get_blockchain_client

# 导入 IPFS 服务
from ipfs_service import get_ipfs_client, generate_report

# 导入数据模型
from models import DiagnosisMetadata, DiagnosisResult, Conversation, Message

# 导入工具函数
from utils.hex_utils import to_hex_str

# 导入数据库
from database import init_database, get_db


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


class DiagnosisSuggestion(BaseApiModel):
    disease: str = Field(..., alias="disease")
    confidence: float = Field(..., alias="confidence")
    recommendations: List[str] = Field(..., alias="recommendations")


class DiagnosisResponse(BaseApiModel):
    diagnosis_id: str = Field(..., alias="diagnosisId")
    suggestions: List[DiagnosisSuggestion] = Field(..., alias="suggestions")
    disclaimer: str = Field(..., alias="disclaimer")
    ipfs_cid: Optional[str] = Field(None, alias="ipfsCid")
    chain_tx_hash: Optional[str] = Field(None, alias="chainTxHash")


class HistoryRecord(BaseApiModel):
    diagnosis_id: str = Field(..., alias="diagnosisId")
    timestamp: int = Field(..., alias="timestamp")
    disease_types: List[str] = Field(..., alias="diseaseTypes")
    chain_status: str = Field(..., alias="chainStatus")
    ipfs_cid: Optional[str] = Field(None, alias="ipfsCid")


class HistoryResponse(BaseApiModel):
    records: List[HistoryRecord] = Field(..., alias="records")


class VerificationResponse(BaseApiModel):
    is_valid: bool = Field(..., alias="isValid")
    chain_record: Optional[dict] = Field(None, alias="chainRecord")
    ipfs_cid: str = Field(..., alias="ipfsCid")


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
                    "diagnosis_id": diag_id_hex,
                    "timestamp": record.get("timestamp", 0),
                    "disease_types": [],  # 疾病类型需要从诊断数据中解析
                    "chain_status": "confirmed" if record else "pending",
                    "ipfs_cid": record.get("ipfsCid", "")  # 添加 IPFS CID 字段
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
                "is_valid": True,
                "chain_record": {
                    "data_hash": data_hash,
                    "model_version": record.get("modelVersion", ""),
                    "timestamp": record.get("timestamp", 0)
                },
                "ipfs_cid": record.get("ipfsCid", "")
            }
        else:
            # 记录不存在
            return {
                "is_valid": False,
                "chain_record": None,
                "ipfs_cid": ""
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
        # 提供更有用的错误信息，包含诊断 ID 供排查
        raise HTTPException(
            status_code=404, 
            detail=f"报告未找到：诊断 ID {diagnosisId} 的记录中 IPFS CID 为空。可能的原因：1) 诊断时 IPFS 上传失败 2) 上链时未正确存储 CID。请联系技术支持。"
        )
    
    # 从 IPFS 下载报告
    import httpx
    import os
    
    # 使用 Pinata API 直接下载（使用 JWT token）
    jwt_token = os.getenv("PINATA_JWT_TOKEN")
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        # 如果有 JWT token，使用 Pinata 网关（带认证）
        # 否则使用公共网关
        if jwt_token:
            headers = {"Authorization": f"Bearer {jwt_token}"}
            # 优先使用 Pinata 网关（带认证）
            gateways = [
                (f"https://{ipfs_cid}.ipfs.pinata.cloud", headers, 60, "gateway"),
                (f"https://gateway.pinata.cloud/ipfs/{ipfs_cid}", headers, 60, "gateway"),
                (f"https://ipfs.io/ipfs/{ipfs_cid}", {}, 60, "gateway"),
                (f"https://cloudflare-ipfs.com/ipfs/{ipfs_cid}", {}, 60, "gateway")
            ]
        else:
            # 没有 JWT token，只使用公共网关
            gateways = [
                (f"https://gateway.pinata.cloud/ipfs/{ipfs_cid}", {}, 60, "gateway"),
                (f"https://ipfs.io/ipfs/{ipfs_cid}", {}, 60, "gateway"),
                (f"https://cloudflare-ipfs.com/ipfs/{ipfs_cid}", {}, 60, "gateway"),
                (f"https://{ipfs_cid}.ipfs.pinata.cloud", {}, 60, "gateway")
            ]
        
        response = None
        last_error = None
        for gateway_url, headers, timeout, gateway_type in gateways:
            try:
                print(f"尝试下载 ({gateway_type}): {gateway_url}")
                resp = await client.get(gateway_url, headers=headers, timeout=timeout)
                
                if gateway_type == "api" and resp.status_code == 200:
                    # Pinata API 返回的是 JSON，需要提取文件内容
                    data = resp.json()
                    # 从 API 响应中获取文件内容
                    if data.get("pinData") and data["pinData"].get("metadata") and data["pinData"]["metadata"].get("ipfsIndex"):
                        # 有索引文件，需要获取实际文件内容
                        print("⚠️ Pinata API 返回索引，需要直接下载文件")
                        # 回退到网关下载
                        continue
                    
                    # 尝试从响应中提取文件内容
                    file_content = data.get("data") or data.get("Content")
                    if file_content:
                        print(f"✓ 从 Pinata API 获取到文件元数据")
                        # 实际上我们需要文件内容，所以还是用网关
                        continue
                
                if resp.status_code == 200:
                    print(f"✓ 成功从 {gateway_url} 下载报告")
                    response = resp
                    break
                elif resp.status_code in [401, 403]:
                    print(f"⚠️ {gateway_url} 需要认证，跳过")
                    response = None
                else:
                    print(f"⚠️ {gateway_url} 返回 {resp.status_code}")
                    response = None
                    last_error = f"HTTP {resp.status_code}"
            except httpx.TimeoutException:
                print(f"⚠️ {gateway_url} 超时")
                response = None
                last_error = "timeout"
            except Exception as e:
                print(f"⚠️ {gateway_url} 连接失败：{type(e).__name__}: {str(e)[:100]}")
                response = None
                last_error = f"{type(e).__name__}: {str(e)[:100]}"
        
        if not response:
            error_detail = f"无法下载报告：所有 IPFS 网关均不可用 (CID: {ipfs_cid})"
            if last_error:
                error_detail += f" - 最后错误：{last_error}"
            raise HTTPException(
                status_code=500, 
                detail=error_detail
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


# ============================================================================
# Conversation API (多轮对话系统 - SPEC-0005)
# ============================================================================

class CreateConversationRequest(BaseModel):
    patientId: str
    title: str


class MessageRequest(BaseModel):
    content: str
    contextWindow: int = 5


@app.post("/api/conversations")
async def create_conversation(request: CreateConversationRequest):
    """创建新对话"""
    conversation = Conversation(
        patient_id=request.patientId,
        title=request.title
    )
    
    with get_db() as conn:
        conn.execute(
            """INSERT INTO conversations (id, patient_id, title, metadata)
               VALUES (?, ?, ?, ?)""",
            (conversation.id, conversation.patient_id, conversation.title, json.dumps({}))
        )
    
    return {
        "conversationId": conversation.id,
        "patientId": conversation.patient_id,
        "title": conversation.title,
        "createdAt": int(conversation.created_at.timestamp())
    }


@app.get("/api/conversations")
async def get_conversations(patientId: Optional[str] = None, limit: int = 10, offset: int = 0):
    """获取对话列表"""
    with get_db() as conn:
        if patientId:
            cursor = conn.execute(
                """SELECT id, title, created_at, updated_at,
                          (SELECT COUNT(*) FROM messages WHERE conversation_id = conversations.id) as message_count
                   FROM conversations
                   WHERE patient_id = ?
                   ORDER BY updated_at DESC
                   LIMIT ? OFFSET ?""",
                (patientId, limit, offset)
            )
        else:
            cursor = conn.execute(
                """SELECT id, title, created_at, updated_at,
                          (SELECT COUNT(*) FROM messages WHERE conversation_id = conversations.id) as message_count
                   FROM conversations
                   ORDER BY updated_at DESC
                   LIMIT ? OFFSET ?""",
                (limit, offset)
            )
        
        rows = cursor.fetchall()
        
        count_cursor = conn.execute(
            "SELECT COUNT(*) FROM conversations" + (" WHERE patient_id = ?" if patientId else ""),
            (patientId,) if patientId else ()
        )
        total = count_cursor.fetchone()[0]
    
    conversations = []
    for row in rows:
        conversations.append({
            "id": row["id"],
            "title": row["title"],
            "createdAt": int(row["created_at"].timestamp()) if hasattr(row["created_at"], 'timestamp') else row["created_at"],
            "updatedAt": int(row["updated_at"].timestamp()) if hasattr(row["updated_at"], 'timestamp') else row["updated_at"],
            "messageCount": row["message_count"]
        })
    
    return {"conversations": conversations, "total": total}


@app.get("/api/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    """获取单个对话详情"""
    with get_db() as conn:
        cursor = conn.execute(
            """SELECT * FROM conversations WHERE id = ?""",
            (conversation_id,)
        )
        row = cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        messages_cursor = conn.execute(
            """SELECT * FROM messages WHERE conversation_id = ? ORDER BY timestamp ASC""",
            (conversation_id,)
        )
        messages = messages_cursor.fetchall()
    
    conversation_data = {
        "id": row["id"],
        "patientId": row["patient_id"],
        "title": row["title"],
        "createdAt": int(row["created_at"].timestamp()) if hasattr(row["created_at"], 'timestamp') else row["created_at"],
        "updatedAt": int(row["updated_at"].timestamp()) if hasattr(row["updated_at"], 'timestamp') else row["updated_at"],
        "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
        "messages": [
            {
                "id": m["id"],
                "role": m["role"],
                "content": m["content"],
                "timestamp": int(m["timestamp"].timestamp()) if hasattr(m["timestamp"], 'timestamp') else m["timestamp"],
                "contextRefs": json.loads(m["context_refs"]) if m["context_refs"] else []
            }
            for m in messages
        ]
    }
    
    return conversation_data


@app.delete("/api/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """删除对话"""
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT id FROM conversations WHERE id = ?",
            (conversation_id,)
        )
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
    
    return {"success": True, "message": "Conversation deleted"}


@app.post("/api/conversations/{conversation_id}/messages")
async def send_message(conversation_id: str, request: MessageRequest):
    """发送消息并获取 AI 回复"""
    import uuid
    from context_engine import get_context_engine
    
    # 1. 验证对话存在
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT id FROM conversations WHERE id = ?",
            (conversation_id,)
        )
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Conversation not found")
    
    # 2. 保存用户消息
    user_message_id = str(uuid.uuid4())
    with get_db() as conn:
        conn.execute(
            """INSERT INTO messages (id, conversation_id, role, content, context_refs)
               VALUES (?, ?, ?, ?, ?)""",
            (user_message_id, conversation_id, "user", request.content, json.dumps({}))
        )
    
    # 3. 获取上下文窗口
    context_engine = get_context_engine()
    context_messages = context_engine.get_conversation_context(conversation_id)
    
    # 4. 调用 DeepSeek 客户端
    try:
        deepseek_client = get_deepseek_client()
        diagnosis_result = await deepseek_client.diagnose_with_context(
            conversation_id=conversation_id,
            user_message=request.content,
            context_messages=context_messages
        )
    except Exception as e:
        # 如果 AI 调用失败，回退到简单回复
        diagnosis_result = {
            "suggestions": [{
                "disease": "需要进一步评估",
                "confidence": 0.5,
                "recommendations": ["请咨询专业医生"]
            }],
            "summary": "已收到您的症状描述",
            "disclaimer": "这仅是建议，不能替代专业医疗诊断"
        }
    
    # 5. 保存 AI 消息
    ai_message_id = str(uuid.uuid4())
    ai_content = diagnosis_result.get("summary", "已分析您的症状")
    
    with get_db() as conn:
        conn.execute(
            """INSERT INTO messages (id, conversation_id, role, content, context_refs)
               VALUES (?, ?, ?, ?, ?)""",
            (ai_message_id, conversation_id, "assistant", ai_content, json.dumps(diagnosis_result))
        )
        
        # 更新对话的 updated_at
        conn.execute(
            "UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (conversation_id,)
        )
    
    # 6. 生成追问问题
    follow_up_questions = context_engine.generate_follow_up_questions(diagnosis_result)
    
    return {
        "messageId": ai_message_id,
        "content": ai_content,
        "context": [msg["content"] for msg in context_messages[-3:]],  # 最近 3 条
        "followUpQuestions": follow_up_questions,
        "diagnosisResult": diagnosis_result
    }


# 初始化数据库
@app.on_event("startup")
async def startup_event():
    """启动时初始化数据库"""
    init_database()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
