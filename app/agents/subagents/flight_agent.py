"""
航班查询subagent
调用aviation mcp 的多个工具
"""
from langchain.agents import create_agent
from langchain_community.chat_models import ChatTongyi

from app.config import settings
from app.mcp_core.client import get_mcp_client
from app.utils.logger import app_logger


async def _get_aviation_tools():
    """获取航班相关的mcp工具"""
    manager = await get_mcp_client()
    all_tools = await manager.get_tools()
    #筛选航班工具
    aviation_tools = [
        tool for tool in all_tools
        if any(keyword in tool.name.lower() for keyword in['flight','aviation','searchflights','gettodaydate'])
    ]
    app_logger.info(f'航班工具:{[t.name for t in aviation_tools]}')
    return aviation_tools

async def create_flight_subagent():
    """创建航班查询"""

    llm = ChatTongyi(
        model=settings.qwen_model_name,
        api_key=settings.dashscope_api_key,
        temperature = 0.1
    )
    #异步获取工具
    aviation_tools = await _get_aviation_tools()
    agent = create_agent(
        model=llm,
        tools=aviation_tools,
        system_prompt="""
        你是航班查询专家，负责处理航班查询、机票价格比较以及航班状态查询。可以使用一下工具:
        **可用工具**：
1.
**日期与基础信息**:
getTodayDate：获取今天日期（用于用户提供相对日期时）
2.**航班查询（核心）**：
searchFlightsByDepArr：按出发/到达城市查询航班（需IATA三字码）
searchFlightsByNumber：按航班号查询航班信息
getFlightTransferInfo｀：查询中转航班信息
searchFlightitineraries：查询可购买航班行程和最低价
**IATA三字码示例**：
城市码：北京=BJS，上海=SHA，广州=CAN，西安=XIY，成都=CTU
机场码：首都机场=PEK，浦东=PVG，虹桥=SHA
**工作流程**·
1．分析用户查询，提取出发地、目的地、日期
2，如果用户说"明天"等相对日期，先调用getTodayDate获取今天日期
3.如果查询城市有多个机场，使用depcity/arrcity参数
4.如果查询具体机场，使用dep/arr参数
**输出格式**
航班{航班号}
出发：{机场}{时间}
到达：{机场】{时间}
－价格：¥{价格}
**注意**：
一定要调用工具，不要编造数据
日期格式必须是YYYY-MM-DD
如果没找到航班，明确告知用户
        """
    )
    app_logger.info('航班subagent创建完成')
    return agent