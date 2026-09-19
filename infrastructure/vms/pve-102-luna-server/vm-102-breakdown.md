# 🖥️ Detailed Container & Service Breakdown: `luna-server` (`pve` VM 102)

* **Host Proxmox Node**: `pve` (`192.168.1.250`)
* **Target Virtual Machine**: `VM 102` (`luna-server`)

--- 

## 🐳 Docker Containers & Services Matrix

```text
NAMES                  STATUS                IMAGE                                      PORTS
homeassistant          Up 38 hours           lscr.io/linuxserver/homeassistant:latest   
homebridge             Up 38 hours           homebridge/homebridge:latest               
syncthing              Up 38 hours           lscr.io/linuxserver/syncthing:latest       0.0.0.0:8384->8384/tcp, 0.0.0.0:21027->21027/udp, [::]:8384->8384/tcp, [::]:21027->21027/udp, 0.0.0.0:22000->22000/tcp, [::]:22000->22000/tcp, 0.0.0.0:22000->22000/udp, [::]:22000->22000/udp
watchtower             Up 2 days (healthy)   nickfedor/watchtower:latest                8080/tcp
git-dietpi             Up 4 days             alpine/git:latest                          
portainer              Up 5 days             portainer/portainer-ee:latest              0.0.0.0:8000->8000/tcp, [::]:8000->8000/tcp, 0.0.0.0:9443->9443/tcp, [::]:9443->9443/tcp, 9000/tcp
gitwatch-obsidian      Up 5 days             ghcr.io/gitwatch/gitwatch:latest           
gitwatch-orca-slicer   Up 5 days             ghcr.io/gitwatch/gitwatch:latest           
spoolman2slicer        Up 5 days             spoolman-spoolman2slicer                   
spoolman               Up 5 days (healthy)   ghcr.io/meek2100/spoolman:test             0.0.0.0:7912->8000/tcp, [::]:7912->8000/tcp
```

--- 

## 🌐 Docker Networks

```text
NETWORK ID     NAME                                         DRIVER    SCOPE
93b42140868a   bridge                                       bridge    local
19a4d8e1d69f   git-dietpi_default                           bridge    local
ba9df36c0fee   gitwatch-obsidian_default                    bridge    local
24d9c14041c2   gitwatch-orca-slicer_default                 bridge    local
143c71b48697   host                                         host      local
22b79fa3d6ce   none                                         null      local
f5632c6879ab   portainer-update-1770915776-latest_default   bridge    local
a69769cc1503   portainer-update-1772063522-latest_default   bridge    local
b8e04a2d7a06   prometheus_default                           bridge    local
176e8f43917f   spoolman_default                             bridge    local
1678e23d4ada   syncthing_default                            bridge    local
1058bfc6ba61   vlan40_network                               macvlan   local
eb2e05bce652   watchtower_default                           bridge    local
```
