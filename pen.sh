#!/bin/bash

echo "[+] Updating system..."
apt update -y

echo "[+] Installing required packages..."
apt install -y apache2 php libapache2-mod-php samba openssh-server vsftpd

#################################################
# 1️⃣ FTP SETUP
#################################################

echo "[+] Setting up FTP..."

useradd -m ftpuser
echo "ftpuser:ftp123" | chpasswd

echo "nothing here" > /home/ftpuser/imp.txt
chown ftpuser:ftpuser /home/ftpuser/imp.txt

cat <<EOF > /etc/vsftpd.conf
listen=YES
anonymous_enable=NO
local_enable=YES
write_enable=YES
chroot_local_user=YES
allow_writeable_chroot=YES
EOF

systemctl restart vsftpd

#################################################
# 2️⃣ WEAK SSH USER
#################################################

echo "[+] Creating weak SSH user..."

useradd -m weakuser
echo "weakuser:password123" | chpasswd

sed -i 's/#PasswordAuthentication yes/PasswordAuthentication yes/' /etc/ssh/sshd_config
systemctl restart ssh

#################################################
# 3️⃣ SMB VULNERABLE SHARE
#################################################

echo "[+] Setting up SMB share..."

mkdir -p /srv/smbshare
chmod 777 /srv/smbshare
echo "flag{smb_vulnerable}" > /srv/smbshare/flag.txt

cat <<EOF >> /etc/samba/smb.conf

[pentestshare]
   path = /srv/smbshare
   browsable = yes
   writable = yes
   guest ok = yes
   read only = no
EOF

systemctl restart smbd

#################################################
# 4️⃣ PROFESSIONAL WEB APP
#################################################

echo "[+] Setting up professional vulnerable web app..."

mkdir -p /var/www/html/assets
mkdir -p /var/www/html/pages

################ CSS ################

cat <<EOF > /var/www/html/assets/style.css
body {
    margin: 0;
    font-family: 'Segoe UI', sans-serif;
    background: #0f172a;
    color: #e2e8f0;
}
header {
    background: #1e293b;
    padding: 20px;
    text-align: center;
}
header h1 {
    margin: 0;
    color: #38bdf8;
}
nav {
    background: #0f172a;
    padding: 15px;
    text-align: center;
}
nav a {
    color: #e2e8f0;
    text-decoration: none;
    margin: 0 20px;
    font-weight: bold;
}
nav a:hover {
    color: #38bdf8;
}
.container {
    padding: 40px;
    max-width: 1000px;
    margin: auto;
}
.card {
    background: #1e293b;
    padding: 25px;
    border-radius: 8px;
    margin-bottom: 20px;
    box-shadow: 0 0 10px rgba(0,0,0,0.5);
}
button {
    background: #38bdf8;
    border: none;
    padding: 10px 20px;
    color: #000;
    font-weight: bold;
    border-radius: 5px;
    cursor: pointer;
}
button:hover {
    background: #0ea5e9;
}
footer {
    background: #1e293b;
    text-align: center;
    padding: 20px;
    margin-top: 40px;
    color: #94a3b8;
}
EOF

################ HEADER TEMPLATE ################

cat <<EOF > /var/www/html/pages/header.php
<!DOCTYPE html>
<html>
<head>
    <title>Pentest Lab Portal</title>
    <link rel="stylesheet" href="/assets/style.css">
</head>
<body>
<header>
    <h1>Pentest Corporate Portal</h1>
</header>
<nav>
    <a href="/index.php">Home</a>
    <a href="/resources.php?preview=home">Resources</a>
    <a href="/resources.php?preview=about">About</a>
    <a href="/resources.php?preview=contact">Contact</a>
</nav>
<div class="container">
EOF

################ FOOTER ################

cat <<EOF > /var/www/html/pages/footer.php
</div>
<footer>
    © 2026 Pentest Corporation. All rights reserved.
</footer>
</body>
</html>
EOF

################ INDEX ################

cat <<EOF > /var/www/html/index.php
<?php include("pages/header.php"); ?>
<div class="card">
<h2>Welcome to Pentest Corporate Portal</h2>
<p>This internal platform provides secure employee resources and documentation.</p>
</div>
<?php include("pages/footer.php"); ?>
EOF

################ NORMAL PAGES ################

cat <<EOF > /var/www/html/pages/home.php
<div class="card">
<h2>Employee Resources</h2>
<p>Access training materials and internal documentation.</p>
</div>
EOF

cat <<EOF > /var/www/html/pages/about.php
<div class="card">
<h2>About Company</h2>
<p>We are a cybersecurity research and consulting company.</p>
</div>
EOF

cat <<EOF > /var/www/html/pages/contact.php
<div class="card">
<h2>Contact Us</h2>
<p>Email: admin@pentest.local</p>
</div>
EOF

cat <<EOF > /var/www/html/pages/js-fundamental.php
<div class="card">
<h2>JS Fundamentals</h2>
<p>Learn JavaScript basics here.</p>
</div>
EOF

cat <<EOF > /var/www/html/pages/admin.php
<div class="card">
<h2>Admin Panel</h2>
<p>Restricted access area.</p>
</div>
EOF

echo "flag{lfi_master}" > /var/www/html/pages/secret.txt

################ LFI VULNERABLE FILE ################

cat <<EOF > /var/www/html/resources.php
<?php
include("pages/header.php");
if(isset(\$_GET['preview'])){
    include("pages/" . \$_GET['preview'] . ".php");
} else {
    echo "<div class='card'><h2>No file selected</h2></div>";
}
include("pages/footer.php");
?>
EOF

################ DIRECTORY TRAVERSAL ################

cat <<EOF > /var/www/html/download.php
<?php
if(isset(\$_GET['file'])){
    readfile(\$_GET['file']);
}
?>
EOF

systemctl restart apache2

#################################################

echo ""
echo "🔥 PENTEST LAB READY 🔥"
echo "FTP: ftpuser / ftp123"
echo "SSH: weakuser / password123"
echo "SMB Share: pentestshare (guest access)"
echo ""
echo "Web:"
echo "http://localhost"
echo "LFI Example:"
echo "http://localhost/resources.php?preview=../../../../etc/passwd"
echo ""
echo "php filter bypass:"
echo "http://localhost/resources.php?preview=php://filter/convert.base64-encode/resource=resources"
echo ""
echo "Directory traversal:"
echo "http://localhost/download.php?file=../../etc/passwd"
echo ""
echo "⚠️ Use inside isolated VM only!"
