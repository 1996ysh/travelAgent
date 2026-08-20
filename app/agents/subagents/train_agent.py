"""
航班查询subagent
调用aviation mcp 的多个工具
"""
from langchain.agents import create_agent
from langchain_community.chat_models import ChatTongyi

from app.config import settings
from app.mcp_core.client import get_mcp_client
from app.utils.logger import app_logger


async def _get_railway_tools():
    """获取高铁相关的mcp工具"""
    manager = await get_mcp_client()
    all_tools = await manager.get_tools()
    #筛选航班工具
    railway_tools = [
        tool for tool in all_tools
        if any(keyword in tool.name.lower() for keyword in['station','ticket','train','get-current-date'])
    ]
    app_logger.info(f'高铁工具:{[t.name for t in railway_tools]}')
    return railway_tools

async def create_train_subagent():
    """创建高铁查询"""

    llm = ChatTongyi(
        model=settings.qwen_model_name,
        api_key=settings.dashscope_api_key,
        temperature = 0.1
    )
    #异步获取工具
    railway_tools = await _get_railway_tools()
    agent = create_agent(
        model=llm,
        tools=railway_tools,
        system_prompt="""
        你是高铁查询专家，负责处理火车票查询、行程规划以及车次详情查询。可以使用一下工具:
        **可用工具**：
**可用工具**：
1.
**日期与基础信息**：
get-current-date：获取今日日期（yyyy-MM-dd)。用户提到"明天/下周"时必须先调用此工具。
get-station-code-of-citys：用【城市名】(如"北京"）查询对应的车站代码。
get-station-code-by-names：用【具体车站名】（如"北京南"）查询对应的车站代码。
get-stations-code-in-city：查询某城市内【所有】火车站列表。

2.**余票查询（核心）**：
get-tickets：查询【直达】车次余票。参数：出发/到达代码、日期、车次类型(G/D等)。
get-interline-tickets：查询【中转/接续】方案。**当直达无票，或用户明确询问中转时使用此工具**
3.**车次详情**：
get-train-route-stations：查询某具体车次(如G1o1)的【经停站、时刻表】信息。
**查询流程**:

1.**日期处理**：首先解析日期，若为相对日期必须调用get-current-date计算目标日期。

2.**地点编码**：
-严禁直接将中文地名传给查询接口。
-若用户输入是城市（"北京到上海"），用｀get-station-code-of-citys`。
-若用户输入是具体车站（"北京南到上海虹桥"），用｀get-station-code-by-names`。

3.**余票查询策略**：
-优先调用get-tickets查直达。
**如果get-tickets返回无票，或用户询问"有没有中转"，请立即尝试调用get-interline-tickets

4.**经停查询**：仅当用户询问"这趟车经过哪里"或"时刻表"时，使用get-train-route-stations。
**输出格式**：
请以结构化清晰的方式回答,包含：车次、起降时间、时长、各席别余票与价格。如果是中转方案，请清除标明中转站和换乘时间
        """
    )
    app_logger.info('高铁subagent创建完成')
    return agent