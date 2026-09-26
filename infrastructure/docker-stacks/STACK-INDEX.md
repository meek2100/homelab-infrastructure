# Master Portainer & Docker Stack Index

This document provides a searchable, friendly service catalog mapping every Portainer stack ID across all virtual machines to its application name, container images, exposed ports, host node, and SOPS secret encryption status.

## Summary Metrics
- **Total Stacks Cataloged**: 85
- **Total Docker Services Defined**: 155
- **Stacks with Encrypted Secrets (`secrets.enc.yaml`)**: 68
- **Host Virtual Machines**: 6 (`discovery-server`, `luna-server`, `media-server`, `minecraft-docker`, `nexus-server`, `nexus-server2`)

---

## VM: `discovery-server` (Node: `pve2`, VMID: `100`)
Total Stacks: **24**

| Stack ID | Primary Services | Container Images | Exposed Ports | Encrypted Secrets | Blueprint Path |
| :--- | :--- | :--- | :--- | :---: | :--- |
| **2** | `watchtower` | `nickfedor/watchtower` | `Internal / Host` | — None | [discovery-server/2](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/discovery-server/2) |
| **31** | `browser` | `lscr.io/linuxserver/firefox:latest` | `Internal / Host` | — None | [discovery-server/31](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/discovery-server/31) |
| **32** | `tunnel` | `cloudflare/cloudflared:latest` | `Internal / Host` | 🔒 Yes | [discovery-server/32](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/discovery-server/32) |
| **41** | `docker-wireguard-pia` | `ghcr.io/thrnz/docker-wireguard-pia:latest` | `5900:5900` | 🔒 Yes | [discovery-server/41](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/discovery-server/41) |
| **45** | `firefox` | `jlesage/firefox` | `5800:5800` | 🔒 Yes | [discovery-server/45](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/discovery-server/45) |
| **47** | `firefox` | `lscr.io/linuxserver/firefox:latest` | `3000:3000, 3001:3001` | — None | [discovery-server/47](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/discovery-server/47) |
| **51** | `vpn`<br>`qbittorrent`<br>`qbittorrent-porthelper` | `ghcr.io/thrnz/docker-wireguard-pia:latest`<br>`lscr.io/linuxserver/qbittorrent:latest`<br>`scotte/qbittorrent-porthelper:latest` | `9898:9898/tcp, 8388:8388/tcp, 8388:8388/udp, 8080:8080`<br>`Internal / Host`<br>`Internal / Host` | 🔒 Yes | [discovery-server/51](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/discovery-server/51) |
| **52** | `vpn`<br>`qbittorrent`<br>`qbittorrent-porthelper` | `qmcgaw/gluetun`<br>`lscr.io/linuxserver/qbittorrent:latest`<br>`scotte/qbittorrent-porthelper:latest` | `9898:9898/tcp, 8388:8388/tcp, 8388:8388/udp, 8080:8080`<br>`Internal / Host`<br>`Internal / Host` | 🔒 Yes | [discovery-server/52](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/discovery-server/52) |
| **54** | `gluetun`<br>`qbittorrent`<br>`qbittorrent-porthelper` | `qmcgaw/gluetun`<br>`lscr.io/linuxserver/qbittorrent:latest`<br>`scotte/qbittorrent-porthelper:latest` | `9898:9898/tcp, 8388:8388/tcp, 8388:8388/udp, 8080:8080`<br>`Internal / Host`<br>`Internal / Host` | 🔒 Yes | [discovery-server/54](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/discovery-server/54) |
| **56** | `gluetun`<br>`transmission`<br>`transmission-porthelper` | `qmcgaw/gluetun`<br>`lscr.io/linuxserver/transmission:latest`<br>`scotte/transmission-porthelper:latest` | `9091:9091, 51413:51413, 51413:51413/udp`<br>`Internal / Host`<br>`Internal / Host` | 🔒 Yes | [discovery-server/56](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/discovery-server/56) |
| **57** | `gluetun`<br>`deluge` | `qmcgaw/gluetun`<br>`lscr.io/linuxserver/deluge:latest` | `8112:8112, 6881:6881, 6881:6881/udp, 58846:58846`<br>`Internal / Host` | 🔒 Yes | [discovery-server/57](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/discovery-server/57) |
| **58** | `gluetun`<br>`sabnzbd` | `qmcgaw/gluetun`<br>`lscr.io/linuxserver/sabnzbd:latest` | `9898:9898/tcp, 8388:8388/tcp, 8388:8388/udp, 8090:8090`<br>`Internal / Host` | 🔒 Yes | [discovery-server/58](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/discovery-server/58) |
| **60** | `gluetun`<br>`nzbget` | `qmcgaw/gluetun`<br>`nzbgetcom/nzbget:latest` | `9898:9898/tcp, 8388:8388/tcp, 8388:8388/udp, 6789:6789`<br>`Internal / Host` | 🔒 Yes | [discovery-server/60](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/discovery-server/60) |
| **66** | `plex`<br>`radarr`<br>`sonarr`<br>`lidarr`<br>`prowlarr`<br>`bazarr`<br>`jackett`<br>`overseerr`<br>`ombi`<br>`heimdall`<br>`readarr-ebook`<br>`readarr-audiobook`<br>`kavita`<br>`calibre`<br>`calibre-web`<br>`audiobookshelf`<br>`gluetun`<br>`sabnzbd`<br>`qbittorrent`<br>`qbittorrent-porthelper`<br>`storyteller` | `lscr.io/linuxserver/plex:latest`<br>`lscr.io/linuxserver/radarr:latest`<br>`lscr.io/linuxserver/sonarr:latest`<br>`lscr.io/linuxserver/lidarr:latest`<br>`lscr.io/linuxserver/prowlarr:latest`<br>`lscr.io/linuxserver/bazarr:latest`<br>`lscr.io/linuxserver/jackett:latest`<br>`lscr.io/linuxserver/overseerr:latest`<br>`lscr.io/linuxserver/ombi:latest`<br>`lscr.io/linuxserver/heimdall:latest`<br>`lscr.io/linuxserver/readarr:develop`<br>`lscr.io/linuxserver/readarr:develop`<br>`lscr.io/linuxserver/kavita:latest`<br>`lscr.io/linuxserver/calibre:latest`<br>`lscr.io/linuxserver/calibre-web:latest`<br>`ghcr.io/advplyr/audiobookshelf:latest`<br>`qmcgaw/gluetun`<br>`lscr.io/linuxserver/sabnzbd:latest`<br>`lscr.io/linuxserver/qbittorrent:latest`<br>`scotte/qbittorrent-porthelper:latest`<br>`registry.gitlab.com/smoores/storyteller:latest` | `32400:32400/tcp, 8324:8324/tcp, 32469:32469/tcp, 1900:1900/udp, 32410:32410/udp, 32412:32412/udp, 32413:32413/udp, 32414:32414/udp`<br>`7878:7878`<br>`8989:8989`<br>`8686:8686`<br>`9696:9696`<br>`6767:6767`<br>`9117:9117`<br>`5055:5055`<br>`3579:3579`<br>`80:80, 443:443`<br>`8787:8787`<br>`9797:9797`<br>`5000:5000`<br>`8070:8080, 8181:8181, 8081:8081`<br>`8083:8083`<br>`13378:80`<br>`9898:9898/tcp, 8388:8388/tcp, 8388:8388/udp, 8080:8080, 8090:8090`<br>`Internal / Host`<br>`Internal / Host`<br>`Internal / Host`<br>`8001:8001` | 🔒 Yes | [discovery-server/66](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/discovery-server/66) |
| **67** | `lazylibrarian` | `lscr.io/linuxserver/lazylibrarian:latest` | `5299:5299` | 🔒 Yes | [discovery-server/67](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/discovery-server/67) |
| **69** | `flaresolverr` | `ghcr.io/flaresolverr/flaresolverr:latest` | `${PORT:-8191}:8191` | — None | [discovery-server/69](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/discovery-server/69) |
| **71** | `flare-bypasser` | `ghcr.io/yoori/flare-bypasser:latest` | `20080:8080` | — None | [discovery-server/71](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/discovery-server/71) |
| **73** | `radarr`<br>`sonarr`<br>`prowlarr`<br>`bazarr`<br>`gluetun`<br>`sabnzbd`<br>`qbittorrent`<br>`qbittorrent-porthelper`<br>`firefox`<br>`calibre-web-automated-book-downloader`<br>`audiobookbay-downloader`<br>`audiobookbay-downloader-dev` | `lscr.io/linuxserver/radarr:latest`<br>`lscr.io/linuxserver/sonarr:latest`<br>`lscr.io/linuxserver/prowlarr:latest`<br>`lscr.io/linuxserver/bazarr:latest`<br>`qmcgaw/gluetun`<br>`lscr.io/linuxserver/sabnzbd:latest`<br>`lscr.io/linuxserver/qbittorrent:latest`<br>`scotte/qbittorrent-porthelper:latest`<br>`lscr.io/linuxserver/firefox:latest`<br>`ghcr.io/calibrain/calibre-web-automated-book-downloader:latest`<br>`ghcr.io/meek2100/audiobookbay-automated:refactor_with_tests`<br>`ghcr.io/jamesry96/audiobookbay-automated:latest` | `7878:7878`<br>`8989:8989`<br>`9696:9696`<br>`6767:6767`<br>`8080:8080, 8090:8090, 3000:3000, 3001:3001, 8084:8084, 5078:5078, 5079:5079`<br>`Internal / Host`<br>`Internal / Host`<br>`Internal / Host`<br>`Internal / Host`<br>`Internal / Host`<br>`Internal / Host`<br>`Internal / Host` | 🔒 Yes | [discovery-server/73](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/discovery-server/73) |
| **79** | `tor-browser` | `kasmweb/tor-browser:1.16.0` | `6901:6901` | 🔒 Yes | [discovery-server/79](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/discovery-server/79) |
| **84** | `ngircd` | `lscr.io/linuxserver/ngircd:latest` | `6667:6667` | 🔒 Yes | [discovery-server/84](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/discovery-server/84) |
| **85** | `calibre-web-automated-book-downloader` | `ghcr.io/calibrain/calibre-web-automated-book-downloader:latest` | `8084:8084` | 🔒 Yes | [discovery-server/85](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/discovery-server/85) |
| **86** | `audiobookbay-downloader` | `ghcr.io/jamesry96/audiobookbay-automated:latest` | `5078:5078` | 🔒 Yes | [discovery-server/86](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/discovery-server/86) |
| **96** | `autoheal`<br>`vpn-restarter`<br>`gluetun`<br>`qbittorrent`<br>`qbittorrent-porthelper`<br>`helium`<br>`audiobookbay-automated-dev` | `willfarrell/autoheal:latest`<br>`docker:cli`<br>`qmcgaw/gluetun`<br>`lscr.io/linuxserver/qbittorrent:latest`<br>`scotte/qbittorrent-porthelper:latest`<br>`lscr.io/linuxserver/helium:latest`<br>`ghcr.io/meek2100/audiobookbay-automated:crows_nest1` | `Internal / Host`<br>`Internal / Host`<br>`8080:8080, 3000:3000, 3001:3001, 5077:5077, 5078:5078, 5079:5079, 8112:8112, 9091:9091`<br>`Internal / Host`<br>`Internal / Host`<br>`Internal / Host`<br>`Internal / Host` | 🔒 Yes | [discovery-server/96](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/discovery-server/96) |
| **99** | `prowlarr` | `lscr.io/linuxserver/prowlarr:latest` | `9696:9696` | 🔒 Yes | [discovery-server/99](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/discovery-server/99) |

