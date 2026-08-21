"""
mcp工具筛选器
按需获取特定类型的mcp工具

"""
from langchain_core.tools import BaseTool

from app.mcp_core.client import get_mcp_client
from app.utils.logger import app_logger


async def get_all_mcp_tools()->list[BaseTool]:
    """获取所有mcp工具"""
    manager = await get_mcp_client()
    tools = await manager.get_tools()
    app_logger.info(f'获取{len(tools)}个mcp工具')
    return tools

async def get_hotel_tools()->list[BaseTool]:
    """
    获取酒店相关的工具
    :return: 酒店搜索、周边查询等工具
    """
    manager = await get_mcp_client()
    all_tools = await manager.get_tools()
    hotel_tools = [
        tool for tool in all_tools
        if any(keyword in tool.name.lower() for keyword in[
            'find-hotels',
            'maps_around_search',
        ])
    ]
    app_logger.info(f'酒店工具：{[t.name for t in hotel_tools]}')
    return hotel_tools
async def get_weather_tools()->list[BaseTool]:
    """
    获取天气相关的工具
    :return: 酒店搜索、周边查询等工具
    """
    manager = await get_mcp_client()
    all_tools = await manager.get_tools()
    weather_tools = [
        tool for tool in all_tools
        if any(keyword in tool.name.lower() for keyword in[
            'get_weather_forecast',
        ])
    ]
    app_logger.info(f'天气工具：{[t.name for t in weather_tools]}')
    return weather_tools
async def get_search_tools()->list[BaseTool]:
    """
    获取搜索相关的工具
    :return: 旅游信息搜索工具
    """
    manager = await get_mcp_client()
    all_tools = await manager.get_tools()
    search_tools = [
        tool for tool in all_tools
        if any(keyword in tool.name.lower() for keyword in[
            'search_travel_info',
        ])
    ]
    app_logger.info(f'搜索工具：{[t.name for t in search_tools]}')
    return search_tools
async def get_date_tools()->list[BaseTool]:
    """
    获取日期相关的工具
    :return: 获取当前日期的工具
    """
    manager = await get_mcp_client()
    all_tools = await manager.get_tools()
    date_tools = [
        tool for tool in all_tools
        if any(keyword in tool.name.lower() for keyword in[
            'get-current-date',
            'gettodaydate',
        ])
    ]
    app_logger.info(f'日期工具：{[t.name for t in date_tools]}')
    return date_tools