#!/bin/bash

echo "[+] Updating system..."
apt update -y

echo "[+] Installing Apache, PHP..."
apt install apache2 php libapache2-mod-php -y

echo "[+] Enabling Apache..."
systemctl unmask apache2
systemctl enable apache2
systemctl start apache2

echo "[+] Creating Web Directory..."
mkdir -p /var/www/html/assets
mkdir -p /var/www/html/pages
mkdir -p /var/www/html/hidden
mkdir -p /var/www/html/uploads

echo "[+] Creating Flag..."
echo "FLAG{LFI_MASTER_ACCESS_GRANTED}" > /root/flag.txt
chmod 644 /root/flag.txt

############################################
# INDEX PAGE
############################################

cat > /var/www/html/index.php <<'EOF'
<?php include("header.php"); ?>

<div class="card">
<h2>Welcome to Pentest Corporate Portal</h2>
<p>This internal portal provides access to training materials and company documentation.</p>
<p>Explore resources carefully.</p>
</div>

<?php include("footer.php"); ?>
EOF

############################################
# HEADER
############################################

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
<a href="/resources.php?preview=training">Training</a>
</nav>

<div class="container">
EOF

############################################
# FOOTER
############################################

cat > /var/www/html/footer.php <<'EOF'
</div>
<footer>
© 2026 Pentest Corporation. All rights reserved.
</footer>
</body>
</html>
EOF

############################################
# RESOURCES (VULNERABLE FILE)
############################################

cat > /var/www/html/resources.php <<'EOF'
<?php
include("header.php");

$valid = false;

if(isset($_GET['preview'])) {
    $file = $_GET['preview'];
    $allowed = array("home","about","contact","training","js-fundamental","networking","security");

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
    include($file);   // vulnerable
    $valid = true;
}

if(!$valid){
    http_response_code(404);
    echo "<div class='card'><h2>Invalid Parameter</h2></div>";
}

include("footer.php");
?>
EOF

############################################
# PAGES
############################################

cat > /var/www/html/pages/home.php <<'EOF'
<div class="card">
<h2>Company Home</h2>
<p>Internal documentation available for staff.</p>
</div>
EOF

cat > /var/www/html/config.php  <<'EOF
<?php
// Internal Configuration File
$flag = "FLAG{SOURCE_CODE_LFI_SUCCESS}";

$db_user = "corp_user";
$db_pass = "CorpPass@2026";

// SSH Backup Credentials (DO NOT REMOVE)
// Used by IT Department
$ssh_user = "developer";
$ssh_pass = "Dev@123Secure";
?>
EOF

cat > /var/www/html/pages/about.php <<'EOF'
<div class="card">
<h2>About Us</h2>
<p>We specialize in cyber defense and enterprise security.</p>
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
<h2>Employee Training Portal</h2>
<p>Access secured materials carefully.</p>
</div>
EOF

cat > /var/www/html/pages/js-fundamental.php <<'EOF'
<div class="card">
<h2>JS Fundamentals</h2>
<p>Learn JavaScript basics here.</p>
</div>
EOF

cat > /var/www/html/pages/networking.php <<'EOF'
<div class="card">
<h2>Networking Basics</h2>
<p>TCP/IP, DNS, Routing fundamentals.</p>
</div>
EOF

cat > /var/www/html/pages/security.php <<'EOF'
<div class="card">
<h2>Security Guidelines</h2>
<p>Always sanitize user input.</p>
</div>
EOF

############################################
# CSS DESIGN
############################################

cat > /var/www/html/assets/style.css <<'EOF'
body {
    font-family: Arial, sans-serif;
    background: linear-gradient(120deg,#1f1c2c,#928dab);
    margin: 0;
    color: white;
}

header {
    background: #111;
    padding: 20px;
    text-align: center;
    font-size: 24px;
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
    margin-bottom: 20px;
    border-radius: 10px;
    box-shadow: 0px 0px 15px black;
}

footer {
    text-align: center;
    padding: 15px;
    background: #111;
}
EOF

############################################
# APACHE PERMISSIONS
############################################

chown -R www-data:www-data /var/www/html
chmod -R 755 /var/www/html

systemctl restart apache2

echo ""
echo "========================================="
echo " LAB SETUP COMPLETE"
echo " Visit: http://SERVER-IP/"
echo ""
echo " LFI PARAMETER:"
echo "   resources.php?doc="
echo ""
echo " Try:"
echo "   /etc/passwd"
echo "   php://filter/convert.base64-encode/resource=index.php"
echo ""
echo " Flag Location:"
echo "   /root/flag.txt"
echo "========================================="
