"""
对话 API 集成测试
使用 TestClient 测试 HTTP 端点
"""

import pytest
import sys
import os
import json
import uuid
from datetime import datetime

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 使用测试数据库
os.environ["DATABASE_URL"] = "sqlite:///./test_meditrace.db"

from fastapi.testclient import TestClient
from main import app


class TestConversationsAPI:
    """测试对话管理 API"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """每个测试前设置"""
        self.client = TestClient(app)
        self.test_patient_id = "0x262Ee58D3e7A782ceC68094A6DACb53D02Fa9d0B"
        self.test_conversation_id = str(uuid.uuid4())
    
    def test_create_conversation(self):
        """测试：创建对话"""
        response = self.client.post(
            "/api/conversations",
            json={
                "patientId": self.test_patient_id,
                "title": "头痛诊断测试"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "conversationId" in data
        assert data["patientId"] == self.test_patient_id
        assert data["title"] == "头痛诊断测试"
        assert "createdAt" in data
    
    def test_get_conversations_empty(self):
        """测试：获取空对话列表"""
        response = self.client.get("/api/conversations")
        
        assert response.status_code == 200
        data = response.json()
        assert "conversations" in data
        assert "total" in data
        assert data["total"] >= 0
    
    def test_get_conversations_with_patient_id(self):
        """测试：按患者 ID 过滤获取对话列表"""
        # 先创建一个对话
        self.client.post(
            "/api/conversations",
            json={
                "patientId": self.test_patient_id,
                "title": "测试对话"
            }
        )
        
        # 然后获取该患者的对话
        response = self.client.get(
            "/api/conversations",
            params={"patientId": self.test_patient_id}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert any(c["patientId"] == self.test_patient_id 
                   for c in data["conversations"])
    
    def test_get_conversation_not_found(self):
        """测试：获取不存在的对话"""
        fake_id = str(uuid.uuid4())
        response = self.client.get(f"/api/conversations/{fake_id}")
        
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
    
    def test_delete_conversation(self):
        """测试：删除对话"""
        # 先创建一个对话
        create_response = self.client.post(
            "/api/conversations",
            json={
                "patientId": self.test_patient_id,
                "title": "待删除对话"
            }
        )
        conversation_id = create_response.json()["conversationId"]
        
        # 然后删除它
        response = self.client.delete(f"/api/conversations/{conversation_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        
        # 验证已删除
        get_response = self.client.get(f"/api/conversations/{conversation_id}")
        assert get_response.status_code == 404
    
    def test_send_message(self):
        """测试：发送消息（骨架测试）"""
        # 先创建一个对话
        create_response = self.client.post(
            "/api/conversations",
            json={
                "patientId": self.test_patient_id,
                "title": "消息测试"
            }
        )
        conversation_id = create_response.json()["conversationId"]
        
        # 发送消息
        response = self.client.post(
            f"/api/conversations/{conversation_id}/messages",
            json={
                "content": "我头痛已经 3 天了",
                "contextWindow": 5
            }
        )
        
        # 注意：当前实现返回骨架响应
        assert response.status_code == 200
        data = response.json()
        assert "messageId" in data
        assert "content" in data
        assert "context" in data
        assert "followUpQuestions" in data
    
    def test_send_message_to_nonexistent_conversation(self):
        """测试：向不存在的对话发送消息"""
        fake_id = str(uuid.uuid4())
        response = self.client.post(
            f"/api/conversations/{fake_id}/messages",
            json={
                "content": "测试消息",
                "contextWindow": 5
            }
        )
        
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data


class TestAPIValidation:
    """测试 API 输入验证"""
    
    def setup_method(self):
        """每个测试前初始化"""
        self.client = TestClient(app)
    
    def test_create_conversation_missing_patient_id(self):
        """测试：创建对话缺少 patientId"""
        response = self.client.post(
            "/api/conversations",
            json={"title": "测试"}
        )
        
        # 应该返回验证错误
        assert response.status_code in [422, 400]
    
    def test_create_conversation_missing_title(self):
        """测试：创建对话缺少 title"""
        response = self.client.post(
            "/api/conversations",
            json={"patientId": "0x123"}
        )
        
        # 应该返回验证错误
        assert response.status_code in [422, 400]
    
    def test_create_conversation_empty_title(self):
        """测试：创建对话空 title"""
        response = self.client.post(
            "/api/conversations",
            json={"patientId": "0x123", "title": ""}
        )
        
        # 应该返回验证错误
        assert response.status_code in [422, 400]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
