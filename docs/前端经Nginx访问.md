# 前端经 Nginx 访问后端

后端四个容器已经在跑。浏览器只访问 **80 端口**。Nginx 负责两件事：把页面发给浏览器，把 `/api/` 转发到后端容器的 8000 端口。8000、5432、6379 不要对公网开放。

```text
浏览器
  │  http://公网IP/
  ▼
Nginx（80）
  ├─ /、/index.html     →  frontend/index.html（知行页面）
  └─ /api/v1/...        →  app 容器 :8000（FastAPI）
```

页面通过 `http://公网IP/` 打开时，接口自动发到同一个公网 IP 的 `/api/v1/...`，由 Nginx 转发到后端。

## 这次要上传的文件

在本机 PowerShell 执行（把 `YOUR_IP` 换成公网 IP）：

```powershell
scp E:\pythonProject\travelAgent\frontend\index.html root@YOUR_IP:/root/travel_agent/frontend/index.html
```

`frontend/index.html` 已与 `E:\pythonProject\zhixing.html` 同步。Nginx 配置 `deploy/nginx/default.conf` 已经会反代 `/api/`，这次不用改、也不用重新构建镜像。

## 服务器上生效

```bash
cd /root/travel_agent
docker compose restart nginx
docker compose ps
```

在服务器上自测：

```bash
curl -s http://127.0.0.1/healthz
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1/
```

`healthz` 应返回 JSON，页面应返回 `200`。

## 浏览器访问

阿里云安全组入方向放行 **80**。然后打开：

- 页面：`http://你的公网IP/`
- 接口文档（可选）：`http://你的公网IP/docs`

登录页没有连接设置。注册或登录后，浏览器开发者工具 Network 里应看到：

- `POST /api/v1/users/register` 或 `/api/v1/users/login`
- `GET /api/v1/conversations`
- 发消息时 `POST /api/v1/chat/stream/<会话id>`

这些请求的域名都是公网 IP，端口是 80，不是 8000。

## 端口

| 端口 | 谁在听 | 公网 |
|------|--------|------|
| 80 | Nginx | 要放行，用户只访问这个 |
| 8000 | 应用容器 | 不映射到公网，只给 Nginx 用 |
| 5432 | Postgres | 不开放 |
| 6379 | Redis | 不开放 |

如果 80 已被占用，在服务器 `.env` 增加 `HTTP_HOST_PORT=8080`，然后 `docker compose up -d`。安全组改放行 8080，访问 `http://公网IP:8080/`。

## 以后只改页面

改 `E:\pythonProject\zhixing.html` 后，再复制到 `frontend/index.html` 并上传，然后 `docker compose restart nginx`。不用 `--build`。

改 Python 后端才需要：

```bash
docker compose up -d --build app
```
