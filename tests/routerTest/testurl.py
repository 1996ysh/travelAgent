"""快速测试 DashScope API 连通性"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_openai import ChatOpenAI
from app.config import settings

# 测试1: 检查配置值
print("=" * 50)
print("配置检查:")
print(f"  qwen_base_url: {settings.qwen_base_url}")
print(f"  qwen_model_name: {settings.qwen_model_name}")
print(f"  dashscope_api_key: {settings.dashscope_api_key[:10]}... (已隐藏)")
print("=" * 50)

# 测试2: 直接调用 API
try:
    llm = ChatOpenAI(
        model=settings.qwen_model_name,
        base_url=settings.qwen_base_url,
        api_key=settings.dashscope_api_key,
        temperature=0,
    )
    response = llm.invoke("你好，请用一句话介绍你自己。")
    print(f"\n✅ API 调用成功！")
    print(f"   模型回复: {response.content[:100]}")
except Exception as e:
    print(f"\n❌ API 调用失败: {e}")
    sys.exit(1)