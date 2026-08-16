import asyncio

import pytest

from app.config import settings
from app.core.store import get_user_memory_service, store_lifespan
from langchain.agents import create_agent
from langchain_community.chat_models import ChatTongyi


async def create_travel_agent(user_id:str):
    """创建只使用长期记忆（Store）的 Agent"""

    # 从 Store 读取长期记忆
    service = await get_user_memory_service()
    memory_prompt = await service.format_memory_for_prompt(user_id)

    # 构建 system prompt（长期记忆注入点）
    system_prompt = (
        "你是一个旅行规划助手。\n"
        "请结合用户的历史偏好和出行记录，进行个性化推荐。\n"
        "如果用户去过某些目的地或景点，请尽量避免重复推荐。\n"
    )

    if memory_prompt:
        system_prompt = f"{system_prompt}\n\n{memory_prompt}"

    # 创建 Agent（官网最新版 create_agent）
    agent = create_agent(
        model=ChatTongyi(
            model=settings.qwen_model_name,
            api_key=settings.dashscope_api_key,
            temperature=settings.qwen_temperature,
        ),
        system_prompt=system_prompt,  # ✅ 长期记忆
    )

    return agent

@pytest.mark.asyncio
async def test_main():
   # 必须与 Store 中一致
    user_id = "449bfbbe-bdcb-473d-b7a9-67120f783df0"
    agent = await create_travel_agent(user_id)
    response = await agent.ainvoke({
        "messages": [
            {"role": "user", "content": "根据我的偏好，推荐一个适合的国内旅行目的地"}
        ]
    })

    print(response["messages"][-1].content)



if __name__ == "__main__":
    async def _run():
        async with store_lifespan():
            await test_main()

    asyncio.run(_run())