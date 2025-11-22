# 域名配置快速参考

## 5 分钟快速开始

### 场景 1: 生产环境（Let's Encrypt）

```bash
# 1. 配置域名
./tgo.sh config web_domain www.talkgo.cn
./tgo.sh config widget_domain widget.talkgo.cn
./tgo.sh config api_domain api.talkgo.cn

# 2. 配置 SSL
./tgo.sh config ssl_email admin@talkgo.cn
./tgo.sh config ssl_mode auto
./tgo.sh config setup_letsencrypt

# 3. 启动服务
docker compose --profile ssl-auto up -d

# 4. 验证
curl https://www.talkgo.cn
```

### 场景 2: 开发环境（无 SSL）

```bash
# 1. 配置域名
./tgo.sh config web_domain localhost
./tgo.sh config widget_domain localhost
./tgo.sh config api_domain localhost

# 2. 禁用 SSL
./tgo.sh config ssl_mode none

# 3. 启动服务
docker compose up -d

# 4. 验证
curl http://localhost
```

### 场景 3: 企业证书

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

---

## 常用命令

| 命令 | 说明 |
|------|------|
| `./tgo.sh config show` | 查看当前配置 |
| `./tgo.sh config web_domain <domain>` | 设置 Web 域名 |
| `./tgo.sh config widget_domain <domain>` | 设置 Widget 域名 |
| `./tgo.sh config api_domain <domain>` | 设置 API 域名 |
| `./tgo.sh config ssl_mode auto` | 启用 Let's Encrypt |
| `./tgo.sh config ssl_mode manual` | 启用手动证书 |
| `./tgo.sh config ssl_mode none` | 禁用 SSL |
| `./tgo.sh config ssl_email <email>` | 设置 Let's Encrypt 邮箱 |
| `./tgo.sh config ssl_manual <cert> <key>` | 安装手动证书 |
| `./tgo.sh config setup_letsencrypt` | 设置 Let's Encrypt |
| `./tgo.sh config apply` | 重新生成 Nginx 配置 |

---

## 启动命令

```bash
# 使用 Nginx 反向代理启动
docker compose up -d

# 使用 Let's Encrypt 自动续期启动
docker compose --profile ssl-auto up -d

# 停止服务
docker compose down

# 查看日志
docker compose logs -f nginx
```

---

## 配置文件位置

| 文件 | 说明 |
|------|------|
| `./data/.tgo-domain-config` | 域名配置 |
| `./data/nginx/conf.d/default.conf` | Nginx 配置 |
| `./data/nginx/ssl/<domain>/cert.pem` | SSL 证书 |
| `./data/nginx/ssl/<domain>/key.pem` | SSL 密钥 |
| `./data/certbot/conf/` | Let's Encrypt 配置 |

---

## DNS 配置

```
www.talkgo.cn      A    <your-server-ip>
widget.talkgo.cn   A    <your-server-ip>
api.talkgo.cn      A    <your-server-ip>
```

---

## 防火墙规则

```bash
# 开放 HTTP 和 HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
```

---

## 故障排除

| 问题 | 解决方案 |
|------|--------|
| 证书获取失败 | 检查 DNS 和端口 80 是否开放 |
| Nginx 无法启动 | 运行 `./tgo.sh config apply` |
| 证书续期失败 | 运行 `bash ./scripts/renew-ssl.sh` |
| 无法访问域名 | 检查 DNS 配置和防火墙规则 |

---

## 更新 VITE_API_BASE_URL

```bash
# 在 .env 中设置
VITE_API_BASE_URL=https://api.talkgo.cn

# 或在启动时传入
docker compose -e VITE_API_BASE_URL=https://api.talkgo.cn up -d
```

---

## 查看证书信息

```bash
# 查看证书过期时间
openssl x509 -in ./data/nginx/ssl/www.talkgo.cn/cert.pem -noout -dates

# 查看证书详细信息
openssl x509 -in ./data/nginx/ssl/www.talkgo.cn/cert.pem -noout -text
```

---

## 手动续期证书

```bash
bash ./scripts/renew-ssl.sh
```

---

## 更多帮助

- 详细指南: `docs/DOMAIN_CONFIG_GUIDE.md`
- SSL 续期: `docs/SSL_AUTO_RENEWAL_SETUP.md`
- 查看帮助: `./tgo.sh help`

