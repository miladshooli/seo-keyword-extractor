#!/usr/bin/env bash
# One-shot installer for Debian/Ubuntu. Run as root.
# Usage: bash deploy/setup.sh
set -euo pipefail

APP_DIR=/opt/seo-kwr
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
POS_URL="https://huggingface.co/roshan-research/hazm-postagger/resolve/main/pos_tagger.model"

echo "==> System packages (venv, pip, nginx)"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y python3-venv python3-pip nginx curl

echo "==> App files -> $APP_DIR"
mkdir -p "$APP_DIR/templates" "$APP_DIR/models" "$APP_DIR/uploads"
cp "$REPO_DIR/app.py" "$APP_DIR/app.py"
cp "$REPO_DIR/templates/index.html" "$APP_DIR/templates/index.html"
cp "$REPO_DIR/serpiwi_auth.py" "$APP_DIR/serpiwi_auth.py"
mkdir -p "$APP_DIR/static" && cp "$REPO_DIR/static/"* "$APP_DIR/static/"

echo "==> Python venv + dependencies (hazm pulls numpy/scipy/sklearn/gensim — a few minutes)"
python3 -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/pip" install --no-cache-dir --upgrade pip
"$APP_DIR/venv/bin/pip" install --no-cache-dir -r "$REPO_DIR/requirements.txt"

echo "==> Persian POS tagger model"
if [ ! -s "$APP_DIR/models/pos_tagger.model" ]; then
  curl -sSL -o "$APP_DIR/models/pos_tagger.model" "$POS_URL"
fi

echo "==> systemd service"
cp "$REPO_DIR/deploy/seo-kwr.service" /etc/systemd/system/seo-kwr.service
for v in JINA_API_KEY VOYAGE_API_KEY; do
  val="${!v:-}"
  [ -n "$val" ] && sed -i "/^\[Service\]/a Environment=\"$v=$val\"" /etc/systemd/system/seo-kwr.service
done
systemctl daemon-reload
systemctl enable --now seo-kwr

echo "==> nginx site"
cp "$REPO_DIR/deploy/nginx.conf" /etc/nginx/sites-available/seo-kwr
ln -sf /etc/nginx/sites-available/seo-kwr /etc/nginx/sites-enabled/seo-kwr
nginx -t && systemctl reload nginx

echo "==> Done. gunicorn on 127.0.0.1:8002 (proxied on :80)."
echo "    HTTPS:  certbot --nginx -d your.domain.com --redirect"
