#!/usr/bin/env bash
# ParvMarz terminal menu. Run: parvmarz   (installed by install.sh)
set -uo pipefail
export DOCKER_BUILDKIT=1 COMPOSE_DOCKER_CLI_BUILD=1
SELF="$(readlink -f "${BASH_SOURCE[0]}")"
DIR="${PARVMARZ_DIR:-$(dirname "$SELF")}"
cd "$DIR" || exit 1
command -v docker >/dev/null || { echo "Docker not found"; exit 1; }
dc() { docker compose "$@"; }
pause() { read -r -p "Enter to continue..." _ || true; }
get_env() { grep -E "^$1=" .env 2>/dev/null | tail -n1 | cut -d= -f2-; }
set_env() {
  [ -f .env ] || cp .env.example .env
  grep -v "^$1=" .env > .env.tmp || true
  # Docker Compose expands $ inside env_file values; single quotes keep them literal.
  case "$2" in *'$'*) printf "%s='%s'\n" "$1" "$2" >> .env.tmp;; *) printf '%s=%s\n' "$1" "$2" >> .env.tmp;; esac
  mv .env.tmp .env && chmod 600 .env
}
apply() { echo "Applying..."; dc up -d --build; }
ask() { local v; read -r -p "$1 [$2]: " v || true; printf '%s' "${v:-$2}"; }

edit_env() {
  [ -f .env ] || cp .env.example .env
  ${EDITOR:-$(command -v nano || command -v vi)} .env
  [ "$(ask 'Apply changes now (rebuild/restart)? y/n' y)" = y ] && apply
}
change_port() {
  p="$(ask 'New host port' "$(get_env PORT || echo 8000)")"
  [[ "$p" =~ ^[0-9]+$ ]] && [ "$p" -ge 1 ] && [ "$p" -le 65535 ] || { echo "Invalid port"; return; }
  set_env PORT "$p"; apply
}
change_url() {
  u="$(ask 'Public URL (http://IP:PORT or https://domain)' "$(get_env PUBLIC_BASE_URL)")"
  [ -n "$u" ] || { echo "Empty"; return; }
  set_env PUBLIC_BASE_URL "$u"; set_env CORS_ORIGINS "$u"; apply
}
update() { PARVMARZ_DIR="$DIR" bash "$DIR/install.sh" update; }
backup() {
  dc exec -T subhub python -m cli backup --directory /app/data/backups && \
  dc cp subhub:/app/data/backups ./backups && echo "Copied to $DIR/backups"
}
creds() { dc exec -T subhub cat /app/data/initial-admin.txt 2>/dev/null || echo "No generated credentials file (you set INITIAL_ADMIN_PASSWORD yourself, or use option: Reset admin password)."; }
reset_pw() { u="$(ask 'Admin username' admin)"; dc exec subhub python -m cli reset-admin-password --username "$u"; }
reset_2fa() { u="$(ask 'Admin username' admin)"; dc exec subhub python -m cli disable-2fa --username "$u"; }
uninstall() {
  [ "$(ask 'Remove containers AND data? type yes' no)" = yes ] && dc down -v && echo "Removed (source dir kept: $DIR)"
}

while true; do
  clear 2>/dev/null || true
  echo "=== ParvMarz menu ($DIR) ==="
  echo " 1) Status            9) Reset admin password"
  echo " 2) Logs (live)      10) Show generated admin login"
  echo " 3) Start            11) Clear login lock (restart)"
  echo " 4) Stop             12) Backup database"
  echo " 5) Restart          13) Rebuild"
  echo " 6) Update           14) Uninstall"
  echo " 7) Edit .env        15) Show URL / port"
  echo "16) Disable admin 2FA (lost phone)"
  echo " 8) Change port / URL (p/u)      0) Exit"
  read -r -p "> " c || exit 0
  case "$c" in
    1) dc ps; pause;;
    2) dc logs -f --tail=100;;
    3) dc up -d; pause;;
    4) dc stop; pause;;
    5|11) dc restart; pause;;
    6) update; pause;;
    7) edit_env; pause;;
    8|p) change_port; pause;;
    u) change_url; pause;;
    9) reset_pw; pause;;
    10) creds; pause;;
    12) backup; pause;;
    13) apply; pause;;
    14) uninstall; pause;;
    16) reset_2fa; pause;;
    15) echo "URL:  $(get_env PUBLIC_BASE_URL)/dashboard/"; echo "Port: $(get_env PORT)"; pause;;
    0|q) exit 0;;
  esac
done
