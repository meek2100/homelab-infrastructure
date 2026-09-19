# 🖥️ Detailed Container & Service Breakdown: `media-server` (`pve` VM 103)

* **Host Proxmox Node**: `pve` (`192.168.1.250`)
* **Target Virtual Machine**: `VM 103` (`media-server`)

--- 

## 🐳 Docker Containers & Services Matrix

```text
NAMES                   STATUS                IMAGE                                         PORTS
watchtower              Up 2 days (healthy)   nickfedor/watchtower:latest                   8080/tcp
plex                    Up 2 days             lscr.io/linuxserver/plex:latest               0.0.0.0:8324->8324/tcp, [::]:8324->8324/tcp, 0.0.0.0:1900->1900/udp, [::]:1900->1900/udp, 0.0.0.0:32410->32410/udp, [::]:32410->32410/udp, 0.0.0.0:32400->32400/tcp, [::]:32400->32400/tcp, 0.0.0.0:32412-32414->32412-32414/udp, [::]:32412-32414->32412-32414/udp, 5353/udp, 0.0.0.0:32469->32469/tcp, [::]:32469->32469/tcp
homarr                  Up 5 days             ghcr.io/homarr-labs/homarr:latest             0.0.0.0:7575->7575/tcp, [::]:7575->7575/tcp
seerr                   Up 5 days             ghcr.io/seerr-team/seerr:latest               5055/tcp, 0.0.0.0:5056->5056/tcp, [::]:5056->5056/tcp
filebrowser             Up 5 days             hurlenko/filebrowser:latest                   0.0.0.0:8084->8080/tcp, [::]:8084->8080/tcp
audiobookshelf          Up 5 days             ghcr.io/advplyr/audiobookshelf:latest         0.0.0.0:13378->80/tcp, [::]:13378->80/tcp
heimdall                Up 5 days             lscr.io/linuxserver/heimdall:latest           0.0.0.0:80->80/tcp, [::]:80->80/tcp, 0.0.0.0:443->443/tcp, [::]:443->443/tcp
portainer               Up 5 days             portainer/portainer-ee:latest                 0.0.0.0:8000->8000/tcp, [::]:8000->8000/tcp, 0.0.0.0:9443->9443/tcp, [::]:9443->9443/tcp, 9000/tcp
overseerr               Up 5 days             lscr.io/linuxserver/overseerr:latest          0.0.0.0:5055->5055/tcp, [::]:5055->5055/tcp
calibre-web-automated   Up 5 days (healthy)   crocodilestick/calibre-web-automated:latest   0.0.0.0:8083->8083/tcp, [::]:8083->8083/tcp
```

--- 

## 🌐 Docker Networks

```text
NETWORK ID     NAME                                         DRIVER    SCOPE
ae7875ca99f5   bridge                                       bridge    local
6d2892c642fb   filebrowser_default                          bridge    local
e5b06d22e81b   homarr_default                               bridge    local
240b3cd2174a   host                                         host      local
abbb2928b736   media-management_media-network               bridge    local
27fd705ead1d   none                                         null      local
a9eac0fa2e1a   portainer-update-1770915644-latest_default   bridge    local
19349278de52   watchtower_default                           bridge    local
```
