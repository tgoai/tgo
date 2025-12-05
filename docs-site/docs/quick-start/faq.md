---
id: faq
title: 常见问题
sidebar_position: 2
---

# 常见问题

## 安装问题

### Docker 未安装或版本过低

**问题**：执行安装脚本时提示 Docker 未安装或版本不满足要求。

**解决方案**：

1. 安装 Docker：
   ```bash
   curl -fsSL https://get.docker.com | sh
   ```

2. 确保 Docker Compose V2 可用：
   ```bash
   docker compose version
   ```

3. 启动 Docker 服务：
   ```bash
   sudo systemctl start docker
   sudo systemctl enable docker
   ```

### 端口被占用

**问题**：安装时提示 80 或 443 端口被占用。

**解决方案**：

安装脚本会自动检测端口占用并分配新端口（如 8080、8443）。你也可以手动修改 `.env` 文件：

```bash
NGINX_PORT=8080
NGINX_SSL_PORT=8443
```

修改后重新启动服务：

```bash
./tgo.sh down
./tgo.sh up
```

### 内存不足

**问题**：容器启动失败，日志显示 OOM（Out of Memory）。

**解决方案**：

TGO 需要至少 4GB 内存。检查可用内存：

```bash
free -h
```

如果内存不足，可以：
- 升级服务器配置
- 关闭不必要的服务

## 网络问题

### 中国境内拉取镜像慢

**问题**：在中国境内服务器上，拉取 Docker 镜像非常慢或超时。

**解决方案**：

使用国内加速版安装脚本：

```bash
REF=latest curl -fsSL https://gitee.com/tgoai/tgo/raw/main/bootstrap_cn.sh | bash
```

如果已安装但镜像拉取慢，可以配置 Docker 镜像加速器：

```bash
sudo mkdir -p /etc/docker
sudo tee /etc/docker/daemon.json <<-'EOF'
{
  "registry-mirrors": ["https://mirror.ccs.tencentyun.com"]
}
EOF
sudo systemctl daemon-reload
sudo systemctl restart docker
```

### 无法访问服务

**问题**：安装完成后无法通过浏览器访问。

**解决方案**：

1. 检查服务状态：
   ```bash
   ./tgo.sh doctor
   ```

2. 检查防火墙设置，确保端口开放：
   ```bash
   # Ubuntu/Debian
   sudo ufw allow 80/tcp
   sudo ufw allow 443/tcp
   
   # CentOS/RHEL
   sudo firewall-cmd --permanent --add-port=80/tcp
   sudo firewall-cmd --permanent --add-port=443/tcp
   sudo firewall-cmd --reload
   ```

3. 云服务器需要在安全组中开放对应端口。

## 服务问题

### 服务启动失败

**问题**：某个服务启动失败或一直重启。

**解决方案**：

1. 查看服务日志：
   ```bash
   docker compose logs -f <服务名>
   ```

2. 检查所有服务状态：
   ```bash
   ./tgo.sh doctor
   ```

3. 尝试重启所有服务：
   ```bash
   ./tgo.sh down
   ./tgo.sh up
   ```

### 数据库连接失败

**问题**：API 服务提示无法连接数据库。

**解决方案**：

1. 检查 PostgreSQL 容器状态：
   ```bash
   docker compose ps postgres
   ```

2. 查看数据库日志：
   ```bash
   docker compose logs postgres
   ```

3. 如果数据库损坏，可能需要重新初始化（**注意：会丢失数据**）：
   ```bash
   ./tgo.sh down --volumes
   ./tgo.sh install
   ```

## 升级问题

### 升级后服务异常

**问题**：执行升级后服务无法正常工作。

**解决方案**：

1. 查看升级日志，确认是否有错误
2. 检查服务状态：
   ```bash
   ./tgo.sh doctor
   ```

3. 如果问题持续，尝试重新安装：
   ```bash
   ./tgo.sh down
   ./tgo.sh install
   ```

## 获取帮助

如果以上方案无法解决你的问题，可以：

1. 查看完整日志：
   ```bash
   docker compose logs > tgo-logs.txt
   ```

2. 在 [GitHub Issues](https://github.com/tgoai/tgo/issues) 提交问题，附上：
   - 操作系统版本
   - Docker 版本
   - 错误日志
   - 复现步骤
