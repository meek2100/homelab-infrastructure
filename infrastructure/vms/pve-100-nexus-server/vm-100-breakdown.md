# 🖥️ Detailed Container & Service Breakdown: `nexus-server` (`pve` VM 100)

* **Host Proxmox Node**: `pve` (`192.168.1.250`)
* **Target Virtual Machine**: `VM 100` (`nexus-server`)

--- 

## 🐳 Docker Containers & Services Matrix

```text
NAMES                 STATUS                IMAGE                                         PORTS
cloudflared           Up 2 days             cloudflare/cloudflared:latest                 
rustdesk-hbbs         Up 2 days             rustdesk/rustdesk-server:latest               0.0.0.0:21115-21116->21115-21116/tcp, [::]:21115-21116->21115-21116/tcp, 0.0.0.0:21118->21118/tcp, [::]:21118->21118/tcp, 0.0.0.0:21116->21116/udp, [::]:21116->21116/udp
rustdesk-hbbr         Up 2 days             rustdesk/rustdesk-server:latest               0.0.0.0:21117->21117/tcp, [::]:21117->21117/tcp, 0.0.0.0:21119->21119/tcp, [::]:21119->21119/tcp
watchtower            Up 2 days (healthy)   nickfedor/watchtower:latest                   8080/tcp
adguardhome-sync      Up 57 seconds         lscr.io/linuxserver/adguardhome-sync:latest   0.0.0.0:8080->8080/tcp, [::]:8080->8080/tcp
adguardhome-certbot   Up 2 days             certbot/dns-cloudflare                        80/tcp, 443/tcp
adguardhome           Up 2 days             adguard/adguardhome                           
portainer             Up 2 days             portainer/portainer-ee:latest                 0.0.0.0:8000->8000/tcp, [::]:8000->8000/tcp, 0.0.0.0:9443->9443/tcp, [::]:9443->9443/tcp, 9000/tcp
nginx-proxy-manager   Up 2 days             jc21/nginx-proxy-manager:latest               
cloudflare-ddns       Up 2 days             oznu/cloudflare-ddns:latest                   
wg-easy               Up 2 days (healthy)   ghcr.io/wg-easy/wg-easy                       0.0.0.0:51820->51820/udp, [::]:51820->51820/udp, 0.0.0.0:51821->51821/tcp, [::]:51821->51821/tcp
```

--- 

## 🌐 Docker Networks

```text
NETWORK ID     NAME                                         DRIVER    SCOPE
f0f703eb509d   adguardhome_default                          bridge    local
047006b12dfb   bridge                                       bridge    local
51c433bea17a   cloudflare-ddns_default                      bridge    local
4d4f46ad0962   host                                         host      local
d67c54690562   none                                         null      local
566f4e16dd4c   portainer-update-1770917046-latest_default   bridge    local
047ac66b195f   rustdesk-server_default                      bridge    local
23eea0c7c541   watchtower_default                           bridge    local
92aff97ff438   wireguard-easy_default                       bridge    local
```
