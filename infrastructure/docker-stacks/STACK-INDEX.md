# 🐳 Homelab Docker Stacks & Services Catalog

Master empirical index of all **82 Docker Stacks** across the Proxmox fleet. Each numerical Portainer stack ID is mapped to its primary service names, container images, network ports, and SOPS secret status.

---

## 📊 Stacks Distribution Summary

| Target VM Host | Proxmox Node | VM ID | Stack Count | Key Services Hosted |
| :--- | :--- | :--- | :--- | :--- |
| **`discovery-server`** | `pve2` | `100` | **24** | watchtower, firefox, cloudflared, docker-wireguard-pia, ... |
| **`luna-server`** | `pve` | `102` | **32** | pi-hole, homebridge, homeassistant, watchtower, ... |
| **`media-server`** | `pve` | `103` | **9** | watchtower, storyteller, cloudflared, plex, ... |
| **`minecraft-docker`** | `pve` | `109` | **2** | stack-3, watchtower |
| **`nexus-server`** | `pve` | `100` | **8** | pi-hole, watchtower, wg-easy, cloudflare-ddns, ... |
| **`nexus-server2`** | `pve3` | `100` | **7** | pi-hole, watchtower, wg-easy, cloudflare-ddns, ... |

---

## 🖥️ `discovery-server` (`pve2` VM 100) — 24 Stacks

