# 阿里云 CentOS 部署指南（无域名 / 仅 HTTP）

适用场景：Docker 已安装，本机上传代码，用公网 IP 访问，不配 HTTPS。

访问地址示例：`http://你的公网IP/`（前端）  
健康检查：`http://你的公网IP/healthz`  
API 文档：`http://你的公网IP/docs`

---

## 0. 阿里云安全组

在 ECS 安全组入方向放行：

| 端口 | 说明 |
|------|------|
| 22 | SSH 上传与运维 |
| 80 | 网站（Nginx） |

**不要**对公网开放 5432（Postgres）、6379（Redis）、8000（应用）。

若开了 `firewalld`：

```bash
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --reload
```

---

## 1. 本机打包上传（Windows PowerShell）

在 **本机** 进入项目上级目录（按你的实际路径改）：

```powershell
cd E:\pythonProject

# 打包（排除虚拟环境、本地数据库、缓存）
tar -cf travelAgent-deploy.tar `
  --exclude=travelAgent/.venv `
  --exclude=travelAgent/venv `
  --exclude=travelAgent/.git `
  --exclude=travelAgent/postgres_db `
  --exclude=travelAgent/redis_db `
  --exclude=travelAgent/__pycache__ `
  --exclude=travelAgent/.pytest_cache `
  --exclude=travelAgent/logs `
  --exclude=travelAgent/.idea `
  travelAgent

# 上传到服务器（把 YOUR_IP 换成公网 IP，用户名按实际）
scp travelAgent-deploy.tar root@YOUR_IP:/opt/
```

若本机没有 `tar` / `scp`，可用：

- Git Bash / WSL 执行上面命令  
- 或用阿里云「Workbench」、WinSCP、FinalShell 把整个 `travelAgent` 文件夹拖上去（记得不要传 `.venv`）

---

## 2. 服务器解压并配置

SSH 登录服务器后：

```bash
cd /opt
tar -xf travelAgent-deploy.tar
cd /opt/travelAgent

# 环境变量
cp .env.example .env
vi .env   # 或 nano .env
```

`.env` **至少**改这些：

```env
DASHSCOPE_API_KEY=你的通义Key
POSTGRES_PASSWORD=换成强密码
LANGSMITH_TRACING=false
LANGSMITH_API_KEY=disabled
APP_ENV=production
DEBUG=false

# 可选 MCP（没有就留空，对应工具会不可用）
AMAP_API_KEY=
TAVILY_API_KEY=
VARIFLIGHT_API_KEY=
AIGOHOTEL_MCP_API=
```

> `docker-compose` 会把 `POSTGRES_HOST` / `REDIS_HOST` 自动指到容器名，不必写成公网 IP。

---

## 3. 启动（国内务必先配镜像加速）

首次构建若半小时仍无进度，多半是 Docker Hub / 外网慢。  
先看 [DOCKER_MIRROR_CN.md](./DOCKER_MIRROR_CN.md) 配置 `registry-mirrors`，并上传最新 `Dockerfile`（已去掉 ghcr、改用国内源）。

```bash
cd /opt/travelAgent

# 确认 Docker
docker version
docker compose version   # 若失败再试：docker-compose version

# 建议先看详细进度，便于判断卡在哪
docker compose build --progress=plain

# 再后台启动
docker compose up -d

# 看状态
docker compose ps
docker compose logs -f app
```

看到 MCP / checkpointer / RAG 相关就绪日志后，Ctrl+C 退出日志（容器继续跑）。

验证：

```bash
curl -s http://127.0.0.1/healthz
curl -s http://127.0.0.1/ | head
```

浏览器打开：`http://你的公网IP/`

登录页「连接设置」**留空**即可（会自动用当前 IP 作为 API 地址）。

---

## 4. 日常命令

```bash
cd /opt/travelAgent

docker compose logs -f nginx
docker compose logs -f app
docker compose restart app
docker compose up -d --build app    # 改后端后重建
docker compose down                 # 停止（数据卷保留）
```

更新前端：改完 `frontend/index.html` 后重新上传该文件即可，一般不用重建镜像：

```bash
docker compose restart nginx
```

---

## 5. 本机改代码后再次上传

只更新代码时可打增量包，或用 scp 传单个目录：

```powershell
# 例：只更新前端
scp E:\pythonProject\travelAgent\frontend\index.html root@YOUR_IP:/opt/travelAgent/frontend/

# 例：更新后端 app 目录后重建
scp -r E:\pythonProject\travelAgent\app root@YOUR_IP:/opt/travelAgent/
```

服务器上：

```bash
cd /opt/travelAgent
docker compose up -d --build app
docker compose restart nginx
```

---

## 6. 常见问题

### 浏览器打不开

1. 安全组是否放行 80  
2. `docker compose ps` 里 nginx / app 是否 Up  
3. `curl http://127.0.0.1/healthz` 在服务器上是否通  

### 能打开页面但登录失败

1. 浏览器 F12 → Network 看请求是否打到 `/api/v1/...`  
2. 「连接设置」是否被写成了 `localhost`（应留空）  
3. `docker compose logs -f app`

### SSE 对话卡住

确认用的是 80 端口经 Nginx，且配置里 `proxy_buffering off`（仓库已写好）。

### 80 端口被占用

改 `.env`：

```env
HTTP_HOST_PORT=8080
```

然后 `docker compose up -d`，访问 `http://IP:8080/`，安全组放行 8080。

---

## 目录对应关系

| 路径 | 作用 |
|------|------|
| `frontend/index.html` | 知行前端 |
| `deploy/nginx/default.conf` | Nginx：静态页 + `/api` 反代 |
| `docker-compose.yml` | postgres + redis + app + nginx |
| `.env` | 密钥与密码（不要提交 Git） |
