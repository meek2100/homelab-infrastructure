#!/usr/bin/env python3
# failover-tester.py
# Version: 2.0.0
# Description: Unified Bidirectional Test Suite for OpenWrt 3-Priority Failover

import logging
import traceback
import sys
import subprocess
import os
import time
import socket
import argparse
import json
import re

try:
    import scapy.all as scapy
    HAS_SCAPY = True
except ImportError:
    scapy = None
    HAS_SCAPY = False

# -------------------- Config Defaults --------------------
CONFIG_LOCATIONS = [
    "/etc/vxlan-nm.conf",          # OpenWrt
    "/etc/network/vxlan-nm.conf",  # Debian
    "/etc/failover-nm.conf"        # Fallback
]

DEFAULTS = {
    "REMOTE_IP": "192.168.1.150",
    "REMOTE_VLAN_IP": "192.168.40.1", # Main Router Gateway on VLAN 40
    "GATEWAY_IP": "192.168.1.1",      # Main Router / DHCP Server
    "SSH_PRIVATE_KEY_PATH": "~/.ssh/id_ed25519",
    "VXLAN_IF": "vxlan150",
    "BRIDGE_IF": "br-lan"
}

CONFIG = DEFAULTS.copy()
LOG = None
DEBUG_MODE = False
TEST_RESULTS = {}
_last_tcp_bps = None  # Set by iperf_test(), read by udp_jitter_test()
_tcp_cap_bps = None   # Set via --tcp-cap arg (remote side uses coordinator's TCP rate)

# -------------------- Logging Setup --------------------
def setup_logging():
    global LOG
    LOG = logging.getLogger("failover-tester")
    LOG.setLevel(logging.DEBUG)

    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(logging.Formatter('%(message)s'))
    ch.setLevel(logging.INFO if not DEBUG_MODE else logging.DEBUG)
    LOG.addHandler(ch)
    LOG.propagate = False

def print_info(msg):
    LOG.info(f"\033[1;34mⓘ {msg}\033[0m")

def print_ok(msg):
    LOG.info(f"\033[1;32m✓ {msg}\033[0m")

def print_warn(msg):
    LOG.warning(f"\033[1;33m⚠ {msg}\033[0m")

def print_fail(msg):
    LOG.error(f"\033[1;31m✖ {msg}\033[0m")

def log_debug(msg):
    LOG.debug(f"DEBUG: {msg}")

# -------------------- Config Loader --------------------
def load_config():
    for path in CONFIG_LOCATIONS:
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if "=" in line and not line.startswith("#"):
                            k, v = line.split("=", 1)
                            CONFIG[k.strip()] = v.strip().strip('"').strip("'")
                return True
            except Exception:
                pass
    return False

def is_openwrt():
    return os.path.exists("/etc/openwrt_release")

# -------------------- Active Priority Detection --------------------
def detect_active_priority():
    """Detects which failover priority is currently active on OpenWrt."""
    if not is_openwrt():
        return "DEBIAN-SERVER"

    print_info("Detecting active OpenWrt failover priority...")

    try:
        # P1 Check: wan has carrier AND is in br-lan
        # We check both the carrier and if it's currently master'd (optional but safer)
        try:
            with open("/sys/class/net/wan/carrier", "r") as f:
                if f.read().strip() == "1":
                    # Extra check: Is wan actually in the bridge?
                    if "master br-lan" in subprocess.check_output(["ip", "link", "show", "wan"]).decode():
                        return "P1"
        except Exception:
            pass

        # P2 Check: vxlan150 exists and is UP/carrying and in bridge
        try:
            ip_out = subprocess.check_output(["ip", "link", "show", "vxlan150"], stderr=subprocess.DEVNULL).decode()
            if "UP" in ip_out and "NO-CARRIER" not in ip_out:
                if "master br-lan" in ip_out:
                    return "P2"
        except Exception:
            pass

        # P3 Check: Relayd is running
        try:
            rel_status = subprocess.check_output(["/etc/init.d/relayd", "status"], stderr=subprocess.DEVNULL).decode()
            if "running" in rel_status:
                return "P3"
        except Exception:
            pass

    except Exception as e:
        log_debug(f"Failed Priority Detection: {e}")

    return "UNKNOWN"

# -------------------- Environment Management --------------------
def get_target_mac(ip, iface=None):
    """Resolves MAC address for a target IP using ARP."""
    if not HAS_SCAPY: return "ff:ff:ff:ff:ff:ff"
    try:
        ans = scapy.srp1(scapy.Ether(dst="ff:ff:ff:ff:ff:ff")/scapy.ARP(pdst=ip),
                         iface=iface, timeout=2, verbose=0)
        if ans: return ans[scapy.Ether].src
    except Exception:
        pass
    return "ff:ff:ff:ff:ff:ff"

def teardown_vlan_test_env():
    """Cleans up any VLAN sub-interfaces and bridge filter entries created during testing."""
    iface_base = CONFIG.get("BRIDGE_IF", "br-lan") if is_openwrt() else "br0"
    for vid in [40]:
        run_command(["ip", "link", "del", f"{iface_base}.{vid}"], suppress_output=True)
        # Remove diagnostic bridge VLAN filter entries added during setup (OpenWrt DSA only)
        if is_openwrt():
            run_command(["bridge", "vlan", "del", "dev", iface_base, "vid", str(vid), "self"], suppress_output=True)
            run_command(["bridge", "vlan", "del", "dev", "wan", "vid", str(vid)], suppress_output=True)
    log_debug("Cleaned up diagnostic VLAN interfaces")

