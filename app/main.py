"""
FastAPI 应用入口
集成 Checkpointer 和 Store 的生命周期管理
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.core.Checkpointer import checkpointer_lifespan, get_checkpointer
from app.utils.logger import app_logger
from app.core.store import store_lifespan


@asynccontextmanager
async def lifespan(app:FastAPI):
    """应用生命周期管理"""

    app_logger.info("启动应用....")
    #初始化checkpointer
    async with checkpointer_lifespan():
    # async with :等一个异步操作完成 + 离开时自动清理，本质上就是自动管理资源
        app_logger.info('checkpointer已就绪')
        #初始化 store
        async with store_lifespan():
            # 应用运行期间
            yield

    app_logger.info("关闭应用...")

## 创建fastapi应用
app = FastAPI(
    title = 'langraph旅行规划系统',
    description = '企业级多agent旅行规划服务',
    version = '1.0.0',
    lifespan = lifespan
)
# CORS 配置（允许前端跨域）：CORS (跨源资源共享) 是浏览器的安全机制。
# CORS 配置（允许前端跨域）：CORS (跨源资源共享) 是浏览器的安全机制。
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应指定具体域名
    #意味着任何网站都可以调你的 API。
    #上线前必须改成 ["https://your-frontend-domain.com"]，否则会有严重的安全风险 。
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """健康检查"""
    return {
        "status": "healthy",
        "service": "LangGraph Travel Planner",
        "version": "1.0.0"
    }


@app.get("/api/health")
async def health_check():
    """详细健康检查"""

    from app.core.store import get_store

    try:
        # 检查 Checkpointer
        checkpointer = await get_checkpointer()

        # 检查 Store
        store = await get_store()

        return {
            "status": "healthy",
            "components": {
                "checkpointer": "ready",
                "store": "ready",
                "llm": "configured",
                'isOK':"is that OK"
            }
        }
    except Exception as e:
        app_logger.error(f"健康检查失败: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.debug
    )
