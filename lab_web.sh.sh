#!/bin/bash

set -e

echo "=============================="
echo " ALL-IN-ONE NGINX LAB SCRIPT"
echo "=============================="

# -----------------------------
# 1️⃣ Stop conflicting services
# -----------------------------
echo "[+] Stopping conflicting web servers..."

SERVICES=(apache2 httpd lighttpd lsws)

for svc in "${SERVICES[@]}"; do
    if systemctl list-unit-files | grep -q "$svc"; then
        sudo systemctl stop "$svc" 2>/dev/null || true
        sudo systemctl disable "$svc" 2>/dev/null || true
        sudo systemctl mask "$svc" 2>/dev/null || true
        echo "    [-] $svc stopped & masked"
    fi
done

# -----------------------------
# 2️⃣ Kill ports 80 / 443
# -----------------------------
echo "[+] Clearing ports 80 and 443..."
sudo fuser -k 80/tcp 2>/dev/null || true
sudo fuser -k 443/tcp 2>/dev/null || true

sleep 2

# -----------------------------
# 3️⃣ Check ports are free
# -----------------------------
echo "[+] Verifying ports..."
if sudo ss -tulpn | grep -E ':80|:443'; then
    echo "[✗] Ports still in use — aborting"
    exit 1
else
    echo "[✓] Ports are free"
fi

# -----------------------------
# 4️⃣ Install Nginx if missing
# -----------------------------
if ! command -v nginx >/dev/null 2>&1; then
    echo "[+] Installing Nginx..."
    sudo apt update -y
    sudo apt install nginx -y
else
    echo "[✓] Nginx already installed"
fi

# -----------------------------
# 5️⃣ Create website files
# -----------------------------
echo "[+] Creating website directory..."
sudo mkdir -p /var/www/cyberlab

sudo tee /var/www/cyberlab/index.html > /dev/null << 'EOF'
<!DOCTYPE html>
<html>
<head>
    <title>CyberLab</title>
    <style>
        body {
            background:#0d1117;
            color:#00ff9c;
            font-family: monospace;
            text-align:center;
            padding-top:10%;
        }
        .box {
            border:2px solid #00ff9c;
            display:inline-block;
            padding:30px;
            border-radius:10px;
        }
    </style>
</head>
<body>
<div class="box">
<h1>🚀 CyberLab Online</h1>
<p>Nginx | Port 80</p>
<p>Status: ACTIVE</p>
</div>
</body>
</html>
EOF

# -----------------------------
# 6️⃣ Configure Nginx site
# -----------------------------
echo "[+] Configuring Nginx site..."

sudo tee /etc/nginx/sites-available/cyberlab > /dev/null << 'EOF'
server {
    listen 80 default_server;
    server_name _;

    root /var/www/cyberlab;
    index index.html;

    location / {
        try_files $uri $uri/ =404;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/cyberlab /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# -----------------------------
# 7️⃣ Test Nginx config
# -----------------------------
echo "[+] Testing Nginx configuration..."
sudo nginx -t

# -----------------------------
# 8️⃣ Start Nginx safely
# -----------------------------
echo "[+] Starting Nginx..."
sudo systemctl daemon-reload
sudo systemctl restart nginx
sudo systemctl enable nginx

# -----------------------------
# 9️⃣ Final status
# -----------------------------
IP=$(hostname -I | awk '{print $1}')

echo "=============================="
echo "[✓] NGINX LAB READY"
echo "[✓] Open: http://$IP/"
echo "=============================="
