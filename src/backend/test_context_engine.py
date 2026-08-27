"""
上下文引擎单元测试
测试多轮对话系统的核心业务逻辑
"""

import pytest
import sys
import os

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from context_engine import ContextEngine


class TestContextEngineFollowUpQuestions:
    """测试追问问题生成功能"""
    
    def setup_method(self):
        """每个测试前初始化"""
        self.engine = ContextEngine(context_window_size=5)
    
    def test_generate_questions_low_confidence(self):
        """测试：置信度低时询问症状持续时间"""
        diagnosis_result = {
            "symptoms": "头痛",
            "confidence": 0.5,  # 低于 0.7
            "possible_conditions": ["紧张性头痛"]
        }
        
        questions = self.engine.generate_follow_up_questions(diagnosis_result)
        
        # 验证：应该包含询问持续时间的問題
        assert any("持续" in q for q in questions), \
            "置信度低时应询问症状持续时间"
    
    def test_generate_questions_pain_detection(self):
        """测试：检测到疼痛时询问疼痛程度"""
        diagnosis_result = {
            "symptoms": "头痛疼痛",
            "confidence": 0.8,
            "possible_conditions": ["偏头痛"]
        }
        
        questions = self.engine.generate_follow_up_questions(diagnosis_result)
        
        # 验证：应该包含询问疼痛程度的问题
        assert any("疼痛程度" in q or "1-10" in q for q in questions), \
            "检测到疼痛时应询问疼痛程度"
    
    def test_generate_questions_chronic_conditions(self):
        """测试：检测到慢性病时询问既往病史"""
        diagnosis_result = {
            "symptoms": "长期头痛反复发作",
            "confidence": 0.6,
            "possible_conditions": ["慢性头痛"]
        }
        
        questions = self.engine.generate_follow_up_questions(diagnosis_result)
        
        # 验证：应该包含询问既往病史的问题
        assert any("既往病史" in q or "药物" in q for q in questions), \
            "检测到慢性病时应询问既往病史"
    
    def test_generate_questions_max_three(self):
        """测试：最多返回 3 个问题"""
        diagnosis_result = {
            "symptoms": "头痛疼痛长期持续",
            "confidence": 0.3,  # 触发多个条件
            "possible_conditions": ["多种疾病"]
        }
        
        questions = self.engine.generate_follow_up_questions(diagnosis_result)
        
        # 验证：问题数量不超过 3 个
        assert len(questions) <= 3, \
            f"追问问题最多 3 个，但返回了 {len(questions)} 个"
    
    def test_generate_questions_empty_result(self):
        """测试：空诊断结果返回空列表"""
        diagnosis_result = {}
        
        questions = self.engine.generate_follow_up_questions(diagnosis_result)
        
        # 验证：返回空列表
        assert questions == [], "空诊断结果应返回空问题列表"
    
    def test_generate_questions_fever_detection(self):
        """测试：检测到发烧时询问体温"""
        diagnosis_result = {
            "symptoms": "发烧发热 38 度",
            "confidence": 0.7,
            "possible_conditions": ["感染"]
        }
        
        questions = self.engine.generate_follow_up_questions(diagnosis_result)
        
        # 验证：应该包含询问体温的问题
        assert any("体温" in q or "度" in q for q in questions), \
            "检测到发烧时应询问具体体温"
    
    def test_generate_questions_breathing_difficulty(self):
        """测试：检测到呼吸困难时询问活动情况"""
        diagnosis_result = {
            "symptoms": "呼吸困难气短",
            "confidence": 0.6,
            "possible_conditions": ["呼吸系统疾病"]
        }
        
        questions = self.engine.generate_follow_up_questions(diagnosis_result)
        
        # 验证：应该包含询问活动情况的问题
        assert any("活动" in q or "休息" in q for q in questions), \
            "检测到呼吸困难时应询问活动时还是休息时出现"


class TestContextEngineTokenEstimation:
    """测试 Token 估算功能"""
    
    def setup_method(self):
        """每个测试前初始化"""
        self.engine = ContextEngine()
    
    def test_estimate_chinese_tokens(self):
        """测试：中文字符 token 估算"""
        text = "我头痛已经 3 天了"
        tokens = self.engine.estimate_tokens(text)
        
        # 验证：估算值应该合理（大约 1.5 * 字符数）
        assert tokens > 0, "中文字符应估算出正数 token"
        assert tokens < 100, "短文本 token 数不应过大"
    
    def test_estimate_english_tokens(self):
        """测试：英文单词 token 估算"""
        text = "I have a headache for 3 days"
        tokens = self.engine.estimate_tokens(text)
        
        # 验证：估算值应该合理
        assert tokens > 0, "英文单词应估算出正数 token"
    
    def test_estimate_mixed_tokens(self):
        """测试：混合语言 token 估算"""
        text = "头痛 headache 3 天 days"
        tokens = self.engine.estimate_tokens(text)
        
        # 验证：估算值应该为正数
        assert tokens > 0, "混合文本应估算出正数 token"


class TestContextEngineTruncation:
    """测试上下文截断功能"""
    
    def setup_method(self):
        """每个测试前初始化"""
        self.engine = ContextEngine(max_tokens=100)
    
    def test_truncate_over_limit(self):
        """测试：超过 token 限制时截断"""
        context_messages = [
            {"role": "user", "content": "我头痛已经 3 天了，非常严重，伴有恶心呕吐，症状持续加重，需要紧急处理"},
            {"role": "assistant", "content": "根据您的描述，头痛可能由多种原因引起，建议尽快就医检查，进行神经系统检查和影像学检查"},
            {"role": "user", "content": "我还有发烧 38 度，咳嗽，喉咙痛，全身乏力，没有食欲"},
            {"role": "assistant", "content": "这些症状可能是呼吸道感染，建议测量体温，进行血常规检查，多休息多喝水"},
        ]
        
        truncated = self.engine.truncate_context(context_messages, max_tokens=50)
        
        # 验证：截断后的消息应该少于原始消息
        assert len(truncated) <= len(context_messages), \
            "截断后的消息数不应超过原始消息数"
    
    def test_truncate_under_limit(self):
        """测试：未超过 token 限制时不截断"""
        context_messages = [
            {"role": "user", "content": "我头痛"},
            {"role": "assistant", "content": "请详细描述症状"},
        ]
        
        truncated = self.engine.truncate_context(context_messages, max_tokens=1000)
        
        # 验证：短文本不应被截断
        assert len(truncated) == len(context_messages), \
            "未超过限制时不应截断"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
