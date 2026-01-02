#!/bin/bash

# -----------------------------
# Simple Website Hosting Script
# Ubuntu | Port 80 | Nginx
# With Web Server Conflict Cleanup
# -----------------------------

set -e

echo "[+] Stopping other web servers (if any)..."

SERVICES=(
    apache2
    httpd
    nginx
    lighttpd
    lsws
)

for svc in "${SERVICES[@]}"; do
    if systemctl list-units --type=service | grep -q "$svc"; then
        sudo systemctl stop "$svc" 2>/dev/null
        sudo systemctl disable "$svc" 2>/dev/null
        echo "    [-] Stopped $svc"
    fi
done

echo "[+] Killing processes on ports 80 and 443..."
sudo fuser -k 80/tcp 2>/dev/null || true
sudo fuser -k 443/tcp 2>/dev/null || true

echo "[+] Updating system..."
sudo apt update -y

echo "[+] Installing Nginx..."
sudo apt install nginx -y

echo "[+] Enabling Nginx..."
sudo systemctl enable nginx
sudo systemctl start nginx

echo "[+] Creating website directory..."
sudo mkdir -p /var/www/cyberlab

echo "[+] Creating index.html..."
sudo tee /var/www/cyberlab/index.html > /dev/null << 'EOF'
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>CyberLab</title>
    <style>
        body {
            background-color: #0d1117;
            color: #00ff9c;
            font-family: monospace;
            text-align: center;
            padding-top: 10%;
        }
        h1 {
            font-size: 3em;
        }
        p {
            font-size: 1.2em;
            color: #c9d1d9;
        }
        .box {
            border: 2px solid #00ff9c;
            display: inline-block;
            padding: 20px 40px;
            border-radius: 10px;
        }
    </style>
</head>
<body>
    <div class="box">
        <h1>🚀 CyberLab Online</h1>
        <p>Ubuntu | Nginx | Port 80</p>
        <p>Hosted via Bash Script</p>
        <p>Status: <span style="color:#00ff9c;">ACTIVE</span></p>
    </div>
</body>
</html>
EOF

echo "[+] Creating Nginx config..."
sudo tee /etc/nginx/sites-available/cyberlab > /dev/null << 'EOF'
server {
    listen 80;
    server_name _;

    root /var/www/cyberlab;
    index index.html;

    location / {
        try_files $uri $uri/ =404;
    }
}
EOF

echo "[+] Enabling site..."
sudo ln -sf /etc/nginx/sites-available/cyberlab /etc/nginx/sites-enabled/

echo "[+] Removing default site..."
sudo rm -f /etc/nginx/sites-enabled/default

echo "[+] Testing Nginx config..."
sudo nginx -t

echo "[+] Reloading Nginx..."
sudo systemctl reload nginx

IP=$(hostname -I | awk '{print $1}')

echo "[✔] Website hosted successfully"
echo "[✔] Open: http://$IP/"
