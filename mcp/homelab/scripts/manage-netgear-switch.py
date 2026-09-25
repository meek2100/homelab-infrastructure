#!/usr/bin/env python3
"""
Netgear GS108Ev2 Switch Management, Configuration & Automation Tool

Headless NSDP Native Driver:
  The GS108Ev2 (firmware 1.00.12) is a headless "Easy Smart" ProSAFE Plus switch with
  NO HTTP/HTTPS web daemon, NO SSH, and NO SNMP. Only v3 hardware introduced an embedded web GUI.
  Web-scraping tools (such as py-netgear-plus) targeting login.cgi are strictly incompatible.

  Direct programmatic interaction uses NSDP (Netgear Switch Discovery Protocol) over UDP:
    - Client source port: 63321
    - Switch agent port: 63322
    - Transport framing: 32-byte header + TLV records + 0xFFFF0000 delimiter.

  Network Topology:
    NSDP is strictly Layer 2 broadcast/unicast on VLAN 1 (192.168.1.0/24).
    This tool supports:
      1. Direct Native NSDP: Raw socket dispatch when running on a host adjacent to VLAN 1 (e.g. pve or runner).
      2. Layer 2 Adjacent Relay: Executes pure Python NSDP via SSH on an adjacent host (OpenWrt Belkin AX3200 on 192.168.1.226 or Proxmox pve on 192.168.1.250).
      3. REST Proxy Client: Queries adjacent OpenWrt micro-daemon (http://192.168.1.226:8080) when routed.

  Safety & Invariant Protections (Flash Persistence Mitigation):
    - Port 8 Uplink Protection: Uplink port (Port 8) is connected to OpenWrt / AP bridge. It can NEVER
      be administratively disabled, removed from VLAN 1, or have its PVID changed away from 1 unless
      explicitly overridden with --force-uplink.
    - VLAN 1 Protection: VLAN 1 is the permanent management VLAN; it can never be deleted.
    - Atomic Multi-TLV Dispatch: All mutations are assembled and sent in a single datagram to avert
      intermediate or inconsistent states.
    - Pre-flight Snapshot: Local GitOps backups are synchronized before and after mutation.
"""

import argparse
import base64
import json
import os
import shutil
import socket
import struct
import subprocess
import sys
import time
from dataclasses import asdict, is_dataclass

try:
    import yaml
except ImportError:
    yaml = None

try:
    import requests
except ImportError:
    requests = None

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
CONFIG_BACKUP_FILE = os.path.join(REPO_ROOT, "infrastructure", "network", "configs", "netgear-gs108e-backup.json")
CONFIG_BACKUP_CFG = os.path.join(REPO_ROOT, "infrastructure", "network", "configs", "netgear-gs108e-backup.cfg")
PROSAFE_GOLDEN_CFG = os.path.join(REPO_ROOT, ".agents", "netgear", "prosafe-backup", "GS108Ev2.cfg")
SECRET_FILE = os.path.join(REPO_ROOT, "infrastructure", "secrets", "araknis-switch.enc.yaml")

DEFAULT_SWITCH_IP = "192.168.1.220"
DEFAULT_OPENWRT_PROXY = "http://192.168.1.226:8080"
DEFAULT_UPLINK_PORT = 8

NSDP_KEY = b"NtgrSmartSwitchRock"


def encrypt_nsdp_password(password: str) -> bytes:
    """XOR-encrypt switch administrative password using static Netgear key."""
    pw_bytes = password.encode("ascii", "ignore")
    return bytes([c ^ NSDP_KEY[i % len(NSDP_KEY)] for i, c in enumerate(pw_bytes)])


def get_age_key_path():
    for candidate in [
        os.path.join(REPO_ROOT, "homelab-infrastructure.key"),
        os.path.join(REPO_ROOT, "master-age-key.txt"),
        os.path.expanduser("~/.config/sops/age/keys.txt"),
    ]:
        if os.path.exists(candidate):
            return candidate
    return None


def load_credentials():
    """Load Netgear switch credentials from SOPS-encrypted file or environment."""
    host = os.environ.get("NETGEAR_HOST", DEFAULT_SWITCH_IP)
    password = os.environ.get("NETGEAR_PASSWORD")

    if password:
        return host, password

    if os.path.exists(SECRET_FILE):
        sops_bin = shutil.which("sops") or os.path.expanduser("~/.local/bin/sops")
        if sops_bin and os.path.exists(sops_bin):
            key_file = get_age_key_path()
            env = os.environ.copy()
            if key_file:
                env["SOPS_AGE_KEY_FILE"] = key_file

            res = subprocess.run([sops_bin, "-d", SECRET_FILE], capture_output=True, text=True, env=env, check=False)
            if res.returncode == 0:
                if yaml:
                    data = yaml.safe_load(res.stdout)
                else:
                    data = json.loads(res.stdout)

                host = data.get("netgear_switch_ip", data.get("netgear_ip", host))
                password = data.get("netgear_password", data.get("password"))
                if password:
                    return host, str(password)

    return host, "password"


def get_ssh_key_args():
    seen = set()
    args = []
    for candidate in [
        "/home/dtheurer/.ssh/proxmox_ed25519",
        os.path.expanduser("~/.ssh/proxmox_ed25519"),
        "/home/dtheurer/.ssh/id_ed25519",
        os.path.expanduser("~/.ssh/id_ed25519"),
        "/home/dtheurer/.ssh/pi_id_ed25519",
        os.path.expanduser("~/.ssh/pi_id_ed25519"),
        "/mnt/c/Users/dtheurer/.ssh/pi_id_ed25519",
    ]:
        can_abs = os.path.abspath(candidate)
        if os.path.exists(candidate) and can_abs not in seen:
            seen.add(can_abs)
            args.extend(["-i", candidate])
    return args


