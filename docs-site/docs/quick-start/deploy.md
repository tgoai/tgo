---
id: deploy
title: 一键部署
sidebar_position: 1
---

# 一键部署

本页介绍如何使用一键部署脚本快速安装 TGO。

## 海外网络（GitHub）

在目标服务器上直接执行：

```bash
REF=latest curl -fsSL https://raw.githubusercontent.com/tgoai/tgo/main/bootstrap.sh | bash
```

## 中国大陆网络（Gitee + 阿里云镜像）

如果在中国境内部署，推荐使用国内加速版：

```bash
REF=latest curl -fsSL https://gitee.com/tgoai/tgo/raw/main/bootstrap_cn.sh | bash
```

## 版本说明

`REF` 环境变量用于指定要部署的版本：

- `REF=latest`：使用仓库默认分支的当前最新版本
- 也可以改为具体 Tag/分支/提交号，例如 `REF=v1.0.0`

## 端口配置

TGO 默认使用以下端口：

| 端口 | 用途 |
|------|------|
| **80** | HTTP 访问 |
| **443** | HTTPS 访问 |

如果端口被占用，安装脚本会自动分配其他可用端口（如 8080、8443）。

## 安装完成后如何访问

安装完成后，可以通过以下方式访问：

- **本机浏览器**：`http://localhost`
- **远程访问**：`http://<服务器IP>` 或配置好的域名

如果端口被修改，记得在 URL 中加上端口号，例如 `http://<服务器IP>:8080`

## 下一步

- [常见问题](/quick-start/faq) - 安装过程中遇到问题？
- [配置域名和证书](/config/domain-ssl) - 设置域名和 HTTPS
- [环境变量](/config/env-vars) - 自定义配置
