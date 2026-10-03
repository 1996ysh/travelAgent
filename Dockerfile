# TravelAgent — FastAPI + LangGraph（国内构建友好）
FROM python:3.14-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/ \
    UV_HTTP_TIMEOUT=300 \
    PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/ \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PATH="/app/.venv/bin:$PATH"

# Debian apt 换阿里云源（bookworm 使用 debian.sources）
RUN set -eux; \
    if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
      sed -i 's|deb.debian.org|mirrors.aliyun.com|g; s|security.debian.org|mirrors.aliyun.com|g' \
        /etc/apt/sources.list.d/debian.sources; \
    fi; \
    if [ -f /etc/apt/sources.list ]; then \
      sed -i 's|deb.debian.org|mirrors.aliyun.com|g; s|security.debian.org|mirrors.aliyun.com|g' \
        /etc/apt/sources.list; \
    fi; \
    apt-get update && apt-get install -y --no-install-recommends \
      build-essential \
      curl \
      libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# bootstrap uv：与 ECS 上常用阿里云 PyPI 一致；失败再 fallback（避免 from versions: none）
RUN pip install --no-cache-dir "uv>=0.6.0" \
      --index-url https://mirrors.aliyun.com/pypi/simple/ \
      --trusted-host mirrors.aliyun.com \
    || pip install --no-cache-dir "uv>=0.6.0" \
      --index-url https://pypi.tuna.tsinghua.edu.cn/simple \
    || pip install --no-cache-dir "uv>=0.6.0" \
      --index-url https://pypi.org/simple \
      --trusted-host pypi.org

WORKDIR /app

# 先装依赖，利用 Docker 层缓存
COPY pyproject.toml uv.lock ./
# uv.lock 里每个 wheel 的 URL 写死了清华源；--index-url 不会改写这些地址。
# 清华对 uv 的下载经常返回 403，这里改成阿里云（路径比清华多一层 /pypi）。
RUN sed -i \
      -e 's|https://pypi.tuna.tsinghua.edu.cn/packages/|https://mirrors.aliyun.com/pypi/packages/|g' \
      -e 's|https://pypi.tuna.tsinghua.edu.cn/simple|https://mirrors.aliyun.com/pypi/simple|g' \
      uv.lock pyproject.toml \
    && uv sync --frozen --no-dev --index-url https://mirrors.aliyun.com/pypi/simple/

# 再拷贝业务代码与 RAG 语料
COPY app ./app
COPY data ./data
COPY scripts ./scripts

RUN mkdir -p /app/logs /app/data/vectorestore /app/app/logs

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/ || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
