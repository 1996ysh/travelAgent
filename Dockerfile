# TravelAgent — FastAPI + LangGraph
# Python 版本与 pyproject.toml / .python-version 保持一致
FROM python:3.14-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

# 构建依赖 + curl（健康检查）
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# 先装依赖，利用 Docker 层缓存
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# 再拷贝业务代码与 RAG 语料
COPY app ./app
COPY data ./data
COPY scripts ./scripts

# 运行时目录（日志 / 向量库可挂卷）
RUN mkdir -p /app/logs /app/data/vectorestore /app/app/logs

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/ || exit 1

# 生产环境关闭 reload；MCP stdio 子进程需要 PATH 中有 python
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
