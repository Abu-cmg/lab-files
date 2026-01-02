
#!/bin/bash
sudo systemctl unmask apache2 2>/dev/null || true

set -e

echo "======================================="
echo " APACHE VULNERABLE UPLOAD LAB (FIXED)"
echo "======================================="

# -----------------------------
# 1️⃣ Stop & mask OTHER servers
# -----------------------------
echo "[+] Stopping conflicting web services..."

OTHER_SERVICES=(nginx httpd lighttpd lsws)

for svc in "${OTHER_SERVICES[@]}"; do
    if systemctl list-unit-files | grep -q "^$svc"; then
        sudo systemctl stop "$svc" 2>/dev/null || true
        sudo systemctl disable "$svc" 2>/dev/null || true
        sudo systemctl mask "$svc" 2>/dev/null || true
        echo "    [-] $svc stopped & masked"
    fi
done

# -----------------------------
# 2️⃣ Ensure apache is UNMASKED
# -----------------------------
echo "[+] Ensuring Apache is unmasked..."
sudo systemctl unmask apache2 2>/dev/null || true

# -----------------------------
# 3️⃣ Clear port blockers
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
# 5️⃣ Install Apache + PHP
# -----------------------------
echo "[+] Installing Apache & PHP..."
sudo apt update -y
sudo apt install -y apache2 php libapache2-mod-php

WEB_ROOT="/var/www/html"
USER="www-data"

# -----------------------------
# 6️⃣ Create lab
# -----------------------------
LAB_DIR="$WEB_ROOT/upload_lab"
UPLOAD_DIR="$LAB_DIR/uploads"

echo "[+] Creating lab directories..."
sudo mkdir -p "$UPLOAD_DIR"

echo "[+] Creating vulnerable upload script..."
sudo tee "$LAB_DIR/index.php" > /dev/null << 'EOF'
<?php
$upload_dir = "uploads/";

if (!file_exists($upload_dir)) {
    mkdir($upload_dir, 0777, true);
}

if (isset($_FILES['file'])) {
    move_uploaded_file($_FILES['file']['tmp_name'],
                       $upload_dir . $_FILES['file']['name']);
    echo "<p style='color:lime'>Uploaded!</p>";
}
?>
<form method="POST" enctype="multipart/form-data">
    <input type="file" name="file">
    <input type="submit">
</form>
EOF

# -----------------------------
# 7️⃣ Insecure permissions
# -----------------------------
echo "[+] Applying INSECURE permissions..."
sudo chmod -R 777 "$LAB_DIR"
sudo chown -R "$USER:$USER" "$LAB_DIR"

# -----------------------------
# 8️⃣ Test & start Apache
# -----------------------------
echo "[+] Testing Apache config..."
sudo apachectl -t

echo "[+] Starting Apache..."
sudo systemctl enable apache2
sudo systemctl restart apache2

# -----------------------------
# 9️⃣ Done
# -----------------------------
IP=$(hostname -I | awk '{print $1}')

echo "======================================="
echo "[✓] VULNERABLE UPLOAD LAB READY"
echo "[✓] Access: http://$IP/upload_lab/"
echo "[!] DO NOT expose this machine to the internet"
echo "======================================="

