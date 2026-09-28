#!/usr/bin/env bash
# ==============================================================================
# Non-Destructive Zero-Trust Audit Script for External Cloud Hosts
# (theurer.dev & mail.theurer.dev)
# Collects package drift, systemd services, web/mail configurations, and network
# listening ports into a structured audit bundle.
# ==============================================================================

set -euo pipefail

HOSTNAME=$(hostname -s)
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
AUDIT_DIR="/tmp/audit_${HOSTNAME}_${TIMESTAMP}"
mkdir -p "${AUDIT_DIR}"/{system,network,packages,services,configs,web,mail,security}

echo "🔍 Starting Non-Destructive External Host Audit on: ${HOSTNAME} (${TIMESTAMP})"

# 1. System & OS Info
echo "  ↳ Gathering system and OS baseline..."
uname -a > "${AUDIT_DIR}/system/uname.txt" 2>&1 || true
cat /etc/os-release > "${AUDIT_DIR}/system/os-release.txt" 2>&1 || true
uptime > "${AUDIT_DIR}/system/uptime.txt" 2>&1 || true
df -h > "${AUDIT_DIR}/system/disk-usage.txt" 2>&1 || true
free -m > "${AUDIT_DIR}/system/memory.txt" 2>&1 || true

# 2. Network & Listening Sockets
echo "  ↳ Capturing listening ports and firewall rules..."
ss -tulpn > "${AUDIT_DIR}/network/listening-ports.txt" 2>&1 || netstat -tulpn > "${AUDIT_DIR}/network/listening-ports.txt" 2>&1 || true
ip addr > "${AUDIT_DIR}/network/ip-addr.txt" 2>&1 || true
ip route > "${AUDIT_DIR}/network/ip-route.txt" 2>&1 || true
if command -v ufw >/dev/null 2>&1; then
    ufw status verbose > "${AUDIT_DIR}/network/ufw-status.txt" 2>&1 || true
fi
if command -v iptables >/dev/null 2>&1; then
    iptables -S > "${AUDIT_DIR}/network/iptables-rules.txt" 2>&1 || true
fi

# 3. Installed Packages
echo "  ↳ Capturing installed package inventory..."
if command -v dpkg-query >/dev/null 2>&1; then
    dpkg-query -W -f='${Package} ${Version}\n' > "${AUDIT_DIR}/packages/dpkg-packages.txt" 2>&1 || true
elif command -v rpm >/dev/null 2>&1; then
    rpm -qa > "${AUDIT_DIR}/packages/rpm-packages.txt" 2>&1 || true
fi

# 4. Systemd Services & Containers
echo "  ↳ Identifying active services and containers..."
systemctl list-unit-files --state=enabled > "${AUDIT_DIR}/services/enabled-units.txt" 2>&1 || true
systemctl list-units --type=service --state=running > "${AUDIT_DIR}/services/running-services.txt" 2>&1 || true

if command -v docker >/dev/null 2>&1; then
    docker ps -a > "${AUDIT_DIR}/services/docker-containers.txt" 2>&1 || true
    docker images > "${AUDIT_DIR}/services/docker-images.txt" 2>&1 || true
    if command -v docker-compose >/dev/null 2>&1 || docker compose version >/dev/null 2>&1; then
        docker compose ls > "${AUDIT_DIR}/services/docker-compose-projects.txt" 2>&1 || true
    fi
fi

# 5. Web Server Configuration & SSL
echo "  ↳ Archiving web server configurations..."
if [ -d /etc/nginx ]; then
    cp -r /etc/nginx "${AUDIT_DIR}/web/nginx" 2>/dev/null || true
    nginx -v > "${AUDIT_DIR}/web/nginx-version.txt" 2>&1 || true
fi
if [ -d /etc/apache2 ]; then
    cp -r /etc/apache2 "${AUDIT_DIR}/web/apache2" 2>/dev/null || true
