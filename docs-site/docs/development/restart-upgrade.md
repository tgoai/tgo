---
id: restart-upgrade
title: 重启和升级
sidebar_position: 2
---

# 重启和升级

本页介绍如何管理 TGO 服务的启停和版本升级。

## 服务管理

### 启动服务

```bash
./tgo.sh up
```

源码模式：

```bash
./tgo.sh up --source
```

### 停止服务

```bash
./tgo.sh down
```

停止并删除数据卷（**会丢失数据**）：

```bash
./tgo.sh down --volumes
```

### 重启服务

```bash
./tgo.sh down
./tgo.sh up
```

### 重启单个服务

```bash
docker compose restart tgo-api
```

## 版本升级

### 升级到最新版本

```bash
./tgo.sh upgrade
```

`upgrade` 命令会自动：

1. 拉取最新代码
2. 更新 Docker 镜像
3. 执行数据库迁移
4. 重启所有服务

### 升级命令选项

```bash
./tgo.sh upgrade [--source] [--cn]
```

| 选项 | 说明 |
|------|------|
| `--source` | 从源码构建（而非使用预构建镜像） |
| `--cn` | 使用国内镜像加速 |

### 安装模式记忆

`upgrade` 会记住首次安装时的模式。例如：

```bash
# 首次使用国内镜像安装
./tgo.sh install --cn

# 之后升级自动使用 --cn
./tgo.sh upgrade
```

配置保存在 `./data/.tgo-install-mode` 文件中。

### 升级到特定版本

如需升级到特定版本，可以手动操作：

```bash
# 1. 停止服务
./tgo.sh down

# 2. 拉取特定版本
git fetch origin
git checkout v1.0.0

# 3. 重新安装
./tgo.sh install
```

## 卸载

### 停止并删除服务

```bash
./tgo.sh uninstall
```

该命令会：

1. 停止所有容器
2. 删除容器
3. 询问是否删除数据

### 完全清理

如需完全清理所有数据：

```bash
# 停止服务
./tgo.sh down --volumes

# 删除数据目录
rm -rf ./data

# 删除配置文件
rm -f .env
rm -rf ./envs
```

## 备份与恢复

### 备份数据

主要数据存储在 `./data` 目录：

```bash
# 创建备份
tar -czvf tgo-backup-$(date +%Y%m%d).tar.gz ./data
```

### 恢复数据

```bash
# 停止服务
./tgo.sh down

# 恢复数据
tar -xzvf tgo-backup-20240101.tar.gz

# 启动服务
./tgo.sh up
```

### 数据库备份

单独备份 PostgreSQL 数据库：

```bash
# 导出数据库
docker compose exec postgres pg_dump -U tgo tgo > tgo-db-backup.sql

# 恢复数据库
docker compose exec -T postgres psql -U tgo tgo < tgo-db-backup.sql
```

## 健康检查

检查所有服务状态：

```bash
./tgo.sh doctor
```

输出示例：

```
=========================================
  TGO Service Health Check
=========================================

  ✅ tgo-api           running (healthy)
  ✅ tgo-ai            running (healthy)
  ✅ tgo-rag           running (healthy)
  ✅ tgo-web           running
  ✅ postgres          running (healthy)
  ✅ redis             running (healthy)
  ✅ nginx             running

-----------------------------------------
Summary: 7/7 services healthy
```

## 故障排除

### 服务无法启动

1. 查看日志：
   ```bash
   docker compose logs -f <服务名>
   ```

2. 检查资源使用：
   ```bash
   docker stats
   ```

3. 重建容器：
   ```bash
   ./tgo.sh down
   ./tgo.sh install
   ```

### 升级后异常

1. 检查是否有数据库迁移失败
2. 回滚到之前版本：
   ```bash
   git checkout <之前的版本>
   ./tgo.sh install
   ```
