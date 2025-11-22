# 域名配置指南

本指南介绍如何使用 `./tgo.sh config` 命令配置域名和 SSL 证书。

## 快速开始

### 1. 配置域名

```bash
# 配置 Web 服务域名
./tgo.sh config web_domain www.talkgo.cn

# 配置 Widget 服务域名
./tgo.sh config widget_domain widget.talkgo.cn

# 配置 API 服务域名
./tgo.sh config api_domain api.talkgo.cn
```

### 2. 查看当前配置

```bash
./tgo.sh config show
```

### 3. 启用 SSL（Let's Encrypt 自动）

```bash
# 设置 Let's Encrypt 邮箱
./tgo.sh config ssl_email admin@talkgo.cn

# 设置 SSL 模式为自动
./tgo.sh config ssl_mode auto

# 设置 Let's Encrypt 证书
./tgo.sh config setup_letsencrypt
```

### 4. 启动 Nginx 反向代理

```bash
# 使用 Nginx 反向代理启动服务
docker compose up -d
```

---

## 详细说明

### 配置命令

#### `web_domain <domain>`
设置 Web 服务的域名。

```bash
./tgo.sh config web_domain www.talkgo.cn
```

#### `widget_domain <domain>`
设置 Widget 服务的域名。

```bash
./tgo.sh config widget_domain widget.talkgo.cn
```

#### `api_domain <domain>`
设置 API 服务的域名。

```bash
./tgo.sh config api_domain api.talkgo.cn
```

#### `ssl_mode <auto|manual|none>`
设置 SSL 模式。

- `auto`: 使用 Let's Encrypt 自动证书（推荐生产环境）
- `manual`: 使用手动上传的证书
- `none`: 不使用 SSL（仅 HTTP）

```bash
./tgo.sh config ssl_mode auto
```

#### `ssl_email <email>`
设置 Let's Encrypt 邮箱（用于证书续期通知）。

```bash
./tgo.sh config ssl_email admin@talkgo.cn
```

#### `ssl_manual <cert_file> <key_file> [domain]`
安装手动 SSL 证书。

```bash
# 为所有域名安装证书
./tgo.sh config ssl_manual /path/to/cert.pem /path/to/key.pem

# 为特定域名安装证书
./tgo.sh config ssl_manual /path/to/cert.pem /path/to/key.pem www.talkgo.cn
```

#### `setup_letsencrypt`
自动设置 Let's Encrypt 证书（需要先配置所有域名）。

```bash
./tgo.sh config setup_letsencrypt
```

#### `apply`
重新生成 Nginx 配置文件。

```bash
./tgo.sh config apply
```

#### `show`
显示当前配置。

```bash
./tgo.sh config show
```

---

## SSL 证书管理

### 方案 1: Let's Encrypt 自动证书（推荐）

**优点**:
- 完全自动化
- 免费
- 自动续期

**步骤**:

1. 配置域名和邮箱
2. 运行 `./tgo.sh config setup_letsencrypt`
3. 启动 Nginx 反向代理

**自动续期**:

证书会在 Certbot 容器中自动续期。如果需要手动续期：

```bash
bash ./scripts/renew-ssl.sh
```

### 方案 2: 手动证书

**适用场景**:
- 企业 SSL 证书
- 自签名证书
- 其他证书提供商

**步骤**:

1. 准备证书文件（cert.pem 和 key.pem）
2. 运行 `./tgo.sh config ssl_manual cert.pem key.pem`
3. 启动 Nginx 反向代理

### 方案 3: 无 SSL（开发环境）

```bash
./tgo.sh config ssl_mode none
```

---

## DNS 配置

在使用域名前，需要配置 DNS 记录指向你的服务器：

```
www.talkgo.cn      A    <your-server-ip>
widget.talkgo.cn   A    <your-server-ip>
api.talkgo.cn      A    <your-server-ip>
```

---

## 防火墙配置

确保以下端口开放：

```bash
# HTTP (Let's Encrypt 验证)
80/tcp

# HTTPS (生产流量)
443/tcp
```

---

## 配置文件位置

- **域名配置**: `./data/.tgo-domain-config`
- **Nginx 配置**: `./data/nginx/conf.d/default.conf`
- **SSL 证书**: `./data/nginx/ssl/<domain>/`
- **Let's Encrypt 数据**: `./data/certbot/`

---

## 故障排除

### 问题: 证书获取失败

**原因**: DNS 未正确配置或端口 80 未开放

**解决**:
1. 检查 DNS 记录是否指向正确的 IP
2. 确保端口 80 和 443 开放
3. 检查防火墙规则

### 问题: Nginx 无法启动

**原因**: 配置文件错误或证书文件不存在

**解决**:
1. 检查 `./data/nginx/conf.d/default.conf`
2. 确保证书文件存在于 `./data/nginx/ssl/`
3. 运行 `./tgo.sh config apply` 重新生成配置

### 问题: 证书续期失败

**原因**: Certbot 容器未运行或权限问题

**解决**:
1. 检查 Certbot 容器状态: `docker ps | grep certbot`
2. 查看日志: `docker logs tgo-certbot`
3. 手动续期: `bash ./scripts/renew-ssl.sh`

---

## 常见场景

### 场景 1: 生产环境完整配置

```bash
# 1. 配置域名
./tgo.sh config web_domain www.talkgo.cn
./tgo.sh config widget_domain widget.talkgo.cn
./tgo.sh config api_domain api.talkgo.cn

# 2. 配置 Let's Encrypt
./tgo.sh config ssl_email admin@talkgo.cn
./tgo.sh config ssl_mode auto

# 3. 设置证书
./tgo.sh config setup_letsencrypt

# 4. 启动服务
docker compose up -d
```

### 场景 2: 使用企业证书

```bash
# 1. 配置域名
./tgo.sh config web_domain www.talkgo.cn
./tgo.sh config widget_domain widget.talkgo.cn
./tgo.sh config api_domain api.talkgo.cn

# 2. 安装证书
./tgo.sh config ssl_manual /path/to/cert.pem /path/to/key.pem

# 3. 启动服务
docker compose up -d
```

### 场景 3: 开发环境（无 SSL）

```bash
# 1. 配置域名
./tgo.sh config web_domain localhost
./tgo.sh config widget_domain localhost
./tgo.sh config api_domain localhost

# 2. 禁用 SSL
./tgo.sh config ssl_mode none

# 3. 启动服务
docker compose up -d
```

---

## 更新 VITE_API_BASE_URL

配置域名后，需要更新前端的 API 地址。在 `.env` 中设置：

```bash
VITE_API_BASE_URL=https://api.talkgo.cn
```

或者在启动容器时传入：

```bash
docker compose -e VITE_API_BASE_URL=https://api.talkgo.cn up -d
```

---

## 更多帮助

查看所有可用命令：

```bash
./tgo.sh help
```

查看当前配置：

```bash
./tgo.sh config show
```

