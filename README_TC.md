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

## ✨ 核心特性

### 🤖 AI 智能體編排
- **多智能體支援** - 支援配置多個 AI 智能體，可根據業務場景選擇不同的 Agent
- **多模型集成** - 支援接入多種大模型提供商（OpenAI、Anthropic 等）
- **串流響應** - 基於 SSE 的即時串流訊息傳輸，即時展示 AI 回覆
- **上下文記憶** - 支援歷史對話記錄，AI 可基於上下文提供連貫的對話體驗

### 📚 知識庫管理 (RAG)
- **文檔知識庫** - 支援上傳文檔構建知識庫，增強 AI 回答準確性
- **QA 知識庫** - 問答對形式的知識管理，快速擴展 AI 知識
- **網站知識庫** - 抓取網站內容構建知識，保持資訊同步更新
- **智能檢索** - 基於向量的語意搜尋，精準匹配答案

### 🔧 MCP 工具集成
- **工具商店** - 豐富的 MCP 工具庫，按需啟用
- **自訂工具** - 支援專案級別的工具配置和管理
- **OpenAPI Schema** - 自動解析 Schema 生成互動表單

### 🌐 多渠道接入
- **Web 元件** - 可嵌入網站的聊天元件
- **微信集成** - 支援公眾號、小程式接入
- **統一管理** - 在同一後台管理所有接入渠道

### 💬 即時通訊
- **悟空 IM 集成** - 深度集成悟空 IM，提供穩定可靠的即時通訊能力
- **WebSocket 長連接** - 高效的雙向通訊，支援訊息即時推送
- **訊息狀態同步** - 已讀/未讀狀態、訊息送達確認
- **多媒體支援** - 支援文字、圖片、檔案等多種訊息類型

### 👥 人機協作
- **智能轉接** - 必要時無縫轉接人工客服
- **訪客管理** - 訪客資訊收集、會話分配、歷史記錄
- **坐席工作台** - 統一的人工客服操作介面

### 🎨 UI Widget 系統
- **結構化展示** - AI 回傳的訂單、商品、物流等資訊以精美卡片形式呈現
- **豐富元件** - 訂單卡片、物流追蹤、商品展示、價格對比等
- **互動協議** - 標準化的 Action URI 協議，支援連結跳轉、訊息發送、內容複製

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
