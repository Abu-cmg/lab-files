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
# WEB APP (VULNERABLE)
# ---------------------------

echo "[+] Setting up vulnerable web app"

mkdir -p /var/www/html/shop
chown -R www-data:www-data /var/www/html
chmod -R 755 /var/www/html

cat <<EOF > /var/www/html/shop/index.php
<?php
if (isset(\$_GET['page'])) {
    include(\$_GET['page']);
} else {
    echo "<h1>Welcome to CorpShop</h1>";
}
?>
EOF

cat <<EOF > /var/www/html/shop/view.php
<?php
if (isset(\$_GET['file'])) {
    echo file_get_contents(\$_GET['file']);
}
?>
EOF

cat <<EOF > /var/www/html/shop/config.php
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
KEY_FILE="\$ADMIN_DIR/key.key"
NOTE_FILE="\$ADMIN_DIR/note.txt"
ENC_FILE="\$ADMIN_DIR/root.enc"

openssl rand -hex 16 > "\$KEY_FILE"

cat <<EOF > /tmp/root_note.txt
hey admin the root user on server
is having some issue so we
have reset the password
the password is stored at
/tmp/ps.txt
EOF

openssl enc -aes-256-cbc -pbkdf2 -salt \
  -in /tmp/root_note.txt \
  -out "\$ENC_FILE" \
  -pass file:"\$KEY_FILE"

rm /tmp/root_note.txt

echo "Encrypted note: root.enc" > "\$NOTE_FILE"
echo "Key location: key.key" >> "\$NOTE_FILE"
echo "FLAG: $FLAG3" >> "\$NOTE_FILE"

chown -R admin:admin /home/admin
chmod 700 /home/admin
chmod 600 /home/admin/*

# ---------------------------
# ROOT PASSWORD DROP
# ---------------------------

echo "[+] Creating root password file"

ROOTPASS="Root@987"
echo "\$ROOTPASS" > /tmp/ps.txt
chmod 600 /tmp/ps.txt
echo "root:\$ROOTPASS" | chpasswd

echo "$FLAG4" > /root/root.txt
chmod 600 /root/root.txt

# ---------------------------
# CLEANUP
# ---------------------------

echo "[+] Cleaning history"
history -c || true

echo
echo "======================================"
echo " CCJA EXAM LAB READY "
echo "======================================"
echo " Web : http://<IP>/shop/"
echo " SSH : raj / raj@123"
echo " SUID: /usr/local/bin/adminshell"
echo "======================================"
