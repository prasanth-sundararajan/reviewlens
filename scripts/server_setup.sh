#!/usr/bin/env bash
# ReviewLens - one-command setup / update for an Ubuntu VPS (e.g. Hostinger KVM).
#
# First install (as root on the VPS):
#   curl -fsSLo server_setup.sh https://raw.githubusercontent.com/prasanth-sundararajan/reviewlens/main/scripts/server_setup.sh
#   sudo bash server_setup.sh
#
# Non-interactive (values from environment variables):
#   sudo APP_DOMAIN=www.example.com OPENAI_API_KEY=sk-... bash server_setup.sh
#
# Run it again any time to update: it pulls the latest code and rebuilds.
# An existing /opt/reviewlens/.env is kept as it is (never overwritten).
#
# Options (environment variables):
#   APP_DIR=/opt/reviewlens  REPO=https://github.com/<you>/reviewlens.git  BRANCH=main
#   APP_DOMAIN, APP_PATH (default techstack/ReviewLens), OPENAI_API_KEY, LLM_MODEL (default gpt-4o-mini),
#   MAX_REVIEWS (default 500), APP_PASSWORD (empty = public),
#   SMTP_USER, SMTP_PASSWORD, REPORT_RECIPIENTS (optional weekly email)
#   NO_START=1  - install + configure only, do not start containers
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/reviewlens}"
REPO="${REPO:-https://github.com/prasanth-sundararajan/reviewlens.git}"
BRANCH="${BRANCH:-main}"
COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.prod.yml)

step() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
ok()   { printf '    \033[32mOK\033[0m %s\n' "$*"; }
die()  { printf '\n\033[1;31mERROR:\033[0m %b\n' "$*" >&2; exit 1; }

ask() {  # ask VAR "Question" [default] [secret]
  local var="$1" question="$2" default="${3:-}" secret="${4:-}" answer=""
  if [ -n "${!var:-}" ]; then return; fi
  if [ ! -t 0 ]; then printf -v "$var" '%s' "$default"; return; fi
  if [ -n "$secret" ]; then read -r -s -p "    $question: " answer; echo
  else read -r -p "    $question${default:+ [$default]}: " answer; fi
  printf -v "$var" '%s' "${answer:-$default}"
}

[ "$(id -u)" -eq 0 ] || die "Run as root (sudo bash server_setup.sh)."

step "1/6 Installing Docker, Compose and Git (skipped if present)"
if ! command -v docker >/dev/null || ! docker compose version >/dev/null 2>&1 || ! command -v git >/dev/null; then
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get install -y -qq docker.io docker-compose-v2 git curl ca-certificates >/dev/null
fi
systemctl enable --now docker >/dev/null 2>&1 || true
ok "$(docker --version)"
ok "$(docker compose version)"

step "2/6 Getting the code into $APP_DIR"
if [ -d "$APP_DIR/.git" ]; then
  git -C "$APP_DIR" fetch -q origin "$BRANCH"
  git -C "$APP_DIR" checkout -q "$BRANCH"
  git -C "$APP_DIR" pull -q --ff-only origin "$BRANCH"
  ok "updated to $(git -C "$APP_DIR" log -1 --format='%h %s')"
else
  git clone -q --branch "$BRANCH" "$REPO" "$APP_DIR"
  ok "cloned $(git -C "$APP_DIR" log -1 --format='%h %s')"
fi
cd "$APP_DIR"

step "3/6 Settings file $APP_DIR/.env"
if [ -f .env ]; then
  ok "existing .env kept (edit with: nano $APP_DIR/.env)"
else
  ask APP_DOMAIN "Domain for the app (DNS A record must point here), e.g. www.example.com"
  [ -n "${APP_DOMAIN:-}" ] || die "APP_DOMAIN is required."
  ask APP_PATH "URL path" "techstack/ReviewLens"
  ask OPENAI_API_KEY "OpenAI API key (input hidden)" "" secret
  [ -n "${OPENAI_API_KEY:-}" ] || die "OPENAI_API_KEY is required."
  ask APP_PASSWORD "Login password for the app (empty = public)" ""
  ask SMTP_USER "Gmail address that sends the Monday report (empty = no email)" ""
  if [ -n "${SMTP_USER:-}" ]; then
    ask SMTP_PASSWORD "Google App Password for $SMTP_USER (input hidden)" "" secret
    ask REPORT_RECIPIENTS "Report recipients, comma-separated" ""
  fi
  umask 077
  cat > .env <<EOF
