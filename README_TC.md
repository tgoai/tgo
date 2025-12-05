<p align="center">
  <img src="resources/readme-banner.svg" width="100%" alt="組建智能體團隊為客戶服務">
</p>

<p align="center">
  <a href="./README.md">English</a> | <a href="./README_CN.md">简体中文</a> | <a href="./README_TC.md">繁體中文</a> | <a href="./README_JP.md">日本語</a> | <a href="./README_RU.md">Русский</a>
</p>

<p align="center">
  <a href="https://tgo.ai">官網</a> | <a href="https://docs.tgo.ai">文檔</a>
</p>

## TGO 介紹

TGO 是一個開源的 AI 智能體客服平台，致力於幫助企業「組建智能體團隊為客戶服務」。它集成了多渠道接入、智能體編排、知識庫管理（RAG）、人工坐席協作等核心功能。

<img src="resources/screenshot/zh/home_dark.png" width="100%">

## 產品預覽

| | |
|:---:|:---:|
| **首頁** <br> <img src="resources/screenshot/zh/home_dark.png" width="100%"> | **智能體編排** <br> <img src="resources/screenshot/zh/agent_dark.png" width="100%"> |
| **知識庫管理** <br> <img src="resources/screenshot/zh/knowledge_dark.png" width="100%"> | **問答調試** <br> <img src="resources/screenshot/zh/knowledge_qa_dark.png" width="100%"> |
| **MCP 工具** <br> <img src="resources/screenshot/zh/mcp_dark.png" width="100%"> | **平台管理** <br> <img src="resources/screenshot/zh/platform_dark.png" width="100%"> |

## 🚀 快速開始 (Quick Start)

### 機器配置要求
- **CPU**: >= 2 Core
- **RAM**: >= 4 GiB
- **OS**: macOS / Linux / WSL2

### 一鍵部署

在服務器上運行以下命令即可完成檢查、克隆並啟動服務：

```bash
REF=latest curl -fsSL https://raw.githubusercontent.com/tgoai/tgo/main/bootstrap.sh | bash
```

> **中國境內用戶推薦使用國內加速版**（使用 Gitee 和阿里雲鏡像）：
> ```bash
> REF=latest curl -fsSL https://gitee.com/tgoai/tgo/raw/main/bootstrap_cn.sh | bash
> ```

---

更多詳細信息請參閱 [文檔](https://docs.tgo.ai)。
