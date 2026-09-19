# 🖥️ Detailed Container & Service Breakdown: `nexus-server2` (`pve3` VM 100)

* **Host Proxmox Node**: `pve3` (`192.168.1.245`)
* **Target Virtual Machine**: `VM 100` (`nexus-server2`)

--- 

## 🐳 Docker Containers & Services Matrix

```text
NAMES                 STATUS                IMAGE                         PORTS
watchtower            Up 2 days (healthy)   nickfedor/watchtower:latest   8080/tcp
adguardhome-certbot   Up 8 days             certbot/dns-cloudflare        80/tcp, 443/tcp
adguardhome           Up 8 days             adguard/adguardhome           
portainer             Up 9 days             portainer/portainer-ee:lts    0.0.0.0:8000->8000/tcp, [::]:8000->8000/tcp, 0.0.0.0:9443->9443/tcp, [::]:9443->9443/tcp, 9000/tcp
```

--- 

## 🌐 Docker Networks

```text
NETWORK ID     NAME                  DRIVER    SCOPE
2012238a2c41   adguardhome_default   bridge    local
1f1d3350cbc2   bridge                bridge    local
4d4f46ad0962   host                  host      local
d67c54690562   none                  null      local
23eea0c7c541   watchtower_default    bridge    local
```
