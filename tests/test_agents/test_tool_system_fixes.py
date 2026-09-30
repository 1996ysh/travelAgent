"""
工具系统完善项单测：
1. city_adcode 解析
2. 天气格式化 / weather_agent_node（mock API）
3. synthesizer 章节合并
4. 行程 / 预算纯函数
5. state_back 回退工具不重复
"""
import json
from unittest.mock import AsyncMock, patch

import pytest

from app.agents.routers.destination_router import (
    _format_weather_forecast,
    synthesizer_node,
    weather_agent_node,
)
from app.tools.planning_helpers import (
    build_itinerary,
    estimate_budget,
    format_budget_summary,
)
from app.tools.state_back import ALL_ROLLBACK_TOOLS
from app.utils.city_adcode import resolve_city_adcode


# ---------- city_adcode ----------

class TestCityAdcode:
    def test_exact_match(self):
        assert resolve_city_adcode("西安") == "610100"
        assert resolve_city_adcode("北京") == "110000"

    def test_with_suffix(self):
        assert resolve_city_adcode("西安市") == "610100"
        assert resolve_city_adcode("成都市") == "510100"

    def test_substring(self):
        assert resolve_city_adcode("我想去西安旅游") == "610100"

    def test_unknown(self):
        assert resolve_city_adcode("火星市") is None
        assert resolve_city_adcode("") is None
        assert resolve_city_adcode("  ") is None


# ---------- weather format ----------

class TestWeatherFormat:
    def test_format_success(self):
        raw = json.dumps({
            "city": "西安",
            "province": "陕西",
            "reporttime": "2026-09-26 11:00:00",
            "casts": [
                {
                    "date": "2026-09-26",
                    "week": "5",
                    "dayweather": "晴",
                    "nightweather": "多云",
                    "daytemp": "28",
                    "nighttemp": "16",
                    "daywind": "东北",
                    "daypower": "≤3",
                }
            ],
        }, ensure_ascii=False)
        text = _format_weather_forecast("西安", raw)
        assert "西安" in text
        assert "晴" in text
        assert "28°C" in text
        assert "高德天气预报" in text

    def test_format_error(self):
        raw = json.dumps({"error": "未配置 AMAP_API_KEY"}, ensure_ascii=False)
        text = _format_weather_forecast("西安", raw)
        assert "查询失败" in text
        assert "AMAP_API_KEY" in text


@pytest.mark.asyncio
async def test_weather_agent_node_with_mock_api():
    mock_payload = json.dumps({
        "city": "西安",
        "province": "陕西",
        "reporttime": "2026-09-26 11:00:00",
        "casts": [
            {
                "date": "2026-09-26",
                "week": "5",
                "dayweather": "晴",
                "nightweather": "晴",
                "daytemp": "27",
                "nighttemp": "15",
                "daywind": "北",
                "daypower": "≤3",
            }
        ],
    }, ensure_ascii=False)

    with patch(
        "app.agents.routers.destination_router.get_weather_forecast",
        new_callable=AsyncMock,
        return_value=mock_payload,
    ) as mocked:
        result = await weather_agent_node({
            "query": "西安天气",
            "destination": "西安",
        })
        mocked.assert_awaited_once_with("610100")

    assert len(result["agent_results"]) == 1
    assert result["agent_results"][0]["agent_name"] == "weather"
    assert "晴" in result["agent_results"][0]["result"]
    assert "Mock" not in result["agent_results"][0]["result"]
    assert "简化示例" not in result["agent_results"][0]["result"]


@pytest.mark.asyncio
async def test_weather_agent_unknown_city():
    result = await weather_agent_node({
        "query": "天气",
        "destination": "不存在的城市XYZ",
    })
    assert "无法解析" in result["agent_results"][0]["result"]