fi
if [ -d /var/www ]; then
    ls -la /var/www > "${AUDIT_DIR}/web/var-www-inventory.txt" 2>&1 || true
    find /var/www -maxdepth 3 -ls > "${AUDIT_DIR}/web/var-www-tree.txt" 2>&1 || true
fi
if command -v certbot >/dev/null 2>&1; then
    certbot certificates > "${AUDIT_DIR}/web/certbot-certificates.txt" 2>&1 || true
fi

# 6. Mail Server Configuration (Postfix, Dovecot, OpenDKIM)
echo "  ↳ Archiving mail server configurations..."
if command -v postconf >/dev/null 2>&1; then
    postconf -n > "${AUDIT_DIR}/mail/postfix-main.cf.active" 2>&1 || true
    [ -f /etc/postfix/master.cf ] && cp /etc/postfix/master.cf "${AUDIT_DIR}/mail/postfix-master.cf" 2>/dev/null || true
fi
if command -v doveconf >/dev/null 2>&1; then
    doveconf -n > "${AUDIT_DIR}/mail/dovecot.conf.active" 2>&1 || true
fi
if [ -d /etc/opendkim ]; then
    cp -r /etc/opendkim "${AUDIT_DIR}/mail/opendkim" 2>/dev/null || true
    # Remove private keys from unencrypted audit directory for security
    find "${AUDIT_DIR}/mail/opendkim" -type f -name "*.private" -exec rm -f {} + 2>/dev/null || true
fi
if [ -d /var/vmail ]; then
    ls -la /var/vmail > "${AUDIT_DIR}/mail/var-vmail-inventory.txt" 2>&1 || true
fi

# 7. Fail2Ban & Intrusion Defense
echo "  ↳ Archiving Fail2Ban and security configurations..."
if [ -d /etc/fail2ban ]; then
    cp -r /etc/fail2ban "${AUDIT_DIR}/security/fail2ban" 2>/dev/null || true
fi
if command -v fail2ban-client >/dev/null 2>&1; then
    fail2ban-client status > "${AUDIT_DIR}/security/fail2ban-status.txt" 2>&1 || true
    for jail in $(fail2ban-client status 2>/dev/null | grep "Jail list:" | sed 's/.*Jail list://' | tr -d ',' | tr '\t' ' '); do
        fail2ban-client status "$jail" > "${AUDIT_DIR}/security/fail2ban-jail-${jail}.txt" 2>&1 || true
    done
fi
if [ -d /etc/spamassassin ]; then
    cp -r /etc/spamassassin "${AUDIT_DIR}/mail/spamassassin" 2>/dev/null || true
fi
if [ -d /etc/rspamd ]; then
    cp -r /etc/rspamd "${AUDIT_DIR}/mail/rspamd" 2>/dev/null || true
fi
if [ -d /etc/roundcube ]; then
    cp -r /etc/roundcube "${AUDIT_DIR}/mail/roundcube" 2>/dev/null || true
fi

# 8. Scheduled Tasks, Crons & Logrotate
echo "  ↳ Checking cron schedules and log rotation..."
crontab -l > "${AUDIT_DIR}/configs/root-crontab.txt" 2>&1 || true
ls -la /etc/cron* > "${AUDIT_DIR}/configs/system-cron-inventory.txt" 2>&1 || true
if [ -d /etc/logrotate.d ]; then
    cp -r /etc/logrotate.d "${AUDIT_DIR}/configs/logrotate.d" 2>/dev/null || true
fi

# 9. Package Into Bundle
ARCHIVE="/tmp/audit_${HOSTNAME}_${TIMESTAMP}.tar.gz"
tar -czf "${ARCHIVE}" -C /tmp "audit_${HOSTNAME}_${TIMESTAMP}"
rm -rf "${AUDIT_DIR}"

echo ""
echo "✅ Audit completed successfully!"
echo "📦 Archive bundle created at: ${ARCHIVE}"
echo "    Size: $(du -h "${ARCHIVE}" | awk '{print $1}')"
echo ""
echo "To pull this audit bundle to your workstation:"
echo "  scp <user>@<host>:${ARCHIVE} ./"
