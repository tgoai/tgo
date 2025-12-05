---
id: intro
title: Introduction
sidebar_position: 1
---

# Introduction to TGO

TGO is an open-source AI agent customer service platform, dedicated to helping enterprises "build agent teams to serve customers".

## Core Features

- **Multi-Agent Orchestration**: Create and manage multiple AI agents to collaboratively handle customer inquiries
- **Knowledge Base (RAG)**: Built-in RAG system supporting documents, web pages, and various knowledge sources
- **MCP Tool Integration**: Support for Model Context Protocol to extend agent capabilities
- **Multi-Channel Access**: Support for web embedding, API, and various access methods
- **Human Agent Collaboration**: Seamless switching between AI agents and human agents

## System Requirements

Deploying TGO requires the following minimum configuration:

| Item | Minimum Requirement |
|------|---------------------|
| **CPU** | >= 2 Core |
| **Memory** | >= 4 GiB |
| **OS** | macOS / Linux / WSL2 |
| **Docker** | Docker Engine 20.10+ |
| **Docker Compose** | v2.0+ |

## Architecture

TGO uses a microservices architecture with the following core services:

| Service | Description |
|---------|-------------|
| **tgo-api** | Backend API service for business logic |
| **tgo-ai** | AI inference service for agent conversations |
| **tgo-rag** | RAG service for knowledge base retrieval |
| **tgo-platform** | Platform management service |
| **tgo-web** | Web management console |
| **tgo-widget** | Embeddable customer service widget |

## Next Steps

- [Quick Deploy](/quick-start/deploy) - Deploy TGO on your server quickly
- [Environment Variables](/config/env-vars) - Learn how to configure the system
- [Source Deployment](/development/source-deploy) - Build and deploy from source