---

## VM: `luna-server` (Node: `pve`, VMID: `102`)
Total Stacks: **33**

| Stack ID | Primary Services | Container Images | Exposed Ports | Encrypted Secrets | Blueprint Path |
| :--- | :--- | :--- | :--- | :---: | :--- |
| **1** | `pihole` | `pihole/pihole:latest` | `Internal / Host` | — None | [luna-server/1](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/luna-server/1) |
| **2** | `homebridge` | `homebridge/homebridge:latest` | `Internal / Host` | 🔒 Yes | [luna-server/2](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/luna-server/2) |
| **21** | `homeassistant` | `lscr.io/linuxserver/homeassistant:latest` | `Internal / Host` | 🔒 Yes | [luna-server/21](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/luna-server/21) |
| **32** | `watchtower` | `nickfedor/watchtower` | `Internal / Host` | — None | [luna-server/32](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/luna-server/32) |
| **34** | `global-protect` | `liebesleid1/global-protect:latest` | `41166:41166` | — None | [luna-server/34](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/luna-server/34) |
| **35** | `wireguard` | `lscr.io/linuxserver/wireguard:latest` | `51820:51820/udp` | — None | [luna-server/35](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/luna-server/35) |
| **39** | `weewx` | `mitct02/weewx` | `Internal / Host` | — None | [luna-server/39](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/luna-server/39) |
| **44** | `wg-easy` | `ghcr.io/wg-easy/wg-easy` | `Internal / Host` | 🔒 Yes | [luna-server/44](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/luna-server/44) |
| **45** | `cloudflare-ddns` | `oznu/cloudflare-ddns:latest` | `Internal / Host` | 🔒 Yes | [luna-server/45](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/luna-server/45) |
| **46** | `tunnel` | `cloudflare/cloudflared:latest` | `Internal / Host` | 🔒 Yes | [luna-server/46](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/luna-server/46) |
| **48** | `wireshark` | `lscr.io/linuxserver/wireshark:latest` | `Internal / Host` | 🔒 Yes | [luna-server/48](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/luna-server/48) |
| **49** | `adguardhome-sync` | `lscr.io/linuxserver/adguardhome-sync:latest` | `8080:8080` | 🔒 Yes | [luna-server/49](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/luna-server/49) |
| **59** | `adguardhome`<br>`adguardhome-sync`<br>`adguardhome-certbot` | `adguard/adguardhome`<br>`lscr.io/linuxserver/adguardhome-sync:latest`<br>`certbot/dns-cloudflare` | `Internal / Host`<br>`8080:8080`<br>`Internal / Host` | 🔒 Yes | [luna-server/59](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/luna-server/59) |
| **62** | `nginx-proxy-manager` | `jc21/nginx-proxy-manager:latest` | `80:80, 81:81, 443:443` | 🔒 Yes | [luna-server/62](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/luna-server/62) |
| **63** | `bedrockconnect` | `strausmann/minecraft-bedrock-connect:latest` | `19132:19132/udp` | 🔒 Yes | [luna-server/63](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/luna-server/63) |
| **67** | `site2pdf` | `ghcr.io/meek2100/site2pdf:main` | `Internal / Host` | 🔒 Yes | [luna-server/67](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/luna-server/67) |
| **70** | `obsidian` | `lscr.io/linuxserver/obsidian:latest` | `3000:3000` | 🔒 Yes | [luna-server/70](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/luna-server/70) |
| **71** | `syncthing` | `lscr.io/linuxserver/syncthing:latest` | `8384:8384, 22000:22000/tcp, 22000:22000/udp, 21027:21027/udp` | 🔒 Yes | [luna-server/71](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/luna-server/71) |
| **81** | `gitwatch` | `ghcr.io/gitwatch/gitwatch:latest` | `Internal / Host` | 🔒 Yes | [luna-server/81](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/luna-server/81) |
| **82** | `gitwatch` | `ghcr.io/meek2100/gitwatch:refactor-robust-and-portable` | `Internal / Host` | 🔒 Yes | [luna-server/82](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/luna-server/82) |
| **83** | `webserver` | `httpd:alpine` | `8080:80` | 🔒 Yes | [luna-server/83](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/luna-server/83) |
| **87** | `vpn-proxy` | `ghcr.io/meek2100/gp-proxy:main` | `Internal / Host` | 🔒 Yes | [luna-server/87](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/luna-server/87) |
| **91** | `vpn-proxy` | `ghcr.io/meek2100/gp-proxy:web_gui_codereview` | `8001:8001, 32800:32800/udp, 1080:1080, 1084:1084, 1085:1085, 8080:8080, 8443:8443, 8388:8388, 8388:8388/udp` | 🔒 Yes | [luna-server/91](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/luna-server/91) |
| **92** | `vpn-proxy` | `ghcr.io/meek2100/gp-proxy:web_gui_codereview` | `Internal / Host` | 🔒 Yes | [luna-server/92](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/luna-server/92) |
| **93** | `gitwatch` | `ghcr.io/gitwatch/gitwatch:latest` | `Internal / Host` | 🔒 Yes | [luna-server/93](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/luna-server/93) |
| **94** | `gitwatch` | `ghcr.io/gitwatch/gitwatch:latest` | `Internal / Host` | 🔒 Yes | [luna-server/94](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/luna-server/94) |
| **95** | `git-dietpi` | `alpine/git` | `Internal / Host` | 🔒 Yes | [luna-server/95](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/luna-server/95) |
| **96** | `spoolman`<br>`spoolman2slicer` | `ghcr.io/meek2100/spoolman:test`<br>`custom-build` | `7912:8000`<br>`Internal / Host` | 🔒 Yes | [luna-server/96](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/luna-server/96) |
| **97** | `spoolman2slicer` | `ghcr.io/bofh69/spoolman2slicer:latest` | `Internal / Host` | 🔒 Yes | [luna-server/97](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/luna-server/97) |
| **98** | `grafana` | `grafana/grafana:latest` | `3000:3000` | 🔒 Yes | [luna-server/98](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/luna-server/98) |
| **102** | `prometheus` | `prom/prometheus:latest` | `9090:9090` | 🔒 Yes | [luna-server/102](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/luna-server/102) |
| **104** | `octoeverywhere` | `octoeverywhere/octoeverywhere:latest` | `Internal / Host` | 🔒 Yes | [luna-server/104](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/luna-server/104) |
| **105** | `multicast-relay` | `ghcr.io/scyto/multicast-relay:latest` | `Internal / Host` | — None | [luna-server/105](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/luna-server/105) |

