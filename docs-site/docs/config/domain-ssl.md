---
id: domain-ssl
title: 配置域名和证书
sidebar_position: 2
---

# 配置域名和证书

本页说明如何配置 Web / Widget / API 域名，并开启 HTTPS 证书。

## 配置域名

TGO 支持为不同服务配置独立域名：

| 服务 | 配置项 | 示例 |
|------|--------|------|
| Web 控制台 | `web_domain` | `www.example.com` |
| Widget 组件 | `widget_domain` | `widget.example.com` |
| API 服务 | `api_domain` | `api.example.com` |
| WebSocket | `ws_domain` | `ws.example.com` |

### 设置域名

在仓库根目录执行：

```bash
./tgo.sh config web_domain www.example.com
./tgo.sh config widget_domain widget.example.com
./tgo.sh config api_domain api.example.com
./tgo.sh config ws_domain ws.example.com
```

### 应用配置

设置完域名后，执行 `apply` 使配置生效：

```bash
./tgo.sh config apply
```

这会自动生成/更新 Nginx 配置，将不同域名反向代理到对应服务。

### 查看当前配置

```bash
./tgo.sh config show
```

## 启用 HTTPS

TGO 支持两种 SSL 证书配置方式：

### 方案 A：Let's Encrypt 自动证书（推荐）

**前提条件**：

- 所有域名的 DNS 已正确解析到当前服务器公网 IP
- 服务器 80/443 端口可从公网访问
- 服务器可访问 Let's Encrypt 服务

**配置步骤**：

```bash
# 1. 设置证书邮箱（用于到期提醒）
./tgo.sh config ssl_email your-email@example.com

# 2. 申请证书
./tgo.sh config setup_letsencrypt

# 3. 应用配置
./tgo.sh config apply
```

**证书自动续期**：

Let's Encrypt 证书有效期为 90 天。可以设置 cron 任务自动续期：

```bash
# 编辑 crontab
crontab -e

# 添加以下行（每天凌晨 2 点检查续期）
0 2 * * * cd /path/to/tgo && ./tgo.sh config setup_letsencrypt >/dev/null 2>&1
```

### 方案 B：使用已有证书

如果你已从其他 CA 获取了证书文件：

```bash
# 为所有域名安装同一证书（通配符证书）
./tgo.sh config ssl_manual /path/to/cert.pem /path/to/key.pem

# 或为特定域名安装证书
./tgo.sh config ssl_manual /path/to/cert.pem /path/to/key.pem www.example.com

# 应用配置
./tgo.sh config apply
```

证书文件会被复制到：

```
./data/nginx/ssl/<domain>/cert.pem
./data/nginx/ssl/<domain>/key.pem
```

### 禁用 SSL

如果只需要 HTTP 访问：

```bash
./tgo.sh config ssl_mode none
./tgo.sh config apply
```

## SSL 模式说明

| 模式 | 说明 |
|------|------|
| `none` | 不使用 SSL，仅 HTTP |
| `auto` | 使用 Let's Encrypt 自动证书 |
| `manual` | 使用手动上传的证书 |

查看当前 SSL 模式：

```bash
./tgo.sh config show
```

## 完整配置示例

以下是一个完整的域名和 SSL 配置流程：

```bash
# 1. 配置域名
./tgo.sh config web_domain www.example.com
./tgo.sh config widget_domain widget.example.com
./tgo.sh config api_domain api.example.com

# 2. 配置 Let's Encrypt
./tgo.sh config ssl_email admin@example.com
./tgo.sh config setup_letsencrypt

# 3. 应用所有配置
./tgo.sh config apply

# 4. 查看配置结果
./tgo.sh config show
```

配置完成后，即可通过 HTTPS 访问：

- `https://www.example.com` - Web 控制台
- `https://widget.example.com` - Widget 组件
- `https://api.example.com` - API 服务

## 常见问题

### 证书申请失败

1. 确认域名 DNS 已解析到服务器 IP：
   ```bash
   dig www.example.com
   ```

2. 确认 80 端口可访问（Let's Encrypt 需要验证）

3. 检查防火墙和安全组设置

### 证书到期

Let's Encrypt 会在到期前发送邮件提醒。手动续期：

```bash
./tgo.sh config setup_letsencrypt
./tgo.sh config apply
```

### 混合内容警告

如果浏览器报告混合内容警告，检查前端配置中的 API 地址是否也使用了 HTTPS。
