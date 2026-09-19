#!/bin/bash

# Configuration settings (adjust these if needed)
NGINX_CONF_DIR="/etc/nginx/conf.d"  # Or /etc/nginx/sites-available/
CERT_PATH="/etc/letsencrypt/live/secure.theurer.dev/fullchain.pem"
KEY_PATH="/etc/letsencrypt/live/secure.theurer.dev/privkey.pem"
DOMAIN="secure.theurer.dev"

# Helper function to generate the Nginx config
generate_nginx_conf() {
  local service_name="$1"
  local protocol="$2"
  local ip_address="$3"
  local port="$4"

  cat > "$NGINX_CONF_DIR/$service_name.$DOMAIN.conf" <<EOF
server {
    listen 80;
    listen [::]:80;
    server_name $service_name.$DOMAIN;
    return 301 https://\$host\$request_uri;
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name $service_name.$DOMAIN;

    ssl_certificate $CERT_PATH;
    ssl_certificate_key $KEY_PATH;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;
    ssl_ciphers 'ECDHE+AESGCM:CHACHA20';
    ssl_ecdh_curve secp384r1;
    ssl_session_timeout 10m;
    ssl_session_cache shared:SSL:10m;
    ssl_session_tickets off;

    proxy_redirect off;

    access_log /var/log/nginx/$service_name.$DOMAIN.access.log;
    error_log /var/log/nginx/$service_name.$DOMAIN.error.log;

    location / {
        proxy_pass $protocol://$ip_address:$port/;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;

        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
EOF
}

# Generate configurations
generate_nginx_conf "portainer-discovery" "https" "10.25.25.246" "9443"
generate_nginx_conf "portainer-media" "https" "192.168.1.247" "9443"
generate_nginx_conf "portainer-home-automation" "https" "192.168.1.249" "9443"
generate_nginx_conf "openmediavault" "http" "192.168.1.248" "80"
generate_nginx_conf "wireshark" "http" "192.168.1.249" "3000"
generate_nginx_conf "calibreweb" "http" "192.168.1.247" "8083"
generate_nginx_conf "lazylibrarian" "http" "10.25.25.246" "5299"
generate_nginx_conf "homeassistant" "http" "192.168.1.249" "8123"
generate_nginx_conf "overseerr" "http" "192.168.1.247" "5055"
generate_nginx_conf "firefox" "https" "10.25.25.246" "3001"
generate_nginx_conf "homebridge" "http" "192.168.1.249" "8581"
generate_nginx_conf "calibre" "http" "10.25.25.246" "8070"
generate_nginx_conf "plex" "http" "192.168.1.247" "32400"
generate_nginx_conf "wireguard" "http" "192.168.1.249" "51821"
generate_nginx_conf "audiobookshelf" "http" "192.168.1.247" "13378"
generate_nginx_conf "readarr-ebooks" "http" "10.25.25.246" "8787"
generate_nginx_conf "kavita" "http" "192.168.1.247" "5000"
generate_nginx_conf "readarr-audiobooks" "http" "10.25.25.246" "9797"
generate_nginx_conf "prowlarr" "http" "10.25.25.246" "9696"
generate_nginx_conf "storyteller" "http" "192.168.1.247" "8001"
generate_nginx_conf "bazarr" "http" "10.25.25.246" "6767"
generate_nginx_conf "filebrowser" "http" "192.168.1.247" "8084"
generate_nginx_conf "radarr" "http" "10.25.25.246" "7878"
generate_nginx_conf "sonarr" "http" "10.25.25.246" "8989"
generate_nginx_conf "lidarr" "http" "10.25.25.246" "8686"
generate_nginx_conf "sabnzbd" "http" "10.25.25.246" "8090"
generate_nginx_conf "qbittorrent" "http" "10.25.25.246" "8080"
generate_nginx_conf "guard2" "http" "192.168.1.184" "80"
generate_nginx_conf "guard" "http" "192.168.1.185" "80"

# Test Nginx configuration and reload (optional, but recommended)
nginx -t
systemctl reload nginx

echo "Nginx configuration files generated in $NGINX_CONF_DIR/"
echo "Don't forget to test your Nginx configuration and reload!"