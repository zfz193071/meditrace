"""
DeepSeek API 客户端
提供医疗诊断 AI 服务
"""

import os
import httpx
from typing import List, Dict, Any
from dotenv import load_dotenv

load_dotenv()


class DeepSeekClient:
    """DeepSeek API 客户端"""
    
    def __init__(self):
        self.api_key = os.getenv("DEEPSEEK_API_KEY")
        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY 未设置，请在 .env 文件中配置")
        
        self.base_url = "https://api.deepseek.com"
        self.model = "deepseek-chat"
        
    async def diagnose_with_context(self, conversation_id: str, user_message: str, context_messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        调用 DeepSeek API 获取医疗诊断建议（带上下文）
        
        Args:
            conversation_id: 对话 ID（用于追踪）
            user_message: 当前用户消息
            context_messages: 历史上下文消息列表
            
        Returns:
            诊断建议，包含疾病列表、置信度、建议检查
        """
        
        # 医学知识库 RAG - 系统提示词
        system_prompt = """你是一位专业的医疗 AI 助手，负责提供诊断建议。

重要原则:
1. 你提供的只是**建议**,不是**医疗诊断**,不能替代专业医生
2. 必须明确告知用户咨询专业医生
3. 对于紧急情况，建议立即就医
4. 根据对话历史，了解用户之前提到的症状和信息

输出格式要求 (必须严格遵守):
返回 JSON 格式，包含以下字段:
{
    "suggestions": [
        {
            "disease": "疾病名称",
            "confidence": 0.0-1.0 之间的数字，表示置信度,
            "recommendations": ["建议检查项目 1", "建议检查项目 2", ...]
        },
        ...
    ],
    "summary": "对本轮对话的总结",
    "disclaimer": "免责声明文本"
}

约束:
- suggestions 数组至少 1 个，最多 5 个可能疾病
- 按置信度从高到低排序
- 每个疾病必须有至少 1 个建议检查项目
- 置信度必须合理，不要全部 1.0 或全部 0.1
- 免责声明必须明确说明这不是医疗诊断
- summary 要简洁概括当前诊断状态"""

        # 构建历史对话
        history_text = ""
        for msg in context_messages:
            role = "用户" if msg["role"] == "user" else "助手"
            history_text += f"\n{role}: {msg['content']}"
        
        prompt = f"""请根据以下对话历史和用户当前的症状描述，提供可能的疾病诊断建议:

对话历史:{history_text}

用户当前症状描述：{user_message}

请按照上述格式返回 JSON 结果。"""

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.3,
                        "max_tokens": 1500
                    }
                )
                
                response.raise_for_status()
                result = response.json()
                
                # 解析 AI 返回
                ai_content = result["choices"][0]["message"]["content"]
                
                # 提取 JSON (AI 可能返回额外文本)
                import json
                import re
                
                # 尝试提取 JSON 块
                json_match = re.search(r'\{[\s\S]*\}', ai_content)
                if json_match:
                    json_str = json_match.group()
                    parsed = json.loads(json_str)
                else:
                    # 直接尝试解析
                    parsed = json.loads(ai_content)
                
                return parsed
                
        except httpx.HTTPError as e:
            raise Exception(f"DeepSeek API 调用失败：{str(e)}")
        except Exception as e:
            raise Exception(f"诊断处理失败：{str(e)}")
    
    async def diagnose_with_context_stream(self, conversation_id: str, user_message: str, context_messages: List[Dict[str, Any]]):
        """
        调用 DeepSeek API 获取医疗诊断建议（带上下文，流式输出）
        
        Args:
            conversation_id: 对话 ID（用于追踪）
            user_message: 当前用户消息
            context_messages: 历史上下文消息列表
            
        Yields:
            流式生成的文本片段
        """
        
        # 医学知识库 RAG - 系统提示词
        system_prompt = """你是一位专业的医疗 AI 助手，负责提供诊断建议。

重要原则:
1. 你提供的只是**建议**,不是**医疗诊断**,不能替代专业医生
2. 必须明确告知用户咨询专业医生
3. 对于紧急情况，建议立即就医
4. 根据对话历史，了解用户之前提到的症状和信息

输出格式要求 (必须严格遵守):
返回 JSON 格式，包含以下字段:
{
    "suggestions": [
        {
            "disease": "疾病名称",
            "confidence": 0.0-1.0 之间的数字，表示置信度,
            "recommendations": ["建议检查项目 1", "建议检查项目 2", ...]
        },
        ...
    ],
    "summary": "对本轮对话的总结",
    "disclaimer": "免责声明文本"
}

约束:
- suggestions 数组至少 1 个，最多 5 个可能疾病
- 按置信度从高到低排序
- 每个疾病必须有至少 1 个建议检查项目
- 置信度必须合理，不要全部 1.0 或全部 0.1
- 免责声明必须明确说明这不是医疗诊断
- summary 要简洁概括当前诊断状态"""

        # 构建历史对话
        history_text = ""
        for msg in context_messages:
            role = "用户" if msg["role"] == "user" else "助手"
            history_text += f"\n{role}: {msg['content']}"
        
        prompt = f"""请根据以下对话历史和用户当前的症状描述，提供可能的疾病诊断建议:

对话历史:{history_text}

用户当前症状描述：{user_message}

请按照上述格式返回 JSON 结果。"""

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.3,
                        "max_tokens": 1500,
                        "stream": True  # 启用流式输出
                    }
                ) as response:
                    response.raise_for_status()
                    
                    # 逐行读取流式响应
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data = line[6:]  # 移除 "data: " 前缀
                            if data == "[DONE]":
                                break
                            try:
                                import json
                                chunk = json.loads(data)
                                content = chunk["choices"][0]["delta"].get("content", "")
                                if content:
                                    yield content
                            except:
                                pass
                                
        except httpx.HTTPError as e:
            raise Exception(f"DeepSeek API 调用失败：{str(e)}")
        except Exception as e:
            raise Exception(f"诊断处理失败：{str(e)}")
        """
        调用 DeepSeek API 获取医疗诊断建议（带上下文）
        
        Args:
            conversation_id: 对话 ID（用于追踪）
            user_message: 当前用户消息
            context_messages: 历史上下文消息列表
            
        Returns:
            诊断建议，包含疾病列表、置信度、建议检查
        """
        
        # 医学知识库 RAG - 系统提示词
        system_prompt = """你是一位专业的医疗 AI 助手，负责提供诊断建议。

重要原则:
1. 你提供的只是**建议**,不是**医疗诊断**,不能替代专业医生
2. 必须明确告知用户咨询专业医生
3. 对于紧急情况，建议立即就医
4. 根据对话历史，了解用户之前提到的症状和信息

输出格式要求 (必须严格遵守):
返回 JSON 格式，包含以下字段:
{
    "suggestions": [
        {
            "disease": "疾病名称",
            "confidence": 0.0-1.0 之间的数字，表示置信度,
            "recommendations": ["建议检查项目 1", "建议检查项目 2", ...]
        },
        ...
    ],
    "summary": "对本轮对话的总结",
    "disclaimer": "免责声明文本"
}

约束:
- suggestions 数组至少 1 个，最多 5 个可能疾病
- 按置信度从高到低排序
- 每个疾病必须有至少 1 个建议检查项目
- 置信度必须合理，不要全部 1.0 或全部 0.1
- 免责声明必须明确说明这不是医疗诊断
- summary 要简洁概括当前诊断状态"""

        # 构建历史对话
        history_text = ""
        for msg in context_messages:
            role = "用户" if msg["role"] == "user" else "助手"
            history_text += f"\n{role}: {msg['content']}"
        
        prompt = f"""请根据以下对话历史和用户当前的症状描述，提供可能的疾病诊断建议:

对话历史:{history_text}

用户当前症状描述：{user_message}

请按照上述格式返回 JSON 结果。"""

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.3,
                        "max_tokens": 1500
                    }
                )
                
                response.raise_for_status()
                result = response.json()
                
                # 解析 AI 返回
                ai_content = result["choices"][0]["message"]["content"]
                
                # 提取 JSON (AI 可能返回额外文本)
                import json
                import re
                
                # 尝试提取 JSON 块
                json_match = re.search(r'\{[\s\S]*\}', ai_content)
                if json_match:
                    json_str = json_match.group()
                    parsed = json.loads(json_str)
                else:
                    # 直接尝试解析
                    parsed = json.loads(ai_content)
                
                return parsed
                
        except httpx.HTTPError as e:
            raise Exception(f"DeepSeek API 调用失败：{str(e)}")
        except Exception as e:
            raise Exception(f"诊断处理失败：{str(e)}")
    
    async def diagnose(self, symptoms: str) -> Dict[str, Any]:
        """
        调用 DeepSeek API 获取医疗诊断建议
        
        Args:
            symptoms: 用户描述的症状
            
        Returns:
            诊断建议，包含疾病列表、置信度、建议检查
        """
        
        # 医学知识库 RAG - 系统提示词
        system_prompt = """你是一位专业的医疗 AI 助手，负责提供诊断建议。
        
重要原则:
1. 你提供的只是**建议**,不是**医疗诊断**,不能替代专业医生
2. 必须明确告知用户咨询专业医生
3. 对于紧急情况，建议立即就医

输出格式要求 (必须严格遵守):
返回 JSON 格式，包含以下字段:
{
    "suggestions": [
        {
            "disease": "疾病名称",
            "confidence": 0.0-1.0 之间的数字，表示置信度,
            "recommendations": ["建议检查项目 1", "建议检查项目 2", ...]
        },
        ...
    ],
    "disclaimer": "免责声明文本"
}

约束:
- suggestions 数组至少 1 个，最多 5 个可能疾病
- 按置信度从高到低排序
- 每个疾病必须有至少 1 个建议检查项目
- 置信度必须合理，不要全部 1.0 或全部 0.1
- 免责声明必须明确说明这不是医疗诊断"""

        prompt = f"""请根据以下症状描述，提供可能的疾病诊断建议:

症状：{symptoms}

请按照上述格式返回 JSON 结果。"""

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.3,  # 较低温度，保证输出稳定
                        "max_tokens": 1000
                    }
                )
                
                response.raise_for_status()
                result = response.json()
                
                # 解析 AI 返回
                ai_content = result["choices"][0]["message"]["content"]
                
                # 提取 JSON (AI 可能返回额外文本)
                import json
                import re
                
                # 尝试提取 JSON 块
                json_match = re.search(r'\{[\s\S]*\}', ai_content)
                if json_match:
                    json_str = json_match.group()
                    parsed = json.loads(json_str)
                else:
                    # 直接尝试解析
                    parsed = json.loads(ai_content)
                
                return parsed
                
        except httpx.HTTPError as e:
            raise Exception(f"DeepSeek API 调用失败：{str(e)}")
        except Exception as e:
            raise Exception(f"诊断处理失败：{str(e)}")
    
    async def get_medical_knowledge(self, disease_type: str) -> str:
        """
        获取特定疾病类型的医学知识库信息
        (可扩展为真正的 RAG 检索)
        """
        # 当前版本：简单返回通用知识
        # 未来可扩展为向量数据库检索
        
        knowledge_base = {
            "呼吸道感染": "常见症状包括发热、咳嗽、喉咙痛、流鼻涕。建议检查：血常规、胸部 X 光、病毒检测。",
            "消化系统": "常见症状包括腹痛、恶心、呕吐、腹泻。建议检查：血常规、腹部超声、胃肠镜。",
            "心血管疾病": "常见症状包括胸痛、心悸、呼吸困难。建议检查：心电图、心脏超声、心肌酶谱。",
            "神经系统": "常见症状包括头痛、头晕、麻木、意识障碍。建议检查：头颅 CT/MRI、脑电图、神经传导。"
        }
        
        for key, value in knowledge_base.items():
            if key in disease_type:
                return value
        
        return "建议咨询专业医生获取详细诊断建议。"


# 单例模式
client = None

def get_deepseek_client() -> DeepSeekClient:
    """获取 DeepSeek 客户端单例"""
    global client
    if client is None:
        client = DeepSeekClient()
    return client
