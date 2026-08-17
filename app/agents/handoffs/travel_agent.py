from langchain.agents import create_agent
from langchain_openai import ChatOpenAI

from app.config import settings
from app.core.Checkpointer import get_checkpointer
from app.core.middleware import create_step_config_middleware
from app.core.state import TravelState
from app.tools.state_back import ALL_ROLLBACK_TOOLS
from app.tools.state_transition import summarize_budget_tool, record_requirement_tool, select_destination_tool, \
    select_transport_tool, select_accommodation_tool, select_food_tool, generate_itinerary_tool, generate_order_tool
from app.utils.logger import app_logger


# ============== 初始化 LLM ==============

def get_llm():
    """获取配置好的千问模型"""
    return ChatOpenAI(
        model=settings.qwen_model_name,
        base_url=settings.qwen_base_url,
        api_key=settings.dashscope_api_key,
        temperature=settings.qwen_temperature,
        max_tokens=settings.qwen_max_tokens,
        streaming=True
    )


# ============== 创建 Agent ==============

async def create_travel_agent():
    """
    创建 Handoffs 旅行规划 Agent

    返回：
        编译好的 Agent（可直接调用）
    """

    app_logger.info("创建 Travel Agent...")

    llm = get_llm()

    # 异步创建中间件（预加载配置）
    step_config_middleware = await create_step_config_middleware()

    all_tools = [
        record_requirement_tool,
        select_destination_tool,
        select_transport_tool,
        select_accommodation_tool,
        select_food_tool,
        generate_itinerary_tool,
        summarize_budget_tool,
        generate_order_tool,
        *ALL_ROLLBACK_TOOLS,
    ]

    checkpointer = await get_checkpointer()

    agent = create_agent(
        model=llm,
        tools=all_tools,
        state_schema=TravelState,
        middleware=[step_config_middleware],  # 使用预加载的中间件
        checkpointer=checkpointer,
    )

    app_logger.info("✅ Travel Agent 创建完成")

    return agent