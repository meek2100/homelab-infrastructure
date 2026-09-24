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

# Pipe the Python probe script directly through SSH standard input to python3
# This eliminates reliance on remote base64 binaries (which Busybox/OpenWrt lacks) and shell quoting
ssh "${SSH_OPTS[@]}" "root@${RELAY_HOST}" "python3 - '${SWITCH_IP}'" << 'EOF'
import socket, struct, json, os, sys, time

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
seq = int(time.time() * 10) & 0xFFFF
header = struct.pack(
    '>BBHI6s6sHH4s4s',
    0x01,                   # Version: 0x01
    0x01,                   # Opcode: 0x01 Read Request
    0x0000,                 # Result code: OK
    0x00000000,             # Failure TLV
    mgr_mac,                # Host Manager MAC
    sw_mac,                 # Target Switch MAC
    0x0000,                 # Reserved alignment
    seq,                    # Dynamic Sequence ID
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
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
try:
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
except Exception:
    pass
sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

try:
    sock.bind(('', 63321))
except Exception as be:
    print(f"Warning: could not bind source port 63321: {be}")

resp = None
addr = None

# Retry unicast up to 3 times (UDP packet loss protection)
for attempt in range(1, 4):
    try:
        sock.settimeout(2.0)
        sock.sendto(header + body, (switch_ip, 63322))
        resp, addr = sock.recvfrom(4096)
        if resp:
            break
    except Exception:
        time.sleep(0.3)

if not resp:
    print('Unicast query timed out after 3 attempts. Trying broadcast discovery...')
    bcast_header = struct.pack(
        '>BBHI6s6sHH4s4s',
        0x01, 0x01, 0x0000, 0x00000000,
        mgr_mac, b'\x00'*6, 0x0000, (seq + 1) & 0xFFFF,
        b'NSDP', b'\x00'*4
    )
    for b_target in ['192.168.1.255', '255.255.255.255']:
        try:
            sock.settimeout(2.0)
            sock.sendto(bcast_header + body, (b_target, 63322))
            resp, addr = sock.recvfrom(4096)
            if resp:
                break
        except Exception:
            pass

sock.close()

if not resp:
    print('❌ All queries (unicast and broadcast) timed out.')
    sys.exit(1)

print(f'✅ Switch responded from {addr[0]} ({len(resp)} bytes)')

if len(resp) >= 32 and resp[24:28] == b'NSDP':
    offset = 32
    tlvs = {}
    tag_names = {
        0x0001: 'Model', 0x0002: 'Code2', 0x0003: 'DeviceName', 0x0004: 'MAC',
        0x0005: 'Location', 0x0006: 'IP', 0x0007: 'Netmask', 0x0008: 'Gateway',
        0x000B: 'DHCPMode', 0x000C: 'Code0C', 0x000D: 'Firmware_B1',
        0x000E: 'Firmware_B2', 0x000F: 'ActiveSlot', 0x7400: 'CapabilityMask',
        0x6000: 'PortCount', 0x7800: 'SystemStatus'
    }
    port_links = []
    port_stats = []
    speed_map = {0: 'Down', 1: '10M-H', 2: '10M-F', 3: '100M-H', 4: '100M-F', 5: '1000M-F'}

    while offset + 4 <= len(resp):
        tag, length = struct.unpack_from('>HH', resp, offset)
        offset += 4
        if tag == 0xFFFF or offset + length > len(resp):
            break
        val = resp[offset:offset+length]
        if tag == 0x0C00:
            if len(val) == 3:
                pid, spd, dupx = val[0], val[1], val[2]
                port_links.append(f'Port {pid}: {speed_map.get(spd, f"Code {spd}")}')
            elif len(val) % 3 == 0:
                for i in range(len(val) // 3):
                    p = val[i*3:(i+1)*3]
                    port_links.append(f'Port {p[0]}: {speed_map.get(p[1], f"Code {p[1]}")}')
        elif tag == 0x1000:
            if len(val) == 49:
                pid = val[0]
                rx_b, tx_b, rx_p, tx_p, crc, drp = struct.unpack_from('>QQQQQQ', val, 1)
                port_stats.append({
                    'port': pid, 'rx_bytes': rx_b, 'tx_bytes': tx_b,
                    'rx_pkts': rx_p, 'tx_pkts': tx_p, 'crc': crc, 'drops': drp
                })
        else:
            name = tag_names.get(tag, f'0x{tag:04X}')
            if tag in (0x0001, 0x0003, 0x000D, 0x000E):
                tlvs[name] = val.decode('ascii', errors='replace').strip('\x00')
            elif tag == 0x0004:
                tlvs[name] = ':'.join('%02x' % b for b in val)
            elif tag in (0x0006, 0x0007, 0x0008):
                tlvs[name] = socket.inet_ntoa(val)
            elif tag == 0x6000 and len(val) >= 1:
                tlvs[name] = val[0]
            else:
                tlvs[name] = f'{len(val)}B (hex: {val[:16].hex()}...)'
        offset += length

    if port_links:
        tlvs['PortLinks'] = sorted(port_links, key=lambda x: int(x.split()[1].rstrip(':')))
    if port_stats:
        tlvs['PortStats'] = sorted(port_stats, key=lambda x: x['port'])
    print(json.dumps(tlvs, indent=2))
EOF