| Stack ID | Primary Service(s) | Docker Image(s) | Exposed Ports | Secrets | Compose Path |
| :---: | :--- | :--- | :--- | :---: | :--- |
| [`2`](infrastructure/docker-stacks/discovery-server/2/docker-compose.yml) | **watchtower** | `nickfedor/watchtower` | `Internal only` | None | [`deploy.json`](infrastructure/docker-stacks/discovery-server/2/deploy.json) |
| [`31`](infrastructure/docker-stacks/discovery-server/31/docker-compose.yml) | **firefox** | `lscr.io/linuxserver/firefox:latest` | `Internal only` | None | [`deploy.json`](infrastructure/docker-stacks/discovery-server/31/deploy.json) |
| [`32`](infrastructure/docker-stacks/discovery-server/32/docker-compose.yml) | **cloudflared** | `cloudflare/cloudflared:latest` | `Internal only` | 🔒 Encrypted | [`deploy.json`](infrastructure/docker-stacks/discovery-server/32/deploy.json) |
| [`41`](infrastructure/docker-stacks/discovery-server/41/docker-compose.yml) | **docker-wireguard-pia** | `ghcr.io/thrnz/docker-wireguard-pia:latest` | `5900:5900` | 🔒 Encrypted | [`deploy.json`](infrastructure/docker-stacks/discovery-server/41/deploy.json) |
| [`45`](infrastructure/docker-stacks/discovery-server/45/docker-compose.yml) | **firefox** | `jlesage/firefox` | `5800:5800` | 🔒 Encrypted | [`deploy.json`](infrastructure/docker-stacks/discovery-server/45/deploy.json) |
| [`47`](infrastructure/docker-stacks/discovery-server/47/docker-compose.yml) | **firefox** | `lscr.io/linuxserver/firefox:latest` | `3000:3000, 3001:3001` | None | [`deploy.json`](infrastructure/docker-stacks/discovery-server/47/deploy.json) |
| [`51`](infrastructure/docker-stacks/discovery-server/51/docker-compose.yml) | **docker-wireguard-pia, qbittorrent, qbittorrent-porthelper** | `ghcr.io/thrnz/docker-wireguard-pia:latest, lscr.io/linuxserver/qbittorrent:latest, scotte/qbittorrent-porthelper:latest` | `9898:9898/tcp, 8388:8388/tcp, 8388:8388/udp, 8080:8080` | 🔒 Encrypted | [`deploy.json`](infrastructure/docker-stacks/discovery-server/51/deploy.json) |
| [`52`](infrastructure/docker-stacks/discovery-server/52/docker-compose.yml) | **vpn_test2, qbittorrent, qbittorrent-porthelper** | `qmcgaw/gluetun, lscr.io/linuxserver/qbittorrent:latest, scotte/qbittorrent-porthelper:latest` | `9898:9898/tcp, 8388:8388/tcp, 8388:8388/udp, 8080:8080` | 🔒 Encrypted | [`deploy.json`](infrastructure/docker-stacks/discovery-server/52/deploy.json) |
| [`54`](infrastructure/docker-stacks/discovery-server/54/docker-compose.yml) | **gluetun, qbittorrent, qbittorrent-porthelper** | `qmcgaw/gluetun, lscr.io/linuxserver/qbittorrent:latest, scotte/qbittorrent-porthelper:latest` | `9898:9898/tcp, 8388:8388/tcp, 8388:8388/udp, 8080:8080` | 🔒 Encrypted | [`deploy.json`](infrastructure/docker-stacks/discovery-server/54/deploy.json) |
| [`56`](infrastructure/docker-stacks/discovery-server/56/docker-compose.yml) | **gluetun, transmission, transmission-porthelper** | `qmcgaw/gluetun, lscr.io/linuxserver/transmission:latest, scotte/transmission-porthelper:latest` | `9091:9091, 51413:51413, 51413:51413/udp` | 🔒 Encrypted | [`deploy.json`](infrastructure/docker-stacks/discovery-server/56/deploy.json) |
| [`57`](infrastructure/docker-stacks/discovery-server/57/docker-compose.yml) | **gluetun, deluge** | `qmcgaw/gluetun, lscr.io/linuxserver/deluge:latest` | `8112:8112, 6881:6881, 6881:6881/udp, 58846:58846` | 🔒 Encrypted | [`deploy.json`](infrastructure/docker-stacks/discovery-server/57/deploy.json) |
| [`58`](infrastructure/docker-stacks/discovery-server/58/docker-compose.yml) | **gluetun, sabnzbd** | `qmcgaw/gluetun, lscr.io/linuxserver/sabnzbd:latest` | `9898:9898/tcp, 8388:8388/tcp, 8388:8388/udp, 8090:8090` | 🔒 Encrypted | [`deploy.json`](infrastructure/docker-stacks/discovery-server/58/deploy.json) |
| [`60`](infrastructure/docker-stacks/discovery-server/60/docker-compose.yml) | **gluetun, nzbget** | `qmcgaw/gluetun, nzbgetcom/nzbget:latest` | `9898:9898/tcp, 8388:8388/tcp, 8388:8388/udp, 6789:6789` | 🔒 Encrypted | [`deploy.json`](infrastructure/docker-stacks/discovery-server/60/deploy.json) |
| [`66`](infrastructure/docker-stacks/discovery-server/66/docker-compose.yml) | **plex, radarr, sonarr, lidarr, prowlarr, bazarr, jackett, overseerr, ombi, heimdall, readarr-ebook, readarr-audiobook, kavita, calibre, calibre-web, audiobookshelf, gluetun, sabnzbd, qbittorrent, qbittorrent-porthelper, storyteller** | `lscr.io/linuxserver/plex:latest, lscr.io/linuxserver/radarr:latest, lscr.io/linuxserver/sonarr:latest, lscr.io/linuxserver/lidarr:latest, lscr.io/linuxserver/prowlarr:latest, lscr.io/linuxserver/bazarr:latest, lscr.io/linuxserver/jackett:latest, lscr.io/linuxserver/overseerr:latest, lscr.io/linuxserver/ombi:latest, lscr.io/linuxserver/heimdall:latest, lscr.io/linuxserver/readarr:develop, lscr.io/linuxserver/readarr:develop, lscr.io/linuxserver/kavita:latest, lscr.io/linuxserver/calibre:latest, lscr.io/linuxserver/calibre-web:latest, ghcr.io/advplyr/audiobookshelf:latest, qmcgaw/gluetun, lscr.io/linuxserver/sabnzbd:latest, lscr.io/linuxserver/qbittorrent:latest, scotte/qbittorrent-porthelper:latest, registry.gitlab.com/smoores/storyteller:latest` | `32400:32400/tcp, 8324:8324/tcp, 32469:32469/tcp, 1900:1900/udp, 32410:32410/udp, 32412:32412/udp, 32413:32413/udp, 32414:32414/udp, 7878:7878, 8989:8989, 8686:8686, 9696:9696, 6767:6767, 9117:9117, 5055:5055, 3579:3579, 80:80, 443:443, 8787:8787, 9797:9797, 5000:5000, 8070:8080, 8181:8181, 8081:8081, 8083:8083, 13378:80, 9898:9898/tcp, 8388:8388/tcp, 8388:8388/udp, 8080:8080, 8090:8090, 8001:8001` | 🔒 Encrypted | [`deploy.json`](infrastructure/docker-stacks/discovery-server/66/deploy.json) |
| [`67`](infrastructure/docker-stacks/discovery-server/67/docker-compose.yml) | **lazylibrarian** | `lscr.io/linuxserver/lazylibrarian:latest` | `5299:5299` | 🔒 Encrypted | [`deploy.json`](infrastructure/docker-stacks/discovery-server/67/deploy.json) |
| [`69`](infrastructure/docker-stacks/discovery-server/69/docker-compose.yml) | **flaresolverr** | `ghcr.io/flaresolverr/flaresolverr:latest` | `${PORT:-8191}:8191` | None | [`deploy.json`](infrastructure/docker-stacks/discovery-server/69/deploy.json) |
| [`71`](infrastructure/docker-stacks/discovery-server/71/docker-compose.yml) | **flare-bypasser** | `ghcr.io/yoori/flare-bypasser:latest` | `20080:8080` | None | [`deploy.json`](infrastructure/docker-stacks/discovery-server/71/deploy.json) |
| [`73`](infrastructure/docker-stacks/discovery-server/73/docker-compose.yml) | **radarr, sonarr, prowlarr, bazarr, gluetun, sabnzbd, qbittorrent, qbittorrent-porthelper, firefox, calibre-web-automated-book-downloader, audiobookbay-downloader-refactor_with_tests, audiobookbay-downloader-dev** | `lscr.io/linuxserver/radarr:latest, lscr.io/linuxserver/sonarr:latest, lscr.io/linuxserver/prowlarr:latest, lscr.io/linuxserver/bazarr:latest, qmcgaw/gluetun, lscr.io/linuxserver/sabnzbd:latest, lscr.io/linuxserver/qbittorrent:latest, scotte/qbittorrent-porthelper:latest, lscr.io/linuxserver/firefox:latest, ghcr.io/calibrain/calibre-web-automated-book-downloader:latest, ghcr.io/meek2100/audiobookbay-automated:refactor_with_tests, ghcr.io/jamesry96/audiobookbay-automated:latest` | `7878:7878, 8989:8989, 9696:9696, 6767:6767, 8080:8080, 8090:8090, 3000:3000, 3001:3001, 8084:8084, 5078:5078, 5079:5079` | 🔒 Encrypted | [`deploy.json`](infrastructure/docker-stacks/discovery-server/73/deploy.json) |
| [`79`](infrastructure/docker-stacks/discovery-server/79/docker-compose.yml) | **tor-broswer** | `kasmweb/tor-browser:1.16.0` | `6901:6901` | 🔒 Encrypted | [`deploy.json`](infrastructure/docker-stacks/discovery-server/79/deploy.json) |
| [`84`](infrastructure/docker-stacks/discovery-server/84/docker-compose.yml) | **ngircd** | `lscr.io/linuxserver/ngircd:latest` | `6667:6667` | 🔒 Encrypted | [`deploy.json`](infrastructure/docker-stacks/discovery-server/84/deploy.json) |
| [`85`](infrastructure/docker-stacks/discovery-server/85/docker-compose.yml) | **calibre-web-automated-book-downloader** | `ghcr.io/calibrain/calibre-web-automated-book-downloader:latest` | `8084:8084` | 🔒 Encrypted | [`deploy.json`](infrastructure/docker-stacks/discovery-server/85/deploy.json) |
| [`86`](infrastructure/docker-stacks/discovery-server/86/docker-compose.yml) | **audiobookbay-downloader** | `ghcr.io/jamesry96/audiobookbay-automated:latest` | `5078:5078` | 🔒 Encrypted | [`deploy.json`](infrastructure/docker-stacks/discovery-server/86/deploy.json) |
| [`96`](infrastructure/docker-stacks/discovery-server/96/docker-compose.yml) | **autoheal, vpn-restarter, gluetun, qbittorrent, qbittorrent-porthelper, firefox, audiobookbay-downloader-dev** | `willfarrell/autoheal:latest, docker:cli, qmcgaw/gluetun, lscr.io/linuxserver/qbittorrent:latest, scotte/qbittorrent-porthelper:latest, lscr.io/linuxserver/firefox:latest, ghcr.io/meek2100/audiobookbay-automated:crows_nest1` | `8080:8080, 3000:3000, 3001:3001, 5077:5077, 5078:5078, 5079:5079, 8112:8112, 9091:9091` | 🔒 Encrypted | [`deploy.json`](infrastructure/docker-stacks/discovery-server/96/deploy.json) |
| [`99`](infrastructure/docker-stacks/discovery-server/99/docker-compose.yml) | **prowlarr** | `lscr.io/linuxserver/prowlarr:latest` | `9696:9696` | 🔒 Encrypted | [`deploy.json`](infrastructure/docker-stacks/discovery-server/99/deploy.json) |