@pytest.mark.asyncio
async def test_synthesizer_order():
    report = await synthesizer_node({
        "original_query": "推荐西安",
        "destination": "西安",
        "classifications": [],
        "agent_results": [
            {"agent_name": "weather", "result": "## 天气\n晴"},
            {"agent_name": "explore", "result": "## 攻略\n兵马俑"},
        ],
        "final_report": "",
    })
    text = report["final_report"]
    assert "目的地综合报告" in text
    # explore 章节应出现在 weather 之前
    assert text.index("景点与攻略") < text.index("天气实况与预报")
    assert "兵马俑" in text
    assert "晴" in text


# ---------- itinerary / budget ----------

def _sample_state(**overrides):
    state = {
        "user_requirement": {
            "departure_city": "武汉",
            "destination": "西安",
            "departure_date": "2026-10-01",
            "travel_days": 3,
            "adult_count": 2,
            "children_count": 1,
            "budget_min": 3000,
            "budget_max": 6000,
            "budget_level": "comfort",
            "travel_styles": ["culture", "food"],
            "special_needs": None,
        },
        "selected_destination": "西安",
        "selected_transport": "train",
        "selected_accommodation_types": ["economy_hotel"],
        "selected_food_types": ["specialty", "local"],
    }
    state.update(overrides)
    return state


class TestItinerary:
    def test_heuristic_length_and_content(self):
        itinerary, source = build_itinerary(_sample_state())
        assert source == "heuristic"
        assert len(itinerary) == 3
        assert itinerary[0]["day_number"] == 1
        assert "西安" in itinerary[0]["activities"][0]
        # 不应再出现占位文案
        joined = json.dumps(itinerary, ensure_ascii=False)
        assert "活动1" not in joined
        assert "酒店名称" not in joined

    def test_llm_days_normalized(self):
        days = [
            {
                "day_number": 1,
                "morning": "抵达钟楼",
                "afternoon": "回民街",
                "meals": ["飞机餐", "羊肉泡馍"],
                "accommodation": "钟楼酒店",
            },
            {
                "activities": ["兵马俑", "华清宫"],
                "meals": ["酒店早餐", "景区午餐", "城墙夜景餐"],
            },
        ]
        itinerary, source = build_itinerary(_sample_state(), days=days)
        assert source == "mixed"  # 第 3 天缺活动会补全
        assert itinerary[0]["activities"][0].startswith("上午")
        assert itinerary[0]["accommodation"] == "钟楼酒店"
        assert len(itinerary[1]["activities"]) == 2
        assert len(itinerary) == 3
        assert itinerary[2]["activities"]  # 启发式补全


class TestBudget:
    def test_estimate_scales_with_level(self):
        comfort = estimate_budget(_sample_state(user_requirement={
            **_sample_state()["user_requirement"],
            "budget_level": "comfort",
        }))[0]
        luxury_state = _sample_state()
        luxury_state["user_requirement"] = {
            **luxury_state["user_requirement"],
            "budget_level": "luxury",
        }
        luxury = estimate_budget(luxury_state)[0]
        assert luxury["total"] > comfort["total"]

    def test_override_transport(self):
        budget, _ = estimate_budget(_sample_state(), transport=999.0)
        assert budget["transport"] == 999.0

    def test_over_budget_note(self):
        # 把预算上限压得很低，触发超支提示
        state = _sample_state()
        state["user_requirement"] = {
            **state["user_requirement"],
            "budget_min": 100,
            "budget_max": 200,
            "budget_level": "luxury",
        }
        budget, analysis = estimate_budget(state)
        text = format_budget_summary(budget, analysis)
        assert "超出预算" in text
        assert budget["total"] > 0

    def test_flight_more_expensive_than_train(self):
        train = estimate_budget(_sample_state(selected_transport="train"))[0]
        flight = estimate_budget(_sample_state(selected_transport="flight"))[0]
        assert flight["transport"] > train["transport"]


# ---------- rollback tools uniqueness ----------

class TestRollbackTools:
    def test_no_duplicate_tool_names(self):
        names = [t.name for t in ALL_ROLLBACK_TOOLS]
        assert len(names) == len(set(names)), f"重复工具: {names}"
        assert "go_back_to_transport" in names
        assert names.count("go_back_to_transport") == 1
