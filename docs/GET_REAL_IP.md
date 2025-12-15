# 获取客户端真实 IP 地址

## 问题描述

在 Docker 部署环境中，通过访客注册接口获取到的 IP 地址是 Docker 网关地址（如 `172.18.0.1`），而不是客户端的真实 IP。

这是因为 Docker 默认使用 **userland-proxy** 进行端口映射，导致 NAT（网络地址转换）将源 IP 替换为 Docker 网关 IP。

## 解决方案

### 方案 1：修改 Docker Daemon 配置（推荐）

禁用 Docker 的 userland-proxy 可以保留真实客户端 IP。

**步骤：**

1. 编辑 Docker daemon 配置文件：

```bash
sudo nano /etc/docker/daemon.json
```

2. 添加或修改以下配置：

```json
{
  "userland-proxy": false
}
```

3. 重启 Docker 服务：

```bash
sudo systemctl restart docker
```

4. 重新启动 TGO 服务：

```bash
./tgo.sh restart
```

**注意事项：**
- 这个修改会影响所有 Docker 容器
- 需要 root 权限
- 某些老旧的网络环境可能不兼容

---

### 方案 2：使用外部反向代理（生产环境推荐）

如果你使用 CDN（如 Cloudflare）或外部负载均衡器，它们会正确设置 `X-Forwarded-For` 头。

**Cloudflare 设置：**
- 确保开启 "Proxy" 模式（橙色云图标）
- 客户端真实 IP 会通过 `CF-Connecting-IP` 头传递

**AWS ALB / ELB 设置：**
- 负载均衡器会自动设置 `X-Forwarded-For` 头

**外部 Nginx 设置：**

如果在 Docker 外部有一层 Nginx，确保配置如下：

```nginx
location / {
    proxy_pass http://your-docker-host:80;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

---

### 方案 3：Nginx 使用 Host 网络模式

让 Nginx 容器直接使用宿主机网络，可以获取真实 IP，但需要额外配置。

1. 修改 `docker-compose.yml`：

```yaml
nginx:
  image: nginx:alpine
  container_name: tgo-nginx
  network_mode: host
  # 移除 ports 配置，因为 host 模式下直接使用宿主机端口
```

2. 修改 Nginx 配置，使用 `127.0.0.1` 或宿主机 IP 连接其他服务：

```nginx
# 将 proxy_pass http://tgo-api:8000 改为使用宿主机回环地址
# 需要同时让其他服务暴露端口到宿主机
```

3. 暴露其他服务的端口到宿主机。

**注意：** 此方案较复杂，不推荐新手使用。

---

## 验证真实 IP 获取

配置完成后，可以通过以下方式验证：

1. 查看访客注册时的 IP：

```bash
# 查看 API 日志
docker logs tgo-api 2>&1 | grep "ip_address"
```

2. 在数据库中检查：

```sql
SELECT id, nickname, ip_address, geo_city FROM visitors ORDER BY created_at DESC LIMIT 5;
```

## 相关代码

API 获取客户端 IP 的逻辑位于：
- `repos/tgo-api/app/utils/request.py` - `get_client_ip()` 函数

该函数按以下优先级获取 IP：
1. 请求体中提供的 `ip_address` 字段
2. `X-Forwarded-For` 头（第一个 IP）
3. `X-Real-IP` 头
4. `CF-Connecting-IP` 头（Cloudflare）
5. `True-Client-IP` 头（部分 CDN）
6. `request.client.host`（直接连接的 IP）

