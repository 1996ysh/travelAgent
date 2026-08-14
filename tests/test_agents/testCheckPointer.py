# 设置 WindowsSelectorEventLoopPolicy
import asyncio
import sys

from langchain.agents import create_agent
from langchain_community.chat_models import ChatTongyi

from app.config import settings
from app.core.Checkpointer import get_checkpointer

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


async def create_travel_agent():
    """创建带checkpointer的agent"""

    #获取checkpointer
    checkpointer = await get_checkpointer()

    agent = create_agent(
        model=ChatTongyi(
            model=settings.qwen_model_name,
            api_key=settings.dashscope_api_key,
            temperature=settings.qwen_temperature
        ),
    checkpointer = checkpointer  # 关键：传入 Checkpointer
    )
    return agent

async def main():
    agent = await create_travel_agent()

    # 配置（thread_id 用于会话隔离）
    config = {
        "configurable": {
            "thread_id": "user_123_session_4567"
        }
    }

    # 第一轮对话
    response1 = await agent.ainvoke(
        {"messages": [{"role": "user", "content": "我想去西安旅游"}]},
        config
    )

    print(response1["messages"][-1].content)

    # 第二轮对话（Agent 会自动读取 thread_id 对应的历史状态）
    response2 = await agent.ainvoke(
        {"messages": [{"role": "user", "content": "推荐几个景点"}]},
        config
    )

    print(response2["messages"][-1].content)

if __name__ == '__main__':
    asyncio.run(main())