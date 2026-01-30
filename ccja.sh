#!/bin/bash
set -e

echo "[+] Updating system"
apt update -y

echo "[+] Installing packages"
apt install -y apache2 php php-cli openssl sudo gcc

systemctl enable apache2
systemctl start apache2

# -------------------------
# USERS
# -------------------------
useradd -m raj
echo "raj:raj@123" | chpasswd

useradd -m admin
echo "admin:Admin@123" | chpasswd
usermod -aG sudo admin

# -------------------------
# FLAGS
# -------------------------
FLAG1="dwd23123434fe32f4v4412451gbgbsd"
FLAG2="a9f8e12c0b77de231aa9f0cde334ab91"
FLAG3="ee12cd98ab001ff923abcde7741ffed2"
FLAG4="9f00deadbeefaa001122334455667788"

# -------------------------
# WEBSITE SETUP
# -------------------------
WEBROOT="/var/www/html/corpshop"
mkdir -p $WEBROOT/{includes,assets,docs}

cat <<EOF > $WEBROOT/index.php
<?php include("includes/header.php"); ?>
<h2>Welcome to CorpShop</h2>
<p>Internal procurement portal.</p>
<ul>
<li><a href="products.php">Products</a></li>
<li><a href="login.php">Employee Login</a></li>
<li><a href="download.php?file=docs/price-list.txt">Download Price List</a></li>
</ul>
<?php include("includes/footer.php"); ?>
EOF

cat <<EOF > $WEBROOT/products.php
<?php include("includes/header.php"); ?>
<h2>Products</h2>
<ul>
<li><a href="product.php?page=includes/product1.php">Office Laptop</a></li>
<li><a href="product.php?page=includes/product2.php">Network Switch</a></li>
</ul>
<?php include("includes/footer.php"); ?>
EOF

cat <<EOF > $WEBROOT/product.php
<?php
include("includes/header.php");
if (isset(\$_GET['page'])) {
    include(\$_GET['page']); // LFI
}
include("includes/footer.php");
?>
EOF

cat <<EOF > $WEBROOT/download.php
<?php
if (isset(\$_GET['file'])) {
    echo "<pre>";
    echo file_get_contents(\$_GET['file']); // Path Traversal
    echo "</pre>";
}
?>
EOF

cat <<EOF > $WEBROOT/login.php
<?php include("includes/header.php"); ?>
<h2>Employee Login</h2>
<form method="POST">
Username: <input type="text"><br><br>
Password: <input type="password"><br><br>
<input type="submit" value="Login">
</form>
<p><i>Authentication system under maintenance.</i></p>
<?php include("includes/footer.php"); ?>
EOF

cat <<EOF > $WEBROOT/includes/header.php
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

cat <<EOF > $WEBROOT/includes/footer.php
<hr>
<p>© 2026 CorpShop Ltd.</p>
</body>
</html>
EOF

cat <<EOF > $WEBROOT/includes/product1.php
<h3>Office Laptop</h3>
<p>Standard employee laptop.</p>
EOF

cat <<EOF > $WEBROOT/includes/product2.php
<h3>Network Switch</h3>
<p>Corporate managed switch.</p>
EOF

cat <<EOF > $WEBROOT/includes/config.php
<?php
/*
 INTERNAL CONFIG FILE

 SSH Credentials:
 user: raj
 password: raj@123

 FLAG: $FLAG1
*/
?>
EOF

cat <<EOF > $WEBROOT/assets/style.css
body {
  font-family: Arial;
  background: #f4f4f4;
  padding: 20px;
}
h1 { color: #2c3e50; }
EOF

echo "Internal pricing document" > $WEBROOT/docs/price-list.txt

chown -R www-data:www-data /var/www/html
chmod -R 755 /var/www/html

# -------------------------
# RAJ FLAG
# -------------------------
echo "$FLAG2" > /home/raj/user.txt
chown raj:raj /home/raj/user.txt
chmod 600 /home/raj/user.txt

# -------------------------
# SUID (raj -> admin)
# -------------------------
cat <<EOF > /tmp/adminshell.c
#include <unistd.h>
int main(){
  setuid(1001);
  setgid(1001);
  execl("/bin/bash","bash",NULL);
  return 0;
}
EOF

gcc /tmp/adminshell.c -o /usr/local/bin/adminshell
chown admin:admin /usr/local/bin/adminshell
chmod 4755 /usr/local/bin/adminshell
rm /tmp/adminshell.c

# -------------------------
# ADMIN ENCRYPTED NOTE
# -------------------------
openssl rand -hex 16 > /home/admin/key.key

cat <<EOF > /tmp/root_note.txt
Root password was reset.
Temporary password stored in /tmp/ps.txt
EOF

openssl enc -aes-256-cbc -salt \
-in /tmp/root_note.txt \
-out /home/admin/root.enc \
-pass file:/home/admin/key.key

echo "Read root.enc using key.key" > /home/admin/note.txt
echo "FLAG: $FLAG3" >> /home/admin/note.txt

chown -R admin:admin /home/admin
chmod 700 /home/admin
chmod 600 /home/admin/*

# -------------------------
# ROOT ACCESS
# -------------------------
ROOTPASS="Root@987"
echo "$ROOTPASS" > /tmp/ps.txt
chmod 600 /tmp/ps.txt
echo "root:$ROOTPASS" | chpasswd

echo "$FLAG4" > /root/root.txt
chmod 600 /root/root.txt

echo "[+] CCJA LAB READY"
echo "Web: http://<IP>/corpshop/"
