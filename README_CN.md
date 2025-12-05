<p align="center">
  <img src="resources/readme-banner.svg" width="100%" alt="组建智能体团队为客户服务">
</p>

<p align="center">
  <a href="./README.md">English</a> | <a href="./README_CN.md">简体中文</a> | <a href="./README_TC.md">繁體中文</a> | <a href="./README_JP.md">日本語</a> | <a href="./README_RU.md">Русский</a>
</p>

<p align="center">
  <a href="https://tgo.ai">官网</a> | <a href="https://docs.tgo.ai">文档</a>
</p>

## TGO 介绍

TGO 是一个开源的 AI 智能体客服平台，致力于帮助企业“组建智能体团队为客户服务”。它集成了多渠道接入、智能体编排、知识库管理（RAG）、人工坐席协作等核心功能。

<img src="resources/screenshot/zh/home_dark.png" width="100%">

## 产品预览

| | |
|:---:|:---:|
| **首页** <br> <img src="resources/screenshot/zh/home_dark.png" width="100%"> | **智能体编排** <br> <img src="resources/screenshot/zh/agent_dark.png" width="100%"> |
| **知识库管理** <br> <img src="resources/screenshot/zh/knowledge_dark.png" width="100%"> | **问答调试** <br> <img src="resources/screenshot/zh/knowledge_qa_dark.png" width="100%"> |
| **MCP 工具** <br> <img src="resources/screenshot/zh/mcp_dark.png" width="100%"> | **平台管理** <br> <img src="resources/screenshot/zh/platform_dark.png" width="100%"> |

## 🚀 快速开始 (Quick Start)

### 机器配置要求
- **CPU**: >= 2 Core
- **RAM**: >= 4 GiB
- **OS**: macOS / Linux / WSL2

### 一键部署

在服务器上运行以下命令即可完成检查、克隆并启动服务：

```bash
REF=latest curl -fsSL https://raw.githubusercontent.com/tgoai/tgo/main/bootstrap.sh | bash
```

> **中国境内用户推荐使用国内加速版**（使用 Gitee 和阿里云镜像）：
> ```bash
> REF=latest curl -fsSL https://gitee.com/tgoai/tgo/raw/main/bootstrap_cn.sh | bash
> ```

---

更多详细信息请参阅 [文档](https://docs.tgo.ai)。
