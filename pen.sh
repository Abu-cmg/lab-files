#!/bin/bash

echo "[+] Updating system..."
apt update -y

echo "[+] Installing Apache & PHP..."
apt install -y apache2 php libapache2-mod-php

echo "[+] Installing build tools..."
apt install -y build-essential wget unzip

echo "[+] Installing SMB..."
apt install -y samba

echo "[+] Installing Hydra + wordlists..."

echo "[+] Installing vulnerable VSFTPD 2.3.4..."

cd /tmp
wget https://security.appspot.com/downloads/vsftpd-2.3.4.tar.gz
tar -xvzf vsftpd-2.3.4.tar.gz
cd vsftpd-2.3.4

make
cp vsftpd /usr/local/sbin/vsftpd

mkdir -p /etc/vsftpd
cat <<EOF > /etc/vsftpd.conf
listen=YES
anonymous_enable=NO
local_enable=YES
write_enable=YES
local_umask=022
background=NO
EOF

echo "[+] Creating FTP user..."
useradd -m ftpuser
echo "ftpuser:ftp123" | chpasswd

echo "nothing here" > /home/ftpuser/imp.txt
chmod 777 /home/ftpuser/imp.txt

echo "[+] Starting vulnerable VSFTPD..."
/usr/local/sbin/vsftpd /etc/vsftpd.conf &

echo "[+] Configuring SMB vulnerable share..."
mkdir -p /srv/smbshare
chmod 777 /srv/smbshare
echo "SMB SECRET FLAG" > /srv/smbshare/flag.txt

cat <<EOF >> /etc/samba/smb.conf

[share]
   path = /srv/smbshare
   browsable = yes
   writable = yes
   guest ok = yes
   read only = no
EOF

systemctl restart smbd

echo "[+] Creating weak SSH user..."
useradd -m weakuser
echo "weakuser:password123" | chpasswd

echo "[+] Setting up vulnerable web app..."
echo "[+] Unmasking and starting Apache..."

systemctl unmask apache2
systemctl enable apache2
systemctl start apache2
mkdir -p /var/www/html/assets
mkdir -p /var/www/html/pages

# CSS
cat <<EOF > /var/www/html/assets/style.css
body {background:#0f172a;color:#e2e8f0;font-family:Segoe UI;margin:0}
header{background:#1e293b;padding:20px;text-align:center}
nav{background:#0f172a;padding:15px;text-align:center}
nav a{color:#e2e8f0;margin:15px;text-decoration:none}
nav a:hover{color:#38bdf8}
.container{padding:40px}
.card{background:#1e293b;padding:20px;border-radius:8px;margin-bottom:20px}
footer{background:#1e293b;text-align:center;padding:20px;margin-top:40px}
EOF

# index.php
cat <<EOF > /var/www/html/index.php
<!DOCTYPE html>
<html>
<head>
<title>Pentest Corp Portal</title>
<link rel="stylesheet" href="/assets/style.css">
</head>
<body>
<header><h1>Pentest Corporation</h1></header>
<nav>
<a href="/index.php">Home</a>
<a href="/resources.php?preview=pages/home.php">Resources</a>
<a href="/resources.php?preview=pages/about.php">About</a>
<a href="/resources.php?preview=pages/contact.php">Contact</a>
<a href="/resources.php?preview=pages/devops.php">DevOps</a>
</nav>
<div class="container">
<div class="card">
<h2>Welcome</h2>
<p>Internal Training Portal</p>
</div>
</div>
<footer>© 2026 Pentest Corp</footer>
</body>
</html>
EOF

# LFI vulnerable resources.php
cat <<EOF > /var/www/html/resources.php
<?php
if(isset(\$_GET['preview'])) {
    \$file = \$_GET['preview'];
    if(strpos(\$file,"http")!==false){die("Remote include blocked");}
    include(\$file);
} else {
    include("pages/home.php");
}
?>
EOF

# Directory traversal vuln
cat <<EOF > /var/www/html/download.php
<?php
if(isset(\$_GET['file'])) {
    \$file = "pages/".$_GET['file'];
    if(file_exists(\$file)){
        echo file_get_contents(\$file);
    } else {
        echo "File not found";
    }
}
?>
EOF

# Pages
for page in home about contact devops finance roadmap hr js-fundamental
do
cat <<EOF > /var/www/html/pages/$page.php
<div class="container">
<div class="card">
<h2>$page</h2>
<p>Internal documentation for $page department.</p>
</div>
</div>
EOF
done

# Hidden admin page
cat <<EOF > /var/www/html/pages/admin.php
<div class="container">
<div class="card">
<h2>Admin Panel</h2>
<p>DB Password: root:SuperSecretPass</p>
</div>
</div>
EOF

echo "FLAG{LFI_SUCCESS}" > /var/www/html/pages/secret.txt

chown -R www-data:www-data /var/www/html
chmod -R 755 /var/www/html

systemctl unmask apache2
systemctl enable apache2
systemctl restart apache2

echo ""
echo "====================================="
echo " Lab Setup Complete!"
echo "====================================="
echo "FTP  : ftpuser / ftp123"
echo "SSH  : weakuser / password123"
echo "SMB  : //target-ip/share (guest)"
echo "Web  : http://target-ip"
echo "FLAG : via LFI secret.txt"
echo "====================================="
