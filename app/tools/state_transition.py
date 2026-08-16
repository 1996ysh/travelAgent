"""
状态转化工具
用于handoffs流程中的步骤跳转和数据记录
"""
from datetime import datetime
from typing import Optional

from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langgraph.prebuilt import ToolRuntime
from langgraph.types import Command

from app.core.state import TravelState, UserRequirement
from app.utils.logger import app_logger

# step:需求收集->目的地选择->交通方式选择->住宿偏好->餐饮偏好->行程生成->预算汇总->订单生成
# ============== 1️.需求收集工具 ==============

@tool
def record_requirement_tool(
    departure_city: str,
    departure_date: str,
    travel_days: int,
    budget_min: float,
    budget_max: float,
    travel_styles: list[str],  # 传入字符串列表，工具内转换
    special_needs: str = "",
    adult_count: Optional[int] = 1,
    children_count: Optional[int] = 0,
    destination: Optional[str] = None,
    runtime: ToolRuntime[None, TravelState] = None   #这里的runtime参数是langraph框架传进来的  类型第一个参数是工具自身的上下文参数 第二个是graph的state类型
                                                     #这个参数就能配合command参数去修改state节点的状态  也就是对应的TravelState
)->Command:
    """
    记录用户旅行需求，并转换到目的地推荐步骤。

    参数(可为空)说明：
    - destination 目的地
    - departure_city 出发地
    - departure_date: 出发日期，格式 YYYY-MM-DD，如 "2025-08-01"
    - travel_days: 出行天数，如 5
    - adult_count: 成人数量
    - children_count: 儿童数量（< 12 岁）
    - budget_min: 预算下限（元/人）
    - budget_max: 预算上限（元/人）
    - travel_styles: 旅行风格列表，可选值：["relaxation", "culture", "adventure", "food"]
    - special_needs: 特殊需求（可选），如 "需要无障碍设施"
    """
    app_logger.info(f"记录用户需求: {departure_date}, {travel_days}天, 预算 {budget_min}-{budget_max}")
    #验证日期格式
    try:
        datetime.strptime(departure_date,"%Y-%m-%d")
    except ValueError:
        return Command(
            update={
                'messages':[
                    ToolMessage(
                        content = '❌ 日期格式错误，请使用 YYYY-MM-DD 格式，如 2025-08-01',
                        tool_call_id = runtime.tool_call_id
                    )
                ]
            }
        )
    # 推断预算等级
    avg_budget = (budget_min + budget_max) / 2
    if avg_budget < 3000:
        budget_level = "economy"
    elif avg_budget < 8000:
        budget_level = "comfort"
    else:
        budget_level = "luxury"
    # 构建需求对象
    requirement = UserRequirement(
        departure_city=departure_city,
        destination=destination,
        departure_date=departure_date,
        travel_days=travel_days,
        adult_count=adult_count,
        children_count=children_count,
        budget_min=budget_min,
        budget_max=budget_max,
        budget_level=budget_level,
        travel_styles=travel_styles,
        special_needs=special_needs if special_needs else None
    )

    # 返回 Command：更新状态并跳转到下一步
    return Command(update={
        "messages": [
            ToolMessage(
                content=f"需求已记录！\n"
                        f"出发日期：{departure_date}\n"
                        f"{travel_days} 天 | {adult_count + children_count} 人\n"
                        f"预算：{budget_min}-{budget_max} 元/人（{budget_level}级）\n"
                        f"风格：{', '.join(travel_styles)}",
                tool_call_id=runtime.tool_call_id
            )
        ],
        "user_requirement": requirement,
        "current_step": "destination_recommendation"  # 跳转到步骤2
    })

# ============== 2️.目的地选择工具 ==============

@tool
def select_destination_tool(
        destination:str,
        runtime:ToolRuntime[None,TravelState]=None
)->Command:
    """
    确认用户选择的目的地，并转换到交通规划步骤。

    参数说明：
    - destination: 目的地名称，如 "西安"、"成都"
    """
    app_logger.info(f"用户选择目的地: {destination}")
    return Command(
        update={
            'messages':[
                ToolMessage(
                    content=f'目的地已确认:{destination}',
                    tool_call_id = runtime.tool_call_id
                )
            ],
            'selected_destination': destination,
            "current_step": "transport_planning"  # 跳转到步骤3
        }

    )