# -------------------- Handlers --------------------
def get_command_path(cmd):
    """Finds the absolute path of a command, searching common sbin locations if needed."""
    for path in ["", "/sbin/", "/usr/sbin/", "/usr/local/sbin/"]:
        try:
            full_path = os.path.join(path, cmd) if path else cmd
            subprocess.check_call([full_path, "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return full_path
        except Exception:
            try:
                # Some commands like 'bridge' might not support --version but will exist
                subprocess.check_call(["which", full_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return full_path
            except Exception:
                pass
    return cmd # Fallback to just the command name

def run_command(cmd, timeout=10, suppress_output=False):
    if not is_openwrt() and cmd[0] in ["ip", "bridge", "iperf3", "pkill", "python3"]:
        cmd = ["sudo"] + cmd

    # Ensure first element is absolute if possible
    cmd[0] = get_command_path(cmd[0])
    if "sudo" in cmd[0]: cmd[0] = "sudo" # sudo path is fine to just be sudo

    log_debug(f"Executing: {' '.join(cmd)}")
    try:
        result = subprocess.check_output(cmd, stderr=subprocess.STDOUT, universal_newlines=True, timeout=timeout)
        log_debug(f"Output: {result.strip()}")
        return True, result
    except subprocess.CalledProcessError as e:
        log_debug(f"Failed (Code {e.returncode}): {e.output.strip()}")
        return False, e.output
    except Exception as e:
        return False, str(e)

def ping_with_mtu(ip, mtu, iface=None):
    """Full IP packet size (e.g., 1500). Sets DF bit via Scapy if available."""
    payload_size = mtu - 28 # IP Payload = MTU - 20 (IP) - 8 (ICMP)
    if HAS_SCAPY:
        try:
            import logging
            logging.getLogger("scapy.runtime").setLevel(logging.CRITICAL)

            # If iface is provided, use L2 srp1 to bypass OS routing confusion
            if iface:
                target_mac = get_target_mac(ip, iface)
                pkt = scapy.Ether(dst=target_mac) / scapy.IP(dst=ip, flags="DF") / scapy.ICMP() / ("X" * payload_size)
                ans = scapy.srp1(pkt, iface=iface, timeout=2, verbose=0)
            else:
                pkt = scapy.IP(dst=ip, flags="DF")/scapy.ICMP()/("X" * payload_size)
                ans = scapy.sr1(pkt, timeout=2, verbose=0)

            if ans and ans.haslayer(scapy.ICMP) and ans[scapy.ICMP].type == 0:
                log_debug(f"MTU {mtu} passed via Scapy")
                return True
            log_debug(f"MTU {mtu} failed/timed out via Scapy")
            if is_openwrt() and not iface: return False # Busybox ping can't enforce DF
        except Exception as e:
            log_debug(f"Scapy MTU ping failed: {e}")

    # Fallback to ping (warning: BusyBox ping lacks -M do)
    cmd = ["ping", "-c", "1", "-W", "1", "-s", str(payload_size), ip]
    if iface: cmd += ["-I", iface]
    if not is_openwrt():
        cmd += ["-M", "do"]

    return run_command(cmd)[0]

def record_result(test_name, status, detail=""):
    """status: PASS, FAIL, SKIP, WARN"""
    symbols = {"PASS": "✓", "FAIL": "✖", "SKIP": "ⓘ", "WARN": "⚠", "INFO": "ⓘ"}
    TEST_RESULTS[test_name] = {"status_text": status, "status": symbols[status], "details": detail.strip()}

# -------------------- Network Tests --------------------
def icmp_test():
    remote_ip = CONFIG.get("REMOTE_IP")
    if not remote_ip:
        record_result("ICMP_LATENCY", "SKIP", "No REMOTE_IP")
        return

    print_info(f"Pinging {remote_ip} ...")
    success, output = run_command(["ping", "-c", "4", "-W", "2", remote_ip])
    if success:
        latency = re.search(r"= [\d.]+/([\d.]+)", output).group(1) if re.search(r"= [\d.]+/([\d.]+)", output) else "N/A"
        loss = re.search(r"(\d+)% packet loss", output).group(1) + "%" if re.search(r"(\d+)% packet loss", output) else "N/A"
        details = f"{latency} ms, Loss: {loss}"
        print_ok(f"Ping OK ({details})")
        record_result("ICMP_LATENCY", "PASS", details)
    else:
        print_fail("Ping failed.")
        record_result("ICMP_LATENCY", "FAIL", "Ping unreachable")

def gateway_test():
    """Verify reachability to the main router/gateway."""
    gw_ip = CONFIG.get("GATEWAY_IP", "192.168.1.1")
    # P3 (Relayd) needs longer timeout — ARP relay adds ~3s cold-start latency
    wait = "5" if detect_active_priority() == "P3" else "2"
    print_info(f"Pinging gateway {gw_ip} ...")
    cmd_timeout = 25 if wait == "5" else 10
    success, output = run_command(["ping", "-c", "4", "-W", wait, gw_ip], timeout=cmd_timeout)
    if success:
        latency = re.search(r"= [\d.]+/([\d.]+)", output).group(1) if re.search(r"= [\d.]+/([\d.]+)", output) else "N/A"
        loss = re.search(r"(\d+)% packet loss", output).group(1) + "%" if re.search(r"(\d+)% packet loss", output) else "N/A"
        details = f"{latency} ms, Loss: {loss}"
        print_ok(f"Gateway OK ({details})")
        record_result("GW_PING", "PASS", details)
    else:
        print_fail(f"Gateway {gw_ip} unreachable")
        record_result("GW_PING", "FAIL", f"{gw_ip} unreachable")

def internet_test():
    """Verify internet connectivity via external DNS ping."""
    # P3 (Relayd) needs longer timeout — ARP relay adds ~3s cold-start latency
    wait = "5" if detect_active_priority() == "P3" else "3"
    print_info("Pinging 8.8.8.8 (internet) ...")
    cmd_timeout = 25 if wait == "5" else 10
    success, output = run_command(["ping", "-c", "4", "-W", wait, "8.8.8.8"], timeout=cmd_timeout)
    if success:
        latency = re.search(r"= [\d.]+/([\d.]+)", output).group(1) if re.search(r"= [\d.]+/([\d.]+)", output) else "N/A"
        loss = re.search(r"(\d+)% packet loss", output).group(1) + "%" if re.search(r"(\d+)% packet loss", output) else "N/A"
        details = f"{latency} ms, Loss: {loss}"
        print_ok(f"Internet OK ({details})")
        record_result("INTERNET", "PASS", details)
    else:
        print_fail("Internet unreachable (8.8.8.8)")
        record_result("INTERNET", "FAIL", "8.8.8.8 unreachable")

def mtu_sweep_test():
    """Sweeps ICMP MTU configurations to detect Blackholes."""
    active_p = detect_active_priority()

    # During P2, validate interface MTUs directly — Scapy L2 injection (srp1)
    # bypasses kernel MTU enforcement, and VXLAN outer fragmentation masks the
    # real 1450 inner constraint, making ping-based PMTU unreliable.
    if active_p == "P2":
        iface = "br-lan" if is_openwrt() else "br0"
        vxlan_if = "vxlan150"
        print_info(f"Verifying VXLAN path MTU constraints on {iface}...")
        br_mtu = vx_mtu = None
        try:
            out = subprocess.check_output(["ip", "link", "show", iface], text=True)
            m = re.search(r'mtu (\d+)', out)
            if m: br_mtu = int(m.group(1))
        except Exception:
            pass
        try:
            out = subprocess.check_output(["ip", "link", "show", vxlan_if], text=True)
            m = re.search(r'mtu (\d+)', out)
            if m: vx_mtu = int(m.group(1))
        except Exception:
            pass
        if br_mtu == 1450 and vx_mtu == 1450:
            print_ok(f"Path optimal at 1450 MTU (bridge={br_mtu}, vxlan={vx_mtu}).")
            record_result("MTU_SWEEP", "PASS", "Max PMTU: 1450 (Optimal)")
        elif br_mtu is not None and vx_mtu is not None:
            print_warn(f"MTU mismatch: bridge={br_mtu}, vxlan={vx_mtu} (expected 1450)")
            record_result("MTU_SWEEP", "WARN", f"bridge={br_mtu}, vxlan={vx_mtu}")
        else:
            print_fail("Cannot read interface MTUs")
            record_result("MTU_SWEEP", "FAIL", "Interface MTU unreadable")
        return

    if active_p == "P3":
        iface = "br-lan" if is_openwrt() else "br0"
        print_info(f"Verifying bridge MTU for Relayd mode on {iface}...")
        br_mtu = None
        try:
            out = subprocess.check_output(["ip", "link", "show", iface], text=True)
            m = re.search(r'mtu (\d+)', out)
            if m: br_mtu = int(m.group(1))
        except Exception:
            pass
        if br_mtu == 1500:
            print_ok(f"Bridge MTU correct at 1500 (no VXLAN overhead).")
            record_result("MTU_SWEEP", "PASS", "Max PMTU: 1500")
        elif br_mtu is not None:
            print_warn(f"Bridge MTU is {br_mtu}, expected 1500 for P3")
            record_result("MTU_SWEEP", "WARN", f"bridge={br_mtu} (expected 1500)")
        else:
            print_fail("Cannot read bridge MTU")
            record_result("MTU_SWEEP", "FAIL", "Interface MTU unreadable")
        return

    std_ip = CONFIG.get("REMOTE_IP")
    test_ip = CONFIG.get("REMOTE_TEST_IP")

    # On OpenWrt, always test through br-lan to verify the bridge path
    sweep_iface = "br-lan" if is_openwrt() else None

    # Determine remote target
    if active_p == "P1" or not test_ip:
        remote_ip = std_ip
    else:
        # P3 logic: Try test IP first
        if test_ip and ping_with_mtu(test_ip, 64, iface=None):
            remote_ip = test_ip
        else:
            remote_ip = std_ip

    # Fall back to gateway if remote is unreachable — still validates bridge path MTU
    if remote_ip and not ping_with_mtu(remote_ip, 64, iface=sweep_iface):
        gw_ip = CONFIG.get("GATEWAY_IP", "192.168.1.1")
        print_info(f"{remote_ip} unreachable, falling back to gateway {gw_ip} for MTU sweep")
        remote_ip = gw_ip

    if not remote_ip:
        record_result("MTU_SWEEP", "SKIP", "No IP for sweep")
        return

    print_info(f"Sweeping network path MTU capabilities to {remote_ip}...")

    success_1500 = ping_with_mtu(remote_ip, 1500, iface=sweep_iface)
    success_1450 = ping_with_mtu(remote_ip, 1450, iface=sweep_iface)
    success_1446 = ping_with_mtu(remote_ip, 1446, iface=sweep_iface)

    is_test_path = (remote_ip == test_ip)

    if success_1500:
        print_ok("Full 1500 MTU path completely unobstructed.")
        record_result("MTU_SWEEP", "PASS", "Max PMTU: 1500")
    elif success_1450:
        if is_test_path:
            print_warn("1500 Dropped. 1450 Passed strangely on tagged path.")
            record_result("MTU_SWEEP", "WARN", "Max PMTU: 1450 (Tagged Anomalous)")
        else:
            print_ok("Path optimal at 1450 MTU.")
            record_result("MTU_SWEEP", "PASS", "Max PMTU: 1450 (Optimal)")
    elif success_1446:
        if is_test_path:
            print_ok("Inner Path optimal at 1446 MTU (VXLAN+VLAN Limit).")
            record_result("MTU_SWEEP", "PASS", "Max PMTU: 1446 (Optimal)")
        else:
            print_warn("1500/1450 MTU Dropped. 1446 Passed. MSS Clamping recommended.")
            record_result("MTU_SWEEP", "WARN", "Max PMTU: 1446 (MSS Clamped)")
    else:
        if is_test_path:
            print_fail("Inner Path restricted (< 1446). Fragmentation likely.")
            record_result("MTU_SWEEP", "FAIL", "Inner PMTU < 1446")
        else:
            print_fail("Major MTU fragmentation or blackhole detected.")
            record_result("MTU_SWEEP", "FAIL", "PMTU Blackhole Detected")

def mdns_test():
    """Send a real mDNS service discovery query (UDP/5353) and listen for responses."""
    print_info("Testing mDNS service discovery (UDP/5353 → 224.0.0.251) ...")
    iface = "br-lan" if is_openwrt() else "br0"

    # Build DNS-SD browse query: _services._dns-sd._udp.local PTR IN
    # mDNS wire format: TxID=0, Flags=0, QCount=1, then QNAME + QTYPE(PTR=12) + QCLASS(IN=1)
    query = (
        b'\x00\x00'  # Transaction ID (0 for mDNS)
        b'\x00\x00'  # Flags (standard query)
        b'\x00\x01'  # Questions: 1
        b'\x00\x00'  # Answer RRs
        b'\x00\x00'  # Authority RRs
        b'\x00\x00'  # Additional RRs
        b'\x09_services\x07_dns-sd\x04_udp\x05local\x00'  # QNAME
        b'\x00\x0c'  # QTYPE: PTR (12)
        b'\x00\x01'  # QCLASS: IN (1)
    )

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, 25, iface.encode())  # SO_BINDTODEVICE
        sock.settimeout(3)

        # Join multicast group on the bridge interface
        import struct
        mreq = struct.pack("4s4s", socket.inet_aton("224.0.0.251"), socket.inet_aton("0.0.0.0"))
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

        sock.bind(("", 5353))
        sock.sendto(query, ("224.0.0.251", 5353))

        responders = set()
        deadline = time.time() + 3
        while time.time() < deadline:
            try:
                data, addr = sock.recvfrom(4096)
                # Filter out our own query echo — responses have answer count > 0
                if len(data) > 6 and (data[6] | data[7]) > 0:
                    responders.add(addr[0])
            except socket.timeout:
                break
        sock.close()

        if responders:
            msg = f"{len(responders)} mDNS responders"
            print_ok(f"mDNS functional: {msg}")
            record_result("MDNS", "PASS", msg)
        else:
            print_fail("No mDNS responses received.")
            record_result("MDNS", "FAIL", "No responses")
    except PermissionError:
        record_result("MDNS", "FAIL", "Need root for SO_BINDTODEVICE")
    except Exception as e:
        log_debug(f"mDNS error: {traceback.format_exc()}")
        record_result("MDNS", "FAIL", str(e))

def ssdp_test():
    """Send a real SSDP M-SEARCH multicast query and listen for unicast responses."""
    active_p = detect_active_priority()
    if active_p == "P3":
        print_info(f"Skipping SSDP (multicast does not traverse Relayd L3 boundary)")
        record_result("SSDP", "SKIP", f"Skipped for {active_p}")
        return

    print_info("Sending SSDP M-SEARCH (UDP/1900 → 239.255.255.250) ...")
    iface = CONFIG.get("BRIDGE_IF", "br-lan") if is_openwrt() else "br0"

    msearch = (
        'M-SEARCH * HTTP/1.1\r\n'
        'HOST: 239.255.255.250:1900\r\n'
        'MAN: "ssdp:discover"\r\n'
        'MX: 3\r\n'
        'ST: ssdp:all\r\n'
        '\r\n'
    ).encode()

    # Determine correct source IP so unicast responses can route back.
    # br-lan's primary IP is 192.168.2.1 (wrong subnet for 192.168.1.0/24
    # responders). Bind to the mgmt alias on the same subnet as REMOTE_IP.
    src_ip = ""
    try:
        out = subprocess.check_output(
            ["ip", "-4", "addr", "show", "dev", iface], text=True
        )
        remote_ip = CONFIG.get("REMOTE_IP", "192.168.1.150")
        remote_prefix = ".".join(remote_ip.split(".")[:3])
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("inet "):
                ip_addr = line.split()[1].split("/")[0]
                if ip_addr.startswith(remote_prefix + "."):
                    src_ip = ip_addr
                    break
                if not src_ip:
                    src_ip = ip_addr
    except Exception:
        pass

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, 25, iface.encode())  # SO_BINDTODEVICE
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 4)
        # Force multicast source IP — bind() alone doesn't override the kernel's
        # default source selection for multicast sendto(). IP_MULTICAST_IF tells
        # the kernel which local IP to stamp as the source on outgoing multicast.
        if src_ip:
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF,
                            socket.inet_aton(src_ip))
        sock.settimeout(4)
        sock.bind((src_ip, 0))  # Bind to correct subnet IP

        sock.sendto(msearch, ("239.255.255.250", 1900))

        responders = set()
        deadline = time.time() + 4
        while time.time() < deadline:
            try:
                data, addr = sock.recvfrom(4096)
                if b"HTTP/1.1 200 OK" in data:
                    responders.add(addr[0])
            except socket.timeout:
                break
        sock.close()

        if responders:
            msg = f"Found {len(responders)} devices"
            print_ok(f"SSDP functional: {msg}")
            record_result("SSDP", "PASS", msg)
        else:
            print_fail("No SSDP responses.")
            record_result("SSDP", "FAIL", "No responses")
    except PermissionError:
        record_result("SSDP", "FAIL", "Need root for SO_BINDTODEVICE")
    except Exception as e:
        log_debug(f"SSDP error: {traceback.format_exc()}")
        record_result("SSDP", "FAIL", str(e))

