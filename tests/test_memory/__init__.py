"""
示例1：长期记忆完整演示（可直接运行）
- 写入用户画像：旅行风格 / 饮食禁忌 / 饮食偏好
- 写入出行历史：旅行记录 + 住宿偏好
- 打印 format_memory_for_prompt 的最终结果
"""
import sys
import asyncio
# 设置 WindowsSelectorEventLoopPolicy
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from app.core.store import get_user_memory_service


async def run_demo():
    service = await get_user_memory_service()

    user_id = "449bfbbe-bdcb-473d-b7a9-67120f783df0"

    print("\n==============================")
    print("✅ Step A: 保存用户画像（profile）")
    print("==============================")

    await service.update_travel_style(user_id, ["culture", "food"])
    await service.update_dietary_restrictions(user_id, ["seafood-allergy"])
    await service.update_food_preferences(user_id, ["spicy", "local-cuisine"])

    profile = await service.get_user_profile(user_id)
    print("当前画像：", profile.model_dump())

    print("\n==============================")
    print("✅ Step B: 保存出行历史（history）")
    print("==============================")

    await service.add_completed_trip(
        user_id=user_id,
        destination="西安",
        start_date="2025-08-01",
        end_date="2025-08-05",
        visited_attractions=["兵马俑", "华清宫", "大雁塔", "西安城墙"]
    )

    await service.update_accommodation_preference(
        user_id=user_id,
        preferred_types=["star_hotel", "hostel"],
        avg_budget=350.0
    )

    history = await service.get_travel_history(user_id)
    print("当前出行历史：", history.model_dump())

    print("\n==============================")
    print("✅ Step C: 打印注入提示词的长期记忆（format_memory_for_prompt）")
    print("==============================")

    memory_text = await service.format_memory_for_prompt(user_id)
    print(memory_text if memory_text else "(暂无长期记忆)")

    print("\n🎉 示例1完成：你已经验证了 Store 写入 + 读取 + 格式化注入文本全链路")


if __name__ == "__main__":
    asyncio.run(run_demo())