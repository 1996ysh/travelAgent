#回退工具
# 所有可用步骤
from typing import Literal

from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langgraph.prebuilt import ToolRuntime
from langgraph.types import Command

from app.utils.logger import app_logger

ALL_STEPS = [
    "requirement_collection",       # 步骤1：需求收集
    "destination_recommendation",   # 步骤2：目的地推荐
    "transport_planning",           # 步骤3：交通规划
    "accommodation_planning",       # 步骤4：住宿规划
    "food_planning",                # 步骤5：餐饮规划
    "itinerary_generation",         # 步骤6：行程生成
    "budget_summarization",         # 步骤7：预算汇总
    "order_generation"              # 步骤8：订单生成
]
# 步骤中文名称映射
STEP_LABELS = {
    "requirement_collection": "需求收集",
    "destination_recommendation": "目的地推荐",
    "transport_planning": "交通规划",
    "accommodation_planning": "住宿规划",
    "food_planning": "餐饮规划",
    "itinerary_generation": "行程生成",
    "budget_summarization": "预算汇总",
    "order_generation": "订单生成"
}
# 每个步骤回退时需要清除的状态字段  这里的意思就是回退key的时候  清除这个key的value里面字段的值
STEP_STATE_FIELDS = {
    "requirement_collection": ["user_requirement"],
    "destination_recommendation": ["selected_destination", "destination_options"],
    "transport_planning": ["selected_transport", "transport_options"],
    "accommodation_planning": ["selected_accommodation_types", "accommodation_options"],
    "food_planning": ["selected_food_types", "food_options"],
    "itinerary_generation": ["itinerary"],
    "budget_summarization": ["budget"],
    "order_generation": ["order_id"]
}
# ============== 通用回退工具 ==============

