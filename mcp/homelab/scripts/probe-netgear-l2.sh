#!/usr/bin/env bash
set -euo pipefail

PVE_HOST="192.168.1.250"
SWITCH_IP="${1:-192.168.1.220}"

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

echo "🔍 Probing Netgear GS108Ev2 (${SWITCH_IP}) via Proxmox pve (${PVE_HOST} on VLAN 1)..."

ssh "${SSH_OPTS[@]}" "root@${PVE_HOST}" "python3 -c \"
import socket, struct, json, sys

header = struct.pack(
    '>BBHI6s6sHH4s4s',
    0x01, 0x01, 0x0000, 0x00000000,
    b'\\x00'*6, b'\\x00'*6, 0x0000, 1,
    b'NSDP', b'\\x00'*4
)
tags = [0x0001, 0x0003, 0x0004, 0x0006, 0x0007, 0x0008, 0x000D, 0x0C00, 0x1000]
body = b''.join(struct.pack('>HH', t, 0) for t in tags) + struct.pack('>HH', 0xFFFF, 0)

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.settimeout(3.0)
try:
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.sendto(header + body, ('${SWITCH_IP}', 63322))
    resp, addr = sock.recvfrom(4096)
    print(f'✅ Switch responded from {addr[0]} ({len(resp)} bytes)')
    
    if len(resp) >= 32 and resp[24:28] == b'NSDP':
        offset = 32
        tlvs = {}
        tag_names = {
            0x0001: 'Model', 0x0003: 'DeviceName', 0x0004: 'MAC',
            0x0006: 'IP', 0x0007: 'Netmask', 0x0008: 'Gateway',
            0x000D: 'Firmware', 0x0C00: 'PortLink', 0x1000: 'PortStats'
        }
        while offset + 4 <= len(resp):
            tag, length = struct.unpack_from('>HH', resp, offset)
            offset += 4
            if tag == 0xFFFF or offset + length > len(resp):
                break
            val = resp[offset:offset+length]
            name = tag_names.get(tag, hex(tag))
            if tag in (0x0001, 0x0003, 0x000D):
                tlvs[name] = val.decode('ascii', errors='replace').strip('\\x00')
            elif tag == 0x0004:
                tlvs[name] = ':'.join(f'{b:02x}' for b in val)
            elif tag in (0x0006, 0x0007, 0x0008):
                tlvs[name] = socket.inet_ntoa(val)
            else:
                tlvs[name] = f'{len(val)} bytes'
            offset += length
        print(json.dumps(tlvs, indent=2))
except Exception as e:
    print(f'Query error: {e}')
finally:
    sock.close()
\""
