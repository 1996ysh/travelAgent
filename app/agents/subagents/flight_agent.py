"""
航班查询 Subagent
调用 Aviation MCP 服务
"""
from langchain.agents import create_agent
from langchain_community.chat_models import ChatTongyi
from langchain_core.tools import tool

from app.config import settings
from app.utils.logger import app_logger


# ============== 航班查询工具 ==============
@tool
async  def query_flights_from_mcp(
        origin:str,
        destination:str,
        departure_date:str
)->str:
    """
    从 Aviation MCP 查询航班信息

    参数说明：
    - origin: 出发城市
    - destination: 目的地城市
    - departure_date: 出发日期，格式 YYYY-MM-DD

    返回：
    - JSON 格式的航班列表
    """
    app_logger.info(f'查询航班:{origin}->{destination},{departure_date}')
    # TODO: 实际应调用 Aviation MCP
    # from langchain_mcp_adapters.client import MultiServerMCPClient
    # client = MultiServerMCPClient({...})
    # result = await client.invoke_tool("aviation", "search_flights", {...})
    # 这里返回模拟数据
    import json
    mock_flights = [
        {
            "flight_number": "CA1234",
            "airline": "中国国航",
            "departure_airport": f"{origin}首都国际机场",
            "arrival_airport": f"{destination}浦东国际机场",
            "departure_time": f"{departure_date} 08:00",
            "arrival_time": f"{departure_date} 10:30",
            "duration": "2小时30分",
            "price": 800.0,
            "cabin_class": "经济舱",
            "available_seats": 45
        },
        {
            "flight_number": "MU5678",
            "airline": "东方航空",
            "departure_airport": f"{origin}首都国际机场",
            "arrival_airport": f"{destination}虹桥国际机场",
            "departure_time": f"{departure_date} 14:00",
            "arrival_time": f"{departure_date} 16:20",
            "duration": "2小时20分",
            "price": 750.0,
            "cabin_class": "经济舱",
            "available_seats": 23
        }
    ]

    return json.dumps(mock_flights, ensure_ascii=False, indent=2)

#创建航班subagent

def create_flight_subagent():
    """创建航班查询subagent"""
    llm = ChatTongyi(
        model=settings.qwen_model_name,
        api_key = settings.dashscope_api_key,
        temperature = 0.3
    )
    agent = create_agent(
        model=llm,
        tools=[query_flights_from_mcp],
        system_prompt="""你是航班查询专家。

    **职责**：
    1. 接收出发城市、目的地城市、出发日期
    2. 调用 query_flights_from_mcp 工具查询航班
    3. 整理航班信息，按价格从低到高排序
    4. 返回清晰的航班列表

    **输出格式**：
    请按以下格式返回航班信息：

    找到 N 个航班选项：

    1. 【航班号】 {airline} {flight_number}
       - 出发：{departure_airport} {departure_time}
       - 到达：{arrival_airport} {arrival_time}
       - 时长：{duration}
       - 价格：¥{price}
       - 余票：{available_seats} 座

    **注意事项**：
    - 一定要调用工具，不要编造数据
    - 如果没有找到航班，明确告知用户
    - 价格信息要准确清晰
    """
    )

    app_logger.info("✅ 航班 Subagent 创建完成")

    return agent