@tool
def go_back_to_step(
        target_step: Literal[
            "requirement_collection",
            "destination_recommendation",
            "transport_planning",
            "accommodation_planning",
            "food_planning",
            "itinerary_generation",
            "budget_summarization"
        ],
        reason: str,
        clear_subsequent_data: bool = True,
        runtime: ToolRuntime = None
) -> Command:
    """
    回退到指定的历史步骤，允许用户重新进行规划。

    使用场景示例：
    - 用户说"我想重新选择目的地" -> target_step="destination_recommendation"
    - 用户说"我想重新制定旅行计划" -> target_step="requirement_collection"
    - 用户说"换个交通方式" -> target_step="transport_planning"
    - 用户说"住宿要求改一下" -> target_step="accommodation_planning"
    - 用户说"餐饮偏好不对" -> target_step="food_planning"
    - 用户说"行程安排需要调整" -> target_step="itinerary_generation"
    - 用户说"预算超了，重新算" -> target_step="budget_summarization"

    参数说明：
    - target_step: 要回退到的目标步骤
        * "requirement_collection" - 重新收集旅行需求（出发日期、人数、预算等）
        * "destination_recommendation" - 重新选择目的地
        * "transport_planning" - 重新选择交通方式（航班/高铁/自驾）
        * "accommodation_planning" - 重新选择住宿类型
        * "food_planning" - 重新选择餐饮偏好
        * "itinerary_generation" - 重新生成行程安排
        * "budget_summarization" - 重新计算预算

    - reason: 回退原因，用于记录和展示给用户
        示例："用户希望更换目的地为三亚"
        示例："预算超出用户预期，需要调整住宿标准"

    - clear_subsequent_data: 是否清除目标步骤之后的所有数据（默认 True）
        * True: 回退时清除后续步骤产生的选择和数据
        * False: 保留后续数据（谨慎使用，可能导致数据不一致）

    返回：
        Command 对象，包含状态更新和步骤跳转指令

    注意：
    - 不能回退到 "order_generation"（订单生成是最终步骤）
    - 回退会在消息历史中记录，方便追溯
    """
    app_logger.info(f"回退请求: target_step={target_step}, reason={reason}, clear_data={clear_subsequent_data}")
    # 验证目标步骤
    if target_step not in ALL_STEPS:
        app_logger.warning(f"无效的目标步骤: {target_step}")
        return Command(update={
            "messages": [
                ToolMessage(
                    content=f"无效的目标步骤: {target_step}",
                    tool_call_id=runtime.tool_call_id
                )
            ]
        })
    # 不允许回退到订单生成（最终步骤）
    if target_step == "order_generation":
        app_logger.warning("尝试回退到订单生成步骤，已拒绝")
        return Command(update={
            "messages": [
                ToolMessage(
                    content="订单生成是最终步骤，无法回退到此步骤。如需修改，请回退到更早的步骤。",
                    tool_call_id=runtime.tool_call_id
                )
            ]
        })
    # 获取当前步骤（用于日志）
    current_step = runtime.state.get("current_step", "unknown") if runtime.state else "unknown"
    app_logger.info(f"执行回退: {current_step} -> {target_step}")
    # 构建状态更新
    state_update = {
        "current_step": target_step
    }
    # 如果需要清除后续数据  这里的数据就是target_step  也就是要回退的步骤的数据
    cleared_fields = []
    if clear_subsequent_data:
        #返回target_step在ALL_STEPS的下标
        target_index = ALL_STEPS.index(target_step)
        for step in ALL_STEPS[target_index:]:
            for field in STEP_STATE_FIELDS.get(step, []):
                state_update[field] = None
                cleared_fields.append(field)

        if cleared_fields:
            app_logger.debug(f"清除的状态字段: {cleared_fields}")

    step_label = STEP_LABELS.get(target_step,target_step)
    # 构建响应消息
    response_parts = [
        f"已回退到【{step_label}】阶段",
        f"原因: {reason}"
    ]
    if clear_subsequent_data and cleared_fields:
        response_parts.append("已清除后续步骤的数据")

    state_update["messages"] = [
        ToolMessage(
            content="\n".join(response_parts),
            tool_call_id=runtime.tool_call_id
        )
    ]

    app_logger.info(f"回退完成: {target_step}, 清除字段数: {len(cleared_fields)}")

    return Command(update={
        'messages':[
        ToolMessage(
            content="\n".join(response_parts),
            tool_call_id=runtime.tool_call_id
        )
      ]
    })
# ============== 快捷回退工具 ==============
##这里的快捷实际上就是传入具体的参数到通用的back def上
@tool
def go_back_to_requirement(
        reason: str = "用户需要修改旅行需求",
        runtime: ToolRuntime = None
) -> Command:
    """
        快捷回退：返回到需求收集步骤，重新开始规划。

        使用场景：
        - 用户说"我想重新规划"
        - 用户说"出发日期要改"
        - 用户说"预算变了"
        - 用户说"人数不对"
        - 用户说"从头开始"

        参数：
        - reason: 回退原因（可选，默认为"用户需要修改旅行需求"）

        效果：
        - 清除所有已收集的数据
        - 返回到最初的需求收集阶段
        """
    app_logger.info(f"快捷回退到需求收集: {reason}")
    return go_back_to_step.invoke({
        "target_step": "requirement_collection",
        "reason": reason,
        "clear_subsequent_data": True,
        "runtime": runtime
    })
@tool
def go_back_to_transport(
        reason: str = "用户需要更换交通方式",
        runtime: ToolRuntime = None
) -> Command:
    """
    快捷回退：返回到交通规划步骤。

    使用场景：
    - 用户说"不想坐飞机了"
    - 用户说"改成高铁"
    - 用户说"还是自驾吧"
    - 用户说"交通方式重新选"

    参数：
    - reason: 回退原因（可选）

    效果：
    - 保留用户需求和目的地选择
    - 清除交通方式及后续数据
    """
    app_logger.info(f"快捷回退到交通规划: {reason}")

    return go_back_to_step.invoke({
        "target_step": "transport_planning",
        "reason": reason,
        "clear_subsequent_data": True,
        "runtime": runtime
    })