---

## VM: `media-server` (Node: `pve`, VMID: `103`)
Total Stacks: **9**

| Stack ID | Primary Services | Container Images | Exposed Ports | Encrypted Secrets | Blueprint Path |
| :--- | :--- | :--- | :--- | :---: | :--- |
| **2** | `watchtower` | `nickfedor/watchtower` | `Internal / Host` | — None | [media-server/2](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/media-server/2) |
| **24** | `storyteller` | `registry.gitlab.com/smoores/storyteller:latest` | `8001:8001` | 🔒 Yes | [media-server/24](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/media-server/24) |
| **32** | `tunnel` | `cloudflare/cloudflared:latest` | `Internal / Host` | 🔒 Yes | [media-server/32](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/media-server/32) |
| **72** | `plex`<br>`overseerr`<br>`seerr`<br>`heimdall`<br>`calibre-web-automated`<br>`audiobookshelf` | `lscr.io/linuxserver/plex:latest`<br>`lscr.io/linuxserver/overseerr:latest`<br>`ghcr.io/seerr-team/seerr:latest`<br>`lscr.io/linuxserver/heimdall:latest`<br>`crocodilestick/calibre-web-automated:latest`<br>`ghcr.io/advplyr/audiobookshelf:latest` | `32400:32400/tcp, 8324:8324/tcp, 32469:32469/tcp, 1900:1900/udp, 32410:32410/udp, 32412:32412/udp, 32413:32413/udp, 32414:32414/udp`<br>`5055:5055`<br>`5056:5056`<br>`80:80, 443:443`<br>`8083:8083`<br>`13378:80` | 🔒 Yes | [media-server/72](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/media-server/72) |
| **76** | `kavita` | `lscr.io/linuxserver/kavita:latest` | `5000:5000` | 🔒 Yes | [media-server/76](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/media-server/76) |
| **78** | `audiobookshelf` | `ghcr.io/advplyr/audiobookshelf:latest` | `13378:80` | 🔒 Yes | [media-server/78](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/media-server/78) |
| **79** | `filebrowser` | `hurlenko/filebrowser` | `8084:8080` | 🔒 Yes | [media-server/79](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/media-server/79) |
| **80** | `testflight-watcher` | `uzurka/testflight-watcher` | `Internal / Host` | 🔒 Yes | [media-server/80](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/media-server/80) |
| **82** | `homarr` | `ghcr.io/homarr-labs/homarr:latest` | `7575:7575` | 🔒 Yes | [media-server/82](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/media-server/82) |

