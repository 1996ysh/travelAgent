"""
目的地router
并行查询探索agent和天气agent
"""
from _operator import add
from typing import TypedDict, Literal, Annotated

from langchain.agents import create_agent
from langchain_community.chat_models import ChatTongyi
from langgraph.constants import START, END
from langgraph.graph import StateGraph
from langgraph.types import Send
from pydantic import BaseModel, Field

from app.config import settings
from app.tools.rag_tools import get_rag_tools
from app.utils.logger import app_logger


#state定义
class Classification(TypedDict):
    """分类结果"""
    agent:Literal['explore','weather']
    query:str
class AgentOutput(TypedDict):
    """agent输出"""
    agent_name:str
    result:str
##这个是graph里面的主图state
class DestinationRouterState(TypedDict):
    """router状态"""
    original_query:str
    destination:str
    classifications:list[Classification]
    agent_results:Annotated[list[AgentOutput],add]
    final_report:str
#分类器

class ClassificationResult(BaseModel):
    """分类结果(结构化输出)"""
    classifications:list[Classification]=Field(description='要调用的agent列表及其子查询')

def classifier_node(state:DestinationRouterState)->dict:
    """
    分类器节点:分析查询意图，决定调用哪些agent
    :param state:
    :return:
    """
    app_logger.info(f"🔀 分类器分析查询: {state['original_query']}")
    # 初始化 LLM（带结构化输出）
    llm = ChatTongyi(
        model="qwen-plus",
        api_key=settings.dashscope_api_key
    )
    structured_llm = llm.with_structured_output(ClassificationResult)
    # 调用 LLM 分类
    result = structured_llm.invoke([
        {
            "role": "system",
            "content": """你是旅行查询分类专家。

    分析用户查询，决定需要调用哪些 Agent：

    **可用 Agent**：
    - explore：景点攻略、美食推荐、住宿信息、交通指南（从知识库检索）
    - weather：实时天气信息（调用天气 API）

    **分类规则**：
    1. 如果查询涉及景点、美食、住宿、攻略 → 调用 explore
    2. 如果查询涉及天气、气温、降雨 → 调用 weather
    3. 如果查询是综合性的（如"推荐XX旅游"）→ 调用两个 Agent

    **输出格式**：
    返回 JSON，包含 classifications 列表，每项包括：
    - agent: "explore" 或 "weather"
    - query: 针对该 Agent 的具体子查询

    **示例**：
    用户：西安有什么好玩的？
    输出：[{"agent": "explore", "query": "西安景点推荐"}]

    用户：西安现在天气如何？
    输出：[{"agent": "weather", "query": "西安天气"}]

    用户：推荐西安旅游
    输出：[
      {"agent": "explore", "query": "西安旅游攻略"},
      {"agent": "weather", "query": "西安当前天气"}
    ]
    """
        },
        {
            "role": "user",
            "content": f"目的地：{state['destination']}\n查询：{state['original_query']}"
        }
    ])
    app_logger.info(f"✅ 分类完成：{len(result.classifications)} 个 Agent")
    for c in result.classifications:
        app_logger.debug(f"   - {c['agent']}: {c['query']}")
    return {"classifications": result.classifications}

# ============== 路由函数 ==============

def route_to_agents(state: DestinationRouterState) -> list[Send]:
    """
    路由函数：根据分类结果，并行发送任务给 Agent

    返回 Send 对象列表，LangGraph 会并行执行
    """

    sends = []

    for classification in state["classifications"]:
        agent_name = classification["agent"]

        # 创建 Send 对象
        sends.append(
            Send(
                agent_name,  # 目标节点名称
                {
                    "query": classification["query"],
                    "destination": state["destination"]
                }
            )
        )

    app_logger.info(f"📤 并行发送 {len(sends)} 个任务")

    return sends
