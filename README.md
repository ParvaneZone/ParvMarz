# ParvMarz

Central subscription aggregation panel: connect Marzban, Marzdar, Marzyar, PasarGuard and Rebecca reseller/admin accounts, build services from them, and give users one standard subscription link.

> Development build — verify drivers against your real panels before production. Details and limits: [README-fa.md](README-fa.md).

## Quick install (Ubuntu/Debian, as root)

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/ParvaneZone/ParvMarz/main/install.sh)
```

It installs Docker if needed, asks for admin username/password/port (or generates them), creates strong random secrets, then builds and starts the panel. Open `http://SERVER_IP:8000/dashboard/`.

Non-interactive:

```bash
ADMIN_USER=admin ADMIN_PASS='StrongPass' PORT=8000 PUBLIC_URL=https://sub.example.com \
  bash <(curl -fsSL https://raw.githubusercontent.com/ParvaneZone/ParvMarz/main/install.sh)
```

Manage:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/ParvaneZone/ParvMarz/main/install.sh) update
cd /opt/parvmarz && docker compose logs -f      # logs
cd /opt/parvmarz && docker compose ps           # status
```

Use HTTPS in production: see `deploy/Caddyfile.example` / `deploy/nginx.conf.example`.

## Docker only (no python/openssl needed on host)

```bash
docker compose up -d --build        # secrets are auto-generated on first start
docker compose exec subhub cat /app/data/initial-admin.txt   # admin login (never logged)
docker compose exec subhub python -m cli reset-admin-password --username admin
```

Set `PORT=8080` in `.env` if 8000 is taken; set `PUBLIC_BASE_URL` to your real URL. Slow network: `NPM_REGISTRY=https://registry.npmmirror.com`. Login lock: 5 failures per IP+username = 15 min (in memory; `docker compose restart subhub` clears it; `LOGIN_RATE_LIMIT_ENABLED=false` for tests). Auth uses bearer tokens (no cookies), so plain HTTP works, but use HTTPS in production. Changing `INITIAL_ADMIN_PASSWORD` after the first start has no effect; use the reset command.

## Terminal menu

`parvmarz` (installed by install.sh; or `bash parvmarz.sh` inside the project dir) opens a menu: status, logs, start/stop/restart, update, edit `.env`, change port/URL, reset admin password, show generated admin login, clear login lock, backup, rebuild, uninstall.

## Panel credentials

| Panel | Credential |
|---|---|
| Marzban / Marzdar / Marzyar | reseller username + password |
| PasarGuard | username + password, or API key `pg_key_...` as password |
| Rebecca | API key `rk_...` as password (username anything) |
