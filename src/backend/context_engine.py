"""
上下文引擎 (Context Engine)
支持多轮对话系统的核心功能：
1. 上下文窗口组装（最近 N 轮对话）
2. Token 数量限制
3. 追问问题生成逻辑
"""

import sys
import os
import json
from typing import List, Dict, Any, Optional
from datetime import datetime

# 添加父目录到路径以便导入
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import Message
from database import get_db


class ContextEngine:
    """上下文引擎，管理对话上下文和生成追问问题"""
    
    def __init__(self, context_window_size: int = 5, max_tokens: int = 4000):
        """
        初始化上下文引擎
        
        Args:
            context_window_size: 上下文窗口大小（对话轮数），默认 5 轮
            max_tokens: 最大 token 数量限制，默认 4000
        """
        self.context_window_size = context_window_size
        self.max_tokens = max_tokens
    
    def get_conversation_context(self, conversation_id: str) -> List[Dict[str, Any]]:
        """
        获取对话的上下文窗口
        
        Args:
            conversation_id: 对话 ID
            
        Returns:
            上下文消息列表，按时间排序（最近的在前）
        """
        with get_db() as conn:
            cursor = conn.execute(
                """SELECT id, role, content, timestamp, context_refs
                   FROM messages
                   WHERE conversation_id = ?
                   ORDER BY timestamp DESC
                   LIMIT ?""",
                (conversation_id, self.context_window_size * 2)  # 2 表示用户 + 助手各一半
            )
            rows = cursor.fetchall()
        
        # 反转顺序，让最早的在前（符合对话流）
        messages = []
        for row in reversed(rows):
            messages.append({
                "role": row["role"],
                "content": row["content"],
                "timestamp": row["timestamp"],
                "contextRefs": json.loads(row["context_refs"]) if row["context_refs"] else []
            })
        
        return messages
    
    def assemble_prompt(self, conversation_id: str, user_message: str) -> str:
        """
        组装完整的 prompt，包含历史上下文和当前用户消息
        
        Args:
            conversation_id: 对话 ID
            user_message: 当前用户消息
            
        Returns:
            完整的 prompt 字符串
        """
        context_messages = self.get_conversation_context(conversation_id)
        
        # 构建 prompt
        prompt_parts = []
        
        # 添加系统提示
        prompt_parts.append(
            "你是一个专业的医疗 AI 诊断助手。请根据用户的症状描述，提供初步的诊断建议。"
            "请保持专业、谨慎，并始终建议用户咨询专业医生。"
        )
        
        # 添加历史对话上下文
        if context_messages:
            prompt_parts.append("\n\n历史对话记录：")
            for msg in context_messages:
                role = "用户" if msg["role"] == "user" else "助手"
                prompt_parts.append(f"\n{role}: {msg['content']}")
        
        # 添加当前用户消息
        prompt_parts.append(f"\n\n用户当前症状描述：{user_message}")
        
        # 添加指导说明
        prompt_parts.append(
            "\n\n请提供：\n"
            "1. 可能的诊断方向\n"
            "2. 建议的检查项目\n"
            "3. 紧急程度评估\n"
            "4. 需要进一步了解的信息（如果有）"
        )
        
        return "".join(prompt_parts)
    
    def generate_follow_up_questions(self, diagnosis_result: Dict[str, Any]) -> List[str]:
        """
        根据诊断结果生成追问问题
        
        Args:
            diagnosis_result: 诊断结果（包含症状、置信度等信息）
            
        Returns:
            追问问题列表（最多 3 个）
        """
        questions = []
        
        # 提取诊断结果的关键信息
        symptoms = diagnosis_result.get("symptoms", "")
        confidence = diagnosis_result.get("confidence", 1.0)
        conditions = diagnosis_result.get("possible_conditions", [])
        
        # 置信度低时询问症状持续时间
        if confidence < 0.7:
            questions.append("症状持续多久了？")
        
        # 检测到疼痛相关症状
        if any(pain_keyword in symptoms for pain_keyword in ["疼痛", "痛", "疼"]):
            questions.append("疼痛程度 1-10 分是多少？（1 为轻微，10 为最严重）")
        
        # 检测到慢性病症相关
        chronic_keywords = ["慢性", "长期", "反复", "经常", "持续"]
        if any(keyword in symptoms for keyword in chronic_keywords):
            questions.append("您有既往病史或正在服用的药物吗？")
        
        # 检测到发烧相关
        if any(fever_keyword in symptoms for fever_keyword in ["发烧", "发热", "体温"]):
            questions.append("具体体温是多少度？")
        
        # 检测到呼吸困难相关
        if any(breath_keyword in symptoms for breath_keyword in ["呼吸困难", "气短", "喘不过气"]):
            questions.append("呼吸困难是在活动时还是休息时也会出现？")
        
        # 限制最多 3 个问题
        return questions[:3]
    
    def estimate_tokens(self, text: str) -> int:
        """
        估算文本的 token 数量（简单估算：1 个中文字符≈1.5 tokens，1 个英文单词≈1.3 tokens）
        
        Args:
            text: 文本内容
            
        Returns:
            估算的 token 数量
        """
        # 简单估算方法
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        english_words = len([w for w in text.split() if w.isascii()])
        
        return int(chinese_chars * 1.5 + english_words * 1.3)
    
    def truncate_context(self, context_messages: List[Dict[str, Any]], max_tokens: int) -> List[Dict[str, Any]]:
        """
        截断上下文以符合 token 限制
        
        Args:
            context_messages: 上下文消息列表
            max_tokens: 最大 token 数量
            
        Returns:
            截断后的上下文消息列表
        """
        total_tokens = 0
        truncated = []
        
        # 从最近的对话开始添加
        for msg in reversed(context_messages):
            msg_tokens = self.estimate_tokens(msg["content"])
            
            if total_tokens + msg_tokens > max_tokens:
                break
            
            truncated.insert(0, msg)
            total_tokens += msg_tokens
        
        return truncated


# 全局上下文引擎实例
_context_engine: Optional[ContextEngine] = None


def get_context_engine() -> ContextEngine:
    """
    获取全局上下文引擎实例
    
    Returns:
        ContextEngine 实例
    """
    global _context_engine
    
    if _context_engine is None:
        # 从环境变量读取配置
        context_window = int(os.getenv("CONVERSATION_CONTEXT_WINDOW", 5))
        max_tokens = int(os.getenv("CONVERSATION_MAX_TOKENS", 4000))
        
        _context_engine = ContextEngine(
            context_window_size=context_window,
            max_tokens=max_tokens
        )
    
    return _context_engine