# ============== 3️.交通方式选择工具 ==============
@tool
def select_transport_tool(
        transport_type: str,  # "flight" | "train" | "driving"
        runtime: ToolRuntime[None, TravelState] = None
)->Command:
    """
    确认用户选择的交通方式，并转换到住宿规划步骤。

    参数说明：
    - transport_type: 交通方式，可选值：flight（航班）、train（高铁）、driving（自驾）
    """

    app_logger.info(f"用户选择交通方式: {transport_type}")
    # 验证枚举值
    if transport_type not in ["flight", "train", "driving"]:
        return Command(update={
            "messages": [
                ToolMessage(
                    content="❌交通方式无效，请选择：flight、train 或 driving",
                    tool_call_id=runtime.tool_call_id
                )
            ]
        })

    transport_labels = {
        "flight": "航班",
        "train": "高铁",
        "driving": "自驾"
    }
    return Command(update={
        "messages": [
            ToolMessage(
                content=f"交通方式已确认：{transport_labels[transport_type]}",
                tool_call_id=runtime.tool_call_id
            )
        ],
        "selected_transport": transport_type,
        "current_step": "accommodation_planning"  # 跳转到步骤4
    })
# ============== 4️.住宿偏好选择工具 ==============
@tool
def select_accommodation_tool(
        accommodation_types: list[str],  # 可多选
        runtime: ToolRuntime[None, TravelState] = None
) -> Command:
    """
    确认用户选择的住宿偏好（可多选），并转换到餐饮规划步骤。

    参数说明：
    - accommodation_types: 住宿类型列表，可选值：
      ["star_hotel", "economy_hotel", "hostel", "youth_hostel"]
    """

    app_logger.info(f"用户选择住宿类型: {accommodation_types}")

    # 验证枚举值
    valid_types = {"star_hotel", "economy_hotel", "hostel", "youth_hostel"}
    if not all(t in valid_types for t in accommodation_types):
        return Command(update={
            "messages": [
                ToolMessage(
                    content=f"❌住宿类型无效，请从以下选择：{', '.join(valid_types)}",
                    tool_call_id=runtime.tool_call_id
                )
            ]
        })
    type_labels = {
        "star_hotel": "星级酒店",
        "economy_hotel": "经济酒店",
        "hostel": "特色民宿",
        "youth_hostel": "青年旅社"
    }
    selected_labels = [type_labels[t] for t in accommodation_types]
    return Command(update={
        "messages": [
            ToolMessage(
                content=f"住宿偏好已确认：{', '.join(selected_labels)}",
                tool_call_id=runtime.tool_call_id
            )
        ],
        "selected_accommodation_types": accommodation_types,
        "current_step": "food_planning"  # 跳转到步骤5
    })
# ============== 5️.餐饮偏好选择工具 ==============

@tool
def select_food_tool(
        food_types: list[str],  # 可多选
        runtime: ToolRuntime[None, TravelState] = None
) -> Command:
    """
    确认用户选择的餐饮偏好（可多选），并转换到行程生成步骤。

    参数说明：
    - food_types: 餐饮类型列表，可选值：["specialty", "chain", "local"]
    """

    app_logger.info(f"用户选择餐饮类型: {food_types}")

    # 验证枚举值
    valid_types = {"specialty", "chain", "local"}
    if not all(t in valid_types for t in food_types):
        return Command(update={
            "messages": [
                ToolMessage(
                    content=f"❌ 餐饮类型无效，请从以下选择：{', '.join(valid_types)}",
                    tool_call_id=runtime.tool_call_id
                )
            ]
        })

    type_labels = {
        "specialty": "🍽️ 特色美食",
        "chain": "🍔 连锁快餐",
        "local": "🥘 本地小吃"
    }

    selected_labels = [type_labels[t] for t in food_types]

    return Command(update={
        "messages": [
            ToolMessage(
                content=f"餐饮偏好已确认：{', '.join(selected_labels)}",
                tool_call_id=runtime.tool_call_id
            )
        ],
        "selected_food_types": food_types,
        "current_step": "itinerary_generation"  # 跳转到步骤6
    })

# ============== 6️.行程生成工具 ==============

