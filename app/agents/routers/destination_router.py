"""
目的地router
并行查询探索agent和天气agent
"""
import json
from operator import add
from typing import TypedDict, Literal, Annotated

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langgraph.constants import START, END
from langgraph.graph import StateGraph
from langgraph.types import Send
from pydantic import BaseModel, Field

from app.config import settings
from app.mcp_core.servers.weather_server import get_weather_forecast
from app.tools.rag_tools import get_rag_tools
from app.utils.city_adcode import resolve_city_adcode
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

async def classifier_node(state:DestinationRouterState)->dict:
    """
    分类器节点:分析查询意图，决定调用哪些agent
    :param state:
    :return:
    """
    app_logger.info(f"🔀 分类器分析查询: {state['original_query']}")
    # 初始化 LLM（带结构化输出）
    # 初始化模型
    llm = ChatOpenAI(
        model=settings.qwen_model_name,
        base_url=settings.qwen_base_url,
        api_key=settings.dashscope_api_key,
        temperature=0,
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
async def _create_explore_agent():
    """创建带 RAG 工具的探索 Agent"""
    # 初始化模型
    llm = ChatOpenAI(
        model=settings.qwen_model_name,
        base_url=settings.qwen_base_url,
        api_key=settings.dashscope_api_key,
        temperature=0,
    )
    # 获取 RAG 工具
    rag_tools = get_rag_tools()
    # 创建 Agent - Agent 会自主决定调用哪些工具
    agent = create_agent(
        model=llm,
        tools=rag_tools,
        system_prompt="""你是一位专业的旅行顾问，负责为用户提供目的地的详细信息。

    你有以下工具可以使用：
    - search_destination_guide: 目的地概览（景点、门票、行程骨架；美食/住宿仅轻度提及）
    - search_food_recommendations: 分城市美食详细资料（必吃、街区、餐次、饮食注意）
    - search_accommodation_info: 分城市住宿区域详细资料（选区对比、价位、动线；可订酒店另用酒店工具）
    - search_travel_tips: 分城市出行建议详细资料（季节、交通、避坑、预约、安全）

    **工作方式**：
    1. 分析用户的查询需求
    2. 根据需要选择合适的工具进行检索（细节问题优先用对应专用工具）
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
        _explore_agent = await _create_explore_agent()
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


def _format_weather_forecast(destination: str, raw_json: str) -> str:
    """将天气 API JSON 格式化为可读 Markdown。"""
    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError:
        return f"## {destination} 天气信息\n\n{raw_json}"

    if "error" in data:
        return (
            f"## {destination} 天气信息\n\n"
            f"⚠️ 查询失败：{data.get('error')}"
            + (f"（infocode={data.get('infocode')}）" if data.get("infocode") else "")
        )

    city = data.get("city") or destination
    province = data.get("province", "")
    reporttime = data.get("reporttime", "")
    casts = data.get("casts") or []

    lines = [
        f"## {city} 天气信息",
        "",
        f"- 地区：{province}{city}" if province else f"- 地区：{city}",
    ]
    if reporttime:
        lines.append(f"- 发布时间：{reporttime}")
    lines.append("")

    if not casts:
        lines.append("暂无预报数据。")
        return "\n".join(lines)

    for cast in casts:
        date = cast.get("date", "未知日期")
        week = cast.get("week", "")
        dayweather = cast.get("dayweather", "")
        nightweather = cast.get("nightweather", "")
        daytemp = cast.get("daytemp", "")
        nighttemp = cast.get("nighttemp", "")
        daywind = cast.get("daywind", "")
        daypower = cast.get("daypower", "")

        week_label = f"（周{week}）" if week else ""
        wind_label = f"，{daywind}风 {daypower}级" if daywind or daypower else ""
        lines.append(
            f"- **{date}{week_label}**：白天 {dayweather} {daytemp}°C / "
            f"夜间 {nightweather} {nighttemp}°C{wind_label}"
        )

    lines.append("")
    lines.append("*信息来源：高德天气预报*")
    return "\n".join(lines)


async def weather_agent_node(state: dict) -> dict:
    """
    天气 Agent：解析城市 adcode 后调用高德天气预报 API
    """
    query = state["query"]
    destination = state["destination"]

    app_logger.info(f"🌤️ 天气 Agent 执行: {query} @ {destination}")

    adcode = resolve_city_adcode(destination)
    if not adcode:
        result = (
            f"## {destination} 天气信息\n\n"
            f"⚠️ 暂无法解析「{destination}」的城市编码（adcode），"
            f"请换用更常见的城市名（如「西安」「成都」）后重试。"
        )
    else:
        try:
            raw = await get_weather_forecast(adcode)
            result = _format_weather_forecast(destination, raw)
            app_logger.info(f"✅ 天气查询完成: {destination} ({adcode})")
        except Exception as e:
            app_logger.error(f"❌ 天气查询异常: {e}")
            result = f"## {destination} 天气信息\n\n⚠️ 天气服务异常：{e}"

    return {
        "agent_results": [
            {
                "agent_name": "weather",
                "result": result,
            }
        ]
    }


# ============== 综合器 ==============

_AGENT_SECTION_TITLES = {
    "explore": "景点与攻略",
    "weather": "天气实况与预报",
}


async def synthesizer_node(state: DestinationRouterState) -> dict:
    """
    综合器节点：按固定章节顺序合并多个 Agent 的结果。

    不引入额外 LLM 调用，保证延迟可控、结果可测；
    章节标题按 agent 类型规范化，避免简单字符串硬拼。
    """
    app_logger.info("📋 综合 Agent 结果...")

    results = state["agent_results"]
    if not results:
        return {"final_report": "未找到相关信息。"}

    # 固定顺序：探索优先，天气其次，其余按出现顺序追加
    preferred_order = ["explore", "weather"]
    by_name: dict[str, str] = {}
    for agent_output in results:
        by_name[agent_output["agent_name"]] = agent_output["result"]

    ordered_names = [n for n in preferred_order if n in by_name]
    ordered_names.extend(n for n in by_name if n not in preferred_order)

    sections = []
    destination = state.get("destination", "")
    header = f"# {destination} 目的地综合报告\n" if destination else "# 目的地综合报告\n"
    sections.append(header)

    for name in ordered_names:
        title = _AGENT_SECTION_TITLES.get(name, name)
        body = by_name[name].strip()
        sections.append(f"## {title}\n\n{body}")

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