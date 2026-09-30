"""
行程生成与预算估算的纯函数逻辑

供 state_transition 工具调用，也便于单测（不依赖 LangGraph runtime）。
"""
from __future__ import annotations

from typing import Any, Optional

# ---------- 风格 / 类型标签 ----------

STYLE_ACTIVITY_POOL: dict[str, list[str]] = {
    "relaxation": [
        "慢节奏街区漫步与咖啡馆休憩",
        "公园/湖畔休闲，预留午休时间",
        "温泉或轻松夜景（低强度）",
    ],
    "culture": [
        "核心博物馆/历史街区深度游览",
        "古迹或非遗体验（注意预约）",
        "城市文化漫步与本地书店/展馆",
    ],
    "adventure": [
        "轻户外徒步或观景点（按体力分级）",
        "骑行/登山等户外体验（备好装备）",
        "自然景区半日活动 + 休整",
    ],
    "food": [
        "代表性早餐/早市扫街",
        "特色餐厅或本地必吃打卡",
        "夜市/小吃街自由探索",
    ],
}

DEFAULT_ACTIVITIES = [
    "抵达后入住并熟悉周边",
    "核心景点半日游",
    "自由活动与补给采购",
]

FOOD_MEAL_LABELS: dict[str, list[str]] = {
    "specialty": ["特色餐厅早餐", "名店午餐", "特色晚餐"],
    "chain": ["连锁简餐早餐", "商场午餐", "连锁晚餐"],
    "local": ["本地早点", "小吃街午餐", "夜市晚餐"],
}

ACCOMMODATION_LABELS: dict[str, str] = {
    "star_hotel": "星级酒店",
    "economy_hotel": "经济酒店",
    "hostel": "特色民宿",
    "youth_hostel": "青年旅社",
}

TRANSPORT_LABELS: dict[str, str] = {
    "flight": "航班",
    "train": "高铁",
    "driving": "自驾",
}

# 人均单程交通基准（元）
TRANSPORT_BASE: dict[str, float] = {
    "flight": 800,
    "train": 350,
    "driving": 200,  # 油费过路费均摊粗估
}

# 每晚人均住宿基准
ACCOMMODATION_BASE: dict[str, float] = {
    "star_hotel": 450,
    "economy_hotel": 220,
    "hostel": 280,
    "youth_hostel": 120,
}

# 每日人均餐饮基准
FOOD_BASE: dict[str, float] = {
    "specialty": 220,
    "chain": 100,
    "local": 140,
}

# 预算等级整体系数
BUDGET_LEVEL_MULTIPLIER: dict[str, float] = {
    "economy": 0.75,
    "comfort": 1.0,
    "luxury": 1.6,
}

# 每日人均门票 / 杂费基准
ATTRACTIONS_PER_DAY = 120.0
MISC_PER_DAY = 60.0


def _normalize_day_entry(raw: Any, day_number: int, default_accommodation: str) -> dict:
    """把 LLM 传入的一天行程规范成 ItineraryDay 结构。"""
    if not isinstance(raw, dict):
        raw = {}

    activities = raw.get("activities") or []
    if isinstance(activities, str):
        activities = [activities]
    activities = [str(a).strip() for a in activities if str(a).strip()]

    # 兼容 morning/afternoon/evening 字段
    for part in ("morning", "afternoon", "evening", "theme"):
        val = raw.get(part)
        if val and str(val).strip():
            label = {"morning": "上午", "afternoon": "下午", "evening": "晚上", "theme": "主题"}.get(
                part, part
            )
            activities.append(f"{label}：{str(val).strip()}")

    meals = raw.get("meals") or []
    if isinstance(meals, str):
        meals = [meals]
    meals = [str(m).strip() for m in meals if str(m).strip()]

    accommodation = raw.get("accommodation") or default_accommodation

    day_num = raw.get("day_number", day_number)
    try:
        day_num = int(day_num)
    except (TypeError, ValueError):
        day_num = day_number

    return {
        "day_number": day_num,
        "activities": activities,
        "meals": meals,
        "accommodation": str(accommodation),
    }


