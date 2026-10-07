# TravelAgent Docker 部署指南

本文说明如何用 Docker 一键部署本项目（FastAPI 应用 + PostgreSQL + Redis）。

## 架构一览

| 服务 | 镜像 / 构建 | 端口 | 作用 |
|------|-------------|------|------|
| `app` | 本仓库 `Dockerfile` | 8000 | 旅行规划 API |
| `postgres` | `postgres:16-alpine` | 5432 | 业务库 + LangGraph Checkpointer / Store |
| `redis` | `redis:7-alpine` | 6379 | RAG 查询缓存 |

---

## 前置条件

1. 安装 [Docker Desktop](https://www.docker.com/products/docker-desktop/)（Windows / macOS）或 Docker Engine + Compose Plugin（Linux）。
2. 确认 Docker 可用：

```bash
docker version
docker compose version
```

3. 准备好 API Key（至少 `DASHSCOPE_API_KEY`；MCP / LangSmith 按需填写）。

---

## 步骤 1：准备环境变量

在项目根目录：

```bash
# Windows PowerShell
Copy-Item .env.example .env

# macOS / Linux
cp .env.example .env
```

用编辑器打开 `.env`，至少填好：

```env
DASHSCOPE_API_KEY=你的通义 Key
LANGSMITH_API_KEY=你的 LangSmith Key   # 可暂时随便填非空字符串，若关闭 tracing 见下
LANGSMITH_TRACING=false                # 没有 LangSmith 时建议关掉
POSTGRES_PASSWORD=换成强密码
```

可选 MCP Key（缺了对应外部工具会失败，自建 weather/search 仍可用）：

- `AMAP_API_KEY`
- `TAVILY_API_KEY`
- `VARIFLIGHT_API_KEY`
- `AIGOHOTEL_MCP_API`

> 注意：`docker-compose.yml` 会把容器内的 `POSTGRES_HOST` / `REDIS_HOST` 覆盖为服务名 `postgres` / `redis`，不必改成 localhost。

---

## 步骤 2：构建并启动

在项目根目录执行：

```bash
docker compose up -d --build
```

含义：

- `--build`：按 `Dockerfile` 构建应用镜像（首次较慢，会装 Python 依赖）
- `-d`：后台运行

查看状态：

```bash
docker compose ps
docker compose logs -f app
```

看到类似「业务数据库表已就绪」「checkpointer已就绪」「mcp 服务初始化成功」即表示启动成功。

---

## 步骤 3：验证服务

1. 健康检查：

```bash
curl http://localhost:8000/
```

期望返回含 `"status": "healthy"` 的 JSON。

2. 打开交互文档：浏览器访问 [http://localhost:8000/docs](http://localhost:8000/docs)

3. 注册用户（示例）：

```bash
curl -X POST http://localhost:8000/api/v1/users/register \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"demo\",\"password\":\"demo123456\",\"email\":\"demo@example.com\"}"
```

具体字段以 `/docs` 里的 schema 为准。

---

## 步骤 4：日常运维命令

```bash
# 查看日志
docker compose logs -f app
docker compose logs -f postgres

# 停止（保留数据卷）
docker compose stop

# 再次启动
docker compose start

# 重建应用（改代码后）
docker compose up -d --build app

# 进入应用容器排查
docker compose exec app bash

# 完全拆除（会删容器，默认不删 named volume）
docker compose down

# 连数据一起删（危险：清空数据库）
docker compose down -v
```

数据持久化在 Docker named volumes：`postgres_data`、`redis_data`、`chroma_data`，以及宿主机目录 `./logs`。

---

## 仅构建镜像（不启动依赖）

```bash
docker build -t travelagent:latest .
```

单独跑应用（需本机或其它容器已有 Postgres，并正确设置环境变量）：

```bash
docker run --rm -p 8000:8000 --env-file .env \
  -e POSTGRES_HOST=host.docker.internal \
  travelagent:latest
```

Windows / macOS 上 `host.docker.internal` 可访问宿主机上的数据库。

---

## 端口冲突怎么办

若本机 8000 / 5432 / 6379 已被占用，在 `.env` 里改映射端口即可：

```env
APP_HOST_PORT=18000
POSTGRES_HOST_PORT=15432
REDIS_HOST_PORT=16379
```

然后：

```bash
docker compose up -d
```

访问地址变为 `http://localhost:18000`。

---

## 常见问题

### 1. 构建很慢 / 依赖安装失败

国内请先配置 Docker 镜像加速，并使用仓库内已优化的 Dockerfile。详见 [DOCKER_MIRROR_CN.md](./DOCKER_MIRROR_CN.md)。  
PyPI 使用清华源（`pyproject.toml` / `UV_INDEX_URL`）。网络仍不通时可换代理，或在宿主机先 `uv sync` 确认依赖可装。

### 2. `app` 一直重启，日志报数据库连不上

- 等 `postgres` 健康检查通过：`docker compose ps`
- 确认 `.env` 里 `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` 与 compose 一致
- 不要在容器里仍写 `POSTGRES_HOST=localhost`（compose 已覆盖；若你用 `docker run` 则需自己改）

### 3. MCP 初始化警告

外部 HTTP MCP（高德、航班、酒店等）缺 Key 或网络不通时，预加载可能 warning，应用仍会起来；对应工具调用会失败。

### 4. 首次对话很慢

启动时会预热 RAG / 连接 MCP；首请求若仍慢，多半是 LLM API 延迟。看 `docker compose logs -f app`。

### 5. Windows 路径 / 换行

建议在项目根目录用 PowerShell 执行上述命令；`.env` 用 UTF-8 保存。

---

## 文件说明

| 文件 | 作用 |
|------|------|
| `Dockerfile` | 应用镜像：Python 3.14 + uv 安装依赖 + uvicorn |
| `docker-compose.yml` | 编排 app / postgres / redis |
| `.dockerignore` | 减小构建上下文（不含 `.venv`、`.env`、测试等） |
| `.env.example` | 环境变量模板，复制为 `.env` 后填写密钥 |

---

## 生产环境建议（简要）

1. 把 `CORS allow_origins` 从 `*` 改成真实前端域名（`app/main.py`）。
2. 使用强随机 `POSTGRES_PASSWORD`，不要把 `.env` 提交到 Git。
3. 反向代理（Nginx / Caddy）终结 HTTPS，再反代到 `8000`。
4. 定期备份 `postgres_data` volume。
