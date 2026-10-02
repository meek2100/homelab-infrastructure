#!/bin/sh
# sweep-stale-ips.sh: READ-ONLY. Lists config lines that still mention the retired VLAN 1 addresses of
# hosts that moved to VLAN 40 (nexus .185, nexus-server2 .186, media-server .247, NAS .248, luna .249),
# and tags each hit by whether anything still uses it:
#   ACTIVE  a container that is running or ran within ACTIVE_DAYS mounts this path  -> real finding
#   STALE   the container that mounts it exists but has not run within ACTIVE_DAYS -> leftover
#   ORPHAN  inside a docker data dir, but no container mounts it                   -> leftover
#   COMPOSE a Portainer/compose stack file (check whether that stack still runs)
#   BACKUP  a path containing "backup"
#   SYSTEM  host config outside docker (/etc, /root, ...)
#   COMMENT the matching line is commented out (#, ; or //), so it has no effect
# It also prints a leftover inventory: docker app dirs that no active container uses, and containers
# that have not run within ACTIVE_DAYS. Credentials on matching lines are redacted.
#   PowerShell: Get-Content sweep-stale-ips.sh -Raw | ssh <host> "tr -d '\r' | sh -s"
PAT='192\.168\.1\.(185|186|247|248|249)([^0-9]|$)'
ACTIVE_DAYS=14
H=$(hostname)
NOW=$(date +%s)
CUTOFF=$((NOW - ACTIVE_DAYS * 86400))
SUDO=""
[ "$(id -u)" -ne 0 ] && command -v sudo >/dev/null 2>&1 && sudo -n true 2>/dev/null && SUDO="sudo -n"
[ "$(id -u)" -ne 0 ] && [ -z "$SUDO" ] && echo "$H: (no passwordless sudo: only files readable by $(id -un) were searched)"
TMP=$(mktemp -d 2>/dev/null || echo /tmp/sweep.$$); mkdir -p "$TMP"
MAP="$TMP/map"; HITS="$TMP/hits"; : > "$MAP"

# Container map: "<last-active-epoch>|<status>|<name>|<mount-src>|<mount-src>..."
DOCKER=no
if command -v docker >/dev/null 2>&1 && $SUDO docker ps -aq >/dev/null 2>&1; then
  DOCKER=yes
  for id in $($SUDO docker ps -aq); do
    $SUDO docker inspect --format '{{.State.Status}}|{{.State.StartedAt}}|{{.State.FinishedAt}}|{{.Name}}{{range .Mounts}}|{{.Source}}{{end}}' "$id" 2>/dev/null
  done | while IFS='|' read -r st started finished name rest; do
    if [ "$st" = "running" ] || [ "$st" = "restarting" ]; then last=$NOW
    else
      s=$(date -d "$started" +%s 2>/dev/null || echo 0); f=$(date -d "$finished" +%s 2>/dev/null || echo 0)
      [ "$s" -gt "$f" ] && last=$s || last=$f
    fi
    echo "$last|$st|${name#/}|$rest"
  done > "$MAP"
fi

for d in /etc /root /opt /srv /usr/local/bin /usr/local/etc /home/*/docker /home/*/.config /var/lib/docker/volumes; do
  [ -d "$d" ] || continue
  $SUDO grep -rInE "$PAT" "$d" \
    --exclude-dir=Cache --exclude-dir=Logs --exclude-dir=logs --exclude-dir=log --exclude-dir=Metadata \
    --exclude-dir=Media --exclude-dir=transcode --exclude-dir=.git --exclude-dir=node_modules \
    --exclude-dir=Crash\ Reports --exclude='*.log' --exclude='*.log.*' --exclude='*history*' \
    --exclude='*.db' --exclude='*.db-*' --exclude='*.sqlite*' --exclude='querylog*' 2>/dev/null
done | sed -E 's#(://[^:/@ ]+:)[^@ ]+@#\1<redacted>@#g; s#\b((password|passwd|pass|token|secret|api[_-]?key|auth[_-]?key)[[:space:]]*[=:][[:space:]]*)[^[:space:],"]+#\1<redacted>#Ig; s#(Bearer |sk-)[A-Za-z0-9_-]{6,}#\1<redacted>#g' \
  | cut -c1-220 | sort -u > "$HITS"

# Tag each hit with the container (longest mount-source prefix) whose mount contains the file
awk -v cutoff="$CUTOFF" -v docker="$DOCKER" -v H="$H" '
  FILENAME == ARGV[1] { n = split($0, a, "|"); for (i = 4; i <= n; i++) if (a[i] != "") { m++; src[m] = a[i]; who[m] = a[3]; last[m] = a[1]; st[m] = a[2] }; next }
  {
    line = $0; file = line; sub(/:[0-9]+:.*/, "", file)
    body = line; sub(/^[^:]*:[0-9]+:/, "", body)
    best = 0; bl = 0
    for (i = 1; i <= m; i++) { s = src[i]; l = length(s)
      if ((file == s || substr(file, 1, l + 1) == s "/") && l > bl) { best = i; bl = l } }
    if (body ~ /^[[:space:]]*(#|;|\/\/)/) tag = "COMMENT"
    else if (tolower(file) ~ /backup/) tag = "BACKUP"
    else if (file ~ /\/compose\/[0-9]+\//) tag = "COMPOSE"
    else if (best) {
      if (last[best] + 0 >= cutoff) tag = "ACTIVE(" who[best] ")"
      else { cmd = "date -d @" last[best] " +%F"; cmd | getline dt; close(cmd); tag = "STALE(" who[best] " " st[best] ", last ran " dt ")" }
    }
    else if (file ~ /^\/home\/[^\/]+\/docker\// || file ~ /^\/var\/lib\/docker\//) tag = (docker == "yes") ? "ORPHAN(no container mounts it)" : "DOCKER?(no docker access)"
    else tag = "SYSTEM"
    k = tag; sub(/\(.*/, "", k); count[k]++
    print H ": [" tag "] " line
  }
  END { for (t in count) printf "%s: summary %s=%d\n", H, t, count[t] }
' "$MAP" "$HITS"

# Leftover inventory (only when docker is readable)
if [ "$DOCKER" = "yes" ]; then
  for appdir in /home/*/docker/*/; do
    [ -d "$appdir" ] || continue; a=${appdir%/}
    why=$(awk -v a="$a" -v cutoff="$CUTOFF" -F'|' '{ for (i = 4; i <= NF; i++) if ($i == a || index($i, a "/") == 1) { any = 1; if ($1 + 0 >= cutoff) act = 1 } }
      END { if (!any) print "unused"; else if (!act) print "inactive" }' "$MAP")
    [ -n "$why" ] && echo "$H: [LEFTOVER dir, $why by any container in ${ACTIVE_DAYS}d] $a"
  done
  awk -v cutoff="$CUTOFF" -F'|' '$1 + 0 < cutoff { print $1 "|" $2 "|" $3 }' "$MAP" | while IFS='|' read -r t st name; do
    echo "$H: [LEFTOVER container] $name ($st, last ran $(date -d "@$t" +%F 2>/dev/null))"; done
fi
rm -rf "$TMP"
echo "$H: --- done"