## 🖥️ `luna-server` (`pve` VM 102) — 32 Stacks

| Stack ID | Primary Service(s) | Docker Image(s) | Exposed Ports | Secrets | Compose Path |
| :---: | :--- | :--- | :--- | :---: | :--- |
| [`1`](infrastructure/docker-stacks/luna-server/1/docker-compose.yml) | **pi-hole** | `pihole/pihole:latest` | `Internal only` | None | [`deploy.json`](infrastructure/docker-stacks/luna-server/1/deploy.json) |
| [`2`](infrastructure/docker-stacks/luna-server/2/docker-compose.yml) | **homebridge** | `homebridge/homebridge:latest` | `Internal only` | 🔒 Encrypted | [`deploy.json`](infrastructure/docker-stacks/luna-server/2/deploy.json) |
| [`21`](infrastructure/docker-stacks/luna-server/21/docker-compose.yml) | **homeassistant** | `lscr.io/linuxserver/homeassistant:latest` | `Internal only` | 🔒 Encrypted | [`deploy.json`](infrastructure/docker-stacks/luna-server/21/deploy.json) |
| [`32`](infrastructure/docker-stacks/luna-server/32/docker-compose.yml) | **watchtower** | `nickfedor/watchtower` | `Internal only` | None | [`deploy.json`](infrastructure/docker-stacks/luna-server/32/deploy.json) |
| [`34`](infrastructure/docker-stacks/luna-server/34/docker-compose.yml) | **snapone_global-protect** | `liebesleid1/global-protect:latest` | `41166:41166` | None | [`deploy.json`](infrastructure/docker-stacks/luna-server/34/deploy.json) |
| [`35`](infrastructure/docker-stacks/luna-server/35/docker-compose.yml) | **wireguard** | `lscr.io/linuxserver/wireguard:latest` | `51820:51820/udp` | None | [`deploy.json`](infrastructure/docker-stacks/luna-server/35/deploy.json) |
| [`39`](infrastructure/docker-stacks/luna-server/39/docker-compose.yml) | **weewx** | `mitct02/weewx` | `Internal only` | None | [`deploy.json`](infrastructure/docker-stacks/luna-server/39/deploy.json) |
| [`44`](infrastructure/docker-stacks/luna-server/44/docker-compose.yml) | **wg-easy** | `ghcr.io/wg-easy/wg-easy` | `Internal only` | 🔒 Encrypted | [`deploy.json`](infrastructure/docker-stacks/luna-server/44/deploy.json) |
| [`45`](infrastructure/docker-stacks/luna-server/45/docker-compose.yml) | **cloudflare-ddns** | `oznu/cloudflare-ddns:latest` | `Internal only` | 🔒 Encrypted | [`deploy.json`](infrastructure/docker-stacks/luna-server/45/deploy.json) |
| [`46`](infrastructure/docker-stacks/luna-server/46/docker-compose.yml) | **cloudflared** | `cloudflare/cloudflared:latest` | `Internal only` | 🔒 Encrypted | [`deploy.json`](infrastructure/docker-stacks/luna-server/46/deploy.json) |
| [`48`](infrastructure/docker-stacks/luna-server/48/docker-compose.yml) | **wireshark** | `lscr.io/linuxserver/wireshark:latest` | `3000:3000, 3001:3001` | 🔒 Encrypted | [`deploy.json`](infrastructure/docker-stacks/luna-server/48/deploy.json) |
| [`49`](infrastructure/docker-stacks/luna-server/49/docker-compose.yml) | **adguardhome-sync** | `lscr.io/linuxserver/adguardhome-sync:latest` | `8080:8080` | 🔒 Encrypted | [`deploy.json`](infrastructure/docker-stacks/luna-server/49/deploy.json) |
| [`59`](infrastructure/docker-stacks/luna-server/59/docker-compose.yml) | **adguardhome, adguardhome-sync, adguardhome-certbot** | `adguard/adguardhome, lscr.io/linuxserver/adguardhome-sync:latest, certbot/dns-cloudflare` | `8080:8080` | 🔒 Encrypted | [`deploy.json`](infrastructure/docker-stacks/luna-server/59/deploy.json) |
| [`62`](infrastructure/docker-stacks/luna-server/62/docker-compose.yml) | **nginx-proxy-manager** | `jc21/nginx-proxy-manager:latest` | `80:80, 81:81, 443:443` | 🔒 Encrypted | [`deploy.json`](infrastructure/docker-stacks/luna-server/62/deploy.json) |
| [`63`](infrastructure/docker-stacks/luna-server/63/docker-compose.yml) | **bedrockconnect** | `strausmann/minecraft-bedrock-connect:latest` | `19132:19132/udp` | 🔒 Encrypted | [`deploy.json`](infrastructure/docker-stacks/luna-server/63/deploy.json) |
| [`67`](infrastructure/docker-stacks/luna-server/67/docker-compose.yml) | **site2pdf** | `ghcr.io/meek2100/site2pdf:main` | `Internal only` | 🔒 Encrypted | [`deploy.json`](infrastructure/docker-stacks/luna-server/67/deploy.json) |
| [`70`](infrastructure/docker-stacks/luna-server/70/docker-compose.yml) | **obsidian** | `lscr.io/linuxserver/obsidian:latest` | `3000:3000` | 🔒 Encrypted | [`deploy.json`](infrastructure/docker-stacks/luna-server/70/deploy.json) |
| [`71`](infrastructure/docker-stacks/luna-server/71/docker-compose.yml) | **syncthing** | `lscr.io/linuxserver/syncthing:latest` | `8384:8384, 22000:22000/tcp, 22000:22000/udp, 21027:21027/udp` | 🔒 Encrypted | [`deploy.json`](infrastructure/docker-stacks/luna-server/71/deploy.json) |
| [`81`](infrastructure/docker-stacks/luna-server/81/docker-compose.yml) | **gitwatch-obsidian** | `ghcr.io/gitwatch/gitwatch:latest` | `Internal only` | 🔒 Encrypted | [`deploy.json`](infrastructure/docker-stacks/luna-server/81/deploy.json) |
| [`82`](infrastructure/docker-stacks/luna-server/82/docker-compose.yml) | **gitwatch-test** | `ghcr.io/meek2100/gitwatch:refactor-robust-and-portable` | `Internal only` | 🔒 Encrypted | [`deploy.json`](infrastructure/docker-stacks/luna-server/82/deploy.json) |
| [`83`](infrastructure/docker-stacks/luna-server/83/docker-compose.yml) | **t5-update-server** | `httpd:alpine` | `8080:80` | 🔒 Encrypted | [`deploy.json`](infrastructure/docker-stacks/luna-server/83/deploy.json) |
| [`87`](infrastructure/docker-stacks/luna-server/87/docker-compose.yml) | **gp-proxy** | `ghcr.io/meek2100/gp-proxy:web_gui` | `Internal only` | 🔒 Encrypted | [`deploy.json`](infrastructure/docker-stacks/luna-server/87/deploy.json) |
| [`91`](infrastructure/docker-stacks/luna-server/91/docker-compose.yml) | **gp-proxy-ports** | `ghcr.io/meek2100/gp-proxy:web_gui_codereview` | `8001:8001, 32800:32800/udp, 1080:1080, 1084:1084, 1085:1085, 8080:8080, 8443:8443, 8388:8388, 8388:8388/udp` | 🔒 Encrypted | [`deploy.json`](infrastructure/docker-stacks/luna-server/91/deploy.json) |
| [`92`](infrastructure/docker-stacks/luna-server/92/docker-compose.yml) | **gp-proxy-macvlan** | `ghcr.io/meek2100/gp-proxy:web_gui_codereview` | `Internal only` | 🔒 Encrypted | [`deploy.json`](infrastructure/docker-stacks/luna-server/92/deploy.json) |
| [`93`](infrastructure/docker-stacks/luna-server/93/docker-compose.yml) | **gitwatch-orca-slicer** | `ghcr.io/gitwatch/gitwatch:latest` | `Internal only` | 🔒 Encrypted | [`deploy.json`](infrastructure/docker-stacks/luna-server/93/deploy.json) |
| [`94`](infrastructure/docker-stacks/luna-server/94/docker-compose.yml) | **gitwatch-dietpi** | `ghcr.io/gitwatch/gitwatch:latest` | `Internal only` | 🔒 Encrypted | [`deploy.json`](infrastructure/docker-stacks/luna-server/94/deploy.json) |
| [`95`](infrastructure/docker-stacks/luna-server/95/docker-compose.yml) | **git-dietpi** | `alpine/git` | `Internal only` | 🔒 Encrypted | [`deploy.json`](infrastructure/docker-stacks/luna-server/95/deploy.json) |
| [`96`](infrastructure/docker-stacks/luna-server/96/docker-compose.yml) | **spoolman, spoolman2slicer** | `ghcr.io/meek2100/spoolman:test` | `7912:8000` | 🔒 Encrypted | [`deploy.json`](infrastructure/docker-stacks/luna-server/96/deploy.json) |
| [`97`](infrastructure/docker-stacks/luna-server/97/docker-compose.yml) | **spoolman2slicer** | `ghcr.io/bofh69/spoolman2slicer:latest` | `Internal only` | 🔒 Encrypted | [`deploy.json`](infrastructure/docker-stacks/luna-server/97/deploy.json) |
| [`98`](infrastructure/docker-stacks/luna-server/98/docker-compose.yml) | **grafana** | `grafana/grafana:latest` | `3000:3000` | 🔒 Encrypted | [`deploy.json`](infrastructure/docker-stacks/luna-server/98/deploy.json) |
| [`102`](infrastructure/docker-stacks/luna-server/102/docker-compose.yml) | **prometheus** | `prom/prometheus:latest` | `9090:9090` | 🔒 Encrypted | [`deploy.json`](infrastructure/docker-stacks/luna-server/102/deploy.json) |
| [`104`](infrastructure/docker-stacks/luna-server/104/docker-compose.yml) | **octoeverywhere** | `octoeverywhere/octoeverywhere:latest` | `Internal only` | 🔒 Encrypted | [`deploy.json`](infrastructure/docker-stacks/luna-server/104/deploy.json) |

