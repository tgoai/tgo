---
id: source-deploy
title: 源码部署
sidebar_position: 1
---

# 源码部署

本页介绍如何从源代码构建和部署 TGO，适用于需要自定义修改或开发调试的场景。

## 与镜像部署的区别

| 部署方式 | 说明 | 适用场景 |
|----------|------|----------|
| **镜像部署**（默认） | 使用预构建的 Docker 镜像 | 生产环境、快速部署 |
| **源码部署** | 从本地源码构建镜像 | 开发调试、自定义修改 |

## 源码部署步骤

### 1. 克隆仓库

```bash
git clone https://github.com/tgoai/tgo.git
cd tgo
```

中国境内用户：

```bash
git clone https://gitee.com/tgoai/tgo.git
cd tgo
```

### 2. 执行源码安装

使用 `--source` 参数进行源码部署：

```bash
./tgo.sh install --source
```

## 源码目录结构

```
tgo/
└── repos/
    ├── tgo-api/        # 后端 API 服务
    ├── tgo-ai/         # AI 推理服务
    ├── tgo-rag/        # RAG 服务
    ├── tgo-platform/   # 平台管理服务
    ├── tgo-web/        # Web 控制台
    └── tgo-widget/     # Widget 组件
```

## 构建特定服务

如果只修改了某个服务，可以单独重新构建：

```bash
# 构建特定服务
./tgo.sh build api      # 构建 tgo-api
./tgo.sh build ai       # 构建 tgo-ai
./tgo.sh build rag      # 构建 tgo-rag
./tgo.sh build platform # 构建 tgo-platform
./tgo.sh build web      # 构建 tgo-web
./tgo.sh build widget   # 构建 tgo-widget

# 构建所有服务
./tgo.sh build all
```

构建完成后重启服务：

```bash
./tgo.sh down
./tgo.sh up --source
```

## 开发工作流

### 修改代码

1. 进入对应服务目录：
   ```bash
   cd repos/tgo-api
   ```

2. 修改代码

3. 重新构建并启动：
   ```bash
   cd ../..
   ./tgo.sh build api
   ./tgo.sh down
   ./tgo.sh up --source
   ```

### 查看日志

```bash
# 查看所有日志
docker compose logs -f

# 查看特定服务日志
docker compose logs -f tgo-api
```

### 进入容器调试

```bash
docker compose exec tgo-api bash
```

## 安装模式记忆

TGO 会记住你的安装模式，保存在 `./data/.tgo-install-mode` 文件中。

之后执行 `upgrade` 时会自动使用相同模式：

```bash
# 首次使用源码安装
./tgo.sh install --source

# 之后升级会自动使用 --source
./tgo.sh upgrade
```

如需临时切换模式，可以显式指定参数：

```bash
./tgo.sh upgrade --source  # 强制使用源码模式
```

## 切换到镜像部署

如果想从源码部署切换回镜像部署：

```bash
./tgo.sh down
./tgo.sh up  # 不加 --source 参数
```

## 注意事项

1. **首次构建时间较长**：源码构建需要下载依赖并编译，首次可能需要 10-30 分钟

2. **磁盘空间**：源码部署需要更多磁盘空间来存放源码和构建缓存

3. **网络要求**：构建过程需要下载依赖包，确保网络通畅

4. **分支同步**：如果更新了主仓库，记得同步子模块：
   ```bash
   git pull
   git submodule update --recursive
   ```
