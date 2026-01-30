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
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
  font-family: "Segoe UI", Tahoma, sans-serif;
}

body {
  background: linear-gradient(135deg, #0f2027, #203a43, #2c5364);
  color: #fff;
  min-height: 100vh;
}

/* Header */
header {
  background: rgba(0, 0, 0, 0.65);
  padding: 20px 0;
  box-shadow: 0 4px 15px rgba(0,0,0,0.4);
}

.header-inner {
  width: 90%;
  max-width: 1200px;
  margin: auto;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

header h1 {
  font-size: 1.8rem;
  letter-spacing: 1px;
}

nav a {
  color: #00e6e6;
  margin-left: 20px;
  text-decoration: none;
  font-weight: 600;
}

nav a:hover {
  opacity: 0.7;
}

/* Hero */
.hero {
  padding: 80px 20px;
  text-align: center;
}

.hero h2 {
  font-size: 2.5rem;
  margin-bottom: 10px;
}

/* Layout */
.container {
  width: 90%;
  max-width: 1200px;
  margin: 40px auto;
}

.card {
  background: rgba(255,255,255,0.12);
  backdrop-filter: blur(8px);
  padding: 30px;
  border-radius: 12px;
  box-shadow: 0 15px 35px rgba(0,0,0,0.35);
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 25px;
  margin-top: 30px;
}

footer {
  margin-top: 60px;
  padding: 20px;
  text-align: center;
  background: rgba(0,0,0,0.6);
  opacity: 0.8;
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
  <div class="header-inner">
    <h1>CorpShop</h1>
    <nav>
      <a href="?page=home.php">Home</a>
      <a href="?page=about.php">About</a>
      <a href="?page=contact.php">Contact</a>
      <a href="?page=services.php">Services</a>
      <a href="?page=employees.php">Employees</a>
      <a href="?page=docs.php">Docs</a>
      <a href="?page=admin.php">Admin</a>
    </nav>
  </div>
</header>

<section class="hero">
  <h2>CorpShop Internal Portal</h2>
  <p>Secure corporate shopping & administration platform</p>
</section>

<div class="container">
  <div class="card">
    <h2>Welcome</h2>
    <p>Internal company shopping and admin portal.</p>
    <p><b>Employees only.</b></p>
  </div>

  <div class="grid">
    <div class="card">
      <h3>Inventory</h3>
      <p>View internal stock and equipment.</p>
    </div>
    <div class="card">
      <h3>Orders</h3>
      <p>Process internal purchase requests.</p>
    </div>
    <div class="card">
      <h3>IT Services</h3>
      <p>Request support and system access.</p>
    </div>
  </div>
</div>

<footer>© 2026 CorpShop · Internal Use Only</footer>
</body>
</html>
EOF

# ---- Pages ----
cat <<EOF > $WEBROOT/home.php
<h2>Home</h2>
<p>Welcome employee. Please browse responsibly.</p>
EOF

cat <<EOF > $WEBROOT/services.php
<h2>Internal Services</h2>
<ul>
  <li>Procurement System</li>
  <li>Asset Management</li>
  <li>Internal Ticketing</li>
  <li>Finance Dashboard</li>
</ul>
<p><i>Access restricted based on department.</i></p>
EOF

cat <<EOF > $WEBROOT/employees.php
<h2>Employees</h2>
<table border="0" cellpadding="10">
<tr><td><b>Name</b></td><td><b>Department</b></td></tr>
<tr><td>Alice Morgan</td><td>Finance</td></tr>
<tr><td>John Carter</td><td>IT Support</td></tr>
<tr><td>Sarah Lee</td><td>Procurement</td></tr>
</table>
EOF

cat <<EOF > $WEBROOT/admin.php
<h2>Administration Panel</h2>
<p><b>Warning:</b> Restricted area.</p>
<p>Unauthorized access attempts are logged.</p>
<p style="color:#ffcccc;">Access denied.</p>
EOF

cat <<EOF > $WEBROOT/about.php
<h2>About</h2>
<p>CorpShop is an internal-only corporate service.</p>
EOF

cat <<EOF > $WEBROOT/contact.php
<h2>Contact</h2>
<p>IT Support: it-support@corp.local</p>
EOF

cat <<EOF > $WEBROOT/docs.php
<h2>System Status</h2>
<ul>
  <li>Web Portal: Online</li>
  <li>Database: Online</li>
  <li>Internal File Server: Online</li>
</ul>
<p>Last updated: <?php echo date("Y-m-d H:i"); ?></p>
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
cat <<EOF > $WEBROOT/breakinglink.php
<?php
// Internal testing credentials
// SSH access
// user: raj
// password: raj@123
// FLAG: FLAG{corp_shop_lfi_success}
?>
EOF

# ---------------------------
# /etc/passwd HINT
# ---------------------------

echo "[+] Adding hint in /etc/passwd"
sed -i '1i # corp-note: dev forgot creds in web somewhere in web ' /etc/passwd

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
    setgid($ADMIN_GID);
    setuid($ADMIN_UID);
    execl("/bin/bash", "bash", "-p", NULL);
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
chmod 600 /tmp/ps.txt

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