## 🖥️ `media-server` (`pve` VM 103) — 9 Stacks

| Stack ID | Primary Service(s) | Docker Image(s) | Exposed Ports | Secrets | Compose Path |
| :---: | :--- | :--- | :--- | :---: | :--- |
| [`2`](infrastructure/docker-stacks/media-server/2/docker-compose.yml) | **watchtower** | `nickfedor/watchtower` | `Internal only` | None | [`deploy.json`](infrastructure/docker-stacks/media-server/2/deploy.json) |
| [`24`](infrastructure/docker-stacks/media-server/24/docker-compose.yml) | **storyteller** | `registry.gitlab.com/smoores/storyteller:latest` | `8001:8001` | 🔒 Encrypted | [`deploy.json`](infrastructure/docker-stacks/media-server/24/deploy.json) |
| [`32`](infrastructure/docker-stacks/media-server/32/docker-compose.yml) | **cloudflared** | `cloudflare/cloudflared:latest` | `Internal only` | 🔒 Encrypted | [`deploy.json`](infrastructure/docker-stacks/media-server/32/deploy.json) |
| [`72`](infrastructure/docker-stacks/media-server/72/docker-compose.yml) | **plex, overseerr, seerr, heimdall, calibre-web-automated, audiobookshelf** | `lscr.io/linuxserver/plex:latest, lscr.io/linuxserver/overseerr:latest, ghcr.io/seerr-team/seerr:latest, lscr.io/linuxserver/heimdall:latest, crocodilestick/calibre-web-automated:latest, ghcr.io/advplyr/audiobookshelf:latest` | `32400:32400/tcp, 8324:8324/tcp, 32469:32469/tcp, 1900:1900/udp, 32410:32410/udp, 32412:32412/udp, 32413:32413/udp, 32414:32414/udp, 5055:5055, 5056:5056, 80:80, 443:443, 8083:8083, 13378:80` | 🔒 Encrypted | [`deploy.json`](infrastructure/docker-stacks/media-server/72/deploy.json) |
| [`76`](infrastructure/docker-stacks/media-server/76/docker-compose.yml) | **kavita** | `lscr.io/linuxserver/kavita:latest` | `5000:5000` | 🔒 Encrypted | [`deploy.json`](infrastructure/docker-stacks/media-server/76/deploy.json) |
| [`78`](infrastructure/docker-stacks/media-server/78/docker-compose.yml) | **audiobookshelf** | `ghcr.io/advplyr/audiobookshelf:latest` | `13378:80` | 🔒 Encrypted | [`deploy.json`](infrastructure/docker-stacks/media-server/78/deploy.json) |
| [`79`](infrastructure/docker-stacks/media-server/79/docker-compose.yml) | **filebrowser** | `hurlenko/filebrowser` | `8084:8080` | 🔒 Encrypted | [`deploy.json`](infrastructure/docker-stacks/media-server/79/deploy.json) |
| [`80`](infrastructure/docker-stacks/media-server/80/docker-compose.yml) | **testflight-watcher** | `uzurka/testflight-watcher` | `Internal only` | 🔒 Encrypted | [`deploy.json`](infrastructure/docker-stacks/media-server/80/deploy.json) |
| [`82`](infrastructure/docker-stacks/media-server/82/docker-compose.yml) | **homarr** | `ghcr.io/homarr-labs/homarr:latest` | `7575:7575` | 🔒 Encrypted | [`deploy.json`](infrastructure/docker-stacks/media-server/82/deploy.json) |

