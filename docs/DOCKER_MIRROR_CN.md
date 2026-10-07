# Docker / pip 国内加速（CentOS / 阿里云）

首次 `docker compose up -d --build` 慢，在国内通常卡在：

1. 拉 Docker Hub 镜像（`python` / `postgres` / `redis` / `nginx`）
2. 拉 `ghcr.io`（旧 Dockerfile 装 uv 会卡这里）
3. `uv sync` 下载 Python 包（依赖较多时仍需几分钟；已移除本地 torch / sentence-transformers）

仓库 Dockerfile 已改为：apt 与 **PyPI（pip / uv sync）** 优先阿里云；bootstrap `uv` 另有清华、官方 fallback。  
**Docker 引擎的 registry-mirrors（阿里云 ACR 加速器）** 只加速拉 `python` / `postgres` 等**容器镜像**，**不能**代替 PyPI，也解决不了 `pip install uv` 找不到包的问题。

---

## 1. 配置 Docker 镜像加速（必做）

SSH 登录服务器：

```bash
sudo mkdir -p /etc/docker

# 若已有 daemon.json，先备份
sudo cp /etc/docker/daemon.json /etc/docker/daemon.json.bak 2>/dev/null || true

sudo tee /etc/docker/daemon.json >/dev/null <<'EOF'
{
  "registry-mirrors": [
    "https://docker.1ms.run",
    "https://docker.m.daocloud.io",
    "https://mirror.ccs.tencentyun.com"
  ],
  "max-concurrent-downloads": 10
}
EOF

sudo systemctl daemon-reload
sudo systemctl restart docker
docker info | grep -A5 "Registry Mirrors"
```

说明：

- 公网镜像地址会变化，若某个失效可换 [DaoCloud](https://docker.m.daocloud.io) 或阿里云「容器镜像服务 ACR → 镜像加速器」里给你的专属地址（最稳）。
- 阿里云 ECS 登录 [容器镜像服务控制台](https://cr.console.aliyun.com/) → 镜像工具 → 镜像加速器，复制加速器地址，放到 `registry-mirrors` **第一位**。

---

## 2. 更新本仓库 Dockerfile 后再构建

把最新代码（含改过的 `Dockerfile`）上传到服务器后：

```bash
cd /opt/travelAgent

# 看清卡在哪一步（推荐）
docker compose build --progress=plain 2>&1 | tee build.log

# 成功后再后台启动
docker compose up -d
```

若之前卡死了一小时，先清掉半成品再重来：

```bash
docker compose down
docker builder prune -f
docker compose build --progress=plain
docker compose up -d
```

---

## 3. 如何判断卡在哪

| 日志特征 | 原因 | 处理 |
|----------|------|------|
| `Pulling python` / `postgres` / `redis` | Docker Hub 慢 | 配 registry-mirrors |
| `ghcr.io/astral-sh/uv` | GitHub 容器慢 | 用新 Dockerfile（已去掉） |
| `apt-get update` 很久 | Debian 源慢 | 新 Dockerfile 已换阿里云 |
| `uv sync` 很久 | 依赖多或 PyPI 慢 | 确认 Dockerfile 使用阿里云 PyPI；配好后通常数分钟级 |
| `pip install uv` / `(from versions: none)` | PyPI 镜像未同步或不可达 | Dockerfile 已对 uv 做阿里云→清华→官方 fallback |
| `uv sync` 403，URL 仍是 `pypi.tuna.tsinghua.edu.cn` | `uv.lock` 写死了清华文件地址，`--index-url` 不会改写 | Dockerfile 构建前把 lock 里的清华 URL 换成阿里云 |
| 一直无新输出 | 网络挂起 | Ctrl+C，换加速器后重试 |

配好镜像加速且去掉 torch 后，首次构建常见 **5–15 分钟**；超过半小时且无进度，基本是镜像源问题。

---

## 4. 可选：本机构建后传到服务器（开发机网络更好时）

若服务器仍然很慢，可在网络好的机器构建并导出：

```bash
# 本机构建
docker compose build app
docker save travelagent-app:latest | gzip > travelagent-app.tar.gz
scp travelagent-app.tar.gz root@YOUR_IP:/opt/

# 服务器导入
gunzip -c /opt/travelagent-app.tar.gz | docker load
cd /opt/travelAgent && docker compose up -d
```

镜像名以 `docker images` 实际名为准（可能是 `travelagent-app` 或带前缀）。

---

## 5. 构建成功后的缓存

只要不改 `pyproject.toml` / `uv.lock`，再次 `docker compose up -d --build` 会走缓存，通常几分钟内完成。改业务代码（`app/`）也不会重装全部 Python 依赖。