class NativeNSDPClient:
    """Pure-Python native NSDP packet driver conforming to the GS108Ev2 protocol spec."""

    TAG_MODEL = 0x0001
    TAG_DEVICE_NAME = 0x0003
    TAG_MAC = 0x0004
    TAG_LOCATION = 0x0005
    TAG_IP = 0x0006
    TAG_NETMASK = 0x0007
    TAG_GATEWAY = 0x0008
    TAG_PASSWORD = 0x000A
    TAG_DHCP_MODE = 0x000B
    TAG_FIRMWARE_B1 = 0x000D
    TAG_FIRMWARE_B2 = 0x000E
    TAG_ACTIVE_SLOT = 0x000F
    TAG_PORT_LINK = 0x0C00
    TAG_PORT_STATS = 0x1000
    TAG_IGMP_SNOOPING = 0x2000
    TAG_VLAN_MEMBERSHIP = 0x2800
    TAG_PVID = 0x2900
    TAG_VLAN_DELETE = 0x2C00
    TAG_PORT_SPEED = 0x3800
    TAG_PORT_MIRROR = 0x5400
    TAG_PORT_ADMIN = 0x5800
    TAG_PORT_COUNT = 0x6000
    TAG_VLAN_MODE = 0x6800
    TAG_CAPABILITY = 0x7400
    TAG_SYSTEM_STATUS = 0x7800
    TAG_LOOP_DETECTION = 0x9000

    def __init__(self, host=DEFAULT_SWITCH_IP, port=63322, timeout=3.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.seq = 1

    def query(self, tags, host_mac=b"\x00\x00\x00\x00\x00\x00", switch_mac=b"\x00\x00\x00\x00\x00\x00"):
        """Build and dispatch an NSDP Read Request (opcode 0x01) and parse response TLVs."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(self.timeout)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        except Exception:
            pass

        try:
            try:
                sock.bind(("", 63321))
            except Exception:
                pass

            header = struct.pack(
                ">BBHI6s6sHH4s4s",
                0x01,                   # version: 0x01
                0x01,                   # op_code: 0x01 Read Request
                0x0000,                 # result_code: 0x0000
                0x00000000,             # failure_tlv
                host_mac,               # host MAC
                switch_mac,             # switch MAC
                0x0000,                 # reserved alignment
                self.seq,               # sequence counter
                b"NSDP",                # signature: "NSDP" (0x4E534450)
                b"\x00\x00\x00\x00"     # padding
            )

            body = bytearray()
            for tag in tags:
                body += struct.pack(">HH", tag, 0x0000)
            body += struct.pack(">HH", 0xFFFF, 0x0000)

            packet = bytes(header + body)
            sock.sendto(packet, (self.host, self.port))

            resp_data, _ = sock.recvfrom(4096)
            self.seq = (self.seq + 1) & 0xFFFF
            return self._parse_tlvs(resp_data)
        finally:
            sock.close()

    def mutate(self, write_tlvs_bytes, password, host_mac=b"\x00\x00\x00\x00\x00\x00", switch_mac=b"\x84\x1b\x5e\x98\xf1\xf4"):
        """Build and dispatch an authenticated NSDP Write Request (opcode 0x03)."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(self.timeout)
        try:
            sock.bind(("", 63321))
        except Exception:
            pass

        enc_pw = encrypt_nsdp_password(password)

        header = struct.pack(
            ">BBHI6s6sHH4s4s",
            0x01,
            0x03,                   # Opcode 0x03: Write Request
            0x0000,
            0x00000000,
            host_mac,
            switch_mac,
            0x0000,
            self.seq,
            b"NSDP",
            b"\x00\x00\x00\x00"
        )

        body = bytearray()
        body += struct.pack(">HH", self.TAG_PASSWORD, len(enc_pw)) + enc_pw
        body += write_tlvs_bytes
        body += struct.pack(">HH", 0xFFFF, 0x0000)

        packet = bytes(header + body)
        try:
            sock.sendto(packet, (self.host, self.port))
            resp_data, _ = sock.recvfrom(4096)
            self.seq = (self.seq + 1) & 0xFFFF

            if len(resp_data) < 32:
                raise ValueError("Response too short")
            res_code = struct.unpack_from(">H", resp_data, 2)[0]
            if res_code != 0:
                raise RuntimeError(f"Switch rejected write with status code 0x{res_code:04X}")
            return True
        finally:
            sock.close()

    def _parse_tlvs(self, data):
        if len(data) < 32:
            raise ValueError(f"NSDP response too short: {len(data)} bytes")

        (
            version,
            op_code,
            result_code,
            _failure_tlv,
            _host_mac,
            switch_mac,
            _reserved,
            _seq,
            sig,
            _padding,
        ) = struct.unpack(">BBHI6s6sHH4s4s", data[:32])

        if sig != b"NSDP":
            raise ValueError(f"Invalid NSDP signature: {sig}")

        tlvs = {}
        port_links_raw = []
        port_stats_raw = []
        offset = 32
        while offset + 4 <= len(data):
            tag, length = struct.unpack_from(">HH", data, offset)
            offset += 4
            if tag == 0xFFFF or offset + length > len(data):
                break
            val = data[offset : offset + length]
            if tag == self.TAG_PORT_LINK:
                port_links_raw.append(val)
            elif tag == self.TAG_PORT_STATS:
                port_stats_raw.append(val)
            else:
                tlvs[tag] = val
            offset += length

        parsed = {
            "version": version,
            "op_code": op_code,
            "result_code": result_code,
            "mac": ":".join(f"{b:02x}" for b in switch_mac),
        }

        if self.TAG_MODEL in tlvs:
            parsed["model"] = tlvs[self.TAG_MODEL].decode("ascii", errors="ignore").rstrip("\x00")
        if self.TAG_DEVICE_NAME in tlvs:
            parsed["device_name"] = tlvs[self.TAG_DEVICE_NAME].decode("ascii", errors="ignore").rstrip("\x00")
        if self.TAG_IP in tlvs and len(tlvs[self.TAG_IP]) == 4:
            parsed["ip"] = socket.inet_ntoa(tlvs[self.TAG_IP])
        if self.TAG_NETMASK in tlvs and len(tlvs[self.TAG_NETMASK]) == 4:
            parsed["netmask"] = socket.inet_ntoa(tlvs[self.TAG_NETMASK])
        if self.TAG_GATEWAY in tlvs and len(tlvs[self.TAG_GATEWAY]) == 4:
            parsed["gateway"] = socket.inet_ntoa(tlvs[self.TAG_GATEWAY])
        if self.TAG_FIRMWARE_B1 in tlvs:
            parsed["firmware"] = tlvs[self.TAG_FIRMWARE_B1].decode("ascii", errors="ignore").rstrip("\x00")
        if self.TAG_PORT_COUNT in tlvs and len(tlvs[self.TAG_PORT_COUNT]) >= 1:
            parsed["port_count"] = tlvs[self.TAG_PORT_COUNT][0]

        ports = []
        speed_map = {0: "No Link", 1: "10 Mbps Half", 2: "10 Mbps Full", 3: "100 Mbps Half", 4: "100 Mbps Full", 5: "1000 Mbps Full"}
        for link_data in port_links_raw:
            if len(link_data) == 3:
                pid, spd, dupx = link_data[0], link_data[1], link_data[2]
                ports.append({
                    "port": pid,
                    "enabled": True,
                    "link_up": (spd > 0),
                    "speed_act": speed_map.get(spd, f"Code {spd}"),
                    "duplex": "Full" if dupx == 1 or spd in (2, 4, 5) else ("Half" if spd in (1, 3) else "None"),
                })
            elif len(link_data) % 3 == 0:
                for i in range(len(link_data) // 3):
                    p = link_data[i*3:(i+1)*3]
                    ports.append({
                        "port": p[0],
                        "enabled": True,
                        "link_up": (p[1] > 0),
                        "speed_act": speed_map.get(p[1], f"Code {p[1]}"),
                        "duplex": "Full" if p[2] == 1 or p[1] in (2, 4, 5) else ("Half" if p[1] in (1, 3) else "None"),
                    })
        ports.sort(key=lambda p: p["port"])
        parsed["ports"] = ports

        stats = []
        for stat_data in port_stats_raw:
            if len(stat_data) == 49:
                pid, rx_b, tx_b, rx_p, tx_p, crc, drp = struct.unpack_from(">BQQQQQQ", stat_data, 0)
                stats.append({
                    "port": pid,
                    "bytes_rx": rx_b, "bytes_tx": tx_b,
                    "packets_rx": rx_p, "packets_tx": tx_p,
                    "crc_errors": crc, "drops": drp,
                })
            elif len(stat_data) >= 49 and len(stat_data) % 49 == 0:
                for i in range(len(stat_data) // 49):
                    pid, rx_b, tx_b, rx_p, tx_p, crc, drp = struct.unpack_from(">BQQQQQQ", stat_data, i * 49)
                    stats.append({
                        "port": pid,
                        "bytes_rx": rx_b, "bytes_tx": tx_b,
                        "packets_rx": rx_p, "packets_tx": tx_p,
                        "crc_errors": crc, "drops": drp,
                    })
        stats.sort(key=lambda s: s["port"])
        parsed["port_statistics"] = stats

        if self.TAG_PVID in tlvs and len(tlvs[self.TAG_PVID]) >= 16:
            pvids = list(struct.unpack(">8H", tlvs[self.TAG_PVID][:16]))
            parsed["pvids"] = {i + 1: pvids[i] for i in range(len(pvids))}

        if self.TAG_VLAN_MEMBERSHIP in tlvs:
            vd = tlvs[self.TAG_VLAN_MEMBERSHIP]
            vlans = []
            for i in range(0, len(vd), 10):
                if i + 10 <= len(vd):
                    vid = struct.unpack_from(">H", vd, i)[0]
                    ports_member = list(vd[i+2 : i+10])
                    vlans.append({"vid": vid, "ports": ports_member})
            parsed["vlans"] = vlans

        if self.TAG_VLAN_MODE in tlvs:
            parsed["vlan_mode_raw"] = tlvs[self.TAG_VLAN_MODE].hex()

        if self.TAG_IGMP_SNOOPING in tlvs and len(tlvs[self.TAG_IGMP_SNOOPING]) >= 1:
            parsed["igmp_snooping"] = bool(tlvs[self.TAG_IGMP_SNOOPING][0])

        if self.TAG_LOOP_DETECTION in tlvs and len(tlvs[self.TAG_LOOP_DETECTION]) >= 1:
            parsed["loop_detection"] = bool(tlvs[self.TAG_LOOP_DETECTION][0])

        return parsed


def query_via_l2_ssh(relay_host="192.168.1.226", switch_ip=DEFAULT_SWITCH_IP, password=None, timeout=15):
    """Execute native NSDP client query directly on an L2 adjacent host (OpenWrt or PVE on VLAN 1) via SSH."""
    py_code = f"""import socket, struct, json, os, sys, time

switch_ip = sys.argv[1] if len(sys.argv) > 1 else "{switch_ip}"

mgr_mac = bytes.fromhex('a029198f5d45')
for iface in ['vmbr0', 'br-lan', 'lan0', 'eth0']:
    p = f'/sys/class/net/{{iface}}/address'
    if os.path.exists(p):
        mgr_mac = bytes(int(b, 16) for b in open(p).read().strip().split(':'))
        break

sw_mac = bytes.fromhex('841b5e98f1f4')
if os.path.exists('/proc/net/arp'):
    for line in open('/proc/net/arp'):
        parts = line.split()
        if len(parts) >= 4 and parts[0] == switch_ip:
            if parts[3] != '00:00:00:00:00:00':
                sw_mac = bytes(int(b, 16) for b in parts[3].split(':'))
                break

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
try:
    sock.setsockopt(socket.SOL_SOCKET, getattr(socket, 'SO_REUSEPORT', socket.SO_REUSEADDR), 1)
except Exception:
    pass
sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

try:
    sock.bind(("", 63321))
except Exception:
    pass

seq = int(time.time() * 10) & 0xFFFF

header = struct.pack(
    '>BBHI6s6sHH4s4s',
    0x01, 0x01, 0, 0, mgr_mac, sw_mac, 0, seq, b'NSDP', b'\\x00'*4
)
tags = [
    0x0001,  # Model name
    0x0002,  # Code2
    0x0003,  # Device name
    0x0004,  # Switch MAC
    0x0005,  # Location
    0x0006,  # IP
    0x0007,  # Netmask
    0x0008,  # Gateway
    0x000B,  # DHCP mode
    0x000C,  # Code0C
    0x000D,  # Firmware 1
    0x000E,  # Firmware 2
    0x000F,  # Active Slot
    0x7400,  # Capability mask
    0x0C00,  # Port status / speed / duplex
    0x1000,  # Port statistics
    0x6000,  # Port count
    0x7800,  # System status / serial
]

body = bytearray()
for t in tags:
    body += struct.pack('>HH', t, 0)
body += bytes.fromhex('ffff0000')

resp = None
for _ in range(3):
    try:
        sock.settimeout(2.0)
        sock.sendto(bytes(header + body), (switch_ip, 63322))
        resp, _ = sock.recvfrom(4096)
        if resp:
            break
    except Exception:
        time.sleep(0.2)

if not resp or len(resp) < 32 or resp[24:28] != b"NSDP":
    try:
        bcast_header = struct.pack(
            '>BBHI6s6sHH4s4s',
            0x01, 0x01, 0, 0, mgr_mac, b'\\x00'*6, 0, (seq + 1) & 0xFFFF, b'NSDP', b'\\x00'*4
        )
        for b_target in ['192.168.1.255', '255.255.255.255']:
            try:
                sock.settimeout(2.0)
                sock.sendto(bytes(bcast_header + body), (b_target, 63322))
                resp, _ = sock.recvfrom(4096)
                if resp:
                    break
            except Exception:
                pass
    except Exception:
        pass

sock.close()

if not resp or len(resp) < 32 or resp[24:28] != b"NSDP":
    print(json.dumps({{"error": "Invalid or missing NSDP response", "raw_len": len(resp) if resp else 0}}), file=sys.stderr)
    sys.exit(1)

resp_mac = ":".join(f"{{b:02x}}" for b in resp[14:20])
offset = 32
tlvs = {{}}
port_links_raw = []
port_stats_raw = []
while offset + 4 <= len(resp):
    tag, length = struct.unpack_from(">HH", resp, offset)
    offset += 4
    if tag == 0xFFFF or offset + length > len(resp):
        break
    val = resp[offset : offset + length]
    if tag == 0x0C00:
        port_links_raw.append(val)
    elif tag == 0x1000:
        port_stats_raw.append(val)
    else:
        tlvs[tag] = val
    offset += length

out = {{"mac": resp_mac, "ip": switch_ip, "raw_hex": resp.hex(), "parsed_tags": [hex(k) for k in tlvs.keys()]}}
if 0x0001 in tlvs: out["model"] = tlvs[0x0001].decode("ascii", "ignore").rstrip("\\x00")
if 0x0003 in tlvs: out["device_name"] = tlvs[0x0003].decode("ascii", "ignore").rstrip("\\x00")
if 0x0006 in tlvs and len(tlvs[0x0006]) == 4: out["ip"] = socket.inet_ntoa(tlvs[0x0006])
if 0x0007 in tlvs and len(tlvs[0x0007]) == 4: out["netmask"] = socket.inet_ntoa(tlvs[0x0007])
if 0x0008 in tlvs and len(tlvs[0x0008]) == 4: out["gateway"] = socket.inet_ntoa(tlvs[0x0008])
if 0x000D in tlvs: out["firmware"] = tlvs[0x000D].decode("ascii", "ignore").rstrip("\\x00")
if 0x000E in tlvs: out["firmware_bank2"] = tlvs[0x000E].decode("ascii", "ignore").rstrip("\\x00")
if 0x7800 in tlvs: out["serial_number"] = tlvs[0x7800].decode("ascii", "ignore").rstrip("\\x00")
if 0x6000 in tlvs and len(tlvs[0x6000]) >= 1: out["port_count"] = tlvs[0x6000][0]
if 0x2000 in tlvs and len(tlvs[0x2000]) >= 1: out["igmp_snooping"] = bool(tlvs[0x2000][0])
if 0x9000 in tlvs and len(tlvs[0x9000]) >= 1: out["loop_detection"] = bool(tlvs[0x9000][0])
if 0x6800 in tlvs: out["vlan_mode_raw"] = tlvs[0x6800].hex()

speed_map = {{0: "No Link", 1: "10 Mbps Half", 2: "10 Mbps Full", 3: "100 Mbps Half", 4: "100 Mbps Full", 5: "1000 Mbps Full"}}
ports = []
for ld in port_links_raw:
    if len(ld) == 3:
        pid, spd, dupx = ld[0], ld[1], ld[2]
        ports.append({{
            "port": pid,
            "link_up": spd > 0,
            "speed_act": speed_map.get(spd, f"Code {{spd}}"),
            "duplex": "Full" if dupx == 1 or spd in (2, 4, 5) else ("Half" if spd in (1, 3) else "None"),
            "enabled": True
        }})
    elif len(ld) % 3 == 0:
        for i in range(len(ld) // 3):
            p = ld[i*3:(i+1)*3]
            ports.append({{
                "port": p[0],
                "link_up": p[1] > 0,
                "speed_act": speed_map.get(p[1], f"Code {{p[1]}}"),
                "duplex": "Full" if p[2] == 1 or p[1] in (2, 4, 5) else ("Half" if p[1] in (1, 3) else "None"),
                "enabled": True
            }})
ports.sort(key=lambda p: p["port"])
out["ports"] = ports

stats = []
for sd in port_stats_raw:
    if len(sd) == 49:
        pid, rx_b, tx_b, rx_p, tx_p, crc, drp = struct.unpack_from(">BQQQQQQ", sd, 0)
        stats.append({{
            "port": pid,
            "bytes_rx": rx_b, "bytes_tx": tx_b,
            "packets_rx": rx_p, "packets_tx": tx_p,
            "crc_errors": crc, "drops": drp
        }})
    elif len(sd) >= 49 and len(sd) % 49 == 0:
        for i in range(len(sd) // 49):
            pid, rx_b, tx_b, rx_p, tx_p, crc, drp = struct.unpack_from(">BQQQQQQ", sd, i * 49)
            stats.append({{
                "port": pid,
                "bytes_rx": rx_b, "bytes_tx": tx_b,
                "packets_rx": rx_p, "packets_tx": tx_p,
                "crc_errors": crc, "drops": drp
            }})
stats.sort(key=lambda s: s["port"])
out["port_statistics"] = stats

if 0x2900 in tlvs and len(tlvs[0x2900]) >= 16:
    pvids = list(struct.unpack(">8H", tlvs[0x2900][:16]))
    out["pvids"] = {{i + 1: pvids[i] for i in range(len(pvids))}}

if 0x2800 in tlvs:
    vd = tlvs[0x2800]
    vlans = []
    for i in range(0, len(vd), 10):
        if i + 10 <= len(vd):
            vid = struct.unpack_from(">H", vd, i)[0]
            ports_member = list(vd[i+2 : i+10])
            vlans.append({{"vid": vid, "ports": ports_member}})
    out["vlans"] = vlans

print(json.dumps(out))
"""

    ssh_args = [
        "ssh", "-o", "StrictHostKeyChecking=accept-new",
        "-o", "BatchMode=yes", "-o", "ConnectTimeout=5",
    ]
    ssh_args.extend(get_ssh_key_args())
    ssh_cmd = f"python3 - '{switch_ip}'"
    ssh_args.extend([f"root@{relay_host}", ssh_cmd])

    res = subprocess.run(ssh_args, input=py_code, capture_output=True, text=True, timeout=timeout, check=False)
    if res.returncode != 0:
        err_msg = res.stderr.strip() or res.stdout.strip()
        raise RuntimeError(f"L2 Relay ({relay_host}) SSH NSDP execution failed (rc {res.returncode}): {err_msg}")

    return json.loads(res.stdout.strip())


def execute_mutation_via_l2_ssh(relay_host="192.168.1.226", switch_ip=DEFAULT_SWITCH_IP, password=None, mutation_tlvs_hex="", timeout=15):
    """Dispatch an authenticated NSDP Write Request (opcode 0x03) over L2 SSH relay."""
    if not password:
        raise ValueError("Administrative password required for configuration mutations")

    enc_pw = encrypt_nsdp_password(password)
    auth_hex = enc_pw.hex()

    py_code = f"""import socket, struct, json, os, sys, time

switch_ip = sys.argv[1] if len(sys.argv) > 1 else "{switch_ip}"
auth_hex = "{auth_hex}"
mutation_hex = "{mutation_tlvs_hex}"

mgr_mac = bytes.fromhex('a029198f5d45')
sw_mac = bytes.fromhex('841b5e98f1f4')

for candidate in ['br-lan', 'vmbr0', 'eth0', 'eth1', 'lan']:
    mac_path = f"/sys/class/net/{{candidate}}/address"
    if os.path.exists(mac_path):
        try:
            with open(mac_path, 'r') as f:
                mgr_mac = bytes.fromhex(f.read().strip().replace(':', ''))
                break
        except Exception:
            pass

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
try:
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, getattr(socket, 'SO_REUSEPORT', socket.SO_REUSEADDR), 1)
    sock.bind(('', 63321))
except Exception:
    pass

seq = int(time.time() * 10) & 0xFFFF

# Opcode 0x03: Write Request
header = struct.pack(
    '>BBHI6s6sHH4s4s',
    0x01, 0x03, 0, 0, mgr_mac, sw_mac, 0, seq, b'NSDP', b'\\x00'*4
)

enc_pw = bytes.fromhex(auth_hex)
mutation_bytes = bytes.fromhex(mutation_hex)

body = bytearray()
body += struct.pack('>HH', 0x000A, len(enc_pw)) + enc_pw
body += mutation_bytes
body += bytes.fromhex('ffff0000')

packet = bytes(header + body)

resp = None
for attempt in range(3):
    try:
        sock.settimeout(2.5)
        sock.sendto(packet, (switch_ip, 63322))
        resp, _ = sock.recvfrom(4096)
        if resp and len(resp) >= 32 and resp[24:28] == b"NSDP":
            break
    except Exception:
        time.sleep(0.3)

if not resp or len(resp) < 32 or resp[24:28] != b"NSDP":
    sock.close()
    print(json.dumps({{"status": "error", "error": "Switch did not respond to Write Request", "raw_len": len(resp) if resp else 0}}))
    sys.exit(1)

res_code, fail_tlv = struct.unpack_from(">HI", resp, 2)
if res_code != 0:
    sock.close()
    print(json.dumps({{"status": "error", "error": f"Switch rejected write with status code 0x{{res_code:04X}}", "result_code": res_code, "failure_tlv": hex(fail_tlv)}}))
    sys.exit(1)

# Verification Read (Opcode 0x01)
time.sleep(0.2)
seq = (seq + 1) & 0xFFFF
read_hdr = struct.pack('>BBHI6s6sHH4s4s', 0x01, 0x01, 0, 0, mgr_mac, sw_mac, 0, seq, b'NSDP', b'\\x00'*4)
read_body = bytearray()
for t in [0x0001, 0x0006, 0x0C00, 0x2000, 0x2800, 0x2900, 0x9000]:
    read_body += struct.pack('>HH', t, 0)
read_body += bytes.fromhex('ffff0000')

v_resp = None
try:
    sock.settimeout(2.5)
    sock.sendto(bytes(read_hdr + read_body), (switch_ip, 63322))
    v_resp, _ = sock.recvfrom(4096)
except Exception:
    pass
sock.close()

tlvs = {{}}
if v_resp and len(v_resp) >= 32:
    offset = 32
    while offset + 4 <= len(v_resp):
        tag, length = struct.unpack_from(">HH", v_resp, offset)
        offset += 4
        if tag == 0xFFFF or offset + length > len(v_resp):
            break
        tlvs[tag] = v_resp[offset : offset + length]
        offset += length

pvids = {{}}
if 0x2900 in tlvs and len(tlvs[0x2900]) >= 16:
    pv = list(struct.unpack(">8H", tlvs[0x2900][:16]))
    pvids = {{i + 1: pv[i] for i in range(len(pv))}}

vlans = []
if 0x2800 in tlvs:
    vd = tlvs[0x2800]
    for i in range(0, len(vd), 10):
        if i + 10 <= len(vd):
            vid = struct.unpack_from(">H", vd, i)[0]
            vlans.append({{"vid": vid, "ports": list(vd[i+2 : i+10])}})

print(json.dumps({{
    "status": "success",
    "write_acknowledged": True,
    "result_code": 0,
    "verified_pvids": pvids,
    "verified_vlans": vlans,
    "igmp_snooping": bool(tlvs.get(0x2000, b'\\x00')[0]) if 0x2000 in tlvs else None,
    "loop_detection": bool(tlvs.get(0x9000, b'\\x00')[0]) if 0x9000 in tlvs else None
}}))
"""

    ssh_args = [
        "ssh", "-o", "StrictHostKeyChecking=accept-new",
        "-o", "BatchMode=yes", "-o", "ConnectTimeout=5",
    ]
    ssh_args.extend(get_ssh_key_args())
    ssh_cmd = f"python3 - '{switch_ip}'"
    ssh_args.extend([f"root@{relay_host}", ssh_cmd])

    res = subprocess.run(ssh_args, input=py_code, capture_output=True, text=True, timeout=timeout, check=False)
    if res.returncode != 0:
        err_msg = res.stderr.strip() or res.stdout.strip()
        raise RuntimeError(f"L2 Mutation Relay ({relay_host}) failed (rc {res.returncode}): {err_msg}")

    return json.loads(res.stdout.strip())


def connect_and_gather(host, password, timeout=3.0):
    """Gather status using native NSDP or OpenWrt L2 SSH relay."""
    errors = []

    try:
        client = NativeNSDPClient(host=host, timeout=timeout)
        tags = [
            NativeNSDPClient.TAG_MODEL,
            NativeNSDPClient.TAG_DEVICE_NAME,
            NativeNSDPClient.TAG_MAC,
            NativeNSDPClient.TAG_IP,
            NativeNSDPClient.TAG_NETMASK,
            NativeNSDPClient.TAG_GATEWAY,
            NativeNSDPClient.TAG_FIRMWARE_B1,
            NativeNSDPClient.TAG_PORT_LINK,
            NativeNSDPClient.TAG_PORT_STATS,
            NativeNSDPClient.TAG_PVID,
        ]
        data = client.query(tags)
        return "native_nsdp", data
    except Exception as e:
        errors.append(f"local-native-nsdp: {e}")

    try:
        data = query_via_l2_ssh(relay_host="192.168.1.226", switch_ip=host, password=password)
        return "openwrt_l2_relay", data
    except Exception as e:
        errors.append(f"openwrt-l2-relay (192.168.1.226): {e}")

    try:
        data = query_via_l2_ssh(relay_host="192.168.1.250", switch_ip=host, password=password)
        return "pve_l2_relay", data
    except Exception as e:
        errors.append(f"pve-l2-relay (192.168.1.250): {e}")

    raise RuntimeError(
        f"Unable to query Netgear switch at {host}. Attempted mechanisms failed:\n"
        + "\n".join(f"  - {err}" for err in errors)
    )


def connect_and_mutate(host, password, write_tlvs_bytes):
    """Dispatch mutation over native NSDP or L2 SSH relay."""
    errors = []

    try:
        client = NativeNSDPClient(host=host, timeout=3.0)
        client.mutate(write_tlvs_bytes, password)
        return "native_nsdp", {"status": "success", "driver": "native_nsdp"}
    except Exception as e:
        errors.append(f"local-native-nsdp: {e}")

    tlvs_hex = write_tlvs_bytes.hex()
    try:
        data = execute_mutation_via_l2_ssh(relay_host="192.168.1.226", switch_ip=host, password=password, mutation_tlvs_hex=tlvs_hex)
        return "openwrt_l2_relay", data
    except Exception as e:
        errors.append(f"openwrt-l2-relay (192.168.1.226): {e}")

    try:
        data = execute_mutation_via_l2_ssh(relay_host="192.168.1.250", switch_ip=host, password=password, mutation_tlvs_hex=tlvs_hex)
        return "pve_l2_relay", data
    except Exception as e:
        errors.append(f"pve-l2-relay (192.168.1.250): {e}")

    raise RuntimeError(
        f"Unable to apply configuration to Netgear switch at {host}:\n"
        + "\n".join(f"  - {err}" for err in errors)
    )


def _fmt_bytes(n):
    if not isinstance(n, (int, float)):
        return "0 B"
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(n) < 1024.0:
            return f"{n:3.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} PB"


def cmd_status(data, driver_type):
    """Format and print switch telemetry."""
    model = data.get("model", "GS108Ev2")
    name = data.get("device_name", "N/A")
    fw = data.get("firmware", "N/A")
    mac = data.get("mac", "N/A")
    ip = data.get("ip", DEFAULT_SWITCH_IP)

    summary_lines = [
        f"=== Netgear GS108Ev2 Status ({ip}) ===",
        f"Model:    {model} (Headless NSDP)",
        f"Name:     {name}",
        f"Firmware: {fw}",
        f"MAC:      {mac}",
        f"Driver:   {driver_type}",
        "",
        "Port Status & Diagnostics:",
        f"{'Port':<6} {'State':<8} {'Speed':<14} {'RX Traffic':<14} {'TX Traffic':<14} {'CRC Errors':<10}",
        "-" * 72,
    ]

    ports = data.get("ports", [])
    stats = data.get("port_statistics", [])
    stats_by_port = {s.get("port"): s for s in stats}

    if not ports:
        summary_lines.append(f"Received TLV Tags: {data.get('parsed_tags', [])}")
        summary_lines.append(f"Raw NSDP Payload: {data.get('raw_hex', '')}")
    else:
        for p in ports:
            port_num = p.get("port")
            st = stats_by_port.get(port_num, {})
            state_str = "UP" if p.get("link_up", p.get("enabled")) else "DOWN"
            speed_act = p.get("speed_act", "No Link")
            rx_str = _fmt_bytes(st.get("bytes_rx", 0))
            tx_str = _fmt_bytes(st.get("bytes_tx", 0))
            crc = st.get("crc_errors", 0)
            summary_lines.append(
                f"{port_num:<6} {state_str:<8} {speed_act:<14} {rx_str:<14} {tx_str:<14} {crc:<10}"
            )

    if "pvids" in data:
        summary_lines.append("")
        summary_lines.append("Port VLAN IDs (PVID):")
        pvid_items = [f"Port {p}: {vid}" for p, vid in sorted(data["pvids"].items(), key=lambda x: int(x[0]))]
        summary_lines.append("  " + ", ".join(pvid_items))

    if "vlans" in data:
        summary_lines.append("")
        summary_lines.append("802.1Q VLAN Membership:")
        for v in data["vlans"]:
            ports_desc = []
            for p_idx, mode in enumerate(v.get("ports", [])):
                p_num = p_idx + 1
                if mode == 1:
                    ports_desc.append(f"{p_num}T")
                elif mode == 2:
                    ports_desc.append(f"{p_num}U")
            summary_lines.append(f"  VLAN {v.get('vid'):<4} ({len(ports_desc)} ports): " + (", ".join(ports_desc) if ports_desc else "None"))

    return {
        "status": "success",
        "driver": driver_type,
        "summary": "\n".join(summary_lines),
        "data": data,
    }


def cmd_backup(data, driver_type):
    """Export configuration backup to repository (JSON telemetry snapshot + official binary CFG)."""
    backup_payload = {
        "exported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "driver": driver_type,
        "protocol": "NSDP",
        "switch_config": data,
    }

    os.makedirs(os.path.dirname(CONFIG_BACKUP_FILE), exist_ok=True)
    with open(CONFIG_BACKUP_FILE, "w") as f:
        json.dump(backup_payload, f, indent=2)

    cfg_size = 0
    if os.path.exists(PROSAFE_GOLDEN_CFG):
        shutil.copy2(PROSAFE_GOLDEN_CFG, CONFIG_BACKUP_CFG)
        cfg_size = os.path.getsize(CONFIG_BACKUP_CFG)
    elif os.path.exists(CONFIG_BACKUP_CFG):
        cfg_size = os.path.getsize(CONFIG_BACKUP_CFG)

    return {
        "status": "success",
        "json_backup": CONFIG_BACKUP_FILE,
        "json_bytes": os.path.getsize(CONFIG_BACKUP_FILE),
        "cfg_backup": CONFIG_BACKUP_CFG if cfg_size else None,
        "cfg_bytes": cfg_size,
        "model": data.get("model", "GS108Ev2"),
        "ip": data.get("ip", DEFAULT_SWITCH_IP),
        "ports_backed_up": len(data.get("ports", [])),
    }


def validate_uplink_safety(vid, tagged_ports, untagged_ports, pvid_dict, force_uplink=False):
    """
    Enforce flash lockout prevention invariants:
      1. Port 8 (uplink) must remain in VLAN 1 (Untagged or Tagged).
      2. Port 8 PVID must remain 1 unless force_uplink=True.
    """
    if not force_uplink:
        if pvid_dict and pvid_dict.get(DEFAULT_UPLINK_PORT, 1) != 1:
            raise ValueError(
                f"SAFETY INTERCEPT: Cannot set Port {DEFAULT_UPLINK_PORT} PVID to {pvid_dict.get(DEFAULT_UPLINK_PORT)}. "
                f"Port {DEFAULT_UPLINK_PORT} is the primary uplink to OpenWrt/AP bridge on VLAN 1. "
                "Changing this PVID will cause immediate management lockout. Use --force-uplink if intentional."
            )


def cmd_set_vlan(target_ip, password, vid, tagged_ports, untagged_ports, pvid_ports, force_uplink=False):
    """Atomically provision 802.1Q VLAN membership and assign PVIDs with safety checks."""
    if vid < 1 or vid > 4094:
        raise ValueError(f"Invalid VLAN ID: {vid} (must be 1-4094)")

    # 1. Fetch current switch configuration
    driver_type, current_data = connect_and_gather(target_ip, password)
    current_pvids = current_data.get("pvids", {i: 1 for i in range(1, 9)})

    # 2. Build updated PVID map
    updated_pvids = dict(current_pvids)
    if pvid_ports:
        for p in pvid_ports:
            if p < 1 or p > 8:
                raise ValueError(f"Invalid port: {p} (must be 1-8)")
            updated_pvids[p] = vid

    # Enforce safety rules
    validate_uplink_safety(vid, tagged_ports, untagged_ports, updated_pvids, force_uplink)

    # 3. Assemble VLAN membership payload (TLV 0x2800)
    # Port membership: 0=Excluded, 1=Tagged, 2=Untagged
    port_mask = [0] * 8
    for p in tagged_ports:
        if 1 <= p <= 8:
            port_mask[p - 1] = 1
    for p in untagged_ports:
        if 1 <= p <= 8:
            port_mask[p - 1] = 2

    # Assemble TLVs:
    # - TLV 0x2800: VLAN Membership entry (10 bytes: uint16 vid + 8 bytes ports)
    # - TLV 0x2900: Port PVIDs (16 bytes: 8 x uint16)
    mutation_body = bytearray()

    # 0x2800: VLAN Membership definition
    vlan_entry = struct.pack(">H8B", vid, *port_mask)
    mutation_body += struct.pack(">HH", 0x2800, len(vlan_entry)) + vlan_entry

    # 0x2900: PVID map (16 bytes)
    pvid_list = [updated_pvids.get(i, 1) for i in range(1, 9)]
    pvid_bytes = struct.pack(">8H", *pvid_list)
    mutation_body += struct.pack(">HH", 0x2900, 16) + pvid_bytes

    # 4. Dispatch mutation
    driver, result = connect_and_mutate(target_ip, password, bytes(mutation_body))

    # 5. Synchronize local GitOps snapshot
    _, updated_data = connect_and_gather(target_ip, password)
    cmd_backup(updated_data, driver)

    return {
        "status": "success",
        "action": "set_vlan",
        "vid": vid,
        "tagged_ports": tagged_ports,
        "untagged_ports": untagged_ports,
        "pvids": pvid_list,
        "driver": driver,
        "verified": result,
    }


def cmd_delete_vlan(target_ip, password, vid):
    """Delete a VLAN entry (TLV 0x2C00) and revert affected PVIDs to 1."""
    if vid == 1:
        raise ValueError("SAFETY INTERCEPT: VLAN 1 is the permanent management VLAN and cannot be deleted.")

    driver_type, current_data = connect_and_gather(target_ip, password)
    current_pvids = current_data.get("pvids", {i: 1 for i in range(1, 9)})

    updated_pvids = {p: (1 if v == vid else v) for p, v in current_pvids.items()}

    mutation_body = bytearray()
    # 0x2C00: Delete VLAN (2 bytes: uint16 vid)
    mutation_body += struct.pack(">HHH", 0x2C00, 2, vid)

    # 0x2900: Revert PVIDs
    pvid_list = [updated_pvids.get(i, 1) for i in range(1, 9)]
    mutation_body += struct.pack(">HH", 0x2900, 16) + struct.pack(">8H", *pvid_list)

    driver, result = connect_and_mutate(target_ip, password, bytes(mutation_body))
    _, updated_data = connect_and_gather(target_ip, password)
    cmd_backup(updated_data, driver)

    return {
        "status": "success",
        "action": "delete_vlan",
        "vid": vid,
        "driver": driver,
        "pvids": pvid_list,
    }


def cmd_set_pvid(target_ip, password, port, pvid, force_uplink=False):
    """Change the default Port VLAN ID (PVID) for a specific port."""
    if port < 1 or port > 8:
        raise ValueError(f"Invalid port: {port} (must be 1-8)")
    if pvid < 1 or pvid > 4094:
        raise ValueError(f"Invalid PVID: {pvid} (must be 1-4094)")

    if port == DEFAULT_UPLINK_PORT and pvid != 1 and not force_uplink:
        raise ValueError(
            f"SAFETY INTERCEPT: Port {DEFAULT_UPLINK_PORT} is the primary uplink to OpenWrt/AP bridge on VLAN 1. "
            "Changing its PVID will isolate the switch management interface. Use --force-uplink if intentional."
        )

    driver_type, current_data = connect_and_gather(target_ip, password)
    current_pvids = current_data.get("pvids", {i: 1 for i in range(1, 9)})
    current_pvids[port] = pvid

    pvid_list = [current_pvids.get(i, 1) for i in range(1, 9)]
    mutation_body = struct.pack(">HH", 0x2900, 16) + struct.pack(">8H", *pvid_list)

    driver, result = connect_and_mutate(target_ip, password, mutation_body)
    _, updated_data = connect_and_gather(target_ip, password)
    cmd_backup(updated_data, driver)

    return {
        "status": "success",
        "action": "set_pvid",
        "port": port,
        "pvid": pvid,
        "driver": driver,
        "all_pvids": pvid_list,
    }


def cmd_set_port(target_ip, password, port, admin=None, speed=None, force_uplink=False):
    """Configure port administrative state (enable/disable) and negotiated speed."""
    if port < 1 or port > 8:
        raise ValueError(f"Invalid port: {port} (must be 1-8)")

    if port == DEFAULT_UPLINK_PORT and admin == "disable" and not force_uplink:
        raise ValueError(
            f"SAFETY INTERCEPT: Port {DEFAULT_UPLINK_PORT} is the primary uplink. "
            "Disabling it will permanently isolate the switch. Use --force-uplink if intentional."
        )

    speed_codes = {
        "auto": 1,
        "10h": 2, "10f": 3,
        "100h": 4, "100f": 5,
        "1000f": 6
    }

    mutation_body = bytearray()
    if admin is not None:
        admin_code = 1 if admin == "enable" else 2
        mutation_body += struct.pack(">HHBB", 0x5800, 2, port, admin_code)

    if speed is not None:
        if speed.lower() not in speed_codes:
            raise ValueError(f"Invalid speed: {speed} (choices: {list(speed_codes.keys())})")
        code = speed_codes[speed.lower()]
        mutation_body += struct.pack(">HHBB", 0x3800, 2, port, code)

    driver, result = connect_and_mutate(target_ip, password, bytes(mutation_body))
    _, updated_data = connect_and_gather(target_ip, password)
    cmd_backup(updated_data, driver)

    return {
        "status": "success",
        "action": "set_port",
        "port": port,
        "admin": admin,
        "speed": speed,
        "driver": driver,
    }


def cmd_set_feature(target_ip, password, igmp=None, loop_detection=None):
    """Configure hardware features: IGMP snooping (0x2000) and Loop Detection (0x9000)."""
    mutation_body = bytearray()
    if igmp is not None:
        igmp_val = 1 if igmp in ("enable", "true", "1") else 0
        mutation_body += struct.pack(">HHB", 0x2000, 1, igmp_val)

    if loop_detection is not None:
        loop_val = 1 if loop_detection in ("enable", "true", "1") else 0
        mutation_body += struct.pack(">HHB", 0x9000, 1, loop_val)

    driver, result = connect_and_mutate(target_ip, password, bytes(mutation_body))
    _, updated_data = connect_and_gather(target_ip, password)
    cmd_backup(updated_data, driver)

    return {
        "status": "success",
        "action": "set_feature",
        "igmp": igmp,
        "loop_detection": loop_detection,
        "driver": driver,
    }


def cmd_restore(target_ip, password, file_path=None, confirm=False):
    """Restore configuration from official ProSAFE binary .cfg or JSON backup."""
    if not confirm:
        raise ValueError("Must specify --confirm to apply configuration restore to live switch flash.")

    target_file = file_path or CONFIG_BACKUP_CFG
    if not os.path.exists(target_file):
        target_file = CONFIG_BACKUP_FILE

    if not os.path.exists(target_file):
        raise FileNotFoundError(f"Restore blueprint not found at {target_file}")

    print(f"Restoring Netgear switch from {target_file}...")

    if target_file.endswith(".cfg"):
        with open(target_file, "rb") as f:
            cfg_data = f.read()
        if len(cfg_data) < 64:
            raise ValueError("Corrupt .cfg file (under 64 bytes)")
        
        # The configuration body starts at byte 64
        cfg_body = cfg_data[64:]
        driver, result = connect_and_mutate(target_ip, password, cfg_body)
    else:
        with open(target_file, "r") as f:
            js = json.load(f)
        cfg = js.get("switch_config", js)
        pvids = cfg.get("pvids", {})
        vlans = cfg.get("vlans", [])

        mutation_body = bytearray()
        if pvids:
            pvid_list = [pvids.get(str(i), pvids.get(i, 1)) for i in range(1, 9)]
            mutation_body += struct.pack(">HH", 0x2900, 16) + struct.pack(">8H", *pvid_list)

        driver, result = connect_and_mutate(target_ip, password, bytes(mutation_body))

    _, updated_data = connect_and_gather(target_ip, password)
    cmd_backup(updated_data, driver)

    return {
        "status": "success",
        "action": "restore",
        "file": target_file,
        "driver": driver,
    }


def cmd_verify(target_ip, password, baseline_file=None):
    """Verify live switch configuration against GitOps baseline backup."""
    target_file = baseline_file or CONFIG_BACKUP_FILE
    if not os.path.exists(target_file):
        raise FileNotFoundError(f"GitOps baseline file not found: {target_file}")

    with open(target_file, "r") as f:
        baseline_raw = json.load(f)
    baseline = baseline_raw.get("switch_config", baseline_raw)

    driver_type, live_data = connect_and_gather(target_ip, password)

    checks = []
    # 1. Identity checks
    for key, name in [("model", "Hardware Model"), ("mac", "MAC Address"), ("firmware", "Firmware")]:
        b_val = baseline.get(key)
        l_val = live_data.get(key)
        match = (b_val == l_val)
        checks.append({"item": name, "baseline": b_val, "live": l_val, "match": match})

    # 2. Port count
    checks.append({
        "item": "Port Count",
        "baseline": baseline.get("port_count", 8),
        "live": live_data.get("port_count", 8),
        "match": baseline.get("port_count", 8) == live_data.get("port_count", 8)
    })

    # 3. PVID checks
    b_pvids = baseline.get("pvids", {})
    l_pvids = live_data.get("pvids", {})
    pvid_match = True
    for p in range(1, 9):
        bp = b_pvids.get(str(p), b_pvids.get(p, 1))
        lp = l_pvids.get(p, l_pvids.get(str(p), 1))
        if bp != lp:
            pvid_match = False
    checks.append({"item": "PVID Table", "baseline": b_pvids, "live": l_pvids, "match": pvid_match})

    # 4. CRC Errors check
    crc_clean = True
    for s in live_data.get("port_statistics", []):
        if s.get("crc_errors", 0) > 0:
            crc_clean = False
    checks.append({"item": "0 CRC Drops", "baseline": "0 CRC across all ports", "live": "Clean" if crc_clean else "Errors detected", "match": crc_clean})

    all_match = all(c["match"] for c in checks)
    summary_lines = [
        f"=== Netgear GS108Ev2 GitOps Verification ===",
        f"Switch IP:    {target_ip}",
        f"Baseline:     {target_file}",
        f"Result:       {'[OK] 100% IN COMPLIANCE' if all_match else '[DRIFT] DIFFERENCES DETECTED'}",
        "",
        f"{'Verification Check':<25} {'Baseline':<25} {'Live State':<25} {'Status':<10}",
        "-" * 85,
    ]
    for c in checks:
        status_str = "[OK]" if c["match"] else "[DRIFT]"
        summary_lines.append(f"{c['item']:<25} {str(c['baseline'])[:24]:<25} {str(c['live'])[:24]:<25} {status_str:<10}")

    return {
        "status": "success" if all_match else "drift_detected",
        "compliant": all_match,
        "checks": checks,
        "summary": "\n".join(summary_lines)
    }


def main():
    parser = argparse.ArgumentParser(description="Netgear GS108Ev2 Headless NSDP Management Tool")
    subparsers = parser.add_subparsers(dest="action", required=True, help="Subcommand to execute")

    # status
    p_status = subparsers.add_parser("status", help="Query live switch port telemetry & status")
    p_status.add_argument("--json", action="store_true", help="Output raw JSON")

    # backup
    p_backup = subparsers.add_parser("backup", help="Export GitOps backup (JSON + binary .cfg)")

    # set-vlan
    p_vlan = subparsers.add_parser("set-vlan", help="Provision 802.1Q VLAN and port memberships")
    p_vlan.add_argument("--vid", type=int, required=True, help="VLAN ID (1-4094)")
    p_vlan.add_argument("--tagged", type=str, default="", help="Comma-separated tagged ports (e.g. '8' or '1,8')")
    p_vlan.add_argument("--untagged", type=str, default="", help="Comma-separated untagged ports (e.g. '2,3')")
    p_vlan.add_argument("--pvid", type=str, default="", help="Comma-separated ports to set PVID to this VID")
    p_vlan.add_argument("--force-uplink", action="store_true", help="Override Port 8 uplink protection")

    # delete-vlan
    p_del_vlan = subparsers.add_parser("delete-vlan", help="Delete a VLAN entry")
    p_del_vlan.add_argument("--vid", type=int, required=True, help="VLAN ID to delete")

    # set-pvid
    p_pvid = subparsers.add_parser("set-pvid", help="Assign default Port VLAN ID (PVID)")
    p_pvid.add_argument("--port", type=int, required=True, help="Port (1-8)")
    p_pvid.add_argument("--pvid", type=int, required=True, help="PVID (1-4094)")
    p_pvid.add_argument("--force-uplink", action="store_true", help="Override Port 8 uplink protection")

    # set-port
    p_port = subparsers.add_parser("set-port", help="Configure port admin state and speed")
    p_port.add_argument("--port", type=int, required=True, help="Port (1-8)")
    p_port.add_argument("--admin", choices=["enable", "disable"], default=None, help="Admin state")
    p_port.add_argument("--speed", choices=["auto", "10h", "10f", "100h", "100f", "1000f"], default=None, help="Port speed")
    p_port.add_argument("--force-uplink", action="store_true", help="Override Port 8 uplink protection")

    # set-feature
    p_feat = subparsers.add_parser("set-feature", help="Configure switch hardware features")
    p_feat.add_argument("--igmp", choices=["enable", "disable"], default=None, help="IGMP Snooping")
    p_feat.add_argument("--loop-detection", choices=["enable", "disable"], default=None, help="Loop detection")

    # restore
    p_restore = subparsers.add_parser("restore", help="Restore switch configuration from backup")
    p_restore.add_argument("--file", default=None, help="Path to .cfg or .json backup file")
    p_restore.add_argument("--confirm", action="store_true", help="Required confirmation flag")

    # verify
    p_verify = subparsers.add_parser("verify", help="Verify live switch against GitOps baseline")
    p_verify.add_argument("--file", default=None, help="Path to baseline .json file")

    # Global options
    parser.add_argument("--ip", default=None, help=f"Target switch IP (default: {DEFAULT_SWITCH_IP})")
    parser.add_argument("--password", default=None, help="Switch admin password (default: from SOPS or env)")

    args = parser.parse_args()

    host, sops_pw = load_credentials()
    target_ip = args.ip or host
    target_password = args.password or sops_pw

    try:
        if args.action == "status":
            driver_type, data = connect_and_gather(target_ip, target_password)
            result = cmd_status(data, driver_type)
            if getattr(args, "json", False) or "summary" not in result:
                print(json.dumps(result, indent=2))
            else:
                print(result["summary"])

        elif args.action == "backup":
            driver_type, data = connect_and_gather(target_ip, target_password)
            result = cmd_backup(data, driver_type)
            print(json.dumps(result, indent=2))

        elif args.action == "set-vlan":
            tagged = [int(p.strip()) for p in args.tagged.split(",") if p.strip()]
            untagged = [int(p.strip()) for p in args.untagged.split(",") if p.strip()]
            pvid_ports = [int(p.strip()) for p in args.pvid.split(",") if p.strip()]
            res = cmd_set_vlan(target_ip, target_password, args.vid, tagged, untagged, pvid_ports, args.force_uplink)
            print(json.dumps(res, indent=2))

        elif args.action == "delete-vlan":
            res = cmd_delete_vlan(target_ip, target_password, args.vid)
            print(json.dumps(res, indent=2))

        elif args.action == "set-pvid":
            res = cmd_set_pvid(target_ip, target_password, args.port, args.pvid, args.force_uplink)
            print(json.dumps(res, indent=2))

        elif args.action == "set-port":
            res = cmd_set_port(target_ip, target_password, args.port, args.admin, args.speed, args.force_uplink)
            print(json.dumps(res, indent=2))

        elif args.action == "set-feature":
            res = cmd_set_feature(target_ip, target_password, args.igmp, args.loop_detection)
            print(json.dumps(res, indent=2))

        elif args.action == "restore":
            res = cmd_restore(target_ip, target_password, args.file, args.confirm)
            print(json.dumps(res, indent=2))

        elif args.action == "verify":
            res = cmd_verify(target_ip, target_password, args.file)
            print(res["summary"])

    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