def vlan_test(active_priority):
    if active_priority == "P3":
        print_info(f"Skipping VLAN injection (Not applicable for active Layer 3 Priority: {active_priority})")
        record_result("L2_VLAN", "SKIP", f"Skipped for {active_priority}")
        return

    # Support multiple VLANS: Default 40 (Real VXLAN)
    vlan_ids = [40]
    iface_base = CONFIG.get("BRIDGE_IF", "br-lan") if is_openwrt() else "br0"

    # Target the real gateway on VLAN 40 for transparency verification
    target_ip = CONFIG.get("REMOTE_VLAN_IP", "192.168.40.1")

    overall_status = "PASS"
    overall_details = []

    for vlan_id in vlan_ids:
        vlan_iface = f"{iface_base}.{vlan_id}"
        print_info(f"Injecting VLAN ID {vlan_id} probe to {iface_base} (Target Gateway: {target_ip}) ...")

        try:
            # Always (re)create with correct VLAN IP
            setup_vlan_interface(iface_base, vlan_id, active_priority)
            time.sleep(2) # Allow for kernel/STP convergence

            # Verify L2 VLAN transparency via ping and ARP resolution.
            run_command(["arping", "-c", "2", "-w", "3", "-I", vlan_iface, target_ip], suppress_output=True)
            ping_ok, ping_out = run_command(["ping", "-c", "3", "-W", "3", "-I", vlan_iface, target_ip], suppress_output=True)
            success, arp_out = run_command(["ip", "neigh", "show", target_ip, "dev", vlan_iface])
            if ping_ok or (success and arp_out.strip() and ("REACHABLE" in arp_out.upper() or "DELAY" in arp_out.upper() or "lladdr" in arp_out)):
                mac = arp_out.strip().split("lladdr")[1].split()[0] if "lladdr" in arp_out else "responded"
                print_ok(f"VLAN {vlan_id} L2 transparent (Target: {target_ip}, MAC: {mac})")
                overall_details.append(f"V{vlan_id}:OK")
            else:
                print_fail(f"VLAN {vlan_id} failed to reach Gateway. (ping_ok={ping_ok}, arp={arp_out.strip()})")
                overall_details.append(f"V{vlan_id}:FAIL")
                overall_status = "FAIL"
        except Exception as e:
            overall_details.append(f"V{vlan_id}:ERR")
            overall_status = "FAIL"
            print_fail(f"VLAN {vlan_id} exception: {e}")
            log_debug(f"VLAN {vlan_id} error: {traceback.format_exc()}")

    record_result("L2_VLAN", overall_status, ", ".join(overall_details))

