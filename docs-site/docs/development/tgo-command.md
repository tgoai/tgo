---
id: tgo-command
title: tgo 命令
sidebar_position: 4
---

# tgo 命令

`tgo.sh` 是 TGO 的主要管理脚本，提供了部署、运维和配置的所有常用命令。

## 命令概览

```bash
./tgo.sh <command> [options]
```

## 基础命令

### help

显示帮助信息：

```bash
./tgo.sh help
```

### install

首次安装并启动所有服务：

```bash
./tgo.sh install [--source] [--cn]
```

| 选项 | 说明 |
|------|------|
| `--source` | 从源码构建（而非使用预构建镜像） |
| `--cn` | 使用国内镜像加速 |

示例：

```bash
# 默认安装（使用预构建镜像）
./tgo.sh install

# 源码安装
./tgo.sh install --source

# 国内镜像安装
./tgo.sh install --cn

# 组合使用
./tgo.sh install --source --cn
```

### up

启动所有服务（不执行初始化）：

```bash
./tgo.sh up [--source] [--cn]
```

适用于 `down` 之后重新启动服务。

### down

停止并移除所有容器：

```bash
./tgo.sh down [--volumes]
```

| 选项 | 说明 |
|------|------|
| `--volumes` | 同时删除数据卷（**会丢失数据**） |

### upgrade

升级到最新版本：

```bash
./tgo.sh upgrade [--source] [--cn]
```

会自动记住首次安装时的模式（source/cn）。

### uninstall

卸载 TGO：

```bash
./tgo.sh uninstall [--source] [--cn]
```

会询问是否删除数据。

### doctor

检查所有服务的健康状态：

```bash
./tgo.sh doctor
```

输出包括：

- 各服务运行状态
- 配置检查
- 端点响应测试

## 服务管理命令

### service

管理核心服务：

```bash
./tgo.sh service <start|stop|remove> [--source] [--cn]
```

| 子命令 | 说明 |
|--------|------|
| `start` | 启动服务 |
| `stop` | 停止服务 |
| `remove` | 移除服务 |

### tools

管理调试工具（Kafka UI、Adminer）：

```bash
./tgo.sh tools <start|stop>
```

| 子命令 | 说明 |
|--------|------|
| `start` | 启动调试工具 |
| `stop` | 停止调试工具 |

### build

从源码构建特定服务：

```bash
./tgo.sh build <service>
```

| 服务名 | 说明 |
|--------|------|
| `api` | 构建 tgo-api |
| `ai` | 构建 tgo-ai |
| `rag` | 构建 tgo-rag |
| `platform` | 构建 tgo-platform |
| `web` | 构建 tgo-web |
| `widget` | 构建 tgo-widget |
| `all` | 构建所有服务 |

## 配置命令

### config

域名和 SSL 证书配置：

```bash
./tgo.sh config <subcommand> [args]
```

#### 域名配置

```bash
./tgo.sh config web_domain <domain>      # 设置 Web 域名
./tgo.sh config widget_domain <domain>   # 设置 Widget 域名
./tgo.sh config api_domain <domain>      # 设置 API 域名
./tgo.sh config ws_domain <domain>       # 设置 WebSocket 域名
```

#### SSL 配置

```bash
./tgo.sh config ssl_mode <auto|manual|none>   # 设置 SSL 模式
./tgo.sh config ssl_email <email>              # 设置 Let's Encrypt 邮箱
./tgo.sh config ssl_manual <cert> <key> [domain]  # 安装手动证书
./tgo.sh config setup_letsencrypt              # 申请 Let's Encrypt 证书
```

#### 其他配置命令

```bash
./tgo.sh config apply   # 应用配置（重新生成 Nginx 配置）
./tgo.sh config show    # 显示当前配置
```

## 完整配置示例

### 域名和 HTTPS 配置

```bash
# 配置域名
./tgo.sh config web_domain www.example.com
./tgo.sh config widget_domain widget.example.com
./tgo.sh config api_domain api.example.com

# 配置 SSL
./tgo.sh config ssl_email admin@example.com
./tgo.sh config setup_letsencrypt

# 应用配置
./tgo.sh config apply

# 查看配置
./tgo.sh config show
```

## 命令选项说明

| 选项 | 说明 |
|------|------|
| `--source` | 使用源码模式（从 `repos/` 目录构建镜像） |
| `--cn` | 使用国内镜像（阿里云 ACR、Gitee） |
| `--volumes` | 包含数据卷操作 |

## 环境变量

一键安装脚本支持以下环境变量：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `REF` | 部署版本（分支/Tag/提交号） | `latest` |
| `DIR` | 安装目录 | `./tgo` |

示例：

```bash
REF=v1.0.0 DIR=/opt/tgo curl -fsSL https://raw.githubusercontent.com/tgoai/tgo/main/bootstrap.sh | bash
```

## 配置文件

| 文件 | 说明 |
|------|------|
| `.env` | 全局环境变量 |
| `envs/*.env` | 各服务环境变量 |
| `data/.tgo-install-mode` | 安装模式记忆 |
| `data/.tgo-domain-config` | 域名和 SSL 配置 |

## 数据目录

| 目录 | 说明 |
|------|------|
| `data/postgres/` | PostgreSQL 数据 |
| `data/redis/` | Redis 数据 |
| `data/wukongim/` | WuKongIM 数据 |
| `data/nginx/` | Nginx 配置和证书 |
| `data/uploads/` | 上传文件 |

## 使用建议

1. **生产环境**：使用 `./tgo.sh install` 默认镜像部署
2. **开发环境**：使用 `./tgo.sh install --source` 源码部署
3. **国内服务器**：添加 `--cn` 参数加速
4. **问题排查**：先运行 `./tgo.sh doctor` 检查状态
