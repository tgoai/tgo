---
id: deploy
title: Quick Deploy
sidebar_position: 1
---

# Quick Deploy

This page explains how to quickly install TGO using the one-click deployment script.

## International (GitHub)

Run the following command on your server:

```bash
REF=latest curl -fsSL https://raw.githubusercontent.com/tgoai/tgo/main/bootstrap.sh | bash
```

## China Mainland (Gitee + Alibaba Cloud Mirror)

For deployment within China, we recommend using the accelerated version:

```bash
REF=latest curl -fsSL https://gitee.com/tgoai/tgo/raw/main/bootstrap_cn.sh | bash
```

## Version Selection

The `REF` environment variable specifies the version to deploy:

- `REF=latest`: Use the latest version from the default branch
- Can also be a specific Tag/branch/commit, e.g., `REF=v1.0.0`

## Port Configuration

TGO uses the following default ports:

| Port | Purpose |
|------|---------|
| **80** | HTTP access |
| **443** | HTTPS access |

If ports are occupied, the installation script will automatically assign available ports (e.g., 8080, 8443).

## Access After Installation

After installation, you can access TGO via:

- **Local browser**: `http://localhost`
- **Remote access**: `http://<server-ip>` or your configured domain

If ports were changed, remember to include the port number, e.g., `http://<server-ip>:8080`

## Next Steps

- [FAQ](/quick-start/faq) - Having issues during installation?
- [Domain and SSL](/config/domain-ssl) - Configure domain and HTTPS
- [Environment Variables](/config/env-vars) - Custom configuration
