#!/bin/bash
# VPS setup for My Money Went Bot — nginx reverse proxy + Let's Encrypt TLS.
# Tested on Ubuntu 22.04.
#
#   1. Copy the project onto the VPS first:
#        scp -r ./my-money-went-bot ubuntu@<vps-ip>:~/
#   2. Put your .env and credentials.json in that directory.
#   3. sudo bash setup.sh your-domain.com
#
# The bot's webhooks must be reachable over HTTPS — SePay, Telegram and Apps
# Script all refuse plain HTTP — which is the whole reason this script exists
# rather than a bare `uvicorn` command.

set -e
DOMAIN=${1:-"your-domain.com"}
SERVICE="mmwbot"
BOT_DIR="${BOT_DIR:-/home/ubuntu/my-money-went-bot}"
RUN_USER="${RUN_USER:-ubuntu}"

if [ ! -f "$BOT_DIR/main.py" ]; then
  echo "No bot at $BOT_DIR — copy the project there first, or set BOT_DIR=<path>."
  exit 2
fi
if [ ! -f "$BOT_DIR/.env" ]; then
  echo "No $BOT_DIR/.env — the bot exits at startup without its environment."
  echo "Copy .env.example to .env and fill it in first."
  exit 2
fi

echo "=== [1/6] System dependencies ==="
apt update && apt install -y python3.11 python3-pip python3.11-venv nginx certbot python3-certbot-nginx

echo "=== [2/6] Permissions on the secrets ==="
chmod 600 "$BOT_DIR/.env"
[ -f "$BOT_DIR/credentials.json" ] && chmod 600 "$BOT_DIR/credentials.json"
chown -R "$RUN_USER" "$BOT_DIR"

echo "=== [3/6] Python virtualenv + deps ==="
cd "$BOT_DIR"
sudo -u "$RUN_USER" python3.11 -m venv venv
sudo -u "$RUN_USER" ./venv/bin/pip install -r requirements.txt

echo "=== [4/6] systemd service ($SERVICE) ==="
cat > /etc/systemd/system/$SERVICE.service << EOF
[Unit]
Description=My Money Went Bot
After=network.target

[Service]
User=$RUN_USER
WorkingDirectory=$BOT_DIR
EnvironmentFile=$BOT_DIR/.env
ExecStart=$BOT_DIR/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable $SERVICE
systemctl restart $SERVICE

echo "=== [5/6] Nginx reverse proxy ==="
cat > /etc/nginx/sites-available/$SERVICE << EOF
server {
    listen 80;
    server_name $DOMAIN;

    location / {
        proxy_pass         http://127.0.0.1:8000;
        proxy_set_header   Host \$host;
        proxy_set_header   X-Real-IP \$remote_addr;
        proxy_read_timeout 30;
    }
}
EOF

ln -sf /etc/nginx/sites-available/$SERVICE /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx

echo "=== [6/6] TLS with Let's Encrypt ==="
certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos -m "admin@$DOMAIN"

echo ""
echo "Done. Check it is up:"
echo "    systemctl status $SERVICE"
echo "    journalctl -u $SERVICE -f"
echo "    curl https://$DOMAIN/healthz"
echo ""
echo "Then register the Telegram webhook:"
echo "    curl \"https://api.telegram.org/bot\$BOT_TOKEN/setWebhook?url=https://$DOMAIN/webhook&secret_token=\$TELEGRAM_WEBHOOK_SECRET&drop_pending_updates=true\""
