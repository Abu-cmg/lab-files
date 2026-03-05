#!/bin/bash

echo "[+] Creating vulnerable user..."

# create user
useradd -m -s /bin/bash normaluser
echo "normaluser:password123" | chpasswd

echo "[+] Installing required packages..."
apt update
apt install -y sudo cron wget gcc

echo "[+] Adding weak sudo permission..."

# allow sudo but with misconfiguration
echo "normaluser ALL=(ALL) NOPASSWD: /usr/bin/find" >> /etc/sudoers

echo "[+] Creating SUID vulnerable binary..."

cat << 'EOF' > /tmp/rootbash.c
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

int main(){
    setuid(0);
    setgid(0);
    system("/bin/bash");
    return 0;
}
EOF

gcc /tmp/rootbash.c -o /usr/local/bin/rootbash

chmod 4755 /usr/local/bin/rootbash
chown root:root /usr/local/bin/rootbash

echo "[+] Creating vulnerable cron job..."

mkdir -p /opt/backup

cat << 'EOF' > /opt/backup/backup.sh
#!/bin/bash
tar -cf /tmp/backup.tar /home
EOF

chmod +x /opt/backup/backup.sh
chmod 777 /opt/backup/backup.sh

echo "* * * * * root /opt/backup/backup.sh" >> /etc/crontab

echo "[+] Downloading pspy for monitoring cron..."

wget https://github.com/DominicBreuker/pspy/releases/download/v1.2.1/pspy64 -O /home/normaluser/pspy64
chmod +x /home/normaluser/pspy64
chown normaluser:normaluser /home/normaluser/pspy64

echo "[+] Lab Setup Complete!"

echo ""
echo "======================================"
echo "Login with:"
echo "username: normaluser"
echo "password: password123"
echo "======================================"

echo ""
echo "Privilege Escalation Paths:"
echo "1. sudo -l (find misconfig)"
echo "2. SUID binary /usr/local/bin/rootbash"
echo "3. Cron job writable script (discover with pspy)"
echo ""
