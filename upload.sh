#!/bin/bash

echo "[+] Starting vulnerable upload lab setup..."

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
else
    sudo yum install -y httpd php
    WEB_ROOT="/var/www/html"
    SERVICE="httpd"
fi

# -----------------------------
# Start & enable server
# -----------------------------
sudo systemctl start $SERVICE
sudo systemctl enable $SERVICE

# -----------------------------
# Create lab directory
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
    <title>File Upload Vulnerability Lab</title>
</head>
<body>
<h2>🔥 Vulnerable File Upload Lab</h2>

<form method="POST" enctype="multipart/form-data">
    <input type="file" name="file">
    <br><br>
    <input type="submit" value="Upload">
</form>

<p><b>Warning:</b> This lab is intentionally insecure.</p>
</body>
</html>
EOF

# -----------------------------
# Set permissions (INSECURE)
# -----------------------------
echo "[+] Setting insecure permissions..."
sudo chmod -R 777 $LAB_DIR
sudo chown -R www-data:www-data $LAB_DIR 2>/dev/null || sudo chown -R apache:apache $LAB_DIR

# -----------------------------
# Restart server
# -----------------------------
sudo systemctl restart $SERVICE

# -----------------------------
# Done
# -----------------------------
IP=$(hostname -I | awk '{print $1}')

echo ""
echo "[✓] VULNERABLE LAB INSTALLED SUCCESSFULLY"
echo "[✓] Open in browser:"
echo "    http://$IP/upload_lab/"
echo ""
echo "[!] DO NOT expose this server to the internet"
