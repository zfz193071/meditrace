"""
测试 DeepSeek 诊断功能
"""

import asyncio
from deepseek_client import get_deepseek_client


async def test_diagnose():
    """测试诊断功能"""
    
    print("=" * 60)
    print("MediTrace - DeepSeek 诊断测试")
    print("=" * 60)
    
    # 测试症状
    test_symptoms = "头痛、发烧持续 3 天、咳嗽、喉咙痛"
    
    print(f"\n测试症状：{test_symptoms}\n")
    
    try:
        client = get_deepseek_client()
        result = await client.diagnose(test_symptoms)
        
        print("诊断结果:")
        print("-" * 60)
        
        suggestions = result.get("suggestions", [])
        for i, suggestion in enumerate(suggestions, 1):
            print(f"\n{i}. {suggestion.get('disease')}")
            print(f"   置信度：{suggestion.get('confidence', 0) * 100:.0f}%")
            print(f"   建议检查:")
            for rec in suggestion.get("recommendations", []):
                print(f"     - {rec}")
        
        print("\n" + "-" * 60)
        print("免责声明:")
        print(result.get("disclaimer", "无"))
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ 测试失败：{str(e)}")
        print("\n请检查:")
        print("1. .env 文件中是否配置了 DEEPSEEK_API_KEY")
        print("2. API Key 是否有效")
        print("3. 网络连接是否正常")


if __name__ == "__main__":
    asyncio.run(test_diagnose())
