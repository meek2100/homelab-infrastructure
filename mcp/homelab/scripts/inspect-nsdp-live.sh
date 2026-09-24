#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARSER_SCRIPT="${SCRIPT_DIR}/parse-nsdp-capture.py"
PVE_HOST="192.168.1.250"
VM_ID="102"

SSH_KEY=""
for candidate in \
  "${HOME}/.ssh/proxmox_ed25519" \
  "/home/dtheurer/.ssh/proxmox_ed25519" \
  "${HOME}/.ssh/id_ed25519" \
  "/home/dtheurer/.ssh/id_ed25519"; do
  if [ -f "$candidate" ]; then
    SSH_KEY="$candidate"
    break
  fi
done

SSH_OPTS=(-o StrictHostKeyChecking=accept-new -o BatchMode=yes)
if [ -n "$SSH_KEY" ]; then
  SSH_OPTS+=(-i "$SSH_KEY")
fi

echo "📡 Reading active Wireshark capture on luna-server (VM ${VM_ID}) via ${PVE_HOST}..."

B64_PAYLOAD=$(base64 -w 0 "${PARSER_SCRIPT}")

ssh "${SSH_OPTS[@]}" "root@${PVE_HOST}" "qm guest exec ${VM_ID} -- sh -c '
  echo \"${B64_PAYLOAD}\" | base64 -d > /tmp/parse_nsdp.py
  docker cp /tmp/parse_nsdp.py wireshark:/tmp/parse_nsdp.py
  docker exec wireshark python3 /tmp/parse_nsdp.py /captures
'" | python3 -c '
import sys, json
try:
    raw = sys.stdin.read()
    data = json.loads(raw)
    out = data.get("out-data", "")
    err = data.get("err-data", "")
    if out:
        print(out)
    if err:
        print("STDERR:", err)
except Exception:
    print(raw)
'
