"""
全局中间件
动态配置agent行为
"""
from typing import Callable

from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse
from app.core.state import TravelState
from app.utils.logger import app_logger


class StepConfigMiddleware(AgentMiddleware):
    """
    步骤配置中间件 - 根据current_step动态配置Agent
    """
    def __init__(self,step_config:dict):
        """
        初始化中间件
        :param step_config:预加载的步骤配置字典
        """
        self._step_config = step_config
    async def awrap_model_call(
            self,
            request:ModelRequest,
            handler:Callable[[ModelRequest],ModelResponse]
    )->ModelResponse:
        """
        根据current_step 动态配置agent
        :param request:
        :param handler:
        :return:
        """
        # 获取当前步骤
        state:TravelState = request.state
        current_step = state.get('current_step','requirement_collection')
        app_logger.info(f'当前步骤:{current_step}')
        if current_step not in self._step_config:
            app_logger.error(f"❌ 未知步骤: {current_step}")
            raise ValueError(f"未知步骤: {current_step}")
        step_config = self._step_config[current_step]
        # ========== 验证前置依赖 ==========
        for required_field in step_config["requires"]:
            #requires里面存的代表需要的一些参数，在TravelState里面
            if required_field not in state or state[required_field] is None:
                error_msg = f"步骤 {current_step} 需要完整状态: {required_field} 未设置"
                app_logger.error(f"❌ {error_msg}")
                app_logger.error(f"当前状态: {list(state.keys())}")
                raise ValueError(error_msg)
            # ========== 动态填充提示词变量 ==========
            # 使用 state 字段替换提示词中的占位符
        try:
            system_prompt = step_config["prompt"].format(**state)
        except KeyError as e:
            app_logger.warning(f"⚠️ 提示词变量缺失: {e}，使用原始模板")
            system_prompt = step_config["prompt"]

            # ========== 注入配置 ==========
        modified_request = request.override(
            system_prompt=system_prompt,
            tools=step_config["tools"]
        )

        app_logger.info(f"✅ 已注入步骤配置: {len(step_config['tools'])} 个工具")

        # 传递给 LLM
        return await handler(modified_request)


async def create_step_config_middleware() -> StepConfigMiddleware:
    """
    工厂函数：创建步骤配置中间件

    Returns:
        预加载配置的 StepConfigMiddleware 实例
    """
    from app.agents.handoffs.step_config import get_step_config

    step_config = await get_step_config()

    app_logger.info("✅ StepConfigMiddleware 创建完成")

    return StepConfigMiddleware(step_config)