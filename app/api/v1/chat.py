"""
流式对话 API（SSE）
"""
import json
import asyncio
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse #流式返回
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from langchain_core.messages import HumanMessage, AIMessage, AIMessageChunk
from app.models.base import get_db
from app.models.user import User
from app.models.conversation import Conversation
from app.models.messages import Message
from app.schemas.message import MessageCreate
from app.api.dependencies import get_current_user
from app.agents.handoffs.travel_agent import create_travel_agent
from app.utils.logger import app_logger

router = APIRouter(prefix="/chat", tags=["对话"])

# 工具名 → 前端可展示的状态文案
TOOL_STATUS_MESSAGES: dict[str, str] = {
    "search_destination_guide": "正在检索目的地攻略…",
    "search_food_recommendations": "正在检索美食推荐…",
    "search_accommodation_info": "正在检索住宿信息…",
    "search_travel_tips": "正在检索出行贴士…",
    "query_destination_info": "正在查询目的地综合信息…",
    "query_transport_options": "正在查询交通方案…",
}


def _tool_status(tool_name: str) -> str:
    if tool_name in TOOL_STATUS_MESSAGES:
        return TOOL_STATUS_MESSAGES[tool_name]
    if tool_name.startswith("search_") or "rag" in tool_name.lower():
        return "正在检索知识库…"
    if tool_name:
        return f"正在调用工具：{tool_name}…"
    return "正在处理…"


# 只允许主 Travel Agent 的模型节点把 token 推给前端
_MAIN_AGENT_NODES = frozenset({"model", "agent", "model_request"})
# 目的地 Router / 子 Agent 等内部节点，绝不能泄漏到 SSE
_NESTED_BLOCK_NODES = frozenset({
    "tools", "tool",
    "classifier", "explore", "weather", "synthesizer",
})


def _should_stream_model_token(event: dict) -> bool:
    """
    只转发主 Travel Agent 的 token。

    嵌套场景（必须拦截）：
    - RAG Multi-Query / HyDE
    - 目的地 Router 的 classifier（否则会把 classifications JSON 推到前端）
    - explore / weather / 交通子 Agent 内部 LLM
    """
    tags = set(event.get("tags") or [])
    if tags & {"nostream", "rag_internal", "router_internal", "subagent_internal"}:
        return False

    metadata = event.get("metadata") or {}
    node = metadata.get("langgraph_node") or ""

    if node in _NESTED_BLOCK_NODES:
        return False

    # 工具内嵌套图：checkpoint_ns 形如 tools:xxx 或 ...|tools:xxx|...
    ns = str(metadata.get("langgraph_checkpoint_ns") or "")
    if "tools:" in ns or ns.startswith("tools") or "|tools" in ns:
        return False

    # 没有主节点标记时，默认不推（避免 structured_output 等裸 invoke 泄漏）
    if not node:
        return False

    return node in _MAIN_AGENT_NODES


async def save_message(
        db: AsyncSession,
        conversation_id: str,
        role: str,
        content: str,
        metadata: dict = None
) -> Message:
    """保存消息到数据库"""

    message = Message(
        conversation_id=conversation_id,
        role=role,
        content=content,
        metadata=metadata or {}
    )

    db.add(message)
    await db.commit()
    await db.refresh(message)

    return message


def sse(data: dict) -> str:
    """
    SSE 标准 data 帧
    """
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


async def generate_sse_stream(
        conversation_id: str,
        user_message: str,
        db: AsyncSession,
        user: User
):
    assistant_message = ""

    try:
        # 1. 保存用户消息
        await save_message(db, conversation_id, "user", user_message)

        # 2. 创建 agent  整个ai对话的入口
        agent = await create_travel_agent()

        # 3. 关键修复：输入必须是字典格式！
        # LangGraph StateGraph 期望输入是 state 的部分更新
        input_data = {
            "messages": [HumanMessage(content=user_message)],
            "user_id": str(user.id),
        }

        # 4. 使用 astream_events 获取更细粒度的流式输出
        async for event in agent.astream_events(
                input_data,
                config={
                    "configurable": {
                        "thread_id": conversation_id
                    }
                },
                version="v2"
        ):
            kind = event.get("event")

            # 捕获 LLM 流式输出（排除 RAG 内部查询优化等嵌套 LLM）
            if kind == "on_chat_model_stream":
                if not _should_stream_model_token(event):
                    continue
                chunk = event.get("data", {}).get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    token = chunk.content
                    # content 有时是 list（多模态块），只拼字符串
                    if not isinstance(token, str):
                        continue
                    assistant_message += token
                    yield sse({
                        "type": "token",
                        "content": token,
                    })

            # 工具开始：推送可读状态，便于前端展示「正在检索…」
            elif kind == "on_tool_start":
                tool_name = event.get("name", "")
                yield sse({
                    "type": "tool_call",
                    "tool": tool_name,
                    "status": _tool_status(tool_name),
                    "message": _tool_status(tool_name),
                })

            elif kind == "on_tool_end":
                tool_name = event.get("name", "")
                yield sse({
                    "type": "tool_end",
                    "tool": tool_name,
                })

            await asyncio.sleep(0)

        # 5. 保存 AI 回复
        if assistant_message.strip():
            await save_message(
                db,
                conversation_id,
                "assistant",
                assistant_message,
            )

        yield sse({"type": "done"})

    except Exception as e:
        app_logger.exception("❌ SSE 流式对话错误")
        yield sse({
            "type": "error",
            "message": str(e),
        })



@router.post("/stream/{conversation_id}")
async def stream_chat(
        conversation_id: str,
        data: MessageCreate,
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    """
    流式对话（SSE）

    Returns:
        StreamingResponse: SSE 流式响应
    """

    # 验证会话归属
    result = await db.execute(
        select(Conversation)
        .where(Conversation.id == conversation_id)
        .where(Conversation.user_id == user.id)
    )

    conversation = result.scalar_one_or_none()

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="会话不存在"
        )

    # 返回 SSE 流
    return StreamingResponse(
        generate_sse_stream(conversation_id, data.content, db, user),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # 禁用 Nginx 缓冲
        }
    )


@router.get("/history/{conversation_id}")
async def get_chat_history(
        conversation_id: str,
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    """获取会话历史消息"""

    # 验证会话归属
    result = await db.execute(
        select(Conversation)
        .where(Conversation.id == conversation_id)
        .where(Conversation.user_id == user.id)
    )

    conversation = result.scalar_one_or_none()

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="会话不存在"
        )

    # 查询消息
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )

    messages = result.scalars().all()

    return {
        "conversation": conversation.to_dict(),
        "messages": [m.to_dict() for m in messages]
    }
