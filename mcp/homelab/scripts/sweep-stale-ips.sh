#!/bin/sh
# sweep-stale-ips.sh: READ-ONLY. Lists config lines that still mention the retired VLAN 1 addresses of
# hosts that moved to VLAN 40 (nexus .185, nexus-server2 .186, media-server .247, NAS .248, luna .249).
# Run it on each host over SSH (it changes nothing). Credentials on matching lines are redacted.
#   PowerShell: Get-Content sweep-stale-ips.sh -Raw | ssh <host> "tr -d '\r' | sh -s"
PAT='192\.168\.1\.(185|186|247|248|249)([^0-9]|$)'
H=$(hostname)
SUDO=""
[ "$(id -u)" -ne 0 ] && command -v sudo >/dev/null 2>&1 && sudo -n true 2>/dev/null && SUDO="sudo -n"
[ "$(id -u)" -ne 0 ] && [ -z "$SUDO" ] && echo "$H: (no passwordless sudo: only files readable by $(id -un) were searched)"
for d in /etc /root /opt /srv /usr/local/bin /usr/local/etc /home/*/docker /home/*/.config /var/lib/docker/volumes; do
  [ -d "$d" ] || continue
  $SUDO grep -rInE "$PAT" "$d" \
    --exclude-dir=Cache --exclude-dir=Logs --exclude-dir=logs --exclude-dir=log --exclude-dir=Metadata \
    --exclude-dir=Media --exclude-dir=transcode --exclude-dir=.git --exclude-dir=node_modules \
    --exclude-dir=Crash\ Reports --exclude='*.log' --exclude='*.log.*' --exclude='*history*' \
    --exclude='*.db' --exclude='*.db-*' --exclude='*.sqlite*' --exclude='querylog*' 2>/dev/null
done | sed -E 's#(://[^:/@ ]+:)[^@ ]+@#\1<redacted>@#g; s#\b((password|passwd|pass|token|secret|api[_-]?key|auth[_-]?key)[[:space:]]*[=:][[:space:]]*)[^[:space:],"]+#\1<redacted>#Ig; s#(Bearer |sk-)[A-Za-z0-9_-]{6,}#\1<redacted>#g' \
  | cut -c1-220 | sort -u | head -150 | sed "s|^|$H: |"
echo "$H: --- done"
