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

## Panel credentials

| Panel | Credential |
|---|---|
| Marzban / Marzdar / Marzyar | reseller username + password |
| PasarGuard | username + password, or API key `pg_key_...` as password |
| Rebecca | API key `rk_...` as password (username anything) |