# 创建探索 Agent（带 RAG 工具）
def _create_explore_agent():
    """创建带 RAG 工具的探索 Agent"""
    llm = ChatTongyi(
        model=settings.qwen_model_name,
        api_key=settings.dashscope_api_key,
        temperature=0.7
    )
    # 获取 RAG 工具
    rag_tools = get_rag_tools()
    # 创建 Agent - Agent 会自主决定调用哪些工具
    agent = create_agent(
        model=llm,
        tools=rag_tools,
        system_prompt="""你是一位专业的旅行顾问，负责为用户提供目的地的详细信息。

    你有以下工具可以使用：
    - search_destination_guide: 检索景点攻略、门票、游玩建议
    - search_food_recommendations: 检索美食推荐
    - search_accommodation_info: 检索住宿建议
    - search_travel_tips: 检索旅行注意事项

    **工作方式**：
    1. 分析用户的查询需求
    2. 根据需要选择合适的工具进行检索
    3. 你可以调用多个工具来获取全面的信息
    4. 基于检索到的信息，生成专业、详细的回答

    **注意**：
    - 只有当你需要知识库中的信息时才调用工具
    - 如果用户只是闲聊或问简单问题，直接回答即可
    - 整合多个工具的结果时，注意信息的逻辑性和连贯性
    """
    )
    return agent
# 全局 Agent 实例（避免重复创建）
_explore_agent = None
# ============== Agent 节点 ==============

async def explore_agent_node(state: dict) -> dict:
    """
    探索 Agent：从 RAG 检索景点攻略
    Agent 自主决定是否调用 RAG 工具
    """
    global _explore_agent
    query = state["query"]
    destination = state["destination"]

    app_logger.info(f"🏛️ 探索 Agent 执行: {query}")
    # 懒加载 Agent
    if _explore_agent is None:
        _explore_agent = _create_explore_agent()
    # 构建用户消息
    user_message = f"请为我提供关于 {destination} 的以下信息：{query}"
    # 调用 Agent - Agent 会自主决定是否使用 RAG 工具
    response = await _explore_agent.ainvoke({
        "messages": [{"role": "user", "content": user_message}]
    })

    # 提取 Agent 的最终回复
    final_message = response["messages"][-1].content

    formatted_result = f"""## {destination} 旅游信息

    {final_message}

    ---
    *信息来源：知识库检索*
    """

    return {
        "agent_results": [
            {
                "agent_name": "explore",
                "result": formatted_result
            }
        ]
    }


def weather_agent_node(state: dict) -> dict:
    """
    天气 Agent：调用天气 API
    """

    query = state["query"]
    destination = state["destination"]

    app_logger.info(f"🌤️ 天气 Agent 执行: {query}")

    # TODO: 实际调用高德天气 API
    # 这里先返回模拟结果

    result = f"""## {destination} 天气信息

📅 今天：晴，25-32°C，空气质量良
📅 明天：多云，24-30°C
📅 后天：阵雨，22-28°C

（此处为简化示例，实际会调用天气 API）
"""

    return {
        "agent_results": [
            {
                "agent_name": "weather",
                "result": result
            }
        ]
    }


# ============== 综合器 ==============

async def synthesizer_node(state: DestinationRouterState) -> dict:
    """
    综合器节点：合并多个 Agent 的结果
    """

    app_logger.info("📋 综合 Agent 结果...")

    results = state["agent_results"]

    if not results:
        return {"final_report": "未找到相关信息。"}

    # 简单合并 todo（生产环境应使用 LLM 生成连贯报告）
    sections = []

    for agent_output in results:
        sections.append(f"**来自 {agent_output['agent_name']}：**\n{agent_output['result']}")

    final_report = "\n\n".join(sections)

    app_logger.info("✅ 综合完成")

    return {"final_report": final_report}


# ============== 构建 Router 图 ==============

def create_destination_router():
    """创建目的地 Router"""

    workflow = StateGraph(DestinationRouterState)

    # 添加节点
    workflow.add_node("classifier", classifier_node)
    workflow.add_node("explore", explore_agent_node)
    workflow.add_node("weather", weather_agent_node)
    workflow.add_node("synthesizer", synthesizer_node)

    # 添加边
    workflow.add_edge(START, "classifier")
    workflow.add_conditional_edges(
        "classifier",
        route_to_agents,
        ["explore", "weather"]
    )
    workflow.add_edge("explore", "synthesizer")
    workflow.add_edge("weather", "synthesizer")
    workflow.add_edge("synthesizer", END)

    # 编译
    app = workflow.compile()

    app_logger.info("✅ 目的地 Router 创建完成")

    return app