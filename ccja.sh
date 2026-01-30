#!/bin/bash
set -e
echo "[+] Unmasking required services..."

systemctl unmask apache2 2>/dev/null || true
systemctl enable apache2
systemctl start apache2

echo "[+] Updating system"

echo "[+] Installing packages"
sudo apt install -y apache2 php php-cli openssl gcc sudo

echo "[+] Enabling Apache"
sudo systemctl enable apache2
sudo systemctl start apache2

# =========================
# USERS
# =========================

echo "[+] Creating users"

sudo useradd -m raj || true
echo "raj:raj@123" | sudo chpasswd

sudo useradd -m admin || true
echo "admin:Admin@123" | sudo chpasswd
sudo usermod -aG sudo admin

# =========================
# FLAGS
# =========================

FLAG1="dwd23123434fe32f4v4412451gbgbsd"
FLAG2="a9f8e12c0b77de231aa9f0cde334ab91"
FLAG3="ee12cd98ab001ff923abcde7741ffed2"
FLAG4="9f00deadbeefaa001122334455667788"

# =========================
# WEBSITE STRUCTURE
# =========================

echo "[+] Creating CorpShop website"

sudo mkdir -p /var/www/html/corpshop/{includes,assets,docs}

sudo chown -R www-data:www-data /var/www/html/corpshop
sudo chmod -R 755 /var/www/html/corpshop

# =========================
# WEBSITE FILES
# =========================

# index.php
sudo tee /var/www/html/corpshop/index.php > /dev/null <<EOF
<?php include("includes/header.php"); ?>
<h2>Welcome to CorpShop</h2>
<p>Internal procurement portal for employees.</p>
<ul>
  <li><a href="products.php">View Products</a></li>
  <li><a href="login.php">Employee Login</a></li>
  <li><a href="download.php?file=docs/price-list.txt">Download Price List</a></li>
</ul>
<?php include("includes/footer.php"); ?>
EOF

# products.php
sudo tee /var/www/html/corpshop/products.php > /dev/null <<EOF
<?php include("includes/header.php"); ?>
<h2>Available Products</h2>
<ul>
  <li><a href="product.php?page=includes/product1.php">Office Laptop</a></li>
  <li><a href="product.php?page=includes/product2.php">Network Switch</a></li>
</ul>
<?php include("includes/footer.php"); ?>
EOF

# product.php (LFI)
sudo tee /var/www/html/corpshop/product.php > /dev/null <<EOF
<?php
include("includes/header.php");
if (isset(\$_GET['page'])) {
    include(\$_GET['page']); // LFI
} else {
    echo "Product not found.";
}
include("includes/footer.php");
?>
EOF

# download.php (Path Traversal)
sudo tee /var/www/html/corpshop/download.php > /dev/null <<EOF
<?php
if (isset(\$_GET['file'])) {
    echo "<pre>";
    echo file_get_contents(\$_GET['file']); // Path Traversal
    echo "</pre>";
}
?>
EOF

# login.php
sudo tee /var/www/html/corpshop/login.php > /dev/null <<EOF
<?php include("includes/header.php"); ?>
<h2>Employee Login</h2>
<form method="POST">
Username: <input type="text"><br><br>
Password: <input type="password"><br><br>
<input type="submit" value="Login">
</form>
<p><i>Authentication service under maintenance.</i></p>
<?php include("includes/footer.php"); ?>
EOF

# header.php
sudo tee /var/www/html/corpshop/includes/header.php > /dev/null <<EOF
<!DOCTYPE html>
<html>
<head>
<title>CorpShop</title>
<link rel="stylesheet" href="assets/style.css">
</head>
<body>
<hr>
<h1>CorpShop Internal Portal</h1>
<hr>
EOF

# footer.php
sudo tee /var/www/html/corpshop/includes/footer.php > /dev/null <<EOF
<hr>
<p>© 2026 CorpShop Ltd. Internal Use Only.</p>
</body>
</html>
EOF

# products
sudo tee /var/www/html/corpshop/includes/product1.php > /dev/null <<EOF
<h3>Office Laptop</h3>
<p>Standard issue laptop for employees.</p>
EOF

sudo tee /var/www/html/corpshop/includes/product2.php > /dev/null <<EOF
<h3>Network Switch</h3>
<p>Managed switch for corporate network.</p>
EOF

# config.php (LEAK TARGET)
sudo tee /var/www/html/corpshop/includes/config.php > /dev/null <<EOF
<?php
/*
 INTERNAL CONFIG FILE
 SSH Credentials (temporary):
 user: raj
 password: raj@123

 FLAG: $FLAG1
*/
?>
EOF

# CSS
sudo tee /var/www/html/corpshop/assets/style.css > /dev/null <<EOF
body { font-family: Arial; background:#f4f4f4; padding:20px; }
h1 { color:#2c3e50; }
EOF

# price list
sudo tee /var/www/html/corpshop/docs/price-list.txt > /dev/null <<EOF
CorpShop Internal Pricing
Laptop - Confidential
Switch - Confidential
EOF

# =========================
# RAJ FLAG
# =========================

echo "[+] Setting raj flag"
echo "$FLAG2" | sudo tee /home/raj/user.txt > /dev/null
sudo chown raj:raj /home/raj/user.txt
sudo chmod 600 /home/raj/user.txt

# =========================
# SUID BINARY (raj → admin)
# =========================

echo "[+] Creating SUID admin shell"

sudo tee /tmp/adminshell.c > /dev/null <<EOF
#include <unistd.h>
int main() {
  setuid(1001);
  setgid(1001);
  execl("/bin/bash", "bash", NULL);
  return 0;
}
EOF

sudo gcc /tmp/adminshell.c -o /usr/local/bin/adminshell
sudo chown admin:admin /usr/local/bin/adminshell
sudo chmod 4755 /usr/local/bin/adminshell
sudo rm /tmp/adminshell.c

# =========================
# ADMIN → ROOT ESCALATION
# =========================

echo "[+] Creating admin encrypted note"

sudo openssl rand -hex 16 | sudo tee /home/admin/key.key > /dev/null

sudo tee /tmp/root_note.txt > /dev/null <<EOF
hey admin the root user on server
is having some issue so we
have reset the password
the password is stored at
/tmp/ps.txt
EOF

sudo openssl enc -aes-256-cbc -salt \
-in /tmp/root_note.txt \
-out /home/admin/root.enc \
-pass file:/home/admin/key.key

sudo tee /home/admin/note.txt > /dev/null <<EOF
Encrypted note: root.enc
Key location: key.key
FLAG: $FLAG3
EOF

sudo chown -R admin:admin /home/admin
sudo chmod 700 /home/admin
sudo chmod 600 /home/admin/*

sudo rm /tmp/root_note.txt

# =========================
# ROOT FINAL
# =========================

echo "[+] Setting root password and final flag"

echo "Root@987" | sudo tee /tmp/ps.txt > /dev/null
sudo chmod 600 /tmp/ps.txt
echo "root:Root@987" | sudo chpasswd

echo "$FLAG4" | sudo tee /root/root.txt > /dev/null
sudo chmod 600 /root/root.txt

# =========================
# DONE
# =========================

echo
echo "========================================"
echo " CCJA MULTI-PAGE EXAM LAB READY "
echo "========================================"
echo " Web  : http://<IP>/corpshop/"
echo " SSH  : raj / raj@123"
echo " SUID : /usr/local/bin/adminshell"
echo "========================================"