def _heuristic_day(
    day_number: int,
    travel_days: int,
    destination: str,
    styles: list[str],
    food_types: list[str],
    accommodation_label: str,
) -> dict:
    """按风格/餐饮偏好生成单日启发式行程。"""
    styles = styles or ["culture"]
    food_types = food_types or ["local"]

    # 按风格轮转活动池
    activities: list[str] = []
    if day_number == 1:
        activities.append(f"抵达 {destination}，入住并熟悉周边")
    if day_number == travel_days and travel_days > 1:
        activities.append("返程前轻松安排，预留赶路缓冲时间")

    pool: list[str] = []
    for style in styles:
        pool.extend(STYLE_ACTIVITY_POOL.get(style, []))
    if not pool:
        pool = list(DEFAULT_ACTIVITIES)

    # 每天取 2 个不重复活动
    idx = (day_number - 1) * 2
    for offset in range(2):
        activities.append(pool[(idx + offset) % len(pool)])

    # 餐饮
    primary_food = food_types[0]
    meals = list(FOOD_MEAL_LABELS.get(primary_food, ["早餐", "午餐", "晚餐"]))
    if "food" in styles and day_number > 1:
        meals = [f"{destination}特色·{m}" for m in meals]

    return {
        "day_number": day_number,
        "activities": activities,
        "meals": meals,
        "accommodation": accommodation_label if day_number < travel_days else f"{accommodation_label}（退房）",
    }


def build_itinerary(
    state: dict,
    days: Optional[list[dict]] = None,
) -> tuple[list[dict], str]:
    """
    构建行程列表。

    Args:
        state: TravelState 字典
        days: LLM 传入的结构化每日安排（可选）

    Returns:
        (itinerary, source_note)  source_note 说明来源：llm / heuristic / mixed
    """
    requirement = state["user_requirement"]
    travel_days = int(requirement["travel_days"])
    destination = state.get("selected_destination") or requirement.get("destination") or "目的地"
    styles = list(requirement.get("travel_styles") or [])
    food_types = list(state.get("selected_food_types") or [])
    acc_types = list(state.get("selected_accommodation_types") or [])
    acc_label = ACCOMMODATION_LABELS.get(acc_types[0], "酒店") if acc_types else "酒店"

    if days:
        itinerary = [
            _normalize_day_entry(days[i] if i < len(days) else {}, i + 1, acc_label)
            for i in range(travel_days)
        ]
        # 补全空活动：用启发式填充
        filled_from_heuristic = 0
        for i, day in enumerate(itinerary):
            if not day["activities"]:
                heuristic = _heuristic_day(
                    i + 1, travel_days, destination, styles, food_types, acc_label
                )
                day["activities"] = heuristic["activities"]
                filled_from_heuristic += 1
            if not day["meals"]:
                heuristic = _heuristic_day(
                    i + 1, travel_days, destination, styles, food_types, acc_label
                )
                day["meals"] = heuristic["meals"]
        source = "mixed" if filled_from_heuristic else "llm"
        return itinerary, source

    itinerary = [
        _heuristic_day(i, travel_days, destination, styles, food_types, acc_label)
        for i in range(1, travel_days + 1)
    ]
    return itinerary, "heuristic"


def format_itinerary_summary(itinerary: list[dict], destination: str, source: str) -> str:
    """生成给人看的行程摘要文本。"""
    source_label = {
        "llm": "基于你确认的行程安排",
        "heuristic": "基于偏好自动生成（可回退调整）",
        "mixed": "部分来自你的确认、部分自动补全",
    }.get(source, source)

    lines = [
        f"已生成 {destination} {len(itinerary)} 天行程（{source_label}）",
        "",
    ]
    for day in itinerary:
        lines.append(f"【Day {day['day_number']}】住宿：{day.get('accommodation', '-')}")
        for act in day.get("activities") or []:
            lines.append(f"  · {act}")
        meals = day.get("meals") or []
        if meals:
            lines.append(f"  餐饮：{' / '.join(meals)}")
        lines.append("")
    return "\n".join(lines).rstrip()