LLM_PROVIDER=openai
LLM_MODEL=${LLM_MODEL:-gpt-4o-mini}
OPENAI_API_KEY=${OPENAI_API_KEY}
MAX_REVIEWS=${MAX_REVIEWS:-500}
APP_DOMAIN=${APP_DOMAIN}
APP_PATH=${APP_PATH:-techstack/ReviewLens}
APP_PASSWORD=${APP_PASSWORD:-}
APP_URL=https://${APP_DOMAIN}/${APP_PATH:-techstack/ReviewLens}/
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=${SMTP_USER:-}
SMTP_PASSWORD=${SMTP_PASSWORD:-}
REPORT_RECIPIENTS=${REPORT_RECIPIENTS:-}
REPORT_DAY=monday
REPORT_TIME=09:00
REPORT_TIMEZONE=Asia/Kolkata
EOF
  ok "created .env"
fi
chmod 600 .env
DOMAIN="$(grep -E '^APP_DOMAIN=' .env | cut -d= -f2- | cut -d, -f1 | tr -d ' ')"
APATH="$(grep -E '^APP_PATH=' .env | cut -d= -f2- | tr -d ' ')"; APATH="${APATH:-techstack/ReviewLens}"
[ -n "$DOMAIN" ] || die "APP_DOMAIN is missing in .env"
ok "domain: $DOMAIN  path: /$APATH/"

step "4/6 Checking DNS and ports"
SERVER_IP="$(curl -fsS4 --max-time 10 https://ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')"
DNS_IP="$(getent ahostsv4 "$DOMAIN" 2>/dev/null | awk 'NR==1{print $1}')"
if [ "$DNS_IP" = "$SERVER_IP" ]; then ok "$DOMAIN -> $DNS_IP (this server)"
else printf '    \033[33mWARN\033[0m %s resolves to "%s", this server is %s - HTTPS needs the A record to point here.\n' "$DOMAIN" "${DNS_IP:-nothing}" "$SERVER_IP"; fi
if command -v ufw >/dev/null && ufw status | grep -q "Status: active"; then
  ufw allow 80/tcp >/dev/null; ufw allow 443/tcp >/dev/null; ok "ufw: opened 80/443"
fi
BUSY="$(ss -tlnpH '( sport = :80 or sport = :443 )' 2>/dev/null | grep -v docker-proxy || true)"
[ -z "$BUSY" ] || die "Ports 80/443 are used by another program:\n$BUSY"
ok "ports 80/443 free for Caddy"

if [ "${NO_START:-}" = "1" ]; then step "NO_START=1 - stopping before starting containers"; exit 0; fi

step "5/6 Building and starting (app + HTTPS proxy + weekly-email scheduler)"
"${COMPOSE[@]}" up -d --build --remove-orphans
for i in $(seq 1 30); do
  state="$(docker inspect -f '{{.State.Health.Status}}' reviewlens-reviewlens-1 2>/dev/null || echo starting)"
  [ "$state" = "healthy" ] && break; sleep 4
done
"${COMPOSE[@]}" ps --format '    {{.Service}}: {{.Status}}'

step "6/6 Checking the live site"
URL="https://$DOMAIN/$APATH/"
code="000"
for i in $(seq 1 20); do
  code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "${URL}_stcore/health" || true)"
  [ "$code" = "200" ] && break; sleep 6
done
if [ "$code" = "200" ]; then
  ok "$URL is live (HTTPS health check 200)"
  expiry="$(echo | openssl s_client -connect "$DOMAIN:443" -servername "$DOMAIN" 2>/dev/null | openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2)"
  [ -n "$expiry" ] && ok "certificate valid until $expiry (auto-renewed)"
else
  printf '    \033[33mWARN\033[0m HTTPS not ready yet (code %s). Check DNS, then: %s logs caddy\n' "$code" "${COMPOSE[*]}"
fi
"${COMPOSE[@]}" logs scheduler 2>/dev/null | grep -o 'next weekly email at .*' | tail -1 | sed 's/^/    /' || true

printf '\n\033[1;32mDone.\033[0m Open %s\n' "$URL"
printf 'Update later:  sudo bash %s/scripts/server_setup.sh\n' "$APP_DIR"
printf 'Logs:          cd %s && %s logs -f\n' "$APP_DIR" "${COMPOSE[*]}"
