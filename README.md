# tgo-deploy 部署指南

本仓库提供一套基于 Docker Compose 的一键部署方案，编排并启动：
- 依赖：Postgres(pgvector)、Redis、Kafka(+UI)、WuKongIM
- 应用：tgo-api、tgo-ai、tgo-platform、tgo-rag(+worker/beat/flower)、tgo-web、tgo-widget-app

> 说明：本仓库默认使用当前项目的 `repos/` 目录中的各子项目源码，不再在部署时自动克隆。

## 前置条件
- Docker (建议 24+)、Docker Compose 插件
- Bash 环境（macOS / Linux / WSL2 均可）

## 快速开始
1) 克隆并进入仓库
- git clone <this-repo>
- cd tgo-deploy

2) 准备配置
- 首次运行 `./tgo.sh install` 会自动：
  - 如无 `.env`，从 `.env.example` 复制生成
  - 如无 `envs/`，从 `envs.docker/` 复制生成
  - 如 `envs/tgo-api.env` 中 `SECRET_KEY` 缺失/占位，将自动生成安全随机值
- 如需自定义，先编辑 `.env`（端口、数据库 DSN、API_BASE_URL 等），以及 `envs/<service>.env`

3) 启动
- ./tgo.sh install
- 首次会完成镜像构建、数据库迁移并以后台方式启动全部服务

## tgo.sh 命令一览
- `./tgo.sh help`：查看所有命令及用法
- `./tgo.sh install`：构建镜像、执行迁移并启动全部服务
- `./tgo.sh uninstall`：停止并移除所有服务，可选择是否删除 `./data/`
- `./tgo.sh service start`：启动核心服务（等同 `docker compose up -d`）
- `./tgo.sh service stop`：停止核心服务（等同 `docker compose down`）
- `./tgo.sh service remove`：停止核心服务并移除镜像（等同 `docker compose down --rmi local`）
- `./tgo.sh tools start`：启动调试工具（kafka-ui、adminer）
- `./tgo.sh tools stop`：停止调试工具
- `./tgo.sh build <service>`：重建并重启指定服务（api|rag|ai|platform|web|widget|all）

## 目录结构与持久化数据
- `docker-compose.yml`：服务编排
- `envs.docker/`：服务环境变量模板（首次会复制为 `envs/`）
- `envs/`：运行时服务环境。已被 `.gitignore` 忽略
- `repos/`：各子项目源码（本仓库默认已存在/自行放置；`.gitignore` 忽略）
- `data/`：统一的持久化数据目录（`.gitignore` 忽略）
  - `data/postgres` → /var/lib/postgresql/data
  - `data/redis` → /data
  - `data/kafka/data` → /var/lib/kafka/data
  - `data/wukongim` → /root/wukongim
  - `data/tgo-rag/uploads` → /app/uploads

## 配置说明与覆盖规则
- 全局配置：根目录 `.env`
  - 数据库 DSN：`DATABASE_URL`、`TGO_PG_DSN`
  - 端口：`API_PORT`、`AI_PORT`、`PLATFORM_PORT`、`RAG_PORT`、`WEB_PORT` 等
  - API 基础地址：`API_BASE_URL`（默认见 `.env.example`）
- 服务专属配置：`envs/<service>.env`
  - 仅放与该服务强相关的配置
- env_file 加载顺序与覆盖：
  - tgo-api：先加载 `envs/tgo-api.env`，再加载 `.env` → 允许用根目录 `.env` 覆盖 `API_BASE_URL`
  - 其他服务：先加载 `.env`，再加载 `envs/<service>.env` → 服务专属 env 可覆盖全局配置

## 访问入口（默认端口）
- API: http://localhost:8000
- AI: http://localhost:8002
- Platform: http://localhost:8003
- RAG: http://localhost:8082
- Web: http://localhost:3000
- Widget: http://localhost:3001
- Adminer: http://localhost:8888
- Kafka UI: http://localhost:8088
- WuKongIM: 5001(HTTP) / 5100(TCP) / 5200(WS) / 5300(Admin) / 5172(Demo) / 11110(Cluster)

## 常用命令
- 查看状态：`docker compose ps`
- 查看日志：`docker compose logs -f tgo-api`（替换为具体服务名）
- 停止：`docker compose down`
- 重新构建：`docker compose build --no-cache <service>`
- 清理数据（危险）：`docker compose down -v` 然后手动删除 `data/`

## 故障排查
- 子项目是否存在：`repos/` 下应包含 `tgo-api`、`tgo-ai`、`tgo-platform`、`tgo-rag`、`tgo-web`、`tgo-widget-app`
- 端口冲突：如被占用，请修改 `.env` 中相应端口后重启
- 权限问题：确保当前用户对 `data/` 具有读写权限
- 构建失败：检查对应子项目 Dockerfile 是否存在且可用

## 一键远程部署（bootstrap.sh）

适用场景：在一台干净机器上一条命令完成检查、克隆并运行 deploy.sh。
脚本行为概览：
- 检查 git、docker、docker compose
- 如当前目录已存在 deploy.sh 和 docker-compose.yml，直接运行 deploy.sh
- 否则克隆 REPO 到 DIR（默认 https://github.com/tgoai/tgo.git → ./tgo），可选切换到 REF（分支/Tag/提交）
- 在 DIR 中执行 deploy.sh

推荐用法（GitHub Raw 示例）：
- 最新主分支：`curl -fsSL https://raw.githubusercontent.com/tgoai/tgo/main/bootstrap.sh | bash`
- 指定版本/分支：`REF=v1.0.0 curl -fsSL https://raw.githubusercontent.com/tgoai/tgo/main/bootstrap.sh | bash`
- 自定义仓库/目录：`REPO=https://gitee.com/your/tgo.git DIR=tgo curl -fsSL https://raw.githubusercontent.com/tgoai/tgo/main/bootstrap.sh | bash`

通过 SSH 在远程服务器一键执行：
- `ssh user@server 'curl -fsSL https://raw.githubusercontent.com/tgoai/tgo/main/bootstrap.sh | bash'`
- 指定版本：`ssh user@server 'REF=v1.0.0 curl -fsSL https://raw.githubusercontent.com/tgoai/tgo/main/bootstrap.sh | bash'`

本地运行（已在仓库内）：
- `bash ./bootstrap.sh`

可配置项（环境变量）：
- REPO：仓库地址（默认 https://github.com/tgoai/tgo.git）
- DIR：克隆目录名（默认 tgo）
- REF：可选分支/Tag/提交（为空则使用默认分支）

注意：如果你将 bootstrap.sh 托管到自有域名，请把上述 URL 替换为你的地址即可。
