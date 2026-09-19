# 🖥️ Detailed Container & Service Breakdown: `discovery-server` (`pve2` VM 100)

* **Host Proxmox Node**: `pve2` (`192.168.1.240`)
* **Target Virtual Machine**: `VM 100` (`discovery-server`)

--- 

## 🐳 Docker Containers & Services Matrix

```text
NAMES                         STATUS                             IMAGE                                                 PORTS
autoheal                      Up 17 hours (healthy)              willfarrell/autoheal:latest                           
qbittorrent-porthelper        Up 51 seconds (health: starting)   scotte/qbittorrent-porthelper:latest                  
firefox                       Up 34 hours                        lscr.io/linuxserver/firefox:latest                    
audiobookbay-downloader-dev   Up 16 seconds (health: starting)   ghcr.io/meek2100/audiobookbay-automated:crows_nest1   
qbittorrent                   Up 32 seconds (health: starting)   lscr.io/linuxserver/qbittorrent:latest                
gluetun                       Up 25 seconds (health: starting)   qmcgaw/gluetun:latest                                 0.0.0.0:3000-3001->3000-3001/tcp, [::]:3000-3001->3000-3001/tcp, 1080/tcp, 0.0.0.0:5077-5079->5077-5079/tcp, [::]:5077-5079->5077-5079/tcp, 0.0.0.0:8080->8080/tcp, [::]:8080->8080/tcp, 8000/tcp, 1080/udp, 8388/tcp, 0.0.0.0:8112->8112/tcp, [::]:8112->8112/tcp, 8888/tcp, 8388/udp, 0.0.0.0:9091->9091/tcp, [::]:9091->9091/tcp
watchtower                    Up 2 days (healthy)                nickfedor/watchtower:latest                           8080/tcp
vpn-restarter                 Up 3 days                          docker:cli                                            
portainer                     Up 5 days                          portainer/portainer-ee:latest                         0.0.0.0:8000->8000/tcp, [::]:8000->8000/tcp, 0.0.0.0:9443->9443/tcp, [::]:9443->9443/tcp, 9000/tcp
```

--- 

## 🌐 Docker Networks

```text
NETWORK ID     NAME                                     DRIVER    SCOPE
5cc5a6255d13   audiobookbay-automated-dev_default       bridge    local
7c79d8b0a932   audiobookbay-automated-dev_vpn-network   bridge    local
4c6997b95cfb   bridge                                   bridge    local
240b3cd2174a   host                                     host      local
27fd705ead1d   none                                     null      local
55fcd3b418b5   watchtower_default                       bridge    local
```
