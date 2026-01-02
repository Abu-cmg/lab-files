#!/bin/bash

set -e

echo "=============================="
echo " ALL-IN-ONE NGINX LAB SCRIPT"
echo "=============================="

# -----------------------------
# 1️⃣ Stop & mask OTHER servers
# -----------------------------
echo "[+] Stopping conflicting web servers..."

SERVICES=(apache2 httpd lighttpd lsws)

for svc in "${SERVICES[@]}"; do
    if systemctl list-unit-files | grep -q "^$svc"; then
        sudo systemctl stop "$svc" 2>/dev/null || true
        sudo systemctl disable "$svc" 2>/dev/null || true
        sudo systemctl mask "$svc" 2>/dev/null || true
        echo "    [-] $svc stopped & masked"
    fi
done

# -----------------------------
# 2️⃣ Ensure nginx is UNMASKED
# -----------------------------
echo "[+] Ensuring nginx is unmasked..."
sudo systemctl unmask nginx 2>/dev/null || true

# -----------------------------
# 3️⃣ Kill ports 80 / 443
# -----------------------------
echo "[+] Clearing ports 80 and 443..."
sudo fuser -k 80/tcp 2>/dev/null || true
sudo fuser -k 443/tcp 2>/dev/null || true
sleep 2

# -----------------------------
# 4️⃣ Verify ports are free
# -----------------------------
echo "[+] Verifying ports..."
if sudo ss -tulpn | grep -E ':80|:443'; then
    echo "[✗] Ports still in use — aborting"
    exit 1
else
    echo "[✓] Ports are free"
fi

# -----------------------------
# 5️⃣ Install nginx
# -----------------------------
if ! command -v nginx >/dev/null 2>&1; then
    echo "[+] Installing Nginx..."
    sudo apt update -y
    sudo apt install -y nginx
else
    echo "[✓] Nginx already installed"
fi

# -----------------------------
# 6️⃣ Create site files
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
# 7️⃣ Configure nginx site
# -----------------------------
echo "[+] Configuring nginx site..."

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
# 8️⃣ Test & start nginx
# -----------------------------
echo "[+] Testing nginx config..."
sudo nginx -t

echo "[+] Starting nginx..."
sudo systemctl daemon-reload
sudo systemctl enable nginx
sudo systemctl restart nginx

# -----------------------------
# 9️⃣ Done
# -----------------------------
IP=$(hostname -I | awk '{print $1}')

echo "=============================="
echo "[✓] NGINX LAB READY"
echo "[✓] Open: http://$IP/"
echo "=============================="