def setup_vlan_interface(base, vlan_id, active_priority="P1"):
    iface = f"{base}.{vlan_id}"
    print_info(f"Ensuring diagnostic interface {iface}...")

    # Try to remove if exists to ensure a clean state
    subprocess.run(["ip", "link", "delete", iface], capture_output=True)

    # Create with sudo if not root, but script should be run as root
    cmd = ["ip", "link", "add", "link", base, "name", iface, "type", "vlan", "id", str(vlan_id)]
    success, err = run_command(cmd)
    if not success:
        log_debug(f"Failed to create VLAN iface {iface}: {err}")
        raise Exception(f"Failed to create {iface}: {err}")

    # Set MTU to match bridge (1500 for P1, 1446 for P2)
    mtu = "1500" if active_priority == "P1" else "1446"
    run_command(["ip", "link", "set", iface, "mtu", mtu])

    run_command(["ip", "link", "set", iface, "up"])

    # Assign local test IP for the subnet using /32 to avoid hijacking runner's subnet routing
    my_ip = CONFIG.get("LOCAL_VLAN_IP", "192.168.40.254")
    target_ip = CONFIG.get("REMOTE_VLAN_IP", "192.168.40.1")
    run_command(["ip", "addr", "add", f"{my_ip}/32", "dev", iface])
    run_command(["ip", "route", "add", f"{target_ip}/32", "dev", iface, "scope", "link"], suppress_output=True)

    # Add VLAN to bridge filter table so tagged frames pass through
    if is_openwrt():
        run_command(["bridge", "vlan", "add", "dev", base, "vid", str(vlan_id), "self"], suppress_output=True)
        # Split-Trunking: Tagged VLANs always egress across VXLAN tunnel (vxlan150)
        run_command(["bridge", "vlan", "add", "dev", CONFIG.get("VXLAN_IF", "vxlan150"), "vid", str(vlan_id)], suppress_output=True)

