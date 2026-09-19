# 🖥️ Detailed Container & Service Breakdown: `minecraft-docker` (`pve` VM 109)

* **Host Proxmox Node**: `pve` (`192.168.1.250`)
* **Target Virtual Machine**: `VM 109` (`minecraft-docker`)

--- 

## 🐳 Docker Containers & Services Matrix

```text
NAMES                STATUS                   IMAGE                                         PORTS
watchtower           Up 2 days (healthy)      nickfedor/watchtower:latest                   8080/tcp
mcbd-connect         Up 3 days (healthy)      strausmann/minecraft-bedrock-connect:latest   0.0.0.0:19132->19132/udp, [::]:19132->19132/udp
mcbd-proxy           Up 5 days (healthy)      ghcr.io/meek2100/mcbd-proxy:develop           8000/tcp, 19132/udp, 25565/tcp, 25565/udp, 0.0.0.0:19133-19134->19133-19134/udp, [::]:19133-19134->19133-19134/udp
mcbd-friend-server   Exited (0) 2 weeks ago   itzg/minecraft-bedrock-server:latest          
mcbd-family-server   Exited (0) 2 weeks ago   itzg/minecraft-bedrock-server:latest          
portainer            Up 5 days                portainer/portainer-ee:latest                 0.0.0.0:8000->8000/tcp, [::]:8000->8000/tcp, 0.0.0.0:9443->9443/tcp, [::]:9443->9443/tcp, 9000/tcp
```

--- 

## 🌐 Docker Networks

```text
NETWORK ID     NAME                               DRIVER    SCOPE
c0705a30e533   bridge                             bridge    local
8fcba2e2e220   host                               host      local
2548aa4c7abf   minecraft-on-demand_mcbd-network   bridge    local
7e740b71c023   none                               null      local
7f2283d1cdc1   watchtower_default                 bridge    local
```