@tool
def generate_itinerary_tool(
        runtime: ToolRuntime[None, TravelState] = None
) -> Command:
    """
    生成完整行程安排，并转换到预算汇总步骤。

    此工具会综合：
    - 用户需求（天数、人数、风格）
    - 目的地信息
    - 交通信息
    - 住宿信息
    - 餐饮信息

    生成详细的每日行程。
    """
    app_logger.info("开始生成行程...")
    state = runtime.state
    #检查必要信息是否完整
    required_fields=[
        "user_requirement",
        "selected_destination",
        "selected_transport",
        "selected_accommodation_types",
        "selected_food_types"
    ]
    missing = [f for f in required_fields if f not in state or state[f] is None]
    if missing:
        return Command(
            update={
                'messages':[
                    ToolMessage(
                        content=f"❌ 信息不完整，缺少：{', '.join(missing)}",
                        tool_call_id=runtime.tool_call_id
                    )
                ]
            }
        )
    # 生成行程（简化版，实际应调用 LLM）
    travel_days = state["user_requirement"]["travel_days"]
    itinerary = []

    for day in range(1, travel_days + 1):
        itinerary.append({
            "day_number": day,
            "activities": [f"第{day}天活动1", f"第{day}天活动2"],
            "meals": ["早餐", "午餐", "晚餐"],
            "accommodation": "酒店名称"
        })

    return Command(update={
        "messages": [
            ToolMessage(
                content=f"已生成 {travel_days} 天详细行程！",
                tool_call_id=runtime.tool_call_id
            )
        ],
        "itinerary": itinerary,
        "current_step": "budget_summarization"  # 跳转到步骤7
    })


# ============== 7️.预算汇总工具 ==============

@tool
def summarize_budget_tool(
        runtime: ToolRuntime[None, TravelState] = None
) -> Command:
    """
    汇总各项费用，生成预算明细，并转换到订单生成步骤。

    预算明细包括：
    - 交通费用
    - 住宿费用
    - 餐饮费用
    - 景点门票
    - 其他杂费
    """

    app_logger.info("开始计算预算...")

    state = runtime.state

    # 简化版计算（实际应基于查询结果）
    requirement = state["user_requirement"]
    total_people = requirement["adult_count"] + requirement["children_count"]
    travel_days = requirement["travel_days"]

    # 估算费用
    transport_cost = 500 * total_people  # 人均交通
    accommodation_cost = 300 * travel_days * total_people  # 人均住宿
    food_cost = 150 * travel_days * total_people  # 人均餐饮
    attractions_cost = 200 * travel_days * total_people  # 人均门票
    misc_cost = 100 * travel_days * total_people  # 人均杂费

    total_cost = transport_cost + accommodation_cost + food_cost + attractions_cost + misc_cost

    budget_breakdown = {
        "transport": transport_cost,
        "accommodation": accommodation_cost,
        "food": food_cost,
        "attractions": attractions_cost,
        "misc": misc_cost,
        "total": total_cost
    }

    return Command(update={
        "messages": [
            ToolMessage(
                content=f"预算汇总完成！\n"
                        f"总计：{total_cost:.2f} 元\n"
                        f"   - 交通：{transport_cost:.2f}\n"
                        f"   - 住宿：{accommodation_cost:.2f}\n"
                        f"   - 餐饮：{food_cost:.2f}\n"
                        f"   - 门票：{attractions_cost:.2f}\n"
                        f"   - 其他：{misc_cost:.2f}",
                tool_call_id=runtime.tool_call_id
            )
        ],
        "budget": budget_breakdown,
        "current_step": "order_generation"  # 跳转到步骤8
    })


# ============== 8️.订单生成工具 ==============

@tool
def generate_order_tool(
        runtime: ToolRuntime[None, TravelState] = None
) -> Command:
    """
    生成最终订单，完成整个旅行规划流程。

    订单包含：
    - 订单号
    - 完整行程
    - 预算明细
    - 支付链接（模拟）
    """

    app_logger.info("📋 生成订单...")

    import uuid
    order_id = f"ORDER-{uuid.uuid4().hex[:8].upper()}"

    return Command(update={
        "messages": [
            ToolMessage(
                content=f"🎉 订单生成成功！\n"
                        f"📋 订单号：{order_id}\n"
                        f"💳 支付链接：https://pay.example.com/{order_id}\n\n"
                        f"感谢使用智能旅行规划系统！",
                tool_call_id=runtime.tool_call_id
            )
        ],
        "order_id": order_id,
        # 流程结束，不再更新 current_step
    })

