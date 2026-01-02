#!/bin/bash

echo "[+] Starting vulnerable upload lab setup..."

# -----------------------------
# Stop ALL other web servers
# -----------------------------
echo "[+] Stopping any running web servers..."

SERVICES=(
    apache2
    httpd
    nginx
    lighttpd
    lsws
    mysql
)

for svc in "${SERVICES[@]}"; do
    if systemctl list-units --type=service | grep -q "$svc"; then
        sudo systemctl stop "$svc" 2>/dev/null
        sudo systemctl disable "$svc" 2>/dev/null
        echo "    [-] Stopped $svc"
    fi
done

# Kill anything using port 80 or 443
echo "[+] Killing processes on ports 80 and 443..."
sudo fuser -k 80/tcp 2>/dev/null
sudo fuser -k 443/tcp 2>/dev/null

# -----------------------------
# Detect package manager
# -----------------------------
if command -v apt >/dev/null 2>&1; then
    PKG="apt"
elif command -v yum >/dev/null 2>&1; then
    PKG="yum"
else
    echo "[-] Unsupported OS"
    exit 1
fi

# -----------------------------
# Install Apache & PHP
# -----------------------------
echo "[+] Installing Apache and PHP..."

if [ "$PKG" = "apt" ]; then
    sudo apt update
    sudo apt install -y apache2 php libapache2-mod-php
    WEB_ROOT="/var/www/html"
    SERVICE="apache2"
    USER="www-data"
else
    sudo yum install -y httpd php
    WEB_ROOT="/var/www/html"
    SERVICE="httpd"
    USER="apache"
fi

# -----------------------------
# Start ONLY Apache
# -----------------------------
sudo systemctl start $SERVICE
sudo systemctl enable $SERVICE

# -----------------------------
# Create lab directories
# -----------------------------
LAB_DIR="$WEB_ROOT/upload_lab"
UPLOAD_DIR="$LAB_DIR/uploads"

echo "[+] Creating lab directories..."
sudo mkdir -p $UPLOAD_DIR

# -----------------------------
# Create vulnerable PHP file
# -----------------------------
echo "[+] Creating vulnerable upload script..."

sudo tee $LAB_DIR/index.php > /dev/null << 'EOF'
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

    echo "<p style='color:green'>Uploaded: <a href='$upload_dir$name'>$upload_dir$name</a></p>";
}
?>

<!DOCTYPE html>
<html>
<head>
    <title>Vulnerable File Upload Lab</title>
</head>
<body>
<h2>🔥 File Upload Vulnerability Lab</h2>

<form method="POST" enctype="multipart/form-data">
    <input type="file" name="file">
    <br><br>
    <input type="submit" value="Upload">
</form>

<p><b>WARNING:</b> This lab is intentionally insecure.</p>
</body>
</html>
EOF

# -----------------------------
# Insecure permissions
# -----------------------------
echo "[+] Setting INSECURE permissions..."
sudo chmod -R 777 $LAB_DIR
sudo chown -R $USER:$USER $LAB_DIR

# -----------------------------
# Restart server
# -----------------------------
sudo systemctl restart $SERVICE

# -----------------------------
# Done
# -----------------------------
IP=$(hostname -I | awk '{print $1}')

echo ""
echo "[✓] VULNERABLE WEB LAB READY"
echo "[✓] Other web servers STOPPED"
echo "[✓] Access here:"
echo "    http://$IP/upload_lab/"
echo ""
echo "[!] DO NOT expose this machine to the internet"
