#!/bin/bash

set -e

echo "======================================="
echo " APACHE VULNERABLE UPLOAD LAB (ALL-IN-ONE)"
echo "======================================="

# -----------------------------
# 1️⃣ Stop & mask other servers
# -----------------------------
echo "[+] Stopping conflicting web services..."

SERVICES=(nginx apache2 httpd lighttpd lsws)

for svc in "${SERVICES[@]}"; do
    if systemctl list-unit-files | grep -q "^$svc"; then
        sudo systemctl stop "$svc" 2>/dev/null || true
        sudo systemctl disable "$svc" 2>/dev/null || true
        sudo systemctl mask "$svc" 2>/dev/null || true
        echo "    [-] $svc stopped & masked"
    fi
done

# -----------------------------
# 2️⃣ Kill port blockers
# -----------------------------
echo "[+] Clearing ports 80 and 443..."
sudo fuser -k 80/tcp 2>/dev/null || true
sudo fuser -k 443/tcp 2>/dev/null || true
sleep 2

# -----------------------------
# 3️⃣ Verify ports are free
# -----------------------------
echo "[+] Verifying ports..."
if sudo ss -tulpn | grep -E ':80|:443'; then
    echo "[✗] Ports still in use — aborting"
    exit 1
else
    echo "[✓] Ports are free"
fi

# -----------------------------
# 4️⃣ Detect package manager
# -----------------------------
if command -v apt >/dev/null 2>&1; then
    PKG="apt"
    APACHE="apache2"
    USER="www-data"
elif command -v yum >/dev/null 2>&1; then
    PKG="yum"
    APACHE="httpd"
    USER="apache"
else
    echo "[-] Unsupported OS"
    exit 1
fi

# -----------------------------
# 5️⃣ Install Apache + PHP
# -----------------------------
echo "[+] Installing Apache & PHP..."

if [ "$PKG" = "apt" ]; then
    sudo apt update -y
    sudo apt install -y apache2 php libapache2-mod-php
    WEB_ROOT="/var/www/html"
else
    sudo yum install -y httpd php
    WEB_ROOT="/var/www/html"
fi

# -----------------------------
# 6️⃣ Create lab files
# -----------------------------
LAB_DIR="$WEB_ROOT/upload_lab"
UPLOAD_DIR="$LAB_DIR/uploads"

echo "[+] Creating lab directories..."
sudo mkdir -p "$UPLOAD_DIR"

echo "[+] Creating vulnerable PHP upload script..."
sudo tee "$LAB_DIR/index.php" > /dev/null << 'EOF'
<?php
$upload_dir = "uploads/";

if (!file_exists($upload_dir)) {
    mkdir($upload_dir, 0777, true);
}

if (isset($_FILES['file'])) {
    $name = $_FILES['file']['name'];
    $tmp  = $_FILES['file']['tmp_name'];

    // INTENTIONALLY VULNERABLE
    move_uploaded_file($tmp, $upload_dir . $name);

    echo "<p style='color:lime'>Uploaded: <a href='$upload_dir$name'>$upload_dir$name</a></p>";
}
?>
<!DOCTYPE html>
<html>
<head>
    <title>Vulnerable File Upload Lab</title>
</head>
<body>
<h2>🔥 Vulnerable File Upload Lab</h2>

<form method="POST" enctype="multipart/form-data">
    <input type="file" name="file">
    <br><br>
    <input type="submit" value="Upload">
</form>

<p><b>WARNING:</b> This application is intentionally insecure.</p>
</body>
</html>
EOF

# -----------------------------
# 7️⃣ Insecure permissions
# -----------------------------
echo "[+] Applying INSECURE permissions..."
sudo chmod -R 777 "$LAB_DIR"
sudo chown -R "$USER:$USER" "$LAB_DIR"

# -----------------------------
# 8️⃣ Test Apache config
# -----------------------------
echo "[+] Testing Apache configuration..."
if [ "$APACHE" = "apache2" ]; then
    sudo apachectl -t
else
    sudo httpd -t
fi

# -----------------------------
# 9️⃣ Start Apache safely
# -----------------------------
echo "[+] Starting Apache..."
sudo systemctl daemon-reload
sudo systemctl enable "$APACHE"
sudo systemctl restart "$APACHE"

# -----------------------------
# 🔟 Final status
# -----------------------------
IP=$(hostname -I | awk '{print $1}')

echo "======================================="
echo "[✓] VULNERABLE UPLOAD LAB READY"
echo "[✓] Other web servers STOPPED & MASKED"
echo "[✓] Access: http://$IP/upload_lab/"
echo "[!] DO NOT expose this machine to the internet"
echo "======================================="
