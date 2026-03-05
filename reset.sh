#!/bin/bash
# =========================================================
# FULL LAB RESET SCRIPT (STRICT MODE)
# - Stops all web servers
# - Cleans web roots WITHOUT writing files
# - Removes all users except root & antori
# =========================================================

set -e

echo "======================================"
echo " FULL LAB RESET (STRICT CLEAN)"
echo "======================================"

# ---------------------------------------------------------
# 1️⃣ Stop & mask all web servers
# ---------------------------------------------------------
SERVICES=(
    apache2
    httpd
    nginx
    lighttpd
    lsws
)

echo "[+] Stopping & masking web servers..."

for svc in "${SERVICES[@]}"; do
    if systemctl list-unit-files | grep -q "^$svc"; then
        sudo systemctl stop "$svc" 2>/dev/null || true
        sudo systemctl disable "$svc" 2>/dev/null || true
        sudo systemctl mask "$svc" 2>/dev/null || true
        echo "    [-] $svc stopped & masked"
    fi
done

# ---------------------------------------------------------
# 2️⃣ Kill anything using ports 80 / 443
# ---------------------------------------------------------
echo "[+] Killing processes on ports 80 / 443..."
sudo fuser -k 80/tcp 2>/dev/null || true
sudo fuser -k 443/tcp 2>/dev/null || true

# ---------------------------------------------------------
# 3️⃣ SAFE WEB ROOT CLEANING (NO FILE CREATION)
# ---------------------------------------------------------
echo "[+] Cleaning web server roots (delete only)..."

SAFE_BASES=(
    "/var/www"
    "/usr/share/nginx"
)

is_safe_path() {
    for base in "${SAFE_BASES[@]}"; do
        [[ "$1" == "$base"* ]] && return 0
    done
    return 1
}

clean_root() {
    ROOT="$1"

    if [ -z "$ROOT" ] || [ "$ROOT" = "/" ]; then
        echo "    [!] Skipping dangerous root"
        return
    fi

    if ! is_safe_path "$ROOT"; then
        echo "    [!] Skipping unsafe path: $ROOT"
        return
    fi

    if [ -d "$ROOT" ]; then
        echo "    [+] Deleting contents of $ROOT"
        sudo rm -rf "$ROOT"/* "$ROOT"/.[!.]* 2>/dev/null || true
        echo "    [✓] $ROOT cleaned"
    fi
}

# Default roots
clean_root "/var/www/html"
clean_root "/usr/share/nginx/html"

# Apache custom DocumentRoots
if [ -d /etc/apache2/sites-enabled ]; then
    grep -Rho 'DocumentRoot\s\+"[^"]\+"' /etc/apache2/sites-enabled 2>/dev/null \
    | awk -F\" '{print $2}' \
    | while read -r root; do
        clean_root "$root"
    done
fi

# Nginx custom roots
if [ -d /etc/nginx/sites-enabled ]; then
    grep -Rho '^\s*root\s\+[^;]\+' /etc/nginx/sites-enabled 2>/dev/null \
    | awk '{print $2}' \
    | while read -r root; do
        clean_root "$root"
    done
fi

# ---------------------------------------------------------
# 4️⃣ REMOVE ALL USERS EXCEPT root & antori
# ---------------------------------------------------------

ALLOWED_USERS=("root" "antori")

for dir in /home/*; do
    username=$(basename "$dir")

    if [[ ! " ${ALLOWED_USERS[@]} " =~ " $username " ]]; then
        echo "[+] Deleting user: $username"
        # Remove user account if it exists
        userdel "$username" 2>/dev/null || true
        # Remove leftover home folder
        rm -rf "$dir"
        echo "    [-] Deleted home directory: $dir"
    else
        echo "[✓] Keeping user: $username"
    fi
done

# ---------------------------------------------------------
# 5️⃣ Reload systemd
# ---------------------------------------------------------
echo "[+] Reloading systemd..."
sudo systemctl daemon-reload

# ---------------------------------------------------------
# 6️⃣ Final status
# ---------------------------------------------------------
echo "======================================"
echo "[✓] RESET COMPLETE"
echo "[✓] Web servers stopped & masked"
echo "[✓] Web roots wiped (no files written)"
echo "[✓] Only users kept: root, antori"
echo "[✓] Ports 80/443 free"
echo "======================================"


########################################
# FTP LAB RESET
########################################

echo "[+] Resetting FTP lab..."

# Ensure base directory exists
mkdir -p /srv/ftp

echo "    [+] Cleaning old FTP files..."
rm -rf /srv/ftp/*

echo "    [+] Creating upload directory..."
mkdir -p /srv/ftp/uploads

echo "    [+] Creating flags..."
echo "FLAG{FTP_ENUMERATION_SUCCESS}" > /srv/ftp/ftp_flag.txt
echo "FLAG{FTP_UPLOAD_SUCCESS}" > /srv/ftp/uploads/upload_flag.txt

echo "    [+] Setting permissions..."
chmod 755 /srv/ftp
chmod 777 /srv/ftp/uploads
chmod 644 /srv/ftp/ftp_flag.txt
chmod 644 /srv/ftp/uploads/upload_flag.txt

echo "[✓] FTP lab ready"
echo "======================================"
echo "   PRIVESC LAB UNIVERSAL RESET"
echo "======================================"

echo "[+] Removing custom SUID binaries..."

# Remove SUID from common binaries

chmod u-s /usr/bin/python3 2>/dev/null
chmod u-s /usr/bin/bash 2>/dev/null
chmod u-s /usr/bin/find 2>/dev/null

echo "======================================"
echo "   SUDO RESET (KEEP ONLY antori)"
echo "======================================"

# Backup sudoers

cp /etc/sudoers /etc/sudoers.bak

echo "[+] Removing custom sudo rules..."

# Remove user rules except antori

sed -i '/^[^#]*ALL=(ALL)/{/antori/!d}' /etc/sudoers

echo "[+] Cleaning sudoers.d directory..."

for file in /etc/sudoers.d/*; do
    if ! grep -q "antori" "$file" 2>/dev/null; then
        rm -f "$file"
    fi
done

echo "[+] Ensuring antori keeps sudo access..."

grep -q "antori" /etc/sudoers || echo "antori ALL=(ALL:ALL) ALL" >> /etc/sudoers

echo "======================================"
echo "[+] SUDO RESET COMPLETE"
echo "======================================"

echo "======================================"
echo "   CLEAN /opt (KEEP /opt/lab)"
echo "======================================"

TARGET_DIR="/opt"
KEEP_DIR="lab"

echo "[+] Checking directories in $TARGET_DIR ..."

for dir in "$TARGET_DIR"/*; do
    if [ -d "$dir" ]; then
        BASENAME=$(basename "$dir")
        if [ "$BASENAME" != "$KEEP_DIR" ]; then
            echo "[+] Deleting $dir ..."
            rm -rf "$dir"
        else
            echo "[+] Keeping $dir"
        fi
    fi
done

echo "======================================"
echo "[+] CLEANUP COMPLETE"
echo "======================================"