## 🖥️ `minecraft-docker` (`pve` VM 109) — 2 Stacks

| Stack ID | Primary Service(s) | Docker Image(s) | Exposed Ports | Secrets | Compose Path |
| :---: | :--- | :--- | :--- | :---: | :--- |
| [`3`](infrastructure/docker-stacks/minecraft-docker/3/docker-compose.yml) | **stack-3** | `-` | `Internal only` | 🔒 Encrypted | [`deploy.json`](infrastructure/docker-stacks/minecraft-docker/3/deploy.json) |
| [`4`](infrastructure/docker-stacks/minecraft-docker/4/docker-compose.yml) | **watchtower** | `nickfedor/watchtower` | `Internal only` | None | [`deploy.json`](infrastructure/docker-stacks/minecraft-docker/4/deploy.json) |

## 🖥️ `nexus-server` (`pve` VM 100) — 8 Stacks

| Stack ID | Primary Service(s) | Docker Image(s) | Exposed Ports | Secrets | Compose Path |
| :---: | :--- | :--- | :--- | :---: | :--- |
| [`1`](infrastructure/docker-stacks/nexus-server/1/docker-compose.yml) | **pi-hole** | `pihole/pihole:latest` | `Internal only` | None | [`deploy.json`](infrastructure/docker-stacks/nexus-server/1/deploy.json) |
| [`32`](infrastructure/docker-stacks/nexus-server/32/docker-compose.yml) | **watchtower** | `nickfedor/watchtower` | `Internal only` | None | [`deploy.json`](infrastructure/docker-stacks/nexus-server/32/deploy.json) |
| [`44`](infrastructure/docker-stacks/nexus-server/44/docker-compose.yml) | **wg-easy** | `ghcr.io/wg-easy/wg-easy` | `51820:51820/udp, 51821:51821/tcp` | 🔒 Encrypted | [`deploy.json`](infrastructure/docker-stacks/nexus-server/44/deploy.json) |
| [`45`](infrastructure/docker-stacks/nexus-server/45/docker-compose.yml) | **cloudflare-ddns** | `oznu/cloudflare-ddns:latest` | `Internal only` | 🔒 Encrypted | [`deploy.json`](infrastructure/docker-stacks/nexus-server/45/deploy.json) |
| [`46`](infrastructure/docker-stacks/nexus-server/46/docker-compose.yml) | **cloudflared** | `cloudflare/cloudflared:latest` | `Internal only` | 🔒 Encrypted | [`deploy.json`](infrastructure/docker-stacks/nexus-server/46/deploy.json) |
| [`59`](infrastructure/docker-stacks/nexus-server/59/docker-compose.yml) | **adguardhome, adguardhome-sync, adguardhome-certbot** | `adguard/adguardhome, lscr.io/linuxserver/adguardhome-sync:latest, certbot/dns-cloudflare` | `8080:8080` | 🔒 Encrypted | [`deploy.json`](infrastructure/docker-stacks/nexus-server/59/deploy.json) |
| [`62`](infrastructure/docker-stacks/nexus-server/62/docker-compose.yml) | **nginx-proxy-manager** | `jc21/nginx-proxy-manager:latest` | `Internal only` | 🔒 Encrypted | [`deploy.json`](infrastructure/docker-stacks/nexus-server/62/deploy.json) |
| [`68`](infrastructure/docker-stacks/nexus-server/68/docker-compose.yml) | **rustdesk-hbbs, rustdesk-hbbr** | `rustdesk/rustdesk-server:latest, rustdesk/rustdesk-server:latest` | `21115:21115, 21116:21116, 21116:21116/udp, 21118:21118, 21117:21117, 21119:21119` | 🔒 Encrypted | [`deploy.json`](infrastructure/docker-stacks/nexus-server/68/deploy.json) |

