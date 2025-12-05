---
id: faq
title: FAQ
sidebar_position: 2
---

# Frequently Asked Questions

## Installation Issues

### Docker Not Installed or Version Too Low

**Problem**: Installation script reports Docker is not installed or version doesn't meet requirements.

**Solution**:

1. Install Docker:
   ```bash
   curl -fsSL https://get.docker.com | sh
   ```

2. Ensure Docker Compose V2 is available:
   ```bash
   docker compose version
   ```

3. Start Docker service:
   ```bash
   sudo systemctl start docker
   sudo systemctl enable docker
   ```

### Port Already in Use

**Problem**: Installation reports port 80 or 443 is occupied.

**Solution**:

The installation script will automatically detect port occupation and assign new ports (e.g., 8080, 8443). You can also manually modify the `.env` file:

```bash
NGINX_PORT=8080
NGINX_SSL_PORT=8443
```

Then restart services:

```bash
./tgo.sh down
./tgo.sh up
```

### Insufficient Memory

**Problem**: Containers fail to start, logs show OOM (Out of Memory).

**Solution**:

TGO requires at least 4GB of memory. Check available memory:

```bash
free -h
```

If memory is insufficient:
- Upgrade server configuration
- Stop unnecessary services

## Network Issues

### Slow Image Pull in China

**Problem**: Docker image pull is very slow or times out on servers in China.

**Solution**:

Use the China accelerated installation script:

```bash
REF=latest curl -fsSL https://gitee.com/tgoai/tgo/raw/main/bootstrap_cn.sh | bash
```

### Cannot Access Service

**Problem**: Cannot access via browser after installation.

**Solution**:

1. Check service status:
   ```bash
   ./tgo.sh doctor
   ```

2. Check firewall settings:
   ```bash
   # Ubuntu/Debian
   sudo ufw allow 80/tcp
   sudo ufw allow 443/tcp
   
   # CentOS/RHEL
   sudo firewall-cmd --permanent --add-port=80/tcp
   sudo firewall-cmd --permanent --add-port=443/tcp
   sudo firewall-cmd --reload
   ```

3. For cloud servers, ensure ports are open in security groups.

## Service Issues

### Service Fails to Start

**Problem**: A service fails to start or keeps restarting.

**Solution**:

1. Check service logs:
   ```bash
   docker compose logs -f <service-name>
   ```

2. Check all service status:
   ```bash
   ./tgo.sh doctor
   ```

3. Try restarting all services:
   ```bash
   ./tgo.sh down
   ./tgo.sh up
   ```

### Database Connection Failed

**Problem**: API service reports unable to connect to database.

**Solution**:

1. Check PostgreSQL container status:
   ```bash
   docker compose ps postgres
   ```

2. View database logs:
   ```bash
   docker compose logs postgres
   ```

3. If database is corrupted, you may need to reinitialize (**Warning: data will be lost**):
   ```bash
   ./tgo.sh down --volumes
   ./tgo.sh install
   ```

## Getting Help

If the above solutions don't resolve your issue:

1. Export complete logs:
   ```bash
   docker compose logs > tgo-logs.txt
   ```

2. Submit an issue on [GitHub Issues](https://github.com/tgoai/tgo/issues) with:
   - OS version
   - Docker version
   - Error logs
   - Steps to reproduce
