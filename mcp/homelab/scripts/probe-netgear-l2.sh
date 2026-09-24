#!/usr/bin/env bash
set -euo pipefail

SWITCH_IP="${1:-192.168.1.220}"
RELAY_HOST="${2:-192.168.1.250}"

SSH_OPTS=(-o StrictHostKeyChecking=accept-new -o BatchMode=yes -o ConnectTimeout=5)
for candidate in \
  "${HOME}/.ssh/proxmox_ed25519" \
  "/home/dtheurer/.ssh/proxmox_ed25519" \
  "${HOME}/.ssh/id_ed25519" \
  "/home/dtheurer/.ssh/id_ed25519" \
  "${HOME}/.ssh/pi_id_ed25519" \
  "/home/dtheurer/.ssh/pi_id_ed25519"; do
  if [ -f "$candidate" ]; then
    SSH_OPTS+=(-i "$candidate")
  fi
done

echo "🔍 Probing Netgear GS108Ev2 (${SWITCH_IP}) via Layer 2 relay ${RELAY_HOST} on VLAN 1..."

ssh "${SSH_OPTS[@]}" "root@${RELAY_HOST}" "python3 -c \"
import socket, struct, json, os, sys

# 1. Determine local host MAC on VLAN 1
mgr_mac = bytes.fromhex('a029198f5d45')
for iface in ['vmbr0', 'br-lan', 'lan0', 'eth0']:
    path = f'/sys/class/net/{iface}/address'
    if os.path.exists(path):
        mgr_mac = bytes(int(b, 16) for b in open(path).read().strip().split(':'))
        break

# Switch MAC learned from live Wireshark ProSAFE capture
sw_mac = bytes.fromhex('841b5e98f1f4')

print(f'Using Manager MAC: {\":\".join(f\"{b:02x}\" for b in mgr_mac)}')
print(f'Target Switch MAC: {\":\".join(f\"{b:02x}\" for b in sw_mac)}')

# 2. Build Read Request matching authentic ProSAFE broadcast query
header = struct.pack(
    '>BBHI6s6sHH4s4s',
    0x01,                   # Version: 0x01
    0x01,                   # Opcode: 0x01 Read Request
    0x0000,                 # Result code: OK
    0x00000000,             # Failure TLV
    mgr_mac,                # Host Manager MAC
    sw_mac,                 # Target Switch MAC
    0x0000,                 # Reserved alignment
    0x0353,                 # Sequence ID
    b'NSDP',                # Signature
    b'\\x00'*4              # Padding
)

# Core query tags matching ProSAFE Frame #1
tags = [0x0001, 0x0002, 0x0003, 0x0004, 0x0006, 0x0007, 0x0008, 0x000D, 0x0C00, 0x1000]
body = b''.join(struct.pack('>HH', t, 0) for t in tags) + bytes.fromhex('ffff0000')

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.settimeout(3.0)
try:
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    try:
        sock.bind(('', 63321))
    except Exception:
        pass

    # Try unicast to switch IP first
    sock.sendto(header + body, ('${SWITCH_IP}', 63322))
    
    resp, addr = sock.recvfrom(4096)
    print(f'✅ Switch responded from {addr[0]} ({len(resp)} bytes)')
    
    if len(resp) >= 32 and resp[24:28] == b'NSDP':
        offset = 32
        tlvs = {}
        tag_names = {
            0x0001: 'Model', 0x0002: 'Code2', 0x0003: 'DeviceName', 0x0004: 'MAC',
            0x0006: 'IP', 0x0007: 'Netmask', 0x0008: 'Gateway',
            0x000D: 'Firmware', 0x0C00: 'PortLink', 0x1000: 'PortStats'
        }
        while offset + 4 <= len(resp):
            tag, length = struct.unpack_from('>HH', resp, offset)
            offset += 4
            if tag == 0xFFFF or offset + length > len(resp):
                break
            val = resp[offset:offset+length]
            name = tag_names.get(tag, f'0x{tag:04X}')
            if tag in (0x0001, 0x0003, 0x000D):
                tlvs[name] = val.decode('ascii', errors='replace').strip('\\x00')
            elif tag == 0x0004:
                tlvs[name] = ':'.join(f'{b:02x}' for b in val)
            elif tag in (0x0006, 0x0007, 0x0008):
                tlvs[name] = socket.inet_ntoa(val)
            else:
                tlvs[name] = f'{len(val)} bytes (hex: {val[:16].hex()}...)'
            offset += length
        print(json.dumps(tlvs, indent=2))
except Exception as e:
    print(f'Unicast query timed out or errored: {e}. Trying broadcast discovery...')
    try:
        bcast_header = struct.pack(
            '>BBHI6s6sHH4s4s',
            0x01, 0x01, 0x0000, 0x00000000,
            mgr_mac, b'\\x00'*6, 0x0000, 0x0353,
            b'NSDP', b'\\x00'*4
        )
        sock.sendto(bcast_header + body, ('192.168.1.255', 63322))
        resp, addr = sock.recvfrom(4096)
        print(f'✅ Switch responded via broadcast from {addr[0]} ({len(resp)} bytes)')
    except Exception as e2:
        print(f'Broadcast also failed: {e2}')
finally:
    sock.close()
\""
