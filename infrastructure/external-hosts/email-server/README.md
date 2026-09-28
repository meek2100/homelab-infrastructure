# External Email Server (`mail.theurer.dev`) Infrastructure Blueprint

## System Overview
- **Role**: Primary public mail exchanger (MX), submission gateway, IMAP/POP3 host, and Roundcube webmail portal.
- **FQDN**: `mail.theurer.dev`
- **Public IP**: `35.212.229.212` (Google Cloud Compute Engine)
- **OS**: Ubuntu 24.04.5 LTS (Noble Numbat), Linux Kernel `7.0.0-1013-gcp`
- **Audit Baseline**: Captured on 2026-09-28 (`audit_mail_20260928_003525.tar.gz`)

---

## Service Architecture & Daemons
| Service | Daemon / Unit | Ports / Sockets | Purpose |
| :--- | :--- | :--- | :--- |
| **Postfix MTA** | `postfix@-.service` | `25/TCP`, `587/TCP` | Core mail transport agent & submission daemon |
| **Dovecot IMAP/POP3** | `dovecot.service` | `993/TCP`, `995/TCP`, `110/TCP` | Mail storage access, LMTP local delivery, SASL auth |
| **Rspamd Spam Filter** | `rspamd.service` | `/var/run/rspamd/milter.sock` | Milter-based spam scoring, DKIM/DMARC analysis |
| **Redis Cache** | `redis-server.service` | `127.0.0.1:6379/TCP` | Fast key-value cache and Bayes statistical store for Rspamd |
| **Roundcube Webmail** | `nginx.service` + `php8.3-fpm` | `80/TCP`, `443/TCP` | Web-based email interface at `https://mail.theurer.dev` |
| **Postfix Admin** | Web alias `/admin` | `/srv/postfixadmin/public` | Web-based virtual domain and mailbox management |
| **MariaDB Database** | `mariadb.service` | `127.0.0.1:3306/TCP` | Relational backend for virtual mailboxes, aliases, and webmail |
| **Fail2Ban** | `fail2ban.service` | Host iptables | Dynamic protection for SSH (`22`), Postfix (`587`), and Dovecot (`993`) |

---

## Mail Routing & Delivery Pipeline
1. **Inbound Mail**:
   - `Internet (Port 25)` ➔ `Postfix` ➔ `Rspamd Milter (/var/run/rspamd/milter.sock)` ➔ `Dovecot LMTP (/var/spool/postfix/private/dovecot-lmtp)` ➔ `Maildir (/var/vmail/%d/%n/Maildir)`
2. **Outbound Mail**:
   - `Client / Webmail (Port 587 Submission)` ➔ `Dovecot SASL Auth` ➔ `Postfix` ➔ `Rspamd (DKIM Signing)` ➔ `Relayhost: mail.smtp2go.com:2525` (SMTP2Go smarthost)
3. **Spam Training (Pigeonhole Sieve)**:
   - Moving email to `Junk` automatically runs `/etc/dovecot/sieve/report-spam.sieve` to train Rspamd.
   - Moving email out of `Junk` runs `/etc/dovecot/sieve/report-ham.sieve`.

---

## Active Public Listening Sockets
- **22/TCP**: OpenSSH (`meek2100` via `free-email-server_id_ed25519`)
- **25/TCP**: Postfix SMTP inbound
- **80/443/TCP**: Nginx HTTP/HTTPS (Roundcube Webmail & Let's Encrypt TLS)
- **110/995/TCP**: Dovecot POP3 / POP3S
- **587/TCP**: Postfix Submission (STARTTLS)
- **993/TCP**: Dovecot IMAPS (TLS 1.3 encrypted)

---

## FastMCP Management & Automation
Managed programmatically by `mcp/homelab/scripts/manage-external-hosts.py` via tools:
- `audit_external_hosts(host="email")`: Runs automated remote audit and updates GitOps baseline.
- `backup_external_host(host="email")`: Exports sanitized GitOps configuration bundle to `infrastructure/external-hosts/email-server/backups/`.
- `get_external_security_status(host="email")`: Dumps active Fail2ban jails, banned IPs, and open ports.
- `audit_email_pipeline()`: External synthetic probe testing port 587 ESMTP banner, port 993 IMAPS handshake, and HTTPS webmail response.
