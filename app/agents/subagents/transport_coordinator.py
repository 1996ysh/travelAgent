"""
交通规划协调器(主agent)
整合 driving flight train 三个agent
"""
from langchain.agents import create_agent
from langchain_community.chat_models import ChatTongyi
from langchain_core.tools import tool

from app.agents.subagents.driving_agent import create_driving_subagent
from app.agents.subagents.flight_agent import create_flight_subagent
from app.agents.subagents.train_agent import create_train_subagent
from app.config import settings
from app.mcp_core.client import get_mcp_client
from app.utils.logger import app_logger

#获取辅助工具
async def _get_auxiliary_tools():
    """获取辅助工具  也就是mcp提供的tools"""
    manager = await get_mcp_client()
    all_tools = await manager.get_tools()
    aux_tools = [
        tool for tool in all_tools
        if any(keyword in tool.name.lower() for keyword in [
            'getfutureweather','get-current-date','maps_around_search'
        ] )
    ]
    app_logger.info(f'辅助工具:{[t.name for t in aux_tools]}')
    return aux_tools
# ============== 创建交通规划主 Agent ==============

async def create_transport_coordinator():
    """
    创建交通规划协调器（主 Agent）

    这个 Agent 拥有三个工具（封装的 Subagents）：
    - query_flights：查询航班
    - query_trains：查询高铁
    - plan_driving_route：规划自驾路线

    主 Agent 会根据用户需求动态决定调用哪个工具。
    """

    llm = ChatTongyi(
        model=settings.qwen_model_name,
        api_key=settings.dashscope_api_key,
        temperature=0.7
    )
    ##创建三个子agents
    flight_subagent = await create_flight_subagent()
    train_subagent = await create_train_subagent()
    driving_subagent = await create_driving_subagent()

    #  将subagent包装为Tools
    @tool("query_flights", description="查询航班信息。需要提供出发城市、目的地城市、出发日期和乘客数量。")
    async def query_flights_tool(
            origin: str,
            destination: str,
            departure_date: str,
            passenger_count: int = 1
    ) -> str:
        """
        查询航班信息(调用航班subagent)
        :param origin:
        :param destination:
        :param departure_date:
        :param passenger_count:
        :return:
        """
        app_logger.info(f"🔧 调用航班 Subagent: {origin} -> {destination}")

        result = await flight_subagent.ainvoke({
            'messages': [
                {
                    'role': 'user',
                    'content': f'请查询从 {origin} 到 {destination} 的航班，出发日期是 {departure_date}，共 {passenger_count} 人。'
                }
            ]
        })
        # 返回 Subagent 的最终消息
        return result["messages"][-1].content

    @tool("query_trains", description="查询高铁/火车信息。需要提供出发城市、目的地城市、出发日期。")
    async def query_trains_tool(
            origin: str,
            destination: str,
            departure_date: str
    ) -> str:
        """
        查询高铁信息（调用高铁 Subagent）
        """

        app_logger.info(f"🔧 调用高铁 Subagent: {origin} -> {destination}")

        result = await train_subagent.ainvoke({
            "messages": [
                {
                    "role": "user",
                    "content": f"请查询从 {origin} 到 {destination} 的高铁，出发日期是 {departure_date}。"
                }
            ]
        })
        return result['messages'][-1].content

    @tool("plan_driving_route", description="规划自驾路线。需要提供出发城市、目的地城市。")
    async def plan_driving_route_tool(
                origin: str,
                destination: str
        ) -> str:
            """
            规划自驾路线（调用自驾 Subagent）
            """

            app_logger.info(f"🔧 调用自驾 Subagent: {origin} -> {destination}")

            result = await driving_subagent.ainvoke({
                "messages": [
                    {
                        "role": "user",
                        "content": f"请规划从 {origin} 到 {destination} 的自驾路线。"
                    }
                ]
            })
            #-1是拿到最后一条消息
            return result["messages"][-1].content
            #获取辅助工具
    auxiliary_tools = await _get_auxiliary_tools()
            #组合所有工具  所有mcp工具以及给agent tool
    coordinator = create_agent(
            model=llm,
            tools=[
                query_flights_tool,
                query_trains_tool,
                plan_driving_route_tool
        ]+auxiliary_tools,
        system_prompt="""你是交通规划协调专家。

**可用工具**：
**交通查询(主要）**：
1．query_flights：查询航班信息（适合长途，速度快）
2.query_trains：查询高铁信息(适合中短途，舒适便捷）
3.plan_driving_route：规划自驾路线（适合深度游，自由灵活）
**辅助工具（按需使用）**：
-getFutureweatherByAirport：查询机场未来天气
-get-current-date：获取今天日期（调用需要时间的工具前，获取实时时间）
**工作流程**：
1．理解用户的交通需求（出发地、目的地、日期、人数）
2．如果用户明确指定交通方式，直接调用对应工具
3．如果用户未指定，根据距离推荐：
*300km：推荐高铁
*300-1000km：推荐高铁或航班
*>1000km：推荐航班
4，调用工具后，用清晰格式展示结果
5，可以主动询问用户偏好（时间优先还是价格优先）
**注意事项**：
-用户说的今天和明天之类的词要以get-current-date获取的时间为标准
一定要调用工具获取实时信息，不要编造数据
-如果查询失败，告知用户并提供替代方案
。航班和高铁需要提供日期，自驾不需要
调用工具前，先调用get-current-date获取今天日期
"""
    )

    app_logger.info("✅ 交通规划协调器（主 Agent）创建完成")

    return coordinator



