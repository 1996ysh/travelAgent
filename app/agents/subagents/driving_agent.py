"""
自驾路线规划 Subagent
调用高德地图 MCP 服务
"""
from langchain_community.chat_models import ChatTongyi
from langchain.agents import create_agent
from langchain.tools import tool
from app.config import settings
from app.utils.logger import app_logger


@tool
async def plan_driving_route_from_mcp(
        origin: str,
        destination: str
) -> str:
    """
    从高德地图 MCP 规划自驾路线

    参数说明：
    - origin: 出发城市
    - destination: 目的地城市

    返回：
    - JSON 格式的路线方案列表
    """

    app_logger.info(f"🚗 规划自驾路线: {origin} -> {destination}")

    # TODO: 实际调用高德地图 MCP

    import json
    mock_routes = [
        {
            "route_name": "推荐路线（高速优先）",
            "distance": "1200 公里",
            "duration": "约 12 小时",
            "toll_fee": 450.0,
            "fuel_cost": 600.0,
            "steps": [
                "从北京市区出发",
                "进入京沪高速（G2）",
                "途经天津、济南、徐州",
                "进入沪宁高速",
                "到达上海市区"
            ],
            "waypoints": ["天津", "济南", "徐州", "南京"]
        },
        {
            "route_name": "省钱路线（国道优先）",
            "distance": "1250 公里",
            "duration": "约 15 小时",
            "toll_fee": 200.0,
            "fuel_cost": 650.0,
            "steps": [
                "从北京市区出发",
                "走国道 G104",
                "途经天津、德州、济南",
                "走省道到达上海"
            ],
            "waypoints": ["天津", "德州", "济南", "扬州"]
        }
    ]

    return json.dumps(mock_routes, ensure_ascii=False, indent=2)


def create_driving_subagent():
    """创建自驾路线规划 Subagent"""

    llm = ChatTongyi(
        model=settings.qwen_model_name,
        api_key=settings.dashscope_api_key,
        temperature=0.3
    )

    agent = create_agent(
        model=llm,
        tools=[plan_driving_route_from_mcp],
        system_prompt="""你是自驾路线规划专家。

**职责**：
1. 接收出发城市、目的地城市
2. 调用 plan_driving_route_from_mcp 工具规划路线
3. 整理路线信息，提供多个方案对比
4. 返回清晰的路线推荐

**输出格式**：
请按以下格式返回路线信息：

找到 N 个路线方案：

1. 【{route_name}】
   - 总距离：{distance}
   - 预计时长：{duration}
   - 过路费：¥{toll_fee}
   - 油费估算：¥{fuel_cost}
   - 途经城市：{waypoints}
   - 主要路段：
     {steps}

**注意事项**：
- 一定要调用工具，不要编造数据
- 提供至少2个不同类型的路线（时间优先、费用优先等）
- 费用估算要合理
"""
    )

    app_logger.info("✅ 自驾 Subagent 创建完成")

    return agent