@tool
def go_back_to_destination(
        reason: str = "用户需要重新选择目的地",
        runtime: ToolRuntime = None
) -> Command:
    """
    快捷回退：返回到目的地推荐步骤。

    使用场景：
    - 用户说"换个目的地"
    - 用户说"这个地方不想去了"
    - 用户说"有没有其他推荐"
    - 用户说"目的地选错了"

    参数：
    - reason: 回退原因（可选）

    效果：
    - 保留用户需求
    - 清除目的地选择及后续所有数据
    """
    app_logger.info(f"快捷回退到目的地推荐: {reason}")

    return go_back_to_step.invoke({
        "target_step": "destination_recommendation",
        "reason": reason,
        "clear_subsequent_data": True,
        "runtime": runtime
    })
@tool
def go_back_to_transport(
        reason: str = "用户需要更换交通方式",
        runtime: ToolRuntime = None
) -> Command:
    """
    快捷回退：返回到交通规划步骤。

    使用场景：
    - 用户说"不想坐飞机了"
    - 用户说"改成高铁"
    - 用户说"还是自驾吧"
    - 用户说"交通方式重新选"

    参数：
    - reason: 回退原因（可选）

    效果：
    - 保留用户需求和目的地选择
    - 清除交通方式及后续数据
    """
    app_logger.info(f"快捷回退到交通规划: {reason}")

    return go_back_to_step.invoke({
        "target_step": "transport_planning",
        "reason": reason,
        "clear_subsequent_data": True,
        "runtime": runtime
    })


@tool
def go_back_to_accommodation(
        reason: str = "用户需要调整住宿偏好",
        runtime: ToolRuntime = None
) -> Command:
    """
    快捷回退：返回到住宿规划步骤。

    使用场景：
    - 用户说"住宿要求改一下"
    - 用户说"想住民宿"
    - 用户说"酒店太贵了"
    - 用户说"换个住宿类型"

    参数：
    - reason: 回退原因（可选）

    效果：
    - 保留需求、目的地、交通方式
    - 清除住宿选择及后续数据
    """
    app_logger.info(f"快捷回退到住宿规划: {reason}")
    return go_back_to_step.invoke({
        "target_step": "accommodation_planning",
        "reason": reason,
        "clear_subsequent_data": True,
        "runtime": runtime
    })


@tool
def go_back_to_food(
        reason: str = "用户需要调整餐饮偏好",
        runtime: ToolRuntime = None
) -> Command:
    """
    快捷回退：返回到餐饮规划步骤。

    使用场景：
    - 用户说"餐饮偏好改一下"
    - 用户说"想多吃特色美食"
    - 用户说"简单点就行"

    参数：
    - reason: 回退原因（可选）

    效果：
    - 保留需求、目的地、交通、住宿
    - 清除餐饮选择及后续数据
    """
    app_logger.info(f"快捷回退到餐饮规划: {reason}")

    return go_back_to_step.invoke({
        "target_step": "food_planning",
        "reason": reason,
        "clear_subsequent_data": True,
        "runtime": runtime
    })


@tool
def go_back_to_itinerary(
        reason: str = "用户需要调整行程安排",
        runtime: ToolRuntime = None
) -> Command:
    """
    快捷回退：返回到行程生成步骤。

    使用场景：
    - 用户说"行程安排不太合理"
    - 用户说"想加点景点"
    - 用户说"太累了，减少活动"
    - 用户说"重新排一下行程"

    参数：
    - reason: 回退原因（可选）

    效果：
    - 保留所有偏好设置
    - 仅清除行程和预算数据
    """
    app_logger.info(f"快捷回退到行程生成: {reason}")

    return go_back_to_step.invoke({
        "target_step": "itinerary_generation",
        "reason": reason,
        "clear_subsequent_data": True,
        "runtime": runtime
    })


@tool
def go_back_to_budget(
        reason: str = "用户需要重新计算预算",
        runtime: ToolRuntime = None
) -> Command:
    """
    快捷回退：返回到预算汇总步骤。

    使用场景：
    - 用户说"预算超了"
    - 用户说"重新算一下费用"
    - 用户说"看看能不能便宜点"

    参数：
    - reason: 回退原因（可选）

    效果：
    - 保留行程安排
    - 仅清除预算和订单数据
    """
    app_logger.info(f"快捷回退到预算汇总: {reason}")

    return go_back_to_step.invoke({
        "target_step": "budget_summarization",
        "reason": reason,
        "clear_subsequent_data": True,
        "runtime": runtime
    })
# ============== 查询当前进度工具 ==============

@tool
def check_current_progress(
        runtime:ToolRuntime = None
)->str:
    """
    查询当前规划进度，展示已完成和待完成的步骤。

    使用场景：
    - 用户问"现在到哪一步了"
    - 用户问"还有几步"
    - 用户问"进度如何"
    - 需要向用户汇报当前状态

    返回：
        格式化的进度信息字符串
    """
    state = runtime.state
    current_step = state.get('current_step','requirement_collection')
    app_logger.debug(f'查询进度：current_step={current_step}')
    try:
        current_index = ALL_STEPS.index(current_step)
    except ValueError:
        app_logger.warning(f"未知的当前步骤: {current_step}")
        current_index = 0
    # 构建进度展示
    progress_lines = ["当前规划进度", ""]
    for i, step in enumerate(ALL_STEPS):
        label = STEP_LABELS.get(step, step)
        step_num = i + 1
        if i < current_index:
            progress_lines.append(f"  [{step_num}] {label} - 已完成")
        elif i == current_index:
            progress_lines.append(f"  [{step_num}] {label} - 当前步骤")
        else:
            progress_lines.append(f"  [{step_num}] {label} - 待完成")

    #添加已收集的关键信息
    progress_lines.append("")
    progress_lines.append("已收集信息:")

    if state.get('user_requirement'):
        req = state['user_requirement']
        progress_lines.append(f"  - 出发日期: {req.get('departure_date', '未设置')}")
        progress_lines.append(f"  - 出行天数: {req.get('travel_days', '未设置')} 天")
        progress_lines.append(f"  - 人数: {req.get('adult_count', 0)} 成人 + {req.get('children_count', 0)} 儿童")
    if state.get("selected_destination"):
        progress_lines.append(f"  - 目的地: {state['selected_destination']}")
    if state.get("selected_transport"):
        transport_labels = {"flight": "航班", "train": "高铁", "driving": "自驾"}
        progress_lines.append(
            f"  - 交通: {transport_labels.get(state['selected_transport'], state['selected_transport'])}")
    if state.get("selected_accommodation_types"):
        progress_lines.append(f"  - 住宿: {', '.join(state['selected_accommodation_types'])}")

    if state.get("selected_food_types"):
        progress_lines.append(f"  - 餐饮: {', '.join(state['selected_food_types'])}")

    app_logger.info(f"进度查询完成: 当前步骤={current_step}, 进度={current_index + 1}/{len(ALL_STEPS)}")

    return "\n".join(progress_lines)
# ============== 导出所有回退工具 ==============

ALL_ROLLBACK_TOOLS = [
    go_back_to_step,            # 通用回退（推荐）
    go_back_to_requirement,     # 快捷：回到需求收集
    go_back_to_destination,     # 快捷：回到目的地
    go_back_to_transport,       # 快捷：回到交通
    go_back_to_accommodation,   # 快捷：回到住宿
    go_back_to_food,            # 快捷：回到餐饮
    go_back_to_itinerary,       # 快捷：回到行程
    go_back_to_budget,          # 快捷：回到预算
    check_current_progress      # 查询进度
]