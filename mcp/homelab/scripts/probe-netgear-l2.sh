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

# Encode Python probe script into base64 to ensure 100% immunity to shell escaping collisions
B64_SCRIPT=$(base64 -w 0 << 'EOF'
import socket, struct, json, os, sys

switch_ip = sys.argv[1] if len(sys.argv) > 1 else '192.168.1.220'

# 1. Determine local host MAC on VLAN 1
mgr_mac = bytes.fromhex('a029198f5d45')
for iface in ['vmbr0', 'br-lan', 'lan0', 'eth0']:
    path = f'/sys/class/net/{iface}/address'
    if os.path.exists(path):
        mgr_mac = bytes(int(b, 16) for b in open(path).read().strip().split(':'))
        break

# Switch MAC from ARP table or fallback to learned MAC
sw_mac = bytes.fromhex('841b5e98f1f4')
if os.path.exists('/proc/net/arp'):
    for line in open('/proc/net/arp'):
        parts = line.split()
        if len(parts) >= 4 and parts[0] == switch_ip:
            if parts[3] != '00:00:00:00:00:00':
                sw_mac = bytes(int(b, 16) for b in parts[3].split(':'))
                break

mgr_mac_str = ":".join("%02x" % b for b in mgr_mac)
sw_mac_str = ":".join("%02x" % b for b in sw_mac)
print("Using Manager MAC: " + mgr_mac_str)
print("Target Switch MAC: " + sw_mac_str)

# 2. Build Read Request matching authentic ProSAFE broadcast/unicast query
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
    b'\x00' * 4             # Padding
)

# Core query tags matching ProSAFE Frame #1 & discovery
tags = [
    0x0001, 0x0002, 0x0003, 0x0004, 0x0005, 0x0006, 0x0007, 0x0008,
    0x000B, 0x000C, 0x000D, 0x000E, 0x000F, 0x7400, 0x0C00, 0x1000,
    0x6000, 0x7800
]
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
    sock.sendto(header + body, (switch_ip, 63322))
    
    resp, addr = sock.recvfrom(4096)
    print(f'✅ Switch responded from {addr[0]} ({len(resp)} bytes)')
    
    if len(resp) >= 32 and resp[24:28] == b'NSDP':
        offset = 32
        tlvs = {}
        tag_names = {
            0x0001: 'Model', 0x0002: 'Code2', 0x0003: 'DeviceName', 0x0004: 'MAC',
            0x0005: 'Location', 0x0006: 'IP', 0x0007: 'Netmask', 0x0008: 'Gateway',
            0x000B: 'DHCPMode', 0x000C: 'Code0C', 0x000D: 'Firmware_B1',
            0x000E: 'Firmware_B2', 0x000F: 'ActiveSlot', 0x7400: 'CapabilityMask',
            0x0C00: 'PortLink', 0x1000: 'PortStats', 0x6000: 'PortCount', 0x7800: 'SystemStatus'
        }
        while offset + 4 <= len(resp):
            tag, length = struct.unpack_from('>HH', resp, offset)
            offset += 4
            if tag == 0xFFFF or offset + length > len(resp):
                break
            val = resp[offset:offset+length]
            name = tag_names.get(tag, f'0x{tag:04X}')
            if tag in (0x0001, 0x0003, 0x000D, 0x000E):
                tlvs[name] = val.decode('ascii', errors='replace').strip('\x00')
            elif tag == 0x0004:
                tlvs[name] = ':'.join('%02x' % b for b in val)
            elif tag in (0x0006, 0x0007, 0x0008):
                tlvs[name] = socket.inet_ntoa(val)
            elif tag == 0x0C00:
                speed_map = {0: 'Down', 1: '10M-H', 2: '10M-F', 3: '100M-H', 4: '100M-F', 5: '1000M-F'}
                stride = 3 if len(val) % 3 == 0 and len(val) // 3 in (5, 8, 16, 24) else (4 if len(val) % 4 == 0 else 3)
                num_p = len(val) // stride
                ports = []
                for i in range(num_p):
                    p_bytes = val[i*stride : (i+1)*stride]
                    pid = p_bytes[0]
                    pspd = p_bytes[1]
                    s_str = speed_map.get(pspd, f'Code {pspd}')
                    ports.append(f'Port {pid}: {s_str}')
                tlvs[name] = ports
            elif tag == 0x6000 and len(val) >= 1:
                tlvs[name] = val[0]
            else:
                tlvs[name] = f'{len(val)}B (hex: {val[:16].hex()}...)'
            offset += length
        print(json.dumps(tlvs, indent=2))
except Exception as e:
    print(f'Unicast query timed out or errored: {e}. Trying broadcast discovery...')
    try:
        bcast_header = struct.pack(
            '>BBHI6s6sHH4s4s',
            0x01, 0x01, 0x0000, 0x00000000,
            mgr_mac, b'\x00'*6, 0x0000, 0x0353,
            b'NSDP', b'\x00'*4
        )
        sock.sendto(bcast_header + body, ('192.168.1.255', 63322))
        resp, addr = sock.recvfrom(4096)
        print(f'✅ Switch responded via broadcast from {addr[0]} ({len(resp)} bytes)')
    except Exception as e2:
        print(f'Broadcast also failed: {e2}')
finally:
    sock.close()
EOF
)

ssh "${SSH_OPTS[@]}" "root@${RELAY_HOST}" "echo '${B64_SCRIPT}' | base64 -d | python3 - '${SWITCH_IP}'"
