---
id: debug-tools
title: 调试工具
sidebar_position: 3
---

# 调试工具

TGO 内置了一些调试工具，帮助你排查问题和监控系统状态。

## 内置调试工具

TGO 提供了以下调试工具容器：

| 工具 | 用途 | 访问地址 |
|------|------|----------|
| **Kafka UI** | Kafka 消息队列管理界面 | `http://localhost:8080` |
| **Adminer** | 数据库管理界面 | `http://localhost:8081` |

## 启动调试工具

```bash
./tgo.sh tools start
```

## 停止调试工具

```bash
./tgo.sh tools stop
```

## Kafka UI

Kafka UI 是一个 Web 界面，用于管理和监控 Kafka 集群。

### 功能

- 查看 Topic 列表
- 浏览消息内容
- 监控消费者组
- 查看集群状态

### 使用场景

- 调试消息发送/接收问题
- 查看消息内容是否正确
- 监控消费者延迟

### 访问方式

启动工具后访问：`http://<服务器IP>:8080`

## Adminer

Adminer 是一个轻量级的数据库管理工具。

### 功能

- 浏览数据库表结构
- 执行 SQL 查询
- 导入/导出数据
- 编辑表数据

### 连接信息

| 参数 | 值 |
|------|-----|
| 系统 | PostgreSQL |
| 服务器 | `postgres` |
| 用户名 | `tgo`（或查看 `.env` 中的 `POSTGRES_USER`） |
| 密码 | `tgo`（或查看 `.env` 中的 `POSTGRES_PASSWORD`） |
| 数据库 | `tgo`（或查看 `.env` 中的 `POSTGRES_DB`） |

### 访问方式

启动工具后访问：`http://<服务器IP>:8081`

## 日志查看

### 查看所有服务日志

```bash
docker compose logs -f
```

### 查看特定服务日志

```bash
docker compose logs -f tgo-api
docker compose logs -f tgo-ai
docker compose logs -f tgo-rag
```

### 查看最近 N 行日志

```bash
docker compose logs --tail=100 tgo-api
```

### 日志级别

各服务的日志级别可以在对应的 `.env` 文件中配置：

```bash
# envs/tgo-ai.env
LOG_LEVEL=DEBUG
```

日志级别选项：`DEBUG`、`INFO`、`WARNING`、`ERROR`

## 容器调试

### 进入容器

```bash
docker compose exec tgo-api bash
docker compose exec tgo-ai bash
```

### 查看容器状态

```bash
docker compose ps
```

### 查看资源使用

```bash
docker stats
```

## 健康检查

使用 `doctor` 命令进行全面健康检查：

```bash
./tgo.sh doctor
```

该命令会检查：

- 所有服务的运行状态
- 数据库连接
- Nginx 配置
- 数据目录
- API 端点响应

## 网络调试

### 检查容器网络

```bash
docker network ls
docker network inspect tgo_default
```

### 测试容器间连接

```bash
# 从 tgo-api 容器测试连接 postgres
docker compose exec tgo-api ping postgres

# 测试端口连接
docker compose exec tgo-api nc -zv postgres 5432
```

## 数据库调试

### 直接连接数据库

```bash
docker compose exec postgres psql -U tgo -d tgo
```

### 常用 SQL 命令

```sql
-- 查看所有表
\dt

-- 查看表结构
\d table_name

-- 查看连接数
SELECT count(*) FROM pg_stat_activity;
```

## Redis 调试

### 连接 Redis

```bash
docker compose exec redis redis-cli
```

### 常用 Redis 命令

```bash
# 查看所有 key
KEYS *

# 查看 key 值
GET key_name

# 查看内存使用
INFO memory
```

## 常见调试场景

### 消息不发送

1. 启动 Kafka UI 查看消息队列
2. 检查 tgo-api 日志是否有错误
3. 确认 Kafka 服务正常运行

### API 请求失败

1. 查看 tgo-api 日志
2. 使用 `./tgo.sh doctor` 检查服务状态
3. 检查 Nginx 配置和日志

### 数据库查询慢

1. 使用 Adminer 分析慢查询
2. 检查数据库连接数
3. 查看数据库日志

## 安全提示

:::warning 注意
调试工具仅用于开发和调试环境。在生产环境中，请确保：

1. 不要将调试工具端口暴露到公网
2. 使用完毕后及时关闭：`./tgo.sh tools stop`
3. 修改默认的数据库密码
:::
