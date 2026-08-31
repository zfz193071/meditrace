"""
对话管理 API 路由
支持多轮对话系统的 CRUD 操作
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import json
import uuid
from datetime import datetime
import sys
import os

# 添加父目录到路径以便导入
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_db
from models import Conversation, Message
from context_engine import get_context_engine
from deepseek_client import get_deepseek_client

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


# ============================================================================
# Request/Response Models
# ============================================================================

class CreateConversationRequest(BaseModel):
    patient_id: str = Field(..., description="患者 ID (钱包地址)")
    title: str = Field(..., description="对话标题", min_length=1, max_length=200)


class CreateConversationResponse(BaseModel):
    conversation_id: str
    patient_id: str
    title: str
    created_at: int


class ConversationListItem(BaseModel):
    id: str
    title: str
    created_at: int
    updated_at: int
    message_count: int


class ConversationListResponse(BaseModel):
    conversations: List[ConversationListItem]
    total: int


class MessageRequest(BaseModel):
    content: str = Field(..., description="消息内容", min_length=1)
    context_window: int = Field(default=5, description="上下文窗口大小", ge=1, le=10)


class MessageResponse(BaseModel):
    message_id: str
    content: str
    context: List[str]
    follow_up_questions: List[str]


class UpdateConversationRequest(BaseModel):
    title: str = Field(..., description="新的对话标题", min_length=1, max_length=200)


# ============================================================================
# API Endpoints
# ============================================================================

@router.post("/", response_model=CreateConversationResponse)
def create_conversation(request: CreateConversationRequest):
    """创建新对话"""
    # TODO: 验证 patient_id 格式 (钱包地址)
    
    conversation = Conversation(
        patient_id=request.patient_id,
        title=request.title
    )
    
    with get_db() as conn:
        conn.execute(
            """INSERT INTO conversations (id, patient_id, title, metadata)
               VALUES (?, ?, ?, ?)""",
            (conversation.id, conversation.patient_id, conversation.title, json.dumps({}))
        )
    
    return CreateConversationResponse(
        conversation_id=conversation.id,
        patient_id=conversation.patient_id,
        title=conversation.title,
        created_at=int(conversation.created_at.timestamp())
    )


@router.get("/", response_model=ConversationListResponse)
def get_conversations(
    patient_id: Optional[str] = Query(None, description="患者 ID 过滤"),
    limit: int = Query(10, ge=1, le=100, description="每页数量"),
    offset: int = Query(0, ge=0, description="偏移量")
):
    """获取对话列表"""
    with get_db() as conn:
        if patient_id:
            cursor = conn.execute(
                """SELECT id, title, created_at, updated_at,
                          (SELECT COUNT(*) FROM messages WHERE conversation_id = conversations.id) as message_count
                   FROM conversations
                   WHERE patient_id = ?
                   ORDER BY updated_at DESC
                   LIMIT ? OFFSET ?""",
                (patient_id, limit, offset)
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
        
        # 获取总数
        count_cursor = conn.execute(
            "SELECT COUNT(*) FROM conversations" + ( " WHERE patient_id = ?" if patient_id else "" ),
            (patient_id,) if patient_id else ()
        )
        total = count_cursor.fetchone()[0]
    
    conversations = [
        ConversationListItem(
            id=row["id"],
            title=row["title"],
            created_at=int(row["created_at"].timestamp()) if hasattr(row["created_at"], 'timestamp') else row["created_at"],
            updated_at=int(row["updated_at"].timestamp()) if hasattr(row["updated_at"], 'timestamp') else row["updated_at"],
            message_count=row["message_count"]
        )
        for row in rows
    ]
    
    return ConversationListResponse(conversations=conversations, total=total)


@router.get("/{conversation_id}")
def get_conversation(conversation_id: str):
    """获取单个对话详情"""
    with get_db() as conn:
        # 获取对话信息
        cursor = conn.execute(
            """SELECT * FROM conversations WHERE id = ?""",
            (conversation_id,)
        )
        row = cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        # 获取消息列表
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


@router.delete("/{conversation_id}")
def delete_conversation(conversation_id: str):
    """删除对话 (级联删除消息)"""
    with get_db() as conn:
        # 检查对话是否存在
        cursor = conn.execute(
            "SELECT id FROM conversations WHERE id = ?",
            (conversation_id,)
        )
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        # 删除对话 (级联删除消息)
        conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
    
    return {"success": True, "message": "Conversation deleted"}


@router.put("/{conversation_id}")
def update_conversation(conversation_id: str, request: UpdateConversationRequest):
    """更新对话信息（目前仅支持更新标题）"""
    with get_db() as conn:
        # 检查对话是否存在
        cursor = conn.execute(
            "SELECT id FROM conversations WHERE id = ?",
            (conversation_id,)
        )
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        # 更新标题和更新时间
        conn.execute(
            "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
            (request.title, datetime.now(), conversation_id)
        )
    
    return {"success": True, "message": "Conversation updated", "title": request.title}


@router.post("/{conversation_id}/messages", response_model=MessageResponse)
def send_message(conversation_id: str, request: MessageRequest):
    """发送消息并获取 AI 回复"""
    # 1. 验证对话存在
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT id, patient_id, title FROM conversations WHERE id = ?",
            (conversation_id,)
        )
        conversation_row = cursor.fetchone()
        
        if not conversation_row:
            raise HTTPException(status_code=404, detail="Conversation not found")
    
    # 2. 保存用户消息
    user_message = Message(
        conversation_id=conversation_id,
        role="user",
        content=request.content
    )
    
    with get_db() as conn:
        conn.execute(
            """INSERT INTO messages (id, conversation_id, role, content, context_refs)
               VALUES (?, ?, ?, ?, ?)""",
            (user_message.id, conversation_id, "user", request.content, json.dumps([]))
        )
        # 更新对话的 updated_at
        conn.execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ?",
            (datetime.now(), conversation_id)
        )
    
    # 3. 调用上下文引擎获取 AI 回复
    try:
        context_engine = get_context_engine()
        
        # 获取历史上下文
        context_messages = context_engine.get_conversation_context(conversation_id)
        
        # 调用 DeepSeek API 获取诊断建议
        deepseek_client = get_deepseek_client()
        import asyncio
        
        # 同步调用异步方法
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            diagnosis_result = loop.run_until_complete(
                deepseek_client.diagnose_with_context(conversation_id, request.content, context_messages)
            )
        finally:
            loop.close()
        
        # 解析 AI 回复
        suggestions = diagnosis_result.get("suggestions", [])
        summary = diagnosis_result.get("summary", "")
        disclaimer = diagnosis_result.get("disclaimer", "")
        
        # 构建 AI 回复内容
        ai_content = f"**诊断建议**:\n\n"
        for i, suggestion in enumerate(suggestions, 1):
            confidence = int(suggestion.get("confidence", 0) * 100)
            ai_content += f"{i}. **{suggestion.get('disease', '未知疾病')}** (置信度：{confidence}%)\n"
            recommendations = suggestion.get("recommendations", [])
            if recommendations:
                ai_content += f"   - 建议检查：{', '.join(recommendations)}\n"
            ai_content += "\n"
        
        ai_content += f"\n**总结**: {summary}\n\n"
        ai_content += f"⚠️ **{disclaimer}**"
        
        # 4. 生成追问问题
        follow_up_questions = context_engine.generate_follow_up_questions({
            "symptoms": request.content,
            "confidence": suggestions[0].get("confidence", 1.0) if suggestions else 1.0,
            "possible_conditions": [s.get("disease", "") for s in suggestions]
        })
        
        # 5. 保存 AI 消息
        ai_message = Message(
            conversation_id=conversation_id,
            role="assistant",
            content=ai_content,
            context_refs=[]
        )
        
        with get_db() as conn:
            conn.execute(
                """INSERT INTO messages (id, conversation_id, role, content, context_refs)
                   VALUES (?, ?, ?, ?, ?)""",
                (ai_message.id, conversation_id, "assistant", ai_content, json.dumps([]))
            )
            # 更新对话的 updated_at
            conn.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (datetime.now(), conversation_id)
            )
        
        return MessageResponse(
            message_id=ai_message.id,
            content=ai_content,
            context=[msg["content"] for msg in context_messages[-request.context_window:]],
            follow_up_questions=follow_up_questions
        )
        
    except Exception as e:
        # 如果 AI 调用失败，返回错误消息
        print(f"❌ 对话处理失败：{e}")
        import traceback
        traceback.print_exc()
        
        # 保存错误消息
        error_message = Message(
            conversation_id=conversation_id,
            role="assistant",
            content="抱歉，AI 服务暂时不可用，请稍后重试。"
        )
        
        with get_db() as conn:
            conn.execute(
                """INSERT INTO messages (id, conversation_id, role, content, context_refs)
                   VALUES (?, ?, ?, ?, ?)""",
                (error_message.id, conversation_id, "assistant", error_message.content, json.dumps([]))
            )
        
        return MessageResponse(
            message_id=error_message.id,
            content="抱歉，AI 服务暂时不可用，请稍后重试。",
            context=[],
            follow_up_questions=[]
        )