def arp_test():
    """Verify ARP transparency — remote device MAC visible, not the bridge's MAC."""
    remote_ip = CONFIG.get("REMOTE_IP")
    if not remote_ip:
        record_result("ARP_TRANSPARENT", "SKIP", "No REMOTE_IP")
        return

    active_p = detect_active_priority()
    if active_p == "P3":
        print_info("Skipping ARP transparency (Relayd proxies ARP across L3 boundary)")
        record_result("ARP_TRANSPARENT", "SKIP", f"Skipped for {active_p}")
        return

    iface = CONFIG.get("BRIDGE_IF", "br-lan") if is_openwrt() else "br0"
    print_info(f"Verifying ARP transparency for {remote_ip} via {iface}...")

    # Ensure ARP entry exists by pinging through the bridge interface
    run_command(["ping", "-c", "2", "-W", "2", "-I", iface, remote_ip], suppress_output=True)
    time.sleep(0.5)  # Allow ARP table to settle after cold boot

    # Read the neighbor table
    success, output = run_command(["ip", "neigh", "show", remote_ip, "dev", iface])
    if not success or not output.strip():
        record_result("ARP_TRANSPARENT", "FAIL", "No ARP entry")
        return

    # Extract the MAC from the neighbor entry
    parts = output.strip().split()
    if len(parts) >= 3 and ":" in parts[2]:
        remote_mac = parts[2].lower()
    else:
        record_result("ARP_TRANSPARENT", "FAIL", f"Parse error: {output.strip()}")
        return

    # Get the bridge port MACs to compare against
    bridge_macs = set()
    try:
        _, br_out = run_command(["ip", "link", "show", iface])
        for line in br_out.splitlines():
            m = re.search(r'link/ether ([0-9a-f:]{17})', line)
            if m:
                bridge_macs.add(m.group(1).lower())
    except Exception:
        pass

    if remote_mac in bridge_macs:
        print_fail(f"ARP shows bridge MAC ({remote_mac}) — bridge is proxying ARP!")
        record_result("ARP_TRANSPARENT", "FAIL", f"Proxy ARP: {remote_mac}")
        return

    # MAC FDB verification: confirm remote MAC is learned on the expected bridge port
    fdb_info = ""
    if is_openwrt():
        active_p = detect_active_priority()
        if active_p in ("P1", "P2"):
            expected_port = "wan" if active_p == "P1" else CONFIG.get("VXLAN_IF", "vxlan150")
            ok_fdb, fdb_out = run_command(["bridge", "fdb", "show", "br", iface], suppress_output=True)
            if ok_fdb and fdb_out:
                fdb_lines = [l for l in fdb_out.lower().splitlines() if remote_mac in l]
                if fdb_lines:
                    on_expected = any(f"dev {expected_port}" in l for l in fdb_lines)
                    if on_expected:
                        fdb_info = f", FDB:{expected_port} ✓"
                    else:
                        ports = set()
                        for l in fdb_lines:
                            m = re.search(r'dev (\S+)', l)
                            if m: ports.add(m.group(1))
                        fdb_info = f", FDB:{','.join(ports)} (expected {expected_port})"
                        print_warn(f"FDB: {remote_mac} on {','.join(ports)}, expected {expected_port}")
                else:
                    fdb_info = ", FDB:not learned"

    print_ok(f"ARP transparent: {remote_mac}{fdb_info}")
    record_result("ARP_TRANSPARENT", "PASS", f"{remote_mac}{fdb_info}")

def dhcp_test():
    """Verify DHCP discover/offer crosses the bridge.
    P1/P3/Debian: broadcast discover (native L2 path to DHCP server).
    P2: unicast discover to gateway (broadcast doesn't reliably traverse VXLAN
    tunnels without a dedicated relay agent — RFC 2131 §4.1 allows unicast).
    """
    active_p = detect_active_priority()
    iface = CONFIG.get("BRIDGE_IF", "br-lan") if is_openwrt() else "br0"
    # P3: gateway is only reachable via wl1-sta0 (relayd relay), not br-lan L2
    if active_p == "P3" and is_openwrt():
        iface = "wl1-sta0"
    gateway = CONFIG.get("GATEWAY_IP", "192.168.1.1")
    use_unicast = (active_p in ("P2", "P3"))

    if use_unicast:
        print_info(f"Testing DHCP service via unicast to {gateway} ({iface})...")
    else:
        print_info(f"Testing DHCP relay across bridge ({iface})...")

    # Build a minimal DHCP Discover packet
    import random
    xid = random.randint(1, 0xFFFFFFFF).to_bytes(4, 'big')
    # BOOTP: op=1(request), htype=1(eth), hlen=6, hops=0
    bootp = b'\x01\x01\x06\x00' + xid
    bootp += b'\x00\x00'      # secs
    # Always set broadcast flag — the server unicasts the offer to the
    # *offered* yiaddr (not our source IP), so without the flag the reply
    # goes to an IP we don't own and the socket never sees it.
    bootp += b'\x80\x00'      # flags: broadcast bit set
    bootp += b'\x00' * 16     # ciaddr, yiaddr, siaddr, giaddr
    fake_mac = b'\xde\xad\xbe\xef\x00\x01'
    bootp += fake_mac + b'\x00' * 10  # chaddr padded to 16 bytes
    bootp += b'\x00' * 192    # sname + file
    # DHCP magic cookie + option 53 (DHCP Discover) + end
    bootp += b'\x63\x82\x53\x63'  # magic cookie
    bootp += b'\x35\x01\x01'      # Option 53: DHCP Discover
    bootp += b'\xff'               # End

    dhcp_target = (gateway, 67) if use_unicast else ("255.255.255.255", 67)

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.setsockopt(socket.SOL_SOCKET, 25, iface.encode())  # SO_BINDTODEVICE
        # Bind to 0.0.0.0 to receive broadcast replies (server responds to 255.255.255.255)
        sock.bind(("", 68))

        # Retry up to 3 times — first packet through VXLAN may be lost to ARP resolution
        for attempt in range(3):
            sock.settimeout(5)
            sock.sendto(bootp, dhcp_target)
            try:
                data, addr = sock.recvfrom(4096)
                if b'\x63\x82\x53\x63' in data:
                    print_ok(f"DHCP offer received from {addr[0]}")
                    record_result("DHCP_RELAY", "PASS", f"Server: {addr[0]}")
                    sock.close()
                    return
                else:
                    print_fail("Response received but not a valid DHCP offer.")
                    record_result("DHCP_RELAY", "FAIL", "Invalid response")
                    sock.close()
                    return
            except socket.timeout:
                log_debug(f"DHCP attempt {attempt + 1}/3 timed out")
        print_fail("No DHCP offer received (timeout).")
        record_result("DHCP_RELAY", "FAIL", "Timeout")
        sock.close()
    except PermissionError:
        record_result("DHCP_RELAY", "FAIL", "Need root for raw DHCP")
    except Exception as e:
        log_debug(f"DHCP error: {traceback.format_exc()}")
        record_result("DHCP_RELAY", "FAIL", str(e))

