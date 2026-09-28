# External Web Server (`theurer.dev`) Infrastructure Blueprint

## System Overview
- **Role**: Primary public-facing web server hosting static & PHP web applications.
- **FQDN**: `theurer.dev` (also serving `ivyhairlounge.com`, `theivyhairlounge.com`)
- **Public IP**: `146.235.203.133` (Oracle Cloud Infrastructure)
- **OS**: Ubuntu 24.04.5 LTS (Noble Numbat), Linux Kernel `7.0.0-1011-oracle`
- **Audit Baseline**: Captured on 2026-09-28 (`audit_theurer-dev_20260928_070942.tar.gz`)

---

## Service Architecture & Daemons
| Service | Daemon / Unit | Ports / Sockets | Purpose |
| :--- | :--- | :--- | :--- |
| **Nginx Web Server** | `nginx.service` | `80/TCP`, `443/TCP` | High-performance reverse proxy & web server with HTTP/2 and TLS 1.3 |
| **PHP-FPM** | `php8.3-fpm.service` | `unix:/var/run/php/php8.3-fpm.sock` | FastCGI backend for PHP execution |
| **MariaDB Database** | `mariadb.service` | `127.0.0.1:3306/TCP` | Local database storage (MariaDB 10.11.14) |
| **Fail2Ban** | `fail2ban.service` | Host iptables | Dynamic brute-force attack prevention (SSH/Web) |
| **Oracle Agent** | `snap.oracle-cloud-agent` | N/A | Cloud metrics and host telemetry |

---

## Hosted Virtual Hosts & Web Roots
1. **`theurer.dev`** & **`www.theurer.dev`**:
   - Web Root: `/var/www/theurer.dev/html`
   - Nginx Config: `nginx/sites-available/theurer.dev`
   - TLS Certificate: `/etc/letsencrypt/live/theurer.dev/fullchain.pem`
2. **`ivyhairlounge.com`** & **`www.ivyhairlounge.com`**:
   - Web Root: `/var/www/ivyhairlounge.com/html`
   - Nginx Config: `nginx/sites-available/ivyhairlounge.com`
   - TLS Certificate: `/etc/letsencrypt/live/ivyhairlounge.com-0001/fullchain.pem`
3. **`theivyhairlounge.com`** & **`www.theivyhairlounge.com`**:
   - Web Root: `/var/www/theivyhairlounge.com/html`
   - Nginx Config: `nginx/sites-available/theivyhairlounge.com`
   - TLS Certificate: `/etc/letsencrypt/live/theivyhairlounge.com/fullchain.pem`

---

## Zero-Trust Security & Monitoring
1. **No Internal Tailscale / LAN Exposure**:
   - Public cloud VPS instances MUST NEVER be placed on the internal homelab Tailscale tailnet or granted LAN routing paths.
2. **Promtail Log Shipping**:
   - Nginx access logs (`/var/log/nginx/*access.log`) and error logs (`/var/log/nginx/*error.log`) stream to the central Loki 3.0 instance via Cloudflare Tunnel:
     - Ingress: `https://logs.theurer.dev/loki/api/v1/push`
     - Authentication: Bearer Token Authorization Header
3. **Telemetry & Health Verification**:
   - Monitored by `mcp/homelab/scripts/manage-external-services.py` for HTTP status, SSL certificate validity, and response latency.

---

## Backup & Recovery Standard
- **Web Roots & Content**: Tarball backup of `/var/www/`
- **Database Backup**:
  ```bash
  mysqldump --single-transaction --quick --all-databases | gzip > /tmp/mariadb_backup_$(date +%Y%m%d).sql.gz
  ```
- **Nginx Configuration**: Versioned in Git under `nginx/`.
