#!/bin/bash
set -e

echo "[+] Updating system"
apt update -y

echo "[+] Installing required packages"
apt install -y \
  apache2 \
  php \
  libapache2-mod-php \
  php-cli \
  openssl \
  sudo \
  gcc \
  unzip

echo "[+] Enabling Apache"
systemctl unmask apache2
systemctl enable apache2
systemctl restart apache2

# ---------------------------
# USERS SETUP
# ---------------------------

echo "[+] Creating users"

id raj &>/dev/null || useradd -m raj
echo "raj:raj@123" | chpasswd

id admin &>/dev/null || useradd -m admin
echo "admin:Admin@123" | chpasswd

usermod -aG sudo admin

# ---------------------------
# FLAGS
# ---------------------------

FLAG1="dwd23123434fe32f4v4412451gbgbsd"
FLAG2="a9f8e12c0b77de231aa9f0cde334ab91"
FLAG3="ee12cd98ab001ff923abcde7741ffed2"
FLAG4="9f00deadbeefaa001122334455667788"

# ---------------------------
# WEB APP (VULNERABLE + PRETTY)
# ---------------------------

echo "[+] Setting up vulnerable web app"

WEBROOT="/var/www/html/shop"
mkdir -p "$WEBROOT/assets"
chown -R www-data:www-data /var/www/html
chmod -R 755 /var/www/html

# ---- CSS ----
cat <<EOF > $WEBROOT/assets/style.css
body {
  background: linear-gradient(135deg, #0f2027, #203a43, #2c5364);
  font-family: Arial, sans-serif;
  color: #fff;
  margin: 0;
}
header {
  background: rgba(0,0,0,0.6);
  padding: 20px;
  text-align: center;
}
nav a {
  color: #00e6e6;
  margin: 0 15px;
  text-decoration: none;
  font-weight: bold;
}
.container {
  padding: 40px;
}
.card {
  background: rgba(255,255,255,0.1);
  padding: 25px;
  border-radius: 10px;
  width: 60%;
}
footer {
  text-align: center;
  padding: 20px;
  opacity: 0.6;
}
EOF

# ---- index.php (LFI include) ----
cat <<EOF > $WEBROOT/index.php
<?php
if (isset(\$_GET['page'])) {
    include(\$_GET['page']);
    exit;
}
?>
<!DOCTYPE html>
<html>
<head>
  <title>CorpShop</title>
  <link rel="stylesheet" href="assets/style.css">
</head>
<body>
<header>
  <h1>CorpShop Internal Portal</h1>
  <nav>
    <a href="?page=home.php">Home</a>
    <a href="?page=about.php">About</a>
    <a href="?page=contact.php">Contact</a>
  </nav>
</header>

<div class="container">
  <div class="card">
    <h2>Welcome</h2>
    <p>Internal company shopping and admin portal.</p>
    <p><b>Employees only.</b></p>
  </div>
</div>

<footer>© 2026 CorpShop</footer>
</body>
</html>
EOF

# ---- other pages ----
cat <<EOF > $WEBROOT/home.php
<h2>Home</h2>
<p>Welcome employee. Please browse responsibly.</p>
EOF

cat <<EOF > $WEBROOT/about.php
<h2>About</h2>
<p>CorpShop is an internal-only corporate service.</p>
EOF

cat <<EOF > $WEBROOT/contact.php
<h2>Contact</h2>
<p>IT Support: it-support@corp.local</p>
EOF

# ---- view.php (file read vuln) ----
cat <<EOF > $WEBROOT/view.php
<?php
if (isset(\$_GET['file'])) {
    echo file_get_contents(\$_GET['file']);
}
?>
EOF

# ---- config.php (FLAG1) ----
cat <<EOF > $WEBROOT/config.php
<?php
// Internal testing credentials
// SSH access
// user: raj
// password: raj@123
// FLAG: $FLAG1
?>
EOF

# ---------------------------
# /etc/passwd HINT
# ---------------------------

echo "[+] Adding hint in /etc/passwd"
sed -i '1i # corp-note: dev forgot creds in web config' /etc/passwd

# ---------------------------
# RAJ FLAG
# ---------------------------

echo "[+] Setting raj environment"
echo "$FLAG2" > /home/raj/user.txt
chown raj:raj /home/raj/user.txt
chmod 600 /home/raj/user.txt

# ---------------------------
# SUID BINARY (raj -> admin)
# ---------------------------

echo "[+] Creating SUID binary"

ADMIN_UID=$(id -u admin)
ADMIN_GID=$(id -g admin)

cat <<EOF > /tmp/suid_admin.c
#include <unistd.h>
int main() {
    setuid($ADMIN_UID);
    setgid($ADMIN_GID);
    execl("/bin/bash", "bash", NULL);
    return 0;
}
EOF

gcc /tmp/suid_admin.c -o /usr/local/bin/adminshell
chown admin:admin /usr/local/bin/adminshell
chmod 4755 /usr/local/bin/adminshell
rm /tmp/suid_admin.c

# ---------------------------
# ADMIN ENCRYPTED NOTE
# ---------------------------

echo "[+] Creating encrypted admin message"

ADMIN_DIR="/home/admin"
mkdir -p "$ADMIN_DIR"

KEY_FILE="$ADMIN_DIR/key.key"
NOTE_FILE="$ADMIN_DIR/note.txt"
ENC_FILE="$ADMIN_DIR/root.enc"

openssl rand -hex 16 > "$KEY_FILE"

cat <<EOF > /tmp/root_note.txt
hey admin the root user on server
is having some issue so we
have reset the password
the password is stored at
/tmp/ps.txt
EOF

openssl enc -aes-256-cbc -pbkdf2 -salt \
  -in /tmp/root_note.txt \
  -out "$ENC_FILE" \
  -pass file:"$KEY_FILE"

rm /tmp/root_note.txt

echo "Encrypted note: root.enc" > "$NOTE_FILE"
echo "Key location: key.key" >> "$NOTE_FILE"
echo "FLAG: $FLAG3" >> "$NOTE_FILE"

chown -R admin:admin /home/admin
chmod 700 /home/admin
find /home/admin -type f -exec chmod 600 {} \;

# ---------------------------
# ROOT PASSWORD DROP
# ---------------------------

echo "[+] Creating root password file"

ROOTPASS="Root@987"
echo "$ROOTPASS" > /tmp/ps.txt
chmod 600 /tmp/ps.txt
echo "root:$ROOTPASS" | chpasswd

echo "$FLAG4" > /root/root.txt
chmod 600 /root/root.txt

# ---------------------------
# FINISH
# ---------------------------

echo
echo "======================================"
echo " CCJA EXAM LAB READY "
echo "======================================"
echo " Web : http://<IP>/shop/"
echo " SSH : raj / raj@123"
echo " SUID: /usr/local/bin/adminshell"
echo "======================================"