def estimate_budget(
    state: dict,
    transport: Optional[float] = None,
    accommodation: Optional[float] = None,
    food: Optional[float] = None,
    attractions: Optional[float] = None,
    misc: Optional[float] = None,
) -> tuple[dict[str, float], str]:
    """
    估算预算明细。

    未传入的分项按状态中的交通/住宿/餐饮类型与预算等级自动估算。
    儿童按成人费用的 0.6 计。

    Returns:
        (budget_breakdown, analysis_note)
    """
    requirement = state["user_requirement"]
    adult_count = int(requirement.get("adult_count") or 1)
    children_count = int(requirement.get("children_count") or 0)
    # 加权人数：儿童 0.6
    people_weight = adult_count + children_count * 0.6
    travel_days = int(requirement["travel_days"])
    # 住宿晚数：出发当天入住，最后一天退房 → max(days-1, 1) 对短途单日也至少算 1 晚体验
    nights = max(travel_days - 1, 1) if travel_days > 1 else 1

    budget_level = requirement.get("budget_level") or "comfort"
    level_mult = BUDGET_LEVEL_MULTIPLIER.get(budget_level, 1.0)

    transport_type = state.get("selected_transport") or "train"
    acc_types = list(state.get("selected_accommodation_types") or ["economy_hotel"])
    food_types = list(state.get("selected_food_types") or ["local"])

    # 住宿取所选类型均价；餐饮取均价
    acc_base = sum(ACCOMMODATION_BASE.get(t, 220) for t in acc_types) / max(len(acc_types), 1)
    food_base = sum(FOOD_BASE.get(t, 140) for t in food_types) / max(len(food_types), 1)
    transport_base = TRANSPORT_BASE.get(transport_type, 350)

    # 往返交通
    est_transport = transport_base * 2 * people_weight * level_mult
    est_accommodation = acc_base * nights * people_weight * level_mult
    est_food = food_base * travel_days * people_weight * level_mult
    est_attractions = ATTRACTIONS_PER_DAY * travel_days * people_weight * level_mult
    est_misc = MISC_PER_DAY * travel_days * people_weight * level_mult

    transport_cost = float(transport) if transport is not None else est_transport
    accommodation_cost = float(accommodation) if accommodation is not None else est_accommodation
    food_cost = float(food) if food is not None else est_food
    attractions_cost = float(attractions) if attractions is not None else est_attractions
    misc_cost = float(misc) if misc is not None else est_misc

    total = transport_cost + accommodation_cost + food_cost + attractions_cost + misc_cost

    budget = {
        "transport": round(transport_cost, 2),
        "accommodation": round(accommodation_cost, 2),
        "food": round(food_cost, 2),
        "attractions": round(attractions_cost, 2),
        "misc": round(misc_cost, 2),
        "total": round(total, 2),
    }

    # 与用户预算对比（按人均）
    note_parts = [
        f"假设：交通={TRANSPORT_LABELS.get(transport_type, transport_type)}，"
        f"住宿={','.join(ACCOMMODATION_LABELS.get(t, t) for t in acc_types)}，"
        f"{nights} 晚，预算等级={budget_level}（系数 {level_mult}），"
        f"儿童按成人 60% 计。",
    ]

    budget_min = requirement.get("budget_min")
    budget_max = requirement.get("budget_max")
    per_person = total / max(adult_count + children_count, 1)

    if budget_min is not None and budget_max is not None:
        if per_person > float(budget_max):
            over = per_person - float(budget_max)
            note_parts.append(
                f"⚠️ 人均约 {per_person:.0f} 元，超出预算上限 {budget_max} 约 {over:.0f} 元。"
                f"建议回退调整住宿档次或缩短行程。"
            )
        elif per_person < float(budget_min):
            note_parts.append(
                f"✅ 人均约 {per_person:.0f} 元，低于预算下限 {budget_min}，"
                f"仍有余量可用于升级住宿或增加体验。"
            )
        else:
            note_parts.append(
                f"✅ 人均约 {per_person:.0f} 元，落在预算区间 "
                f"{budget_min}-{budget_max} 元/人内。"
            )
    else:
        note_parts.append(f"人均约 {per_person:.0f} 元（全员合计 {total:.0f} 元）。")

    return budget, " ".join(note_parts)


def format_budget_summary(budget: dict[str, float], analysis: str) -> str:
    """生成预算摘要文本。"""
    return (
        f"预算汇总完成！\n"
        f"总计：{budget['total']:.2f} 元\n"
        f"   - 交通：{budget['transport']:.2f}\n"
        f"   - 住宿：{budget['accommodation']:.2f}\n"
        f"   - 餐饮：{budget['food']:.2f}\n"
        f"   - 门票：{budget['attractions']:.2f}\n"
        f"   - 其他：{budget['misc']:.2f}\n\n"
        f"{analysis}"
    )
