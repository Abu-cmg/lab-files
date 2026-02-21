#!/bin/bash

echo "[+] Updating system..."
apt update -y

echo "[+] Installing Apache, PHP, SSH..."
apt install apache2 php libapache2-mod-php openssh-server sudo -y

systemctl unmask apache2
systemctl enable apache2
systemctl start apache2

systemctl enable ssh
systemctl start ssh

echo "[+] Creating SSH user..."
useradd -m developer
echo "developer:Dev@123Secure" | chpasswd

echo "[+] Creating user flag..."
echo "FLAG{USER_ACCESS_GRANTED}" > /home/developer/user.txt
chown developer:developer /home/developer/user.txt
chmod 600 /home/developer/user.txt

echo "[+] Creating root flag..."
echo "FLAG{ROOT_ACCESS_COMPLETE}" > /root/root.txt
chmod 600 /root/root.txt

echo "[+] Adding sudo misconfiguration..."
echo "developer ALL=(ALL) NOPASSWD: /usr/bin/find" >> /etc/sudoers

echo "[+] Creating web structure..."
mkdir -p /var/www/html/assets
mkdir -p /var/www/html/pages

########################################
# FTP SETUP (ANONYMOUS ENABLED)
########################################

echo "[+] Installing vsftpd..."
apt install vsftpd -y

echo "[+] Creating FTP directory..."
mkdir -p /srv/ftp
chmod 777 /srv/ftp

echo "FLAG{FTP_ANONYMOUS_LOGIN_SUCCESS}" > /srv/ftp/ftp_flag.txt
chmod 644 /srv/ftp/ftp_flag.txt

echo "[+] Configuring vsftpd for anonymous login..."

cat > /etc/vsftpd.conf <<'EOF'
listen=YES
listen_ipv6=NO

anonymous_enable=YES
local_enable=YES
write_enable=YES

anon_root=/srv/ftp

anon_upload_enable=YES
anon_mkdir_write_enable=YES
anon_other_write_enable=YES

no_anon_password=YES
hide_ids=YES

dirmessage_enable=YES
use_localtime=YES
xferlog_enable=YES

connect_from_port_20=YES

secure_chroot_dir=/var/run/vsftpd/empty

pam_service_name=vsftpd

pasv_enable=YES
pasv_min_port=40000
pasv_max_port=40100
EOF

echo "[+] Restarting FTP service..."
systemctl restart vsftpd
systemctl enable vsftpd

echo "[+] FTP Anonymous setup complete."
########################################
# INDEX
########################################
cat > /var/www/html/index.php <<'EOF'
<?php include("header.php"); ?>
<div class="card">
<h2>Welcome to Pentest Corporate Portal</h2>
<p>Internal documentation portal for staff training.</p>
<p>Please use the navigation menu.</p>
</div>
<?php include("footer.php"); ?>
EOF

########################################
# HEADER
########################################
cat > /var/www/html/header.php <<'EOF'
<!DOCTYPE html>
<html>
<head>
<title>Pentest Corporate Portal</title>
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

########################################
# FOOTER
########################################
cat > /var/www/html/footer.php <<'EOF'
</div>
<footer>
© 2026 Pentest Corporation
</footer>
</body>
</html>
EOF

########################################
# VULNERABLE FILE
########################################
cat > /var/www/html/resources.php <<'EOF'
<?php
include("header.php");

$valid = false;

if(isset($_GET['preview'])) {
    $file = $_GET['preview'];
    $allowed = array("home","about","contact","training");

    if(in_array($file,$allowed)) {
        include("pages/".$file.".php");
        $valid = true;
    } else {
        http_response_code(404);
        echo "<div class='card'><h2>Page Not Found</h2></div>";
        $valid = true;
    }
}

if(isset($_GET['doc'])) {
    $file = $_GET['doc'];
    include($file);   // INTENTIONAL LFI
    $valid = true;
}

if(!$valid){
    http_response_code(404);
    echo "<div class='card'><h2>Invalid Request</h2></div>";
}

include("footer.php");
?>
EOF

########################################
# HIDDEN CONFIG WITH SSH CREDS
########################################
cat > /var/www/html/config.php <<'EOF'
<?php
$flag = "FLAG{LFI_SOURCE_DISCOVERED}";

$db_user = "corp_user";
$db_pass = "CorpPass@2026";

// SSH Backup Credentials
$ssh_user = "developer";
$ssh_pass = "Dev@123Secure";
?>
EOF

########################################
# PAGES
########################################
cat > /var/www/html/pages/home.php <<'EOF'
<div class="card">
<h2>Company Home</h2>
<p>Internal documentation available.</p>
</div>
EOF

cat > /var/www/html/pages/about.php <<'EOF'
<div class="card">
<h2>About Us</h2>
<p>Cybersecurity and enterprise defense specialists.</p>
</div>
EOF

cat > /var/www/html/pages/contact.php <<'EOF'
<div class="card">
<h2>Contact</h2>
<p>Email: support@pentestcorp.local</p>
</div>
EOF

cat > /var/www/html/pages/training.php <<'EOF'
<div class="card">
<h2>Training Portal</h2>
<p>Advanced internal staff training modules.</p>
</div>
EOF

########################################
# CSS
########################################
cat > /var/www/html/assets/style.css <<'EOF'
body {
    font-family: Arial;
    margin: 0;
    background: linear-gradient(120deg,#141e30,#243b55);
    color: white;
}
header {
    background: #111;
    padding: 20px;
    text-align: center;
}
nav {
    background: #222;
    padding: 10px;
    text-align: center;
}
nav a {
    color: white;
    margin: 0 15px;
    text-decoration: none;
    font-weight: bold;
}
nav a:hover {
    color: #00ffcc;
}
.container {
    padding: 40px;
}
.card {
    background: rgba(0,0,0,0.7);
    padding: 25px;
    border-radius: 10px;
    box-shadow: 0 0 15px black;
}
footer {
    text-align: center;
    padding: 15px;
    background: #111;
}
EOF

########################################
# PERMISSIONS
########################################
chown -R www-data:www-data /var/www/html
chmod -R 755 /var/www/html

systemctl restart apache2

echo ""
echo "======================================"
echo " LAB READY"
echo " Target: http://SERVER-IP/"
echo ""
echo " FLAGS:"
echo " 1) LFI flag inside config.php"
echo " 2) user.txt in developer home"
echo " 3) root.txt via privesc"
echo ""
echo " SSH USER:"
echo " developer : Dev@123Secure"
echo ""
echo " SUDO MISCONFIG:"
echo " developer can run find as root"
echo "======================================"
