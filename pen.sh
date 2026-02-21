#!/bin/bash

echo "[+] Updating system..."
apt update -y

echo "[+] Installing packages..."
apt install -y apache2 php libapache2-mod-php build-essential wget samba hydra wordlists unzip

gunzip -f /usr/share/wordlists/rockyou.txt.gz 2>/dev/null

#################################################
# VULNERABLE VSFTPD 2.3.4
#################################################

cd /tmp
wget https://security.appspot.com/downloads/vsftpd-2.3.4.tar.gz
tar -xzf vsftpd-2.3.4.tar.gz
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

useradd -m ftpuser
echo "ftpuser:ftp123" | chpasswd
echo "nothing here" > /home/ftpuser/imp.txt
chmod 777 /home/ftpuser/imp.txt

/usr/local/sbin/vsftpd /etc/vsftpd.conf &

#################################################
# SMB SHARE
#################################################

mkdir -p /srv/smbshare
chmod 777 /srv/smbshare
echo "FLAG{SMB_PWNED}" > /srv/smbshare/flag.txt

cat <<EOF >> /etc/samba/smb.conf

[share]
   path = /srv/smbshare
   browsable = yes
   writable = yes
   guest ok = yes
   read only = no
EOF

systemctl restart smbd

#################################################
# WEAK SSH USER
#################################################

useradd -m weakuser
echo "weakuser:password123" | chpasswd

#################################################
# WEB APP WITH PROFESSIONAL DESIGN
#################################################

mkdir -p /var/www/html/assets
mkdir -p /var/www/html/pages

################ CSS ################

cat <<EOF > /var/www/html/assets/style.css
*{margin:0;padding:0;box-sizing:border-box}

body{
background:linear-gradient(135deg,#0f172a,#1e293b);
color:#e2e8f0;
font-family:'Segoe UI',sans-serif;
}

header{
background:rgba(30,41,59,0.9);
padding:25px;
text-align:center;
backdrop-filter:blur(8px);
border-bottom:1px solid #334155;
}

header h1{
color:#38bdf8;
font-size:28px;
letter-spacing:1px;
}

nav{
display:flex;
justify-content:center;
gap:25px;
padding:15px;
background:#0f172a;
border-bottom:1px solid #334155;
}

nav a{
color:#e2e8f0;
text-decoration:none;
font-weight:600;
transition:0.3s;
}

nav a:hover{
color:#38bdf8;
transform:scale(1.1);
}

.container{
max-width:1100px;
margin:50px auto;
padding:20px;
}

.card{
background:rgba(30,41,59,0.8);
padding:30px;
border-radius:15px;
box-shadow:0 0 20px rgba(0,0,0,0.5);
margin-bottom:25px;
transition:0.3s;
}

.card:hover{
transform:translateY(-5px);
}

.card h2{
margin-bottom:15px;
color:#38bdf8;
}

footer{
text-align:center;
padding:20px;
margin-top:40px;
background:#0f172a;
border-top:1px solid #334155;
color:#94a3b8;
font-size:14px;
}
EOF

################ index.php ################

cat <<EOF > /var/www/html/index.php
<!DOCTYPE html>
<html>
<head>
<title>Pentest Corp Portal</title>
<link rel="stylesheet" href="/assets/style.css">
</head>
<body>

<header>
<h1>Pentest Corporation Internal Portal</h1>
</header>

<nav>
<a href="/index.php">Home</a>
<a href="/resources.php?preview=pages/home.php">Resources</a>
<a href="/resources.php?preview=pages/about.php">About</a>
<a href="/resources.php?preview=pages/finance.php">Finance</a>
<a href="/resources.php?preview=pages/devops.php">DevOps</a>
<a href="/resources.php?preview=pages/hr.php">HR</a>
</nav>

<div class="container">
<div class="card">
<h2>Welcome to Internal Systems</h2>
<p>This portal contains confidential internal documentation for corporate departments.</p>
<p>Developers may preview documentation using preview parameter.</p>
</div>

<div class="card">
<h2>System Status</h2>
<p>All services operational.</p>
</div>
</div>

<footer>
© 2026 Pentest Corporation | Confidential
</footer>

</body>
</html>
EOF

################ resources.php (LFI + Base64) ################

cat <<EOF > /var/www/html/resources.php
<?php
ob_start();

if(isset(\$_GET['preview'])){
    \$file = \$_GET['preview'];

    if(strpos(\$file,"http")!==false){
        die(base64_encode("Remote include blocked"));
    }

    if(file_exists(\$file)){
        include(\$file);
    } else {
        echo "File not found";
    }
} else {
    include("pages/home.php");
}

\$output = ob_get_clean();
echo base64_encode(\$output);
?>
EOF

################ download.php ################

cat <<EOF > /var/www/html/download.php
<?php
if(isset(\$_GET['file'])){
    \$file="pages/".\$_GET['file'];

    if(file_exists(\$file)){
        echo base64_encode(file_get_contents(\$file));
    } else {
        echo base64_encode("File not found");
    }
}
?>
EOF

################ MULTIPLE CONFUSING PAGES ################

for page in home about contact devops finance hr roadmap compliance marketing security
do
cat <<EOF > /var/www/html/pages/$page.php
<div class="container">
<div class="card">
<h2>$page Department</h2>
<p>Internal documentation for $page operations and strategic initiatives.</p>
<p>For advanced configs check internal files.</p>
</div>
</div>
EOF
done

################ Hidden Admin ################

cat <<EOF > /var/www/html/pages/admin.php
<div class="container">
<div class="card">
<h2>Restricted Admin Panel</h2>
<p>Database Credentials:</p>
<p>root:SuperSecretPass!</p>
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
echo "===================================="
echo "🔥 PROFESSIONAL CTF LAB READY 🔥"
echo "===================================="
echo "FTP   : ftpuser / ftp123"
echo "SSH   : weakuser / password123"
echo "SMB   : //TARGET-IP/share"
echo "WEB   : http://TARGET-IP"
echo "===================================="