## 🖥️ `nexus-server2` (`pve3` VM 100) — 7 Stacks

| Stack ID | Primary Service(s) | Docker Image(s) | Exposed Ports | Secrets | Compose Path |
| :---: | :--- | :--- | :--- | :---: | :--- |
| [`1`](infrastructure/docker-stacks/nexus-server2/1/docker-compose.yml) | **pi-hole** | `pihole/pihole:latest` | `Internal only` | None | [`deploy.json`](infrastructure/docker-stacks/nexus-server2/1/deploy.json) |
| [`32`](infrastructure/docker-stacks/nexus-server2/32/docker-compose.yml) | **watchtower** | `nickfedor/watchtower` | `Internal only` | None | [`deploy.json`](infrastructure/docker-stacks/nexus-server2/32/deploy.json) |
| [`44`](infrastructure/docker-stacks/nexus-server2/44/docker-compose.yml) | **wg-easy** | `ghcr.io/wg-easy/wg-easy` | `51820:51820/udp, 51821:51821/tcp` | 🔒 Encrypted | [`deploy.json`](infrastructure/docker-stacks/nexus-server2/44/deploy.json) |
| [`45`](infrastructure/docker-stacks/nexus-server2/45/docker-compose.yml) | **cloudflare-ddns** | `oznu/cloudflare-ddns:latest` | `Internal only` | 🔒 Encrypted | [`deploy.json`](infrastructure/docker-stacks/nexus-server2/45/deploy.json) |
| [`46`](infrastructure/docker-stacks/nexus-server2/46/docker-compose.yml) | **cloudflared** | `cloudflare/cloudflared:latest` | `Internal only` | 🔒 Encrypted | [`deploy.json`](infrastructure/docker-stacks/nexus-server2/46/deploy.json) |
| [`59`](infrastructure/docker-stacks/nexus-server2/59/docker-compose.yml) | **adguardhome, adguardhome-certbot** | `adguard/adguardhome, certbot/dns-cloudflare` | `Internal only` | 🔒 Encrypted | [`deploy.json`](infrastructure/docker-stacks/nexus-server2/59/deploy.json) |
| [`62`](infrastructure/docker-stacks/nexus-server2/62/docker-compose.yml) | **nginx-proxy-manager** | `jc21/nginx-proxy-manager:latest` | `Internal only` | 🔒 Encrypted | [`deploy.json`](infrastructure/docker-stacks/nexus-server2/62/deploy.json) |

