# Database Setup Guide

This guide covers database initialization, migrations, and common operations for the tgo-platform project.

## Quick Start

### 1. Start Docker Services

```bash
make dev
```

This will:
- Start PostgreSQL container (exposed on port 5442)
- Wait for PostgreSQL to be healthy
- Start the FastAPI development server

The PostgreSQL container is automatically configured with:
- **Database**: `tgo`
- **User**: `tgo_user`
- **Password**: `tgo_pass`
- **Port**: `5442` (mapped from internal 5432)

### 2. Run Database Migrations

```bash
# Generate initial migration (only needed once or when models change)
make migrate-rev

# Apply migrations to create tables
make migrate-upgrade
```

### 3. Verify Database Setup

```bash
make db-verify
```

You should see the `pt_platforms` table listed.

### 4. (Optional) Seed Sample Data

```bash
make db-seed
```

This creates a sample email platform for testing. Edit `scripts/seed_email_platform.sql` to customize the IMAP credentials.

## Database Connection Details

### From Host Machine (for migrations, scripts)
```
postgresql+asyncpg://tgo_user:tgo_pass@127.0.0.1:5442/tgo
```

### From Docker Network (for containerized apps)
```
postgresql+asyncpg://tgo_user:tgo_pass@postgres:5432/tgo
```

**Important**: The tgo-platform app runs on the host machine, so it uses `127.0.0.1:5442`.

## Available Make Targets

### Database Operations

- **`make db-verify`** - Verify database connection and list tables
- **`make db-shell`** - Open interactive psql shell
- **`make db-seed`** - Seed database with sample email platform
- **`make db-reset`** - Drop and recreate database (⚠️ destroys all data)
- **`make db-init`** - Create tables directly using SQLAlchemy (alternative to migrations)

### Migration Operations

- **`make migrate-rev`** - Generate new migration from model changes (autogenerate)
- **`make migrate-upgrade`** - Apply pending migrations
- **`make migrate-downgrade`** - Revert last migration

## Database Schema

### `pt_platforms` Table

Stores platform configurations for multi-channel message routing.

| Column       | Type                     | Description                                    |
|--------------|--------------------------|------------------------------------------------|
| `id`         | UUID                     | Primary key                                    |
| `project_id` | UUID                     | Project identifier (indexed)                   |
| `name`       | VARCHAR(100)             | Platform display name                          |
| `type`       | VARCHAR(20)              | Platform type (e.g., 'email', 'wechat')        |
| `config`     | JSONB                    | Platform-specific configuration                |
| `is_active`  | BOOLEAN                  | Whether platform is active (default: true)     |
| `created_at` | TIMESTAMP WITH TIME ZONE | Creation timestamp (default: now())            |
| `updated_at` | TIMESTAMP WITH TIME ZONE | Last update timestamp (auto-updated)           |
| `deleted_at` | TIMESTAMP WITH TIME ZONE | Soft delete timestamp (NULL if not deleted)    |
| `api_key`    | VARCHAR(255)             | Optional API key for platform authentication   |

### Email Platform Configuration

For `type = 'email'`, the `config` JSONB field contains **IMAP-only** credentials for inbound email fetching:

```json
{
  "imap_host": "imap.gmail.com",
  "imap_port": 993,
  "imap_username": "support@example.com",
  "imap_password": "app-password-here",
  "imap_use_ssl": true,
  "mailbox": "INBOX",
  "poll_interval_seconds": 60
}
```

**Note**: Outbound SMTP is configured globally via environment variables (see below).

## Global SMTP Configuration

Outbound email sending uses a **single global SMTP account** configured via environment variables:

```bash
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=no-reply@example.com
SMTP_PASSWORD=app-password-here
SMTP_USE_TLS=true
SMTP_FROM_ADDRESS=no-reply@example.com
```

Set these in your `.env` file (copy from `.env.example`).

## Common Tasks

### Add a New Email Platform

```sql
INSERT INTO pt_platforms (id, project_id, name, type, config, is_active)
VALUES (
  gen_random_uuid(),
  'your-project-uuid-here'::uuid,
  'Customer Support',
  'email',
  '{
     "imap_host": "imap.gmail.com",
     "imap_port": 993,
     "imap_username": "support@example.com",
     "imap_password": "your-app-password",
     "imap_use_ssl": true,
     "mailbox": "INBOX",
     "poll_interval_seconds": 60
   }'::jsonb,
  true
);
```

Run via:
```bash
make db-shell
# Then paste the SQL above
```

### Update Platform Configuration

```sql
UPDATE pt_platforms
SET config = jsonb_set(config, '{poll_interval_seconds}', '120')
WHERE name = 'Customer Support';
```

### Disable a Platform (Soft Delete)

```sql
UPDATE pt_platforms
SET is_active = false, deleted_at = now()
WHERE name = 'Customer Support';
```

### View Active Email Platforms

```sql
SELECT id, project_id, name, config->>'imap_username' as email, is_active
FROM pt_platforms
WHERE type = 'email' AND is_active = true AND deleted_at IS NULL;
```

## Troubleshooting

### "role tgo_user does not exist"

**Cause**: PostgreSQL role not created (should be automatic with Docker Compose).

**Solution**: Restart Docker services:
```bash
make dev-down
make dev
```

### "Connection refused" or "port 5432"

**Cause**: Using wrong port. Docker exposes PostgreSQL on **5442**, not 5432.

**Solution**: Update `.env`:
```bash
PG_DSN=postgresql+asyncpg://tgo_user:tgo_pass@127.0.0.1:5442/tgo
```

### "No module named 'app'" during migrations

**Cause**: Python path not set correctly.

**Solution**: Use the Makefile targets (they set `PYTHONPATH=.` automatically):
```bash
make migrate-rev
make migrate-upgrade
```

### Reset Database Completely

```bash
make db-reset
make migrate-upgrade
make db-seed
```

## Alembic Migration Workflow

### 1. Modify Models

Edit `app/db/models.py` to add/change tables or columns.

### 2. Generate Migration

```bash
make migrate-rev
```

Alembic will autogenerate a migration file in `migrations/versions/`.

### 3. Review Migration

Check the generated file in `migrations/versions/` to ensure it's correct.

### 4. Apply Migration

```bash
make migrate-upgrade
```

### 5. Rollback (if needed)

```bash
make migrate-downgrade
```

## Database Administration UI

The Docker Compose setup includes **Adminer** for database administration:

- **URL**: http://localhost:8889
- **System**: PostgreSQL
- **Server**: postgres
- **Username**: tgo_user
- **Password**: tgo_pass
- **Database**: tgo

## Production Considerations

1. **Environment Variables**: Never commit real credentials to `.env`. Use secrets management.
2. **Migrations**: Always review autogenerated migrations before applying to production.
3. **Backups**: Implement regular database backups before running migrations.
4. **Connection Pooling**: SQLAlchemy async engine uses connection pooling by default.
5. **Indexes**: The `project_id` column is indexed for efficient multi-tenant queries.

## References

- [SQLAlchemy 2.0 Documentation](https://docs.sqlalchemy.org/en/20/)
- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [PostgreSQL JSONB Documentation](https://www.postgresql.org/docs/current/datatype-json.html)

