#!/bin/bash
# VPS setup script for financial-tracking-bot
# Tested on Ubuntu 22.04
# Usage: bash setup.sh your-domain.com

set -e
DOMAIN=${1:-"your-domain.com"}
BOT_DIR="/home/ubuntu/financial-tracking-bot"

echo "=== [1/6] Installing system dependencies ==="
apt update && apt install -y python3.11 python3-pip python3.11-venv nginx certbot python3-certbot-nginx

echo "=== [2/6] Creating project directory ==="
mkdir -p $BOT_DIR
# Copy your project files here first, then run this script
# scp -r ./financial-tracking-bot ubuntu@your-vps-ip:~/

echo "=== [3/6] Python virtualenv + deps ==="
cd $BOT_DIR
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

echo "=== [4/6] systemd service ==="
cat > /etc/systemd/system/financial-tracking-bot.service << EOF
[Unit]
Description=Financial Tracking Bot — Telegram Bot
After=network.target

[Service]
User=ubuntu
WorkingDirectory=$BOT_DIR
ExecStart=$BOT_DIR/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable financial-tracking-bot
systemctl start financial-tracking-bot

echo "=== [5/6] Nginx config ==="
cat > /etc/nginx/sites-available/financial-tracking-bot << EOF
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

ln -sf /etc/nginx/sites-available/financial-tracking-bot /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx

echo "=== [6/6] SSL with Let's Encrypt ==="
certbot --nginx -d $DOMAIN --non-interactive --agree-tos -m admin@$DOMAIN

echo ""
echo "✅ Done! Now set your Telegram webhook:"
echo "curl \"https://api.telegram.org/bot\$BOT_TOKEN/setWebhook?url=https://$DOMAIN/webhook&drop_pending_updates=true\""
