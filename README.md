<p align="center">
  <img src="resources/readme-banner-en.svg" width="100%" alt="Build AI Agent Teams for Customer Service">
</p>

<p align="center">
  <a href="./README.md">English</a> | <a href="./README_CN.md">简体中文</a> | <a href="./README_TC.md">繁體中文</a> | <a href="./README_JP.md">日本語</a> | <a href="./README_RU.md">Русский</a>
</p>

<p align="center">
  <a href="https://tgo.ai">Website</a> | <a href="https://docs.tgo.ai">Documentation</a>
</p>

## TGO Introduction

TGO is an open-source AI agent customer service platform dedicated to helping enterprises "Build AI Agent Teams for Customer Service". It integrates multi-channel access, agent orchestration, knowledge base management (RAG), and human agent collaboration.

<img src="resources/screenshot/en/home_dark.png" width="100%">

## ✨ Features

### 🤖 AI Agent Orchestration
- **Multi-Agent Support** - Configure multiple AI agents for different business scenarios
- **Multi-Model Integration** - Connect with various LLM providers (OpenAI, Anthropic, etc.)
- **Streaming Response** - Real-time AI responses via SSE for smooth conversation experience
- **Context Memory** - Maintain conversation history for coherent dialogue

### 📚 Knowledge Base (RAG)
- **Document Knowledge Base** - Upload documents to enhance AI response accuracy
- **Q&A Knowledge Base** - Create question-answer pairs for quick knowledge expansion
- **Website Knowledge Base** - Crawl website content to keep information up-to-date
- **Smart Retrieval** - Vector-based semantic search for precise answers

### 🔧 MCP Tools Integration
- **Tool Store** - Rich library of MCP tools, enable on demand
- **Custom Tools** - Project-level tool configuration and management
- **OpenAPI Schema** - Auto-parse schemas to generate interactive forms

### 🌐 Multi-Channel Access
- **Web Widget** - Embeddable chat widget for websites
- **WeChat Integration** - Official Account and Mini Program support
- **Unified Management** - Manage all channels from a single dashboard

### 💬 Real-time Communication
- **WuKongIM Integration** - Stable and reliable instant messaging
- **WebSocket Connection** - Efficient bidirectional communication
- **Message Sync** - Read/unread status, delivery confirmation
- **Rich Media** - Support for text, images, files and more

### 👥 Human-AI Collaboration
- **Smart Handoff** - Seamlessly transfer to human agents when needed
- **Visitor Management** - Collect visitor info, assign sessions, track history
- **Agent Workspace** - Unified interface for human agents

### 🎨 UI Widget System
- **Structured Display** - Render orders, products, logistics as beautiful cards
- **Rich Components** - Order cards, logistics tracking, product display, price comparison
- **Action Protocol** - Standardized URI protocol for interactions

## Product Preview

| | |
|:---:|:---:|
| **Dashboard** <br> <img src="resources/screenshot/en/home_dark.png" width="100%"> | **Agent Orchestration** <br> <img src="resources/screenshot/en/agent_dark.png" width="100%"> |
| **Knowledge Base** <br> <img src="resources/screenshot/en/knowledge_dark.png" width="100%"> | **Q&A Debugging** <br> <img src="resources/screenshot/en/knowledge_qa_dark.png" width="100%"> |
| **MCP Tools** <br> <img src="resources/screenshot/en/mcp_dark.png" width="100%"> | **Platform Admin** <br> <img src="resources/screenshot/en/platform_dark.png" width="100%"> |

## 🚀 Quick Start

### System Requirements
- **CPU**: >= 2 Core
- **RAM**: >= 4 GiB
- **OS**: macOS / Linux / WSL2

### One-Click Deployment

Run the following command on your server to check requirements, clone the repository, and start the services:

```bash
REF=latest curl -fsSL https://raw.githubusercontent.com/tgoai/tgo/main/bootstrap.sh | bash
```

> **For users in China** (using Gitee and Aliyun mirrors):
> ```bash
> REF=latest curl -fsSL https://gitee.com/tgoai/tgo/raw/main/bootstrap_cn.sh | bash
> ```

---

For more details, please visit the [Documentation](https://docs.tgo.ai).