---

## VM: `minecraft-docker` (Node: `pve`, VMID: `109`)
Total Stacks: **2**

| Stack ID | Primary Services | Container Images | Exposed Ports | Encrypted Secrets | Blueprint Path |
| :--- | :--- | :--- | :--- | :---: | :--- |
| **3** | `mcbd-connect`<br>`mcbd-proxy`<br>`mcbd-family-server`<br>`mcbd-friend-server` | `strausmann/minecraft-bedrock-connect:latest`<br>`ghcr.io/meek2100/mcbd-proxy:develop`<br>`itzg/minecraft-bedrock-server:latest`<br>`itzg/minecraft-bedrock-server:latest` | `19132:19132/udp`<br>`19133:19133/udp, 19134:19134/udp`<br>`Internal / Host`<br>`Internal / Host` | 🔒 Yes | [minecraft-docker/3](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/minecraft-docker/3) |
| **4** | `watchtower` | `nickfedor/watchtower` | `Internal / Host` | — None | [minecraft-docker/4](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/minecraft-docker/4) |

---

## VM: `nexus-server` (Node: `pve`, VMID: `100`)
Total Stacks: **10**

| Stack ID | Primary Services | Container Images | Exposed Ports | Encrypted Secrets | Blueprint Path |
| :--- | :--- | :--- | :--- | :---: | :--- |
| **32** | `watchtower` | `nickfedor/watchtower` | `Internal / Host` | — None | [nexus-server/32](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/nexus-server/32) |
| **44** | `wg-easy` | `ghcr.io/wg-easy/wg-easy` | `51820:51820/udp, 51821:51821/tcp` | 🔒 Yes | [nexus-server/44](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/nexus-server/44) |
| **45** | `cloudflare-ddns` | `oznu/cloudflare-ddns:latest` | `Internal / Host` | 🔒 Yes | [nexus-server/45](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/nexus-server/45) |
| **46** | `tunnel` | `cloudflare/cloudflared:latest` | `Internal / Host` | 🔒 Yes | [nexus-server/46](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/nexus-server/46) |
| **59** | `adguardhome`<br>`adguardhome-sync`<br>`adguardhome-certbot` | `adguard/adguardhome`<br>`lscr.io/linuxserver/adguardhome-sync:latest`<br>`certbot/dns-cloudflare` | `Internal / Host`<br>`8080:8080`<br>`Internal / Host` | 🔒 Yes | [nexus-server/59](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/nexus-server/59) |
| **62** | `nginx-proxy-manager` | `jc21/nginx-proxy-manager:latest` | `Internal / Host` | 🔒 Yes | [nexus-server/62](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/nexus-server/62) |
| **68** | `hbbs`<br>`hbbr` | `rustdesk/rustdesk-server:latest`<br>`rustdesk/rustdesk-server:latest` | `Internal / Host`<br>`Internal / Host` | 🔒 Yes | [nexus-server/68](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/nexus-server/68) |
| **69** | `tailscale` | `tailscale/tailscale:latest` | `Internal / Host` | 🔒 Yes | [nexus-server/69](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/nexus-server/69) |
| **70** | `openspeedtest` | `openspeedtest/latest` | `8082:3000` | 🔒 Yes | [nexus-server/70](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/nexus-server/70) |
| **71-monitoring** | `prometheus`<br>`pve-exporter`<br>`snmp-exporter`<br>`node-exporter`<br>`cadvisor`<br>`grafana`<br>`loki`<br>`promtail` | `prom/prometheus:v2.53.1`<br>`prompve/prometheus-pve-exporter:latest`<br>`prom/snmp-exporter:v0.26.0`<br>`prom/node-exporter:v1.8.2`<br>`gcr.io/cadvisor/cadvisor:v0.49.1`<br>`grafana/grafana:11.1.0`<br>`grafana/loki:3.0.0`<br>`grafana/promtail:3.0.0` | `9090:9090`<br>`9221:9221`<br>`9116:9116`<br>`9100:9100`<br>`8088:8080`<br>`3030:3000`<br>`3100:3100`<br>`Internal / Host` | — None | [nexus-server/71-monitoring](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/nexus-server/71-monitoring) |

