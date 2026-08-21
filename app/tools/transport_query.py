"""
交通查询工具
调用交通规划协调器(subagents 主agent)
"""
from langchain_core.tools import tool

from app.agents.subagents.transport_coordinator import create_transport_coordinator
from app.utils.logger import app_logger


@tool
async def query_transport_options(
        origin_city:str,
        destination_city:str,
        departure_date:str,
        transport_type:str =None,
        passenger_count:int =1
)->str:
    """
    查询交通选项（调用交通规划协调器）

    参数说明：
    - origin_city: 出发城市
    - destination_city: 目的地城市
    - departure_date: 出发日期，格式 YYYY-MM-DD
    - transport_type: 交通方式（可选），可选值：flight（航班）、train（高铁）、driving（自驾）
    - passenger_count: 乘客人数（可选）

    返回：
    - 格式化的交通选项信息
    """
    app_logger.info(f"🔧 调用交通规划协调器")
    # 创建协调器（主 Agent）
    coordinator = await create_transport_coordinator()
    # 构建用户查询
    if transport_type:
        # 用户指定了交通方式
        type_labels = {
            "flight": "航班",
            "train": "高铁",
            "driving": "自驾"
        }
        user_query = (
            f"我想从 {origin_city} 去 {destination_city}，"
            f"出发日期是 {departure_date}，"
            f"共 {passenger_count} 人，"
            f"交通方式选择 {type_labels.get(transport_type, transport_type)}，"
            f"请帮我查询详细信息。"
        )
    else:
        # 用户未指定 ，让主 Agent 推荐
        user_query = (
            f"我想从 {origin_city} 去 {destination_city}，"
            f"出发日期是 {departure_date}，"
            f"共 {passenger_count} 人，"
            f"请推荐合适的交通方式并提供详细信息。"
        )
    # 调用协调器
    result = await coordinator.ainvoke({
        "messages": [
            {"role": "user", "content": user_query}
        ]
    })

    # 返回协调器的响应
    return result["messages"][-1].content