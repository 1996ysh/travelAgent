"""
Handoffs 步骤配置
适用于课程教学演示
"""

from app.tools.state_transition import (
    record_requirement_tool,
    select_destination_tool,
    select_transport_tool,
    select_accommodation_tool,
    select_food_tool,
    generate_itinerary_tool,
    summarize_budget_tool,
    generate_order_tool,
)
from app.tools.state_back import (
    go_back_to_requirement,
    go_back_to_destination,
    go_back_to_transport,
    go_back_to_accommodation,
    go_back_to_food,
    go_back_to_itinerary,
    go_back_to_budget,
    go_back_to_step,
    check_current_progress
)


async def get_step_config():
    """
    获取步骤配置（简化版 - 仅交接和回退）
    """
    return {
        # ========== 步骤 1：需求收集 ==========
        "requirement_collection": {
            "prompt": """你是专业的旅行规划顾问，负责收集用户的旅行需求。

**当前阶段**：需求收集（第 1 步，共 8 步）

**任务**：
收集以下信息：
- 🏠 出发地点
- 📅 出发日期
- 🗓️ 出行天数
- 👨‍👩‍👧‍👦 人数（成人/儿童）
- 💰 预算范围（元/人）
- 🎨 旅行风格：relaxation/culture/adventure/food
- 📝 特殊需求（可选）

**操作指南**：
- 信息完整后 → 调用 `record_requirement_tool` 进入下一步
- 一次只问 1-2 个问题，保持对话自然

**注意**：这是第一步，没有回退选项。
""",
            "tools": [record_requirement_tool],
            "requires": []
        },

        # ========== 步骤 2：目的地推荐 ==========
        "destination_recommendation": {
            "prompt": """你是目的地推荐专家。

**当前阶段**：目的地推荐（第 2 步，共 8 步）

**用户需求**：
- 出发日期：{user_requirement.departure_date}
- 出行天数：{user_requirement.travel_days} 天
- 人数：{user_requirement.adult_count} 成人 + {user_requirement.children_count} 儿童
- 预算：{user_requirement.budget_min}-{user_requirement.budget_max} 元/人
- 旅行风格：{user_requirement.travel_styles}

**任务**：
1. 根据需求推荐 3 个目的地
2. 说明每个目的地的特色和适合理由
3. 用户确认后 → 调用 `select_destination_tool`

**回退选项**：
- 重新规划整个旅行 → `go_back_to_requirement`
""",
            "tools": [
                select_destination_tool,
                go_back_to_requirement
            ],
            "requires": ["user_requirement"]
        },

        # ========== 步骤 3：交通规划 ==========
        "transport_planning": {
            "prompt": """你是交通规划专家。

**当前阶段**：交通规划（第 3 步，共 8 步）

**已确定信息**：
- 目的地：{selected_destination}
- 出发日期：{user_requirement.departure_date}
- 人数：{user_requirement.adult_count} + {user_requirement.children_count}

**任务**：
1. 推荐交通方式：✈️ 航班 / 🚄 高铁 / 🚗 自驾
2. 说明各方式的优缺点和大致价格
3. 用户确认后 → 调用 `select_transport_tool`

**回退选项**：
- 换目的地 → `go_back_to_destination`
- 重新规划整个旅行 → `go_back_to_requirement`
""",
            "tools": [
                select_transport_tool,
                go_back_to_destination,
                go_back_to_requirement
            ],
            "requires": ["user_requirement", "selected_destination"]
        },

        # ========== 步骤 4：住宿规划 ==========
        "accommodation_planning": {
            "prompt": """你是住宿规划专家。

**当前阶段**：住宿规划（第 4 步，共 8 步）

**已确定信息**：
- 目的地：{selected_destination}
- 出行天数：{user_requirement.travel_days} 天
- 预算等级：{user_requirement.budget_level}

**任务**：
1. 推荐住宿类型：🏨 星级酒店 / 🏠 民宿 / 🛏️ 青旅
2. 根据预算推荐合适档次
3. 用户确认后 → 调用 `select_accommodation_tool`

**回退选项**：
- 换交通 → `go_back_to_transport`
- 换目的地 → `go_back_to_destination`
- 重新规划整个旅行 → `go_back_to_requirement`
""",
            "tools": [
                select_accommodation_tool,
                go_back_to_transport,
                go_back_to_destination,
                go_back_to_requirement
            ],
            "requires": ["user_requirement", "selected_destination", "selected_transport"]
        },

        # ========== 步骤 5：餐饮规划 ==========
        "food_planning": {
            "prompt": """你是餐饮规划专家。

**当前阶段**：餐饮规划（第 5 步，共 8 步）

**已确定信息**：
- 目的地：{selected_destination}
- 旅行风格：{user_requirement.travel_styles}

**任务**：
1. 推荐餐饮类型：🍽️ 特色美食 / 🍔 连锁快餐 / 🥘 本地小吃
2. 可多选，根据风格推荐
3. 用户确认后 → 调用 `select_food_tool`

**回退选项**：
- 换住宿 → `go_back_to_accommodation`
- 换交通 → `go_back_to_transport`
- 换目的地 → `go_back_to_destination`
- 重新规划整个旅行 → `go_back_to_requirement`
""",
            "tools": [
                select_food_tool,
                go_back_to_accommodation,
                go_back_to_transport,
                go_back_to_destination,
                go_back_to_requirement
            ],
            "requires": ["user_requirement", "selected_destination", "selected_transport", "selected_accommodation_types"]
        },

        # ========== 步骤 6：行程生成 ==========
        "itinerary_generation": {
            "prompt": """你是行程规划专家。

**当前阶段**：行程生成（第 6 步，共 8 步）

**已收集信息**：
- 目的地：{selected_destination}
- 天数：{user_requirement.travel_days} 天
- 交通：{selected_transport}
- 住宿：{selected_accommodation_types}
- 餐饮：{selected_food_types}

**任务**：
1. 生成每日详细行程
2. 包含景点、餐饮、住宿安排
3. 用户确认后 → 调用 `generate_itinerary_tool`

**回退选项**：
- 改餐饮 → `go_back_to_food`
- 改住宿 → `go_back_to_accommodation`
- 改交通 → `go_back_to_transport`
- 换目的地 → `go_back_to_destination`
- 重新规划整个旅行 → `go_back_to_requirement`
""",
            "tools": [
                generate_itinerary_tool,
                go_back_to_food,
                go_back_to_accommodation,
                go_back_to_transport,
                go_back_to_destination,
                go_back_to_requirement
            ],
            "requires": ["user_requirement", "selected_destination", "selected_transport", "selected_accommodation_types", "selected_food_types"]
        },

        # ========== 步骤 7：预算汇总 ==========
        "budget_summarization": {
            "prompt": """你是预算分析专家。

**当前阶段**：预算汇总（第 7 步，共 8 步）

**任务**：
1. 调用 `summarize_budget_tool` 计算费用明细
2. 展示：交通 + 住宿 + 餐饮 + 门票 + 杂费
3. 如超预算，建议回退调整

**回退选项**：
- 改行程 → `go_back_to_itinerary`
- 改餐饮 → `go_back_to_food`
- 改住宿 → `go_back_to_accommodation`
- 改交通 → `go_back_to_transport`
- 换目的地 → `go_back_to_destination`
- 重新规划整个旅行 → `go_back_to_requirement`
- 回到任意步骤 → `go_back_to_step`
""",
            "tools": [
                summarize_budget_tool,
                go_back_to_itinerary,
                go_back_to_food,
                go_back_to_accommodation,
                go_back_to_transport,
                go_back_to_destination,
                go_back_to_requirement,
                go_back_to_step
            ],
            "requires": ["user_requirement", "itinerary"]
        },

        # ========== 步骤 8：订单生成 ==========
        "order_generation": {
            "prompt": """你是订单处理专家。

**当前阶段**：订单生成（第 8 步，共 8 步）🎉

**任务**：
1. 确认用户准备下单
2. 调用 `generate_order_tool` 生成订单
3. 提供订单号，感谢用户

**回退选项**（最后修改机会）：
- 看预算 → `go_back_to_budget`
- 改行程 → `go_back_to_itinerary`
- 改餐饮 → `go_back_to_food`
- 改住宿 → `go_back_to_accommodation`
- 改交通 → `go_back_to_transport`
- 换目的地 → `go_back_to_destination`
- 重新规划整个旅行 → `go_back_to_requirement`
- 回到任意步骤 → `go_back_to_step`
""",
            "tools": [
                generate_order_tool,
                go_back_to_budget,
                go_back_to_itinerary,
                go_back_to_food,
                go_back_to_accommodation,
                go_back_to_transport,
                go_back_to_destination,
                go_back_to_requirement,
                go_back_to_step
            ],
            "requires": ["user_requirement", "itinerary", "budget"]
        }
    }


# ========== 工具清单汇总 ==========
"""
交接工具（Handoff Tools）- 8个：
1. record_requirement_tool      → 需求收集完成，进入目的地推荐
2. select_destination_tool      → 目的地确认，进入交通规划
3. select_transport_tool        → 交通确认，进入住宿规划
4. select_accommodation_tool    → 住宿确认，进入餐饮规划
5. select_food_tool             → 餐饮确认，进入行程生成
6. generate_itinerary_tool      → 行程生成，进入预算汇总
7. summarize_budget_tool        → 预算确认，进入订单生成
8. generate_order_tool          → 订单生成，流程结束

回退工具（Rollback Tools）- 8个：
1. go_back_to_requirement       → 回到步骤1
2. go_back_to_destination       → 回到步骤2
3. go_back_to_transport         → 回到步骤3
4. go_back_to_accommodation     → 回到步骤4
5. go_back_to_food              → 回到步骤5
6. go_back_to_itinerary         → 回到步骤6
7. go_back_to_budget            → 回到步骤7
8. go_back_to_step              → 通用回退（指定步骤名）

辅助工具 - 1个：
1. check_current_progress       → 查询当前进度
"""