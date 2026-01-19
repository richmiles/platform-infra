# Platform Infrastructure

Shared infrastructure for SparkSwarm projects. Manages Docker Compose services, Caddy reverse proxy, and Postgres database on a single DigitalOcean droplet.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Platform Droplet                         │
│                                                             │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐  │
│  │  Caddy  │───▶│  IEOMD  │    │  Umami  │    │ Postgres│  │
│  │  :80    │    │  :8000  │    │  :3000  │    │  :5432  │  │
│  │  :443   │───▶│         │    │         │    │         │  │
│  └─────────┘    └─────────┘    └─────────┘    └─────────┘  │
│       │                             │              │        │
│       │         internal network    └──────────────┘        │
└───────┼─────────────────────────────────────────────────────┘
        │
   internet
```

## Services

| Service | Domain | Description |
|---------|--------|-------------|
| Caddy | - | Reverse proxy with automatic HTTPS |
| Postgres | - | Shared database (internal only) |
| IEOMD | ieomd.com | Time-locked secret delivery |
| Umami | analytics.sparkswarm.com | Privacy-focused analytics |

## Quick Start

### 1. Clone to server

```bash
git clone git@github.com:richmiles/platform-infra.git
cd platform-infra
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your values
```

### 3. Start services

```bash
docker compose up -d
```

### 4. View logs

```bash
docker compose logs -f
```

## Initial Server Setup

For a fresh droplet, run the setup script:

```bash
curl -fsSL https://raw.githubusercontent.com/richmiles/platform-infra/main/setup.sh | bash
```

Or manually:

```bash
# Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Install fail2ban
sudo apt update && sudo apt install -y fail2ban

# Configure firewall
sudo ufw allow 22
sudo ufw allow 80
sudo ufw allow 443
sudo ufw enable
```

## Adding a New Service

1. Add service to `docker-compose.yml`
2. Add domain routing to `Caddyfile`
3. Add any new env vars to `.env.example`
4. Deploy:
   ```bash
   docker compose up -d
   ```

## Database Access

Connect to Postgres:

```bash
docker compose exec postgres psql -U postgres
```

Create a new database for a service:

```sql
CREATE USER myapp WITH PASSWORD 'secure-password';
CREATE DATABASE myapp_db OWNER myapp;
GRANT ALL PRIVILEGES ON DATABASE myapp_db TO myapp;
```

## Useful Commands

```bash
# Restart a single service
docker compose restart ieomd

# View service logs
docker compose logs -f caddy

# Pull latest images and restart
docker compose pull && docker compose up -d

# Check service status
docker compose ps

# Reload Caddy config (no downtime)
docker compose exec caddy caddy reload --config /etc/caddy/Caddyfile
```

## Backups

Postgres data is stored in a Docker volume. To backup:

```bash
docker compose exec postgres pg_dumpall -U postgres > backup.sql
```

To restore:

```bash
cat backup.sql | docker compose exec -T postgres psql -U postgres
```

## Directory Structure

```
platform-infra/
├── docker-compose.yml  # Service definitions
├── Caddyfile           # Reverse proxy config
├── .env.example        # Environment template
├── .env                # Local environment (git-ignored)
├── setup.sh            # Server bootstrap script
└── README.md           # This file
```