def iperf_test():
    remote_ip = CONFIG.get("REMOTE_IP")
    if not remote_ip:
        record_result("BW_UPLOAD", "SKIP", "No REMOTE_IP")
        return

    print_info(f"Running Iperf3 bandwidth upload to {remote_ip}...")
    success, output = run_command(["iperf3", "-c", remote_ip, "-t", "5", "-J"], timeout=15)

    if success:
        try:
            global _last_tcp_bps
            js = json.loads(output)
            bps = js['end']['sum_received']['bits_per_second']
            _last_tcp_bps = bps
            mbps = f"{bps / 1_000_000:.2f} Mbps"
            print_ok(f"Bandwidth: {mbps}")
            record_result("BW_UPLOAD", "PASS", mbps)
        except Exception:
            record_result("BW_UPLOAD", "FAIL", "JSON Parse Error")
    else:
        print_fail("Iperf3 failure.")
        record_result("BW_UPLOAD", "FAIL", "Server Offline/Timeout")

def udp_jitter_test():
    """Test UDP throughput, jitter, and packet loss via iperf3."""
    remote_ip = CONFIG.get("REMOTE_IP")
    if not remote_ip:
        record_result("UDP_JITTER", "SKIP", "No REMOTE_IP")
        return

    time.sleep(3)  # Let iperf3 server fully reset after TCP test

    # Derive UDP rate: 60% of TCP bandwidth
    # If --tcp-cap provided (remote side), use coordinator's TCP as the base rate
    if _tcp_cap_bps and _tcp_cap_bps > 0:
        base_bps = _tcp_cap_bps
        udp_rate = int(base_bps * 0.60)
        udp_rate_str = f"{udp_rate}"
        udp_rate_label = f"{udp_rate / 1_000_000:.0f}M (60% of coordinator TCP)"
    elif _last_tcp_bps and _last_tcp_bps > 0:
        udp_rate = int(_last_tcp_bps * 0.60)
        udp_rate_str = f"{udp_rate}"
        udp_rate_label = f"{udp_rate / 1_000_000:.0f}M (60% of TCP)"
    else:
        udp_rate_str = "200M"
        udp_rate_label = "200M (default)"

    print_info(f"Running UDP saturation test to {remote_ip} at {udp_rate_label}...")
    success, output = run_command(["iperf3", "-c", remote_ip, "-u", "-b", udp_rate_str, "-t", "5", "-J"], timeout=15)

    if success:
        try:
            js = json.loads(output)
            summary = js['end']['sum']
            bps = summary.get('bits_per_second', 0)
            mbps = bps / 1_000_000
            jitter = summary.get('jitter_ms', -1)
            lost = summary.get('lost_packets', 0)
            total = summary.get('packets', 1)
            loss_pct = (lost / total * 100) if total > 0 else 100

            details = f"{mbps:.1f} Mbps, jitter={jitter:.3f}ms, loss={loss_pct:.1f}%"
            if loss_pct > 5:
                print_warn(f"UDP: {details}")
                record_result("UDP_JITTER", "WARN", details)
            else:
                print_ok(f"UDP: {details}")
                record_result("UDP_JITTER", "PASS", details)
        except Exception as e:
            log_debug(f"UDP parse error: {e}")
            record_result("UDP_JITTER", "FAIL", "JSON Parse Error")
    else:
        print_fail("UDP iperf3 failure.")
        record_result("UDP_JITTER", "FAIL", "Server Offline/Timeout")

def multistream_test():
    """Test multi-stream TCP throughput (WiFi 7 MLO aggregation)."""
    remote_ip = CONFIG.get("REMOTE_IP")
    if not remote_ip:
        record_result("MULTI_STREAM", "SKIP", "No REMOTE_IP")
        return

    time.sleep(3)  # Let iperf3 server recover after UDP saturation
    streams = 4
    print_info(f"Running {streams}-stream parallel TCP throughput to {remote_ip}...")
    success, output = run_command(["iperf3", "-c", remote_ip, "-P", str(streams), "-t", "5", "-J"], timeout=20)

    if success:
        try:
            js = json.loads(output)
            if 'error' in js:
                print_fail(f"iperf3 error: {js['error']}")
                record_result("MULTI_STREAM", "FAIL", js['error'][:40])
                return
            bps = js['end']['sum_received']['bits_per_second']
            mbps = f"{bps / 1_000_000:.2f} Mbps"
            print_ok(f"Multi-stream ({streams}P): {mbps}")
            record_result("MULTI_STREAM", "PASS", f"{streams}P: {mbps}")
        except Exception:
            record_result("MULTI_STREAM", "FAIL", "JSON Parse Error")
    else:
        print_fail("Multi-stream iperf3 failure.")
        record_result("MULTI_STREAM", "FAIL", "Server Offline/Timeout")

# -------------------- Remote Co-ordination --------------------
def start_remote_echo():
    print_info("Booting local SSDP/mDNS/Iperf test endpoints...")
    run_command(["iperf3", "-s", "-D"])
    # In full script we would spin up scapy listeners here

