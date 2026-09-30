"""
城市名 → 高德 adcode 映射

天气 API 只认 adcode，不支持中文城市名。
此模块供 Router 天气节点、以及需要城市编码的工具使用。
"""
from __future__ import annotations

from typing import Optional

# 常用旅游城市/直辖市/省会（市级 adcode）
CITY_ADCODE_MAP: dict[str, str] = {
    # 直辖市
    "北京": "110000",
    "上海": "310000",
    "天津": "120000",
    "重庆": "500000",
    # 热门目的地
    "西安": "610100",
    "成都": "510100",
    "杭州": "330100",
    "南京": "320100",
    "武汉": "420100",
    "广州": "440100",
    "深圳": "440300",
    "厦门": "350200",
    "青岛": "370200",
    "大连": "210200",
    "苏州": "320500",
    "桂林": "450300",
    "丽江": "530700",
    "昆明": "530100",
    "长沙": "430100",
    "郑州": "410100",
    "合肥": "340100",
    "福州": "350100",
    "南昌": "360100",
    "济南": "370100",
    "沈阳": "210100",
    "哈尔滨": "230100",
    "长春": "220100",
    "太原": "140100",
    "石家庄": "130100",
    "呼和浩特": "150100",
    "南宁": "450100",
    "海口": "460100",
    "三亚": "460200",
    "贵阳": "520100",
    "拉萨": "540100",
    "银川": "640100",
    "西宁": "630100",
    "乌鲁木齐": "650100",
    "兰州": "620100",
    "宁波": "330200",
    "温州": "330300",
    "无锡": "320200",
    "常州": "320400",
    "扬州": "321000",
    "珠海": "440400",
    "佛山": "440600",
    "东莞": "441900",
    "中山": "442000",
    "惠州": "441300",
    "咸宁": "421200",
    "黄山": "341000",
    "敦煌": "620982",
    "张家界": "430800",
    "凤凰": "433123",
    "大理": "532901",
}


def resolve_city_adcode(city_name: str) -> Optional[str]:
    """
    将中文城市名解析为高德 adcode。

    匹配策略（按优先级）：
    1. 精确匹配（去空白）
    2. 去掉常见后缀后再精确匹配（市/地区/自治州等）
    3. 子串包含匹配（取最长命中，避免「西安」误匹配「安」类短 key）

    Returns:
        adcode 字符串；无法解析时返回 None
    """
    if not city_name:
        return None

    name = city_name.strip()
    if not name:
        return None

    # 1. 精确匹配
    if name in CITY_ADCODE_MAP:
        return CITY_ADCODE_MAP[name]

    # 2. 去掉行政后缀
    for suffix in ("市", "地区", "自治州", "特别行政区", "盟", "县", "区"):
        if name.endswith(suffix) and len(name) > len(suffix):
            bare = name[: -len(suffix)]
            if bare in CITY_ADCODE_MAP:
                return CITY_ADCODE_MAP[bare]

    # 3. 子串包含：优先最长 key（避免短 key 误伤）
    candidates = [
        (key, code)
        for key, code in CITY_ADCODE_MAP.items()
        if key in name or name in key
    ]
    if candidates:
        candidates.sort(key=lambda x: len(x[0]), reverse=True)
        return candidates[0][1]

    return None