---

## VM: `nexus-server2` (Node: `pve3`, VMID: `100`)
Total Stacks: **7**

| Stack ID | Primary Services | Container Images | Exposed Ports | Encrypted Secrets | Blueprint Path |
| :--- | :--- | :--- | :--- | :---: | :--- |
| **1** | `pihole` | `pihole/pihole:latest` | `Internal / Host` | — None | [nexus-server2/1](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/nexus-server2/1) |
| **32** | `watchtower` | `nickfedor/watchtower` | `Internal / Host` | — None | [nexus-server2/32](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/nexus-server2/32) |
| **44** | `wg-easy` | `ghcr.io/wg-easy/wg-easy` | `51820:51820/udp, 51821:51821/tcp` | 🔒 Yes | [nexus-server2/44](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/nexus-server2/44) |
| **45** | `cloudflare-ddns` | `oznu/cloudflare-ddns:latest` | `Internal / Host` | 🔒 Yes | [nexus-server2/45](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/nexus-server2/45) |
| **46** | `tunnel` | `cloudflare/cloudflared:latest` | `Internal / Host` | 🔒 Yes | [nexus-server2/46](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/nexus-server2/46) |
| **59** | `adguardhome`<br>`adguardhome-certbot` | `adguard/adguardhome`<br>`certbot/dns-cloudflare` | `Internal / Host`<br>`Internal / Host` | 🔒 Yes | [nexus-server2/59](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/nexus-server2/59) |
| **62** | `nginx-proxy-manager` | `jc21/nginx-proxy-manager:latest` | `Internal / Host` | 🔒 Yes | [nexus-server2/62](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/nexus-server2/62) |

---
