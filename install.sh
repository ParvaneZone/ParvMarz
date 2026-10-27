#!/usr/bin/env bash
# ParvMarz one-line installer:
#   bash <(curl -fsSL https://raw.githubusercontent.com/ParvaneZone/ParvMarz/main/install.sh)
# Commands: install (default) | update | status | logs | uninstall
set -euo pipefail

REPO="${PARVMARZ_REPO:-https://github.com/ParvaneZone/ParvMarz.git}"
BRANCH="${PARVMARZ_BRANCH:-main}"
DIR="${PARVMARZ_DIR:-/opt/parvmarz}"
CMD="${1:-install}"

say() { printf '\033[1;32m==>\033[0m %s\n' "$*"; }
die() { printf '\033[1;31mERROR:\033[0m %s\n' "$*" >&2; exit 1; }
[ "$(id -u)" -eq 0 ] || die "Run as root (sudo -i)."

ask() { # ask VAR "prompt" default
  local var="$1" prompt="$2" def="$3" val=""
  if [ -n "${!var:-}" ]; then return; fi
  if [ -r /dev/tty ]; then read -r -p "$prompt [$def]: " val < /dev/tty || true; fi
  printf -v "$var" '%s' "${val:-$def}"
}
rnd() { openssl rand -hex "$1"; }
dc() { (cd "$DIR" && docker compose "$@"); }

ensure_deps() {
  command -v git >/dev/null || { say "Installing git"; (apt-get update -qq && apt-get install -y -qq git) || yum install -y git; }
  command -v openssl >/dev/null || { (apt-get install -y -qq openssl) || yum install -y openssl; }
  command -v curl >/dev/null || { (apt-get install -y -qq curl) || yum install -y curl; }
  if ! command -v docker >/dev/null; then say "Installing Docker"; curl -fsSL https://get.docker.com | sh; fi
  docker compose version >/dev/null 2>&1 || die "Docker Compose plugin missing (install docker-compose-plugin)."
  systemctl enable --now docker >/dev/null 2>&1 || true
}

fetch_code() {
  if [ -d "$DIR/.git" ]; then
    say "Updating source"; git -C "$DIR" fetch -q origin "$BRANCH" && git -C "$DIR" reset -q --hard "origin/$BRANCH"
  else
    say "Downloading source to $DIR"; git clone -q --depth 1 -b "$BRANCH" "$REPO" "$DIR"
  fi
}

write_env() {
  if [ -f "$DIR/.env" ]; then say "Keeping existing $DIR/.env"; return; fi
  ask ADMIN_USER "Admin username" "admin"
  ask ADMIN_PASS "Admin password (empty = random)" ""
  [ -n "$ADMIN_PASS" ] || ADMIN_PASS="$(rnd 8)"
  ask PORT "Port" "8000"
  ask PUBLIC_URL "Public URL (e.g. https://sub.example.com, empty = http://SERVER_IP:$PORT)" ""
  if [ -z "$PUBLIC_URL" ]; then
    ip="$(curl -fsS4 --max-time 5 https://api.ipify.org 2>/dev/null || hostname -I | awk '{print $1}')"
    PUBLIC_URL="http://$ip:$PORT"
  fi
  fernet="$(openssl rand -base64 32 | tr '+/' '-_' | tr -d '\n')"
  cat > "$DIR/.env" <<ENV
APP_NAME=ParvMarz
ENVIRONMENT=production
DATABASE_URL=sqlite:///./data/subhub.db
JWT_SECRET=$(rnd 32)
JWT_EXPIRE_MINUTES=60
SUBSCRIPTION_HMAC_KEY=$(rnd 32)
CREDENTIALS_ENCRYPTION_KEY=$fernet
PUBLIC_BASE_URL=$PUBLIC_URL
CORS_ORIGINS=$PUBLIC_URL
OPENAPI_ENABLED=false
PANEL_ALLOW_PRIVATE_ADDRESSES=false
SYNC_INTERVAL_SECONDS=60
LOG_LEVEL=INFO
INITIAL_ADMIN_USERNAME=$ADMIN_USER
INITIAL_ADMIN_PASSWORD=$ADMIN_PASS
PORT=$PORT
ENV
  chmod 600 "$DIR/.env"
  say "Admin: $ADMIN_USER / $ADMIN_PASS   (save it; also in $DIR/.env)"
}

link_menu() { chmod +x "$DIR/parvmarz.sh" "$DIR/docker-entrypoint.sh" 2>/dev/null; ln -sf "$DIR/parvmarz.sh" /usr/local/bin/parvmarz; }

case "$CMD" in
  install)
    ensure_deps; fetch_code; link_menu; write_env
    say "Building and starting (first build takes a few minutes)"
    dc up -d --build
    . "$DIR/.env"
    say "Done. Dashboard: ${PUBLIC_BASE_URL}/dashboard/"
    echo "Menu: run  parvmarz"
    echo "Put HTTPS in front (deploy/Caddyfile.example) and remove INITIAL_ADMIN_PASSWORD from .env after first login."
    ;;
  menu) exec "$DIR/parvmarz.sh" ;;
  update) ensure_deps; fetch_code; link_menu; dc up -d --build; say "Updated." ;;
  status) dc ps ;;
  logs) dc logs -f --tail=100 ;;
  uninstall)
    read -r -p "Remove containers AND data volume? type yes: " a < /dev/tty
    [ "$a" = yes ] && { dc down -v; rm -rf "$DIR"; say "Removed."; } ;;
  *) die "Unknown command: $CMD" ;;
esac