def gather_remote_results(args_str):
    local_on_openwrt = is_openwrt()

    if local_on_openwrt:
        # We are on OpenWrt, Target is Debian
        ssh_user = CONFIG.get("TEST_REMOTE_SSH_USER", "meek2100")
        remote_binary = "/usr/local/bin/failover-tester.py"
        sudo_cmd = "sudo "
    else:
        # We are on Debian, Target is OpenWrt
        ssh_user = "root"
        remote_binary = "/usr/bin/failover-tester.py"
        sudo_cmd = ""

    remote_ip = CONFIG.get("REMOTE_IP")
    key = os.path.expanduser(CONFIG.get("SSH_PRIVATE_KEY_PATH", "~/.ssh/id_ed25519"))

    print_info(f"Triggering remote responder agent ({remote_ip}) to collect reverse metrics...")

    # Dropbear (OpenWrt) is picky about -o options.
    if is_openwrt():
        cmd = ["dbclient", "-y", "-i", key, f"{ssh_user}@{remote_ip}",
               f"{sudo_cmd}python3 {remote_binary} --remote-only {args_str}"]
    else:
        cmd = ["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no",
               f"{ssh_user}@{remote_ip}", f"{sudo_cmd}python3 {remote_binary} --remote-only {args_str}"]

    log_debug(f"Remote command: {' '.join(cmd)}")
    collected = []
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                universal_newlines=True)
        deadline = time.time() + 90
        while True:
            if proc.poll() is not None:
                # Process finished — read remaining output
                for line in proc.stdout:
                    collected.append(line)
                break
            if time.time() > deadline:
                proc.kill()
                print_fail("Remote agent timed out (90s).")
                break
            # Read one line at a time, relay progress lines to console
            line = proc.stdout.readline()
            if not line:
                continue
            collected.append(line)
            stripped = line.strip()
            # Relay human-readable progress lines from the remote side
            if stripped and not stripped.startswith('{'):
                print(f"  ↳ Remote: {stripped}", flush=True)
    except Exception as e:
        print_fail(f"Remote SSH error: {e}")
        return None

    output = "".join(collected)
    if output:
        try:
            start = output.find('{')
            end = output.rfind('}') + 1
            if start != -1 and end != -1:
                return json.loads(output[start:end])
        except Exception:
            pass

    print_fail("Failed to gather bidirectional remote stats.")
    return None

# -------------------- Summary Formatter --------------------
def tabular_print(local_res, remote_res, active_p):
    local_ip = CONFIG.get("LOCAL_IP", "OpenWrt" if is_openwrt() else "Server")
    remote_ip = CONFIG.get("REMOTE_IP", "Remote")

    print("\n\n" + "="*85)
    print("               UNIFIED FAILOVER DIAGNOSTICS")
    print("="*85)
    print(f" * Active Link State: [ {active_p} ]")
    print("-"*85)

    header_local = f"LOCAL ({local_ip}) -> REMOTE"
    header_remote = f"REMOTE ({remote_ip}) -> LOCAL"

    print(f"{'TEST METRIC':<20} | {header_local:<30} | {header_remote:<30}")
    print("-"*85)

    keys = ["GW_PING", "INTERNET", "ICMP_LATENCY", "ARP_TRANSPARENT", "MTU_SWEEP", "BW_UPLOAD", "UDP_JITTER",
            "MULTI_STREAM", "MDNS", "SSDP", "L2_VLAN", "DHCP_RELAY"]
    for k in keys:
        l_res = local_res.get(k, {"status": "ⓘ", "details": "Skipped"})
        r_res = remote_res.get(k, {"status": "ⓘ", "details": "Skipped"}) if remote_res else {"status": "ⓘ", "details": "N/A"}

        l_str = f"{l_res['status']} {l_res['details'][:27]}"
        r_str = f"{r_res['status']} {r_res['details'][:27]}"
        print(f"{k:<20} | {l_str:<30} | {r_str:<30}")

    print("="*85)

# -------------------- Main --------------------
class AliasedParser(argparse.ArgumentParser):
    def parse_args(self, args=None, namespace=None):
        if args is None: args = sys.argv[1:]
        normalized = []
        for arg in args:
            if arg in ['-a', '--a', '-all', '--all']:
                normalized.append('--all')
            elif arg in ['-i', '--i', '-icmp', '--icmp']:
                normalized.append('--icmp')
            elif arg in ['-u', '--u', '-mtu', '--mtu']:
                normalized.append('--mtu')
            elif arg in ['-m', '--m', '-mdns', '--mdns']:
                normalized.append('--mdns')
            elif arg in ['-s', '--s', '-ssdp', '--ssdp']:
                normalized.append('--ssdp')
            elif arg in ['-v', '--v', '-vlan', '--vlan']:
                normalized.append('--vlan')
            elif arg in ['-p', '--p', '-iperf', '--iperf']:
                normalized.append('--iperf')
            elif arg in ['-r', '--r', '-arp', '--arp']:
                normalized.append('--arp')
            elif arg in ['-d', '--d', '-dhcp', '--dhcp']:
                normalized.append('--dhcp')
            elif arg in ['-j', '--j', '-udp', '--udp']:
                normalized.append('--udp')
            elif arg in ['-x', '--x', '-multi', '--multi', '-multistream', '--multistream']:
                normalized.append('--multi')
            elif arg in ['-g', '--g', '-gw', '--gw', '-gateway', '--gateway']:
                normalized.append('--gw')
            elif arg in ['-L', '--L', '-local', '--local']:
                normalized.append('--local')
            elif arg in ['-R', '--R', '-remote', '--remote']:
                normalized.append('--remote')
            else:
                normalized.append(arg)
        return super().parse_args(normalized, namespace)

