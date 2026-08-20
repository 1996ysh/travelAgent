"""测试天气 MCP Server"""
import pytest
import asyncio
from app.mcp_core.servers.weather_server import get_weather_forecast

@pytest.mark.asyncio
async def test():
    print("=== 测试咸宁天气 (adcode:421202) ===")
    result = await get_weather_forecast("110000")
    print(result)

    print("\n=== 测试武汉天气 (adcode: 420100) ===")
    result = await get_weather_forecast("330100")
    print(result)


if __name__ == "__main__":
    asyncio.run(test())