---
id: intro
title: 介绍
sidebar_position: 1
---

# TGO 介绍

TGO 是一个开源的 AI 智能体客服平台，致力于帮助企业「组建智能体团队为客户服务」。

## 核心功能

- **多智能体编排**：支持创建和管理多个 AI 智能体，协同处理客户咨询
- **知识库管理（RAG）**：内置 RAG 系统，支持文档、网页等多种知识源
- **MCP 工具集成**：支持 Model Context Protocol，扩展智能体能力
- **多渠道接入**：支持网页嵌入、API 等多种接入方式
- **人工坐席协作**：智能体与人工坐席无缝切换

## 系统要求

部署 TGO 需要满足以下最低配置：

| 项目 | 最低要求 |
|------|----------|
| **CPU** | >= 2 Core |
| **内存** | >= 4 GiB |
| **操作系统** | macOS / Linux / WSL2 |
| **Docker** | Docker Engine 20.10+ |
| **Docker Compose** | v2.0+ |

## 技术架构

TGO 采用微服务架构，主要包含以下核心服务：

| 服务 | 说明 |
|------|------|
| **tgo-api** | 后端 API 服务，处理业务逻辑 |
| **tgo-ai** | AI 推理服务，负责智能体对话 |
| **tgo-rag** | RAG 服务，处理知识库检索 |
| **tgo-platform** | 平台管理服务 |
| **tgo-web** | Web 管理控制台 |
| **tgo-widget** | 可嵌入的客服组件 |

## 下一步

- [一键部署](/quick-start/deploy) - 快速在服务器上部署 TGO
- [环境变量](/config/env-vars) - 了解如何配置系统
- [源码部署](/development/source-deploy) - 从源码构建和部署