if __name__ == "__main__":
    parser = AliasedParser(
        description="Unified Failover Diagnostics — bidirectional L2/L3 test suite",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n"
               "  %(prog)s --all           Run full suite (default if no flags)\n"
               "  %(prog)s --icmp --arp    Run only ping and ARP tests\n"
               "  %(prog)s --iperf --udp   Run bandwidth tests only\n"
               "  %(prog)s --local         Run local tests only, skip remote\n"
               "  %(prog)s --remote        Run remote tests only, skip local\n"
               "  %(prog)s -L --gw         Local gateway/internet test only\n"
    )
    parser.add_argument("-a", "--all", action="store_true", help="Run all tests (default)")
    parser.add_argument("-i", "--icmp", action="store_true", help="ICMP latency and packet loss")
    parser.add_argument("-r", "--arp", action="store_true", help="ARP transparency verification")
    parser.add_argument("-u", "--mtu", action="store_true", help="MTU path sweep (1500/1450/1446)")
    parser.add_argument("-p", "--iperf", action="store_true", help="TCP bandwidth upload (iperf3)")
    parser.add_argument("-j", "--udp", action="store_true", help="UDP jitter and packet loss")
    parser.add_argument("-x", "--multi", action="store_true", help="Multi-stream TCP throughput (4P)")
    parser.add_argument("-m", "--mdns", action="store_true", help="mDNS service discovery")
    parser.add_argument("-s", "--ssdp", action="store_true", help="SSDP device discovery")
    parser.add_argument("-v", "--vlan", action="store_true", help="L2 VLAN 40 transparency probe")
    parser.add_argument("-d", "--dhcp", action="store_true", help="DHCP relay/offer verification")
    parser.add_argument("-g", "--gw", action="store_true", help="Gateway + internet reachability")
    parser.add_argument("-L", "--local", action="store_true", help="Run local tests only (skip remote)")
    parser.add_argument("-R", "--remote", action="store_true", help="Run remote tests only (skip local)")
    parser.add_argument("--tcp-cap", type=float, default=0, help=argparse.SUPPRESS)
    parser.add_argument("--remote-only", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.local and args.remote:
        print("Error: --local and --remote are mutually exclusive. Omit both for full suite.")
        sys.exit(1)

    load_config()
    setup_logging()

    if args.tcp_cap and args.tcp_cap > 0:
        _tcp_cap_bps = args.tcp_cap

    active_priority = detect_active_priority()

    if not any([args.all, args.icmp, args.mtu, args.mdns, args.ssdp, args.vlan, args.iperf,
                args.arp, args.dhcp, args.udp, args.multi, args.gw]):
        args.all = True

    run_local_tests = not args.remote
    run_remote_tests = not args.local

    if args.remote_only:
        try:
            if args.all or args.gw: gateway_test(); internet_test()
            if args.all or args.icmp: icmp_test()
            if args.all or args.arp: arp_test()
            if args.all or args.mtu: mtu_sweep_test()
            if args.all or args.mdns: mdns_test()
            if args.all or args.ssdp: ssdp_test()
            if args.all or args.vlan: vlan_test(active_priority)
            if args.all or args.iperf: iperf_test()
            if args.all or args.udp: udp_jitter_test()
            if args.all or args.multi: multistream_test()
            if args.all or args.dhcp: dhcp_test()
        finally:
            teardown_vlan_test_env()

        print(json.dumps(TEST_RESULTS))
        sys.exit(0)

    # Main Local Coordinator
    if not CONFIG.get("REMOTE_IP"):
        print_fail("No REMOTE_IP defined in Config! Cannot test.")
        sys.exit(1)

    remote_ip = CONFIG.get("REMOTE_IP")

    # Pre-check: is the remote host reachable?
    remote_reachable = False
    print_info(f"Checking remote host reachability ({remote_ip})...")
    rc = subprocess.call(["ping", "-c", "1", "-W", "2", remote_ip],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if rc == 0:
        remote_reachable = True
        print_ok(f"Remote host {remote_ip} is reachable.")
    else:
        print_fail(f"Remote host {remote_ip} is UNREACHABLE — skipping remote-dependent tests.")

    REMOTE_TESTS = {"ICMP_LATENCY", "ARP_TRANSPARENT", "BW_UPLOAD", "UDP_JITTER", "MULTI_STREAM"}

    print_info(f"Local tests initializing over {active_priority} failover state...")

    # 1. Start endpoints for remote mapping
    if remote_reachable and (args.all or args.iperf or args.udp or args.multi):
        if run_remote_tests:
            run_command(["iperf3", "-s", "-D"])  # Local server for remote→local tests
        if run_local_tests:
            # Pre-start iperf3 on remote so local→remote tests can connect
            key = os.path.expanduser(CONFIG.get("SSH_PRIVATE_KEY_PATH", "~/.ssh/id_ed25519"))
            if is_openwrt():
                ssh_user = CONFIG.get("TEST_REMOTE_SSH_USER", "meek2100")
                run_command(["dbclient", "-y", "-i", key, f"{ssh_user}@{remote_ip}",
                             "sudo iperf3 -s -D"], timeout=10, suppress_output=True)
            else:
                run_command(["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no",
                             f"root@{remote_ip}", "iperf3 -s -D"], timeout=10, suppress_output=True)

    remote_payload = None
    try:
        # 2. Test Local outbound
        if run_local_tests:
            if args.all or args.gw: gateway_test(); internet_test()
            if args.all or args.icmp:
                if remote_reachable: icmp_test()
                else: record_result("ICMP_LATENCY", "SKIP", "Remote unreachable")
            if args.all or args.arp:
                if remote_reachable: arp_test()
                else: record_result("ARP_TRANSPARENT", "SKIP", "Remote unreachable")
            if args.all or args.mtu: mtu_sweep_test()
            if args.all or args.mdns: mdns_test()
            if args.all or args.ssdp: ssdp_test()
            if args.all or args.vlan: vlan_test(active_priority)
            if args.all or args.iperf:
                if not run_remote_tests:
                    record_result("BW_UPLOAD", "SKIP", "Requires bidirectional (omit -L)")
                elif remote_reachable: iperf_test()
                else: record_result("BW_UPLOAD", "SKIP", "Remote unreachable")
            if args.all or args.udp:
                if not run_remote_tests:
                    record_result("UDP_JITTER", "SKIP", "Requires bidirectional (omit -L)")
                elif remote_reachable: udp_jitter_test()
                else: record_result("UDP_JITTER", "SKIP", "Remote unreachable")
            if args.all or args.multi:
                if not run_remote_tests:
                    record_result("MULTI_STREAM", "SKIP", "Requires bidirectional (omit -L)")
                elif remote_reachable: multistream_test()
                else: record_result("MULTI_STREAM", "SKIP", "Remote unreachable")
            if args.all or args.dhcp: dhcp_test()

        # 3. Pull Reverse Tests via SSH
        if run_remote_tests and remote_reachable:
            raw_args = [a for a in sys.argv[1:] if a not in ("--remote-only", "--local", "-L", "--remote", "-R")]
            if _last_tcp_bps and _last_tcp_bps > 0:
                raw_args.append(f"--tcp-cap {int(_last_tcp_bps)}")
            remote_payload = gather_remote_results(" ".join(raw_args))
    finally:
        # 4. Cleanup
        teardown_vlan_test_env()
        if args.all or args.iperf or args.udp or args.multi: run_command(["pkill", "iperf3"])

    # Provide Final Table
    tabular_print(TEST_RESULTS, remote_payload, active_priority)
