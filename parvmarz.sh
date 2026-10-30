#!/usr/bin/env bash
# Jinx Data terminal menu. Run: parvmarz   (installed by install.sh)
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
apply() { echo "Applying..."; dc up -d; }
rebuild() { echo "Rebuilding..."; dc up -d --build; }
ask() { local v; read -r -p "$1 [$2]: " v || true; printf '%s' "${v:-$2}"; }

edit_env() {
  [ -f .env ] || cp .env.example .env
  ${EDITOR:-$(command -v nano || command -v vi)} .env
  [ "$(ask 'Apply changes now (rebuild/restart)? y/n' y)" = y ] && apply
}
server_ip() { curl -fsS4 --max-time 5 https://api.ipify.org 2>/dev/null || hostname -I | awk '{print $1}'; }
CERT_DIR="$DIR/certs"
has_cert() { [ -f "$CERT_DIR/live/$1/fullchain.pem" ]; }
valid_port() { [[ "$1" =~ ^[0-9]+$ ]] && [ "$1" -ge 1 ] && [ "$1" -le 65535 ]; }
panel_port() { local p; p="$(get_env PANEL_PORT)"; [ -n "$p" ] || p="$(get_env PORT)"; echo "${p:-8000}"; }
mkurl() { # scheme host port
  if { [ "$1" = https ] && [ "$3" = 443 ]; } || { [ "$1" = http ] && [ "$3" = 80 ]; }; then echo "$1://$2"; else echo "$1://$2:$3"; fi
}
refresh_urls() {
  local pd sd pp sp host cur
  pd="$(get_env PANEL_DOMAIN)"; sd="$(get_env SUB_DOMAIN)"; pp="$(panel_port)"; sp="$(get_env SUB_PORT)"
  cur="$(get_env PUBLIC_BASE_URL)"
  if [ -n "$pd" ]; then host="$pd"; elif [[ "$cur" =~ ^https?://([^/:]+) ]]; then host="${BASH_REMATCH[1]}"; else host="$(server_ip)"; fi
  if [ -n "$pd" ] && has_cert "$pd"; then cur="$(mkurl https "$host" "$pp")"; else cur="$(mkurl http "$host" "$pp")"; fi
  set_env PUBLIC_BASE_URL "$cur"; set_env CORS_ORIGINS "$cur"
  if [ -n "$sp" ]; then
    if [ -n "$sd" ]; then host="$sd"; fi
    if [ -n "$sd" ] && has_cert "$sd"; then set_env SUB_PUBLIC_BASE_URL "$(mkurl https "$host" "$sp")"; else set_env SUB_PUBLIC_BASE_URL "$(mkurl http "$host" "$sp")"; fi
  else set_env SUB_PUBLIC_BASE_URL ""; fi
}
change_port() {
  local p; p="$(ask 'New PANEL port' "$(panel_port)")"
  valid_port "$p" || { echo "Invalid port"; return; }
  [ "$p" != "$(get_env SUB_PORT)" ] || { echo "Panel and subscription ports must differ"; return; }
  set_env PANEL_PORT "$p"; set_env PORT "$p"; refresh_urls; apply
}
change_sub_port() {
  local p; p="$(ask 'Subscription port (separate from panel; 0 = serve /sub on the panel port)' "$(get_env SUB_PORT)")"
  if [ "$p" = 0 ] || [ -z "$p" ]; then set_env SUB_PORT ""; set_env SUB_BIND 127.0.0.1; set_env SUB_DOMAIN ""; refresh_urls; apply; return; fi
  valid_port "$p" || { echo "Invalid port"; return; }
  [ "$p" != "$(panel_port)" ] || { echo "Panel and subscription ports must differ"; return; }
  set_env SUB_PORT "$p"; set_env SUB_BIND 0.0.0.0; refresh_urls; apply
  echo "Sub links now use: $(get_env SUB_PUBLIC_BASE_URL)/sub/..."
}
change_url() {
  u="$(ask 'Public URL (http://IP:PORT or https://domain)' "$(get_env PUBLIC_BASE_URL)")"
  [ -n "$u" ] || { echo "Empty"; return; }
  set_env PUBLIC_BASE_URL "$u"; set_env CORS_ORIGINS "$u"; apply
}

# ---- SSL (Let's Encrypt via certbot container, HTTP-01 on port 80) ----
cert_cmd() { docker run --rm -p 80:80 -v "$CERT_DIR:/etc/letsencrypt" certbot/certbot "$@"; }
install_cron() {
  [ -d /etc/cron.d ] || return 0
  printf '17 3 * * * root /usr/local/bin/parvmarz renew-cert >/dev/null 2>&1\n' > /etc/cron.d/jinx-renew
}
issue_cert() { # panel | sub
  local who="$1" var dom email
  if [ "$who" = panel ]; then var=PANEL_DOMAIN; else
    [ -n "$(get_env SUB_PORT)" ] || { echo "Set a separate subscription port first (option s)."; return; }
    var=SUB_DOMAIN
  fi
  dom="$(ask "Domain for the $who (its A record must point to this server)" "$(get_env $var)")"; dom="${dom,,}"
  [[ "$dom" =~ ^([a-z0-9]([a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,}$ ]] || { echo "Invalid domain"; return; }
  email="$(ask 'Email for expiry notices (optional)' '')"
  if ss -ltn 2>/dev/null | awk '{print $4}' | grep -qE '[:.]80$'; then echo "Port 80 is in use; stop the service using it and retry."; return; fi
  mkdir -p "$CERT_DIR"
  local args=(certonly --standalone --non-interactive --agree-tos --keep-until-expiring -d "$dom")
  if [ -n "$email" ]; then args+=(-m "$email"); else args+=(--register-unsafely-without-email); fi
  echo "Requesting certificate for $dom ..."
  cert_cmd "${args[@]}" && has_cert "$dom" || { echo "Certificate request failed (check DNS and that port 80 is reachable)."; return; }
  set_env "$var" "$dom"; install_cron; refresh_urls; apply
  echo "Panel: $(get_env PUBLIC_BASE_URL)/dashboard/"
  [ -z "$(get_env SUB_PORT)" ] || echo "Sub:   $(get_env SUB_PUBLIC_BASE_URL)/sub/..."
}
renew_cert() {
  [ -d "$CERT_DIR/live" ] || { echo "No certificates yet."; return 0; }
  rm -f "$CERT_DIR/.renewed"
  cert_cmd renew --quiet --deploy-hook "touch /etc/letsencrypt/.renewed"
  if [ -f "$CERT_DIR/.renewed" ]; then rm -f "$CERT_DIR/.renewed"; dc restart >/dev/null 2>&1; echo "Renewed and restarted."; else echo "Nothing to renew yet."; fi
}
remove_ssl() {
  [ "$(ask 'Disable SSL/domain lock for panel and sub? (certificates are kept) y/n' n)" = y ] || return
  set_env PANEL_DOMAIN ""; set_env SUB_DOMAIN ""; refresh_urls; apply
}
update() { PARVMARZ_DIR="$DIR" bash "$DIR/install.sh" update; }
backup() {
  dc exec -T subhub python -m cli backup --directory /app/data/backups && \
  dc cp subhub:/app/data/backups ./backups && echo "Copied to $DIR/backups"
}
creds() { dc exec -T subhub cat /app/data/initial-admin.txt 2>/dev/null || echo "No generated credentials file (you set INITIAL_ADMIN_PASSWORD yourself, or use option: Reset admin password)."; }
reset_pw() { u="$(ask 'Admin username' admin)"; dc exec subhub python -m cli reset-admin-password --username "$u"; }
clear_lock() { dc exec -T subhub python -m cli clear-login-lock; }
reset_2fa() { u="$(ask 'Admin username' admin)"; dc exec subhub python -m cli disable-2fa --username "$u"; }
uninstall() {
  [ "$(ask 'Remove containers AND data? type yes' no)" = yes ] && dc down -v && echo "Removed (source dir kept: $DIR)"
}

[ "${1:-}" = renew-cert ] && { renew_cert; exit 0; }

while true; do
  clear 2>/dev/null || true
  echo "=== Jinx Data menu ($DIR) ==="
  echo " 1) Status            9) Reset admin password"
  echo " 2) Logs (live)      10) Show generated admin login"
  echo " 3) Start            11) Clear login lock"
  echo " 4) Stop             12) Backup database"
  echo " 5) Restart          13) Rebuild"
  echo " 6) Update           14) Uninstall"
  echo " 7) Edit .env        15) Show URL / port"
  echo "16) Disable admin 2FA (lost phone)"
  echo " 8) Change panel port (p) / URL (u)"
  echo " s) Change subscription port (separate)"
  echo "17) SSL certificate for PANEL domain     18) SSL certificate for SUB domain"
  echo "19) Renew SSL now                        20) Disable SSL / domain lock"
  echo " 0) Exit"
  read -r -p "> " c || exit 0
  case "$c" in
    1) dc ps; pause;;
    2) dc logs -f --tail=100;;
    3) dc up -d; pause;;
    4) dc stop; pause;;
    5) dc restart; pause;;
    11) clear_lock; pause;;
    6) update; pause;;
    7) edit_env; pause;;
    8|p) change_port; pause;;
    u) change_url; pause;;
    s) change_sub_port; pause;;
    17) issue_cert panel; pause;;
    18) issue_cert sub; pause;;
    19) renew_cert; pause;;
    20) remove_ssl; pause;;
    9) reset_pw; pause;;
    10) creds; pause;;
    12) backup; pause;;
    13) rebuild; pause;;
    14) uninstall; pause;;
    16) reset_2fa; pause;;
    15) echo "Panel: $(get_env PUBLIC_BASE_URL)/dashboard/  (port $(panel_port))"; [ -z "$(get_env SUB_PORT)" ] || echo "Sub:   $(get_env SUB_PUBLIC_BASE_URL)/sub/...  (port $(get_env SUB_PORT))"; pause;;
    0|q) exit 0;;
  esac
done
