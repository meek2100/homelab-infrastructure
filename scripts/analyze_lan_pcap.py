#!/usr/bin/env python3
"""
analyze_lan_pcap.py - High-Performance Enterprise LAN PCAP/PCAPNG Diagnostic Analyzer
====================================================================================
Designed for Principal Network Infrastructure Engineers and Security Researchers.

Interrogates completed .pcap / .pcapng files to extract, aggregate, and output
structured JSON and Markdown diagnostic reports covering:
  1. Layer 2 Broadcast/Multicast Hygiene (ARP, mDNS, LLMNR, SSDP, STP/RSTP TCNs)
  2. Transport & Link Health (TCP retransmissions, dup-acks, ZeroWindow, handshakes, MSS clamping)
  3. Core Services Performance (DNS latency, failure codes, external resolvers; DHCP DORA & rogues)
  4. Security & Protocol Anomalies (Cleartext protocols, port/SYN sweeps, ICMP redirects)
  5. Conversation Matrix & Inter-VLAN / Inter-Subnet Routing Flows
"""

import os
import sys
import glob
import json
import time
import socket
import struct
import argparse
from collections import defaultdict, Counter
from typing import Dict, Any, List, Optional, Tuple

try:
    import dpkt
except ImportError:
    print("CRITICAL: 'dpkt' library not found. Install via 'pip install dpkt' or run in Docker.", file=sys.stderr)
    sys.exit(1)


def normalize_path(path_str: str) -> str:
    """Normalize Windows C:\\ paths to Linux/WSL /mnt/c/ if running in WSL/Linux."""
    if not path_str:
        return path_str
    if sys.platform != 'win32' and len(path_str) >= 2 and path_str[1] == ':' and path_str[0].isalpha():
        drive = path_str[0].lower()
        rest = path_str[2:].replace('\\', '/')
        if rest.startswith('/'):
            wsl_path = f"/mnt/{drive}{rest}"
        else:
            wsl_path = f"/mnt/{drive}/{rest}"
        if os.path.exists(wsl_path):
            return wsl_path
    return os.path.expanduser(path_str.replace('\\', '/'))


def format_mac(raw_bytes: bytes) -> str:
    if not raw_bytes or len(raw_bytes) < 6:
        return "00:00:00:00:00:00"
    return ":".join(f"{b:02x}" for b in raw_bytes[:6])


def format_ip(raw_bytes: bytes) -> str:
    if not raw_bytes:
        return ""
    if len(raw_bytes) == 4:
        return socket.inet_ntoa(raw_bytes)
    elif len(raw_bytes) == 16:
        return socket.inet_ntop(socket.AF_INET6, raw_bytes)
    return ""


def is_rfc1918(ip_str: str) -> bool:
    """Check if IPv4 address is in RFC1918 private ranges (10/8, 172.16/12, 192.168/16) or loopback/link-local."""
    try:
        octets = [int(p) for p in ip_str.split('.')]
        if len(octets) != 4:
            return False
        if octets[0] == 10:
            return True
        if octets[0] == 172 and 16 <= octets[1] <= 31:
            return True
        if octets[0] == 192 and octets[1] == 168:
            return True
        if octets[0] == 127 or (octets[0] == 169 and octets[1] == 254):
            return True
    except Exception:
        pass
    return False


def get_subnet_prefix(ip_str: str) -> str:
    """Returns /24 subnet prefix for simple grouping."""
    parts = ip_str.split('.')
    if len(parts) == 4:
        return f"{parts[0]}.{parts[1]}.{parts[2]}.0/24"
    return "Non-IPv4"


class LANPcapAnalyzer:
    def __init__(self, sample_limit: Optional[int] = None):
        self.sample_limit = sample_limit
        
        # General Counters
        self.total_packets = 0
        self.total_bytes = 0
        self.start_timestamp = float('inf')
        self.end_timestamp = 0.0
        self.processed_files = []

        # 1. Layer 2 Broadcast/Multicast
        self.unicast_count = 0
        self.broadcast_count = 0
        self.multicast_count = 0
        self.l2_protocols = Counter()
        
        self.arp_requests_by_source = Counter() # (src_ip, src_mac) -> count
        self.arp_requests_seen = defaultdict(lambda: 0) # target_ip -> count
        self.arp_replies_seen = set() # (target_ip, responder_ip)
        self.arp_sec_buckets = Counter() # int(ts) -> count
        
        self.stp_bpdu_count = 0
        self.stp_tcn_count = 0
        self.stp_bridge_ids = Counter()
        
        # 2. Transport & Link Health
        self.tcp_flows = {} # (sip, sport, dip, dport) -> flow state
        self.tcp_retransmissions = 0
        self.tcp_fast_retransmissions = 0
        self.tcp_duplicate_acks = 0
        self.tcp_out_of_order = 0
        self.tcp_zero_windows = 0
        self.tcp_zero_window_sources = Counter()
        self.tcp_window_full = 0
        self.tcp_resets = 0
        self.tcp_reset_senders = Counter()
        
        self.tcp_syn_sent = Counter() # (sip, sport, dip, dport) -> ts
        self.tcp_syn_ack_rcvd = set()
        self.tcp_syn_rst = Counter()
        
        self.icmp_frag_needed = [] # list of (src, dst, mtu, ip_payload_dest)
        self.tcp_syn_mss_dist = Counter() # mss_value -> count
        self.tcp_mss_clamped_senders = Counter() # (sip, mss) -> count (< 1460)

        # 3. Core Services Performance
        # DNS
        self.dns_queries = {} # (client_ip, client_port, server_ip, tx_id) -> (ts, qname)
        self.dns_latencies = [] # in milliseconds
        self.dns_rcodes = Counter()
        self.dns_client_volume = Counter() # client_ip -> count
        self.dns_external_resolvers = Counter() # ext_ip -> count
        self.dns_top_queries = Counter()
        self.dns_nxdomain_queries = Counter()
        
        # DHCP
        self.dhcp_transactions = defaultdict(dict) # xid -> {'discover_ts', 'offer_ts', 'request_ts', 'ack_ts', 'servers': set(), 'mac': str}
        self.dhcp_msg_types = Counter()
        self.dhcp_nak_loops = Counter() # client_mac -> count
        self.dhcp_rogue_candidates = [] # list of details
        
        # 4. Security & Protocol Anomalies
        self.cleartext_protocols = Counter()
        self.cleartext_samples = []
        self.syn_sweep_tracker = defaultdict(set) # src_ip -> set of (dst_ip, dst_port)
        self.icmp_redirects = [] # (src_router, orig_dst, new_gw)
        
        # 5. Conversation Matrix & VLAN Flows
        self.ip_bandwidth = Counter() # ip -> bytes
        self.ip_packet_count = Counter() # ip -> pkts
        self.vlan_traffic = Counter() # vlan_id -> pkts
        self.vlan_bytes = Counter() # vlan_id -> bytes
        self.cross_subnet_flows = Counter() # (src_subnet, dst_subnet) -> bytes
        self.cross_vlan_flows = Counter() # (src_vlan, dst_vlan or subnet) -> bytes

    def process_file(self, filepath: str):
        """Streams packets from a pcap or pcapng file using dpkt."""
        self.processed_files.append(filepath)
        file_packets = 0
        file_bytes = 0
        
        with open(filepath, 'rb') as f:
            reader = None
            try:
                reader = dpkt.pcapng.Reader(f)
                _ = reader.datalink()
            except Exception:
                f.seek(0)
                try:
                    reader = dpkt.pcap.Reader(f)
                except Exception as e:
                    print(f"[-] Could not open {filepath}: {e}", file=sys.stderr)
                    return

            for ts, buf in reader:
                file_packets += 1
                pkt_len = len(buf)
                file_bytes += pkt_len
                self.total_packets += 1
                self.total_bytes += pkt_len
                
                if ts < self.start_timestamp:
                    self.start_timestamp = ts
                if ts > self.end_timestamp:
                    self.end_timestamp = ts
                    
                self._analyze_packet(ts, buf, pkt_len)
                
                if self.sample_limit and self.total_packets >= self.sample_limit:
                    break

    def _analyze_packet(self, ts: float, buf: bytes, pkt_len: int):
        try:
            eth = dpkt.ethernet.Ethernet(buf)
        except Exception:
            return

        dst_mac_raw = eth.dst
        src_mac_raw = eth.src
        dst_mac = format_mac(dst_mac_raw)
        src_mac = format_mac(src_mac_raw)
        
        # Determine L2 Frame Type (Broadcast / Multicast / Unicast)
        is_broadcast = (dst_mac_raw == b'\xff\xff\xff\xff\xff\xff')
        is_multicast = False
        if not is_broadcast and len(dst_mac_raw) > 0 and (dst_mac_raw[0] & 1) == 1:
            is_multicast = True
            
        if is_broadcast:
            self.broadcast_count += 1
        elif is_multicast:
            self.multicast_count += 1
        else:
            self.unicast_count += 1

        # Check 802.1Q VLAN Tags
        vlan_id = None
        if hasattr(eth, 'vlan_tags') and eth.vlan_tags:
            vlan_id = eth.vlan_tags[0].id
            self.vlan_traffic[vlan_id] += 1
            self.vlan_bytes[vlan_id] += pkt_len
        elif hasattr(eth, 'vlanid') and eth.vlanid:
            vlan_id = eth.vlanid
            self.vlan_traffic[vlan_id] += 1
            self.vlan_bytes[vlan_id] += pkt_len

        # Check STP / RSTP (01:80:c2:00:00:00 or Cisco PVST+ 01:00:0c:cc:cc:cd)
        if dst_mac_raw in (b'\x01\x80\xc2\x00\x00\x00', b'\x01\x00\x0c\xcc\xcc\xcd'):
            self.l2_protocols['STP/RSTP'] += 1
            self._handle_stp(eth)
            return

        # Check LLDP (0x88cc) or CDP (0x2000 SNAP)
        if eth.type == 0x88cc:
            self.l2_protocols['LLDP'] += 1
            return
        elif dst_mac_raw == b'\x01\x00\x0c\xcc\xcc\xcc':
            self.l2_protocols['CDP'] += 1
            return

        payload = eth.data

        # --- ARP Processing ---
        if isinstance(payload, dpkt.arp.ARP) or eth.type == dpkt.ethernet.ETH_TYPE_ARP:
            self.l2_protocols['ARP'] += 1
            self._handle_arp(ts, payload)
            return

        # --- IP Processing ---
        if isinstance(payload, dpkt.ip.IP):
            self._handle_ipv4(ts, payload, pkt_len, vlan_id)
        elif isinstance(payload, dpkt.ip6.IP6):
            self.l2_protocols['IPv6'] += 1

    def _handle_stp(self, eth):
        self.stp_bpdu_count += 1
        llc = eth.data
        if isinstance(llc, dpkt.llc.LLC):
            stp_data = llc.data
            if isinstance(stp_data, dpkt.stp.STP):
                bridge_hex = format_mac(stp_data.bridge_id[2:]) if len(stp_data.bridge_id) >= 8 else stp_data.bridge_id.hex()
                self.stp_bridge_ids[bridge_hex] += 1
                
                # Check for TCN (type 0x80) or TC flag (bit 0 == 1 or bit 7 == 1)
                if stp_data.type == 0x80 or (stp_data.flags & 0x01) or (stp_data.flags & 0x80):
                    self.stp_tcn_count += 1

    def _handle_arp(self, ts: float, arp: dpkt.arp.ARP):
        sec_bucket = int(ts)
        self.arp_sec_buckets[sec_bucket] += 1
        
        try:
            spa = socket.inet_ntoa(arp.spa)
            tpa = socket.inet_ntoa(arp.tpa)
            sha = format_mac(arp.sha)
            
            if arp.op == dpkt.arp.ARP_OP_REQUEST:
                self.arp_requests_by_source[(spa, sha)] += 1
                self.arp_requests_seen[tpa] += 1
            elif arp.op == dpkt.arp.ARP_OP_REPLY:
                self.arp_replies_seen.add((spa, tpa))
        except Exception:
            pass

    def _handle_ipv4(self, ts: float, ip: dpkt.ip.IP, pkt_len: int, vlan_id: Optional[int]):
        sip = format_ip(ip.src)
        dip = format_ip(ip.dst)
        
        # Track Top Talkers
        self.ip_bandwidth[sip] += pkt_len
        self.ip_bandwidth[dip] += pkt_len
        self.ip_packet_count[sip] += 1
        self.ip_packet_count[dip] += 1
        
        # Track Cross-Subnet Flows
        src_sub = get_subnet_prefix(sip)
        dst_sub = get_subnet_prefix(dip)
        if src_sub != dst_sub and src_sub != "Non-IPv4" and dst_sub != "Non-IPv4":
            self.cross_subnet_flows[(src_sub, dst_sub)] += pkt_len

        # Protocol Specific Demux
        if ip.p == dpkt.ip.IP_PROTO_ICMP:
            self._handle_icmp(ts, sip, dip, ip.data)
        elif ip.p == dpkt.ip.IP_PROTO_IGMP:
            self.l2_protocols['IGMP'] += 1
        elif ip.p == dpkt.ip.IP_PROTO_TCP:
            if isinstance(ip.data, dpkt.tcp.TCP):
                self._handle_tcp(ts, sip, dip, ip.data, pkt_len)
        elif ip.p == dpkt.ip.IP_PROTO_UDP:
            if isinstance(ip.data, dpkt.udp.UDP):
                self._handle_udp(ts, sip, dip, ip.data, pkt_len)

    def _handle_icmp(self, ts: float, sip: str, dip: str, icmp: Any):
        if not isinstance(icmp, dpkt.icmp.ICMP):
            return
        
        # ICMP Type 3 Code 4: Fragmentation Needed
        if icmp.type == 3 and icmp.code == 4:
            next_hop_mtu = getattr(icmp.data, 'mtu', 0) if hasattr(icmp.data, 'mtu') else 0
            self.icmp_frag_needed.append({
                "time": ts,
                "router": sip,
                "target_host": dip,
                "advertised_mtu": next_hop_mtu
            })
        
        # ICMP Type 5: Redirect Message
        elif icmp.type == 5:
            new_gw = ""
            if hasattr(icmp.data, 'gw'):
                new_gw = socket.inet_ntoa(icmp.data.gw)
            self.icmp_redirects.append({
                "time": ts,
                "router": sip,
                "target_host": dip,
                "suggested_gateway": new_gw,
                "code": icmp.code
            })

    def _handle_tcp(self, ts: float, sip: str, dip: str, tcp: dpkt.tcp.TCP, pkt_len: int):
        sport = tcp.sport
        dport = tcp.dport
        flags = tcp.flags
        payload = tcp.data
        payload_len = len(payload)
        
        flow_key = (sip, sport, dip, dport)
        rev_key = (dip, dport, sip, sport)
        
        # Detect Cleartext Protocols
        if dport == 80 or sport == 80:
            self.cleartext_protocols['HTTP'] += 1
            if payload_len > 0 and (payload.startswith(b'GET ') or payload.startswith(b'POST ') or payload.startswith(b'HTTP/')):
                if b'Authorization: Basic' in payload:
                    self.cleartext_samples.append(f"HTTP Basic Auth detected from {sip}:{sport} -> {dip}:{dport} [REDACTED]")
        elif dport == 23 or sport == 23:
            self.cleartext_protocols['Telnet'] += 1
        elif dport == 21 or sport == 21:
            self.cleartext_protocols['FTP'] += 1
        elif dport == 389 or sport == 389:
            self.cleartext_protocols['Unencrypted LDAP'] += 1
        elif dport in (139, 445) or sport in (139, 445):
            if payload.startswith(b'\xffSMB') or (payload_len >= 8 and b'\xffSMB' in payload[:10]):
                self.cleartext_protocols['SMBv1 (Legacy/Insecure)'] += 1

        # Check TCP MSS option on SYN
        if flags & dpkt.tcp.TH_SYN:
            try:
                opts = dpkt.tcp.parse_opts(tcp.opts)
                for opt_type, opt_val in opts:
                    if opt_type == dpkt.tcp.TCP_OPT_MSS and len(opt_val) == 2:
                        mss_val = struct.unpack('>H', opt_val)[0]
                        self.tcp_syn_mss_dist[mss_val] += 1
                        if mss_val < 1460:
                            self.tcp_mss_clamped_senders[(sip, mss_val)] += 1
            except Exception:
                pass
            
            # Port sweep tracking: only SYN without ACK
            if not (flags & dpkt.tcp.TH_ACK):
                self.syn_sweep_tracker[sip].add((dip, dport))
                self.tcp_syn_sent[flow_key] = ts
            else:
                self.tcp_syn_ack_rcvd.add(rev_key)

        # Check Resets
        if flags & dpkt.tcp.TH_RST:
            self.tcp_resets += 1
            self.tcp_reset_senders[sip] += 1
            if rev_key in self.tcp_syn_sent:
                self.tcp_syn_rst[rev_key] += 1

        # Check ZeroWindow
        if tcp.win == 0 and not (flags & (dpkt.tcp.TH_SYN | dpkt.tcp.TH_RST)):
            self.tcp_zero_windows += 1
            self.tcp_zero_window_sources[sip] += 1

        # TCP Sequence / Flow Analysis (Retransmissions, Dup ACKs, Out-of-Order)
        f_state = self.tcp_flows.get(flow_key)
        if not f_state:
            self.tcp_flows[flow_key] = {
                'highest_seq': tcp.seq + payload_len,
                'last_seq': tcp.seq,
                'last_len': payload_len,
                'last_ack': tcp.ack,
                'last_win': tcp.win,
                'dup_ack_count': 0
            }
        else:
            highest_seq = f_state['highest_seq']
            cur_seq = tcp.seq
            
            # Retransmission Check
            if payload_len > 0:
                if ((highest_seq - cur_seq) & 0xFFFFFFFF) < 0x80000000:
                    if cur_seq < highest_seq:
                        if cur_seq + payload_len <= highest_seq:
                            rev_state = self.tcp_flows.get(rev_key)
                            if rev_state and rev_state.get('dup_ack_count', 0) >= 3:
                                self.tcp_fast_retransmissions += 1
                            else:
                                self.tcp_retransmissions += 1
                        else:
                            self.tcp_out_of_order += 1
                
                new_end = cur_seq + payload_len
                if ((new_end - highest_seq) & 0xFFFFFFFF) < 0x80000000:
                    f_state['highest_seq'] = new_end
            
            # Duplicate ACK Check
            if (flags & dpkt.tcp.TH_ACK) and payload_len == 0 and not (flags & (dpkt.tcp.TH_SYN | dpkt.tcp.TH_FIN | dpkt.tcp.TH_RST)):
                if tcp.ack == f_state['last_ack'] and tcp.win == f_state['last_win']:
                    rev_state = self.tcp_flows.get(rev_key)
                    if rev_state and ((rev_state['highest_seq'] - tcp.ack) & 0xFFFFFFFF) < 0x80000000 and rev_state['highest_seq'] > tcp.ack:
                        f_state['dup_ack_count'] += 1
                        self.tcp_duplicate_acks += 1
                else:
                    f_state['dup_ack_count'] = 0

            # Window Full Check
            rev_state = self.tcp_flows.get(rev_key)
            if rev_state and payload_len > 0:
                receiver_win = rev_state.get('last_win', 65535)
                if receiver_win > 0 and (cur_seq + payload_len - f_state['last_ack']) >= receiver_win:
                    self.tcp_window_full += 1

            f_state['last_seq'] = cur_seq
            f_state['last_len'] = payload_len
            f_state['last_ack'] = tcp.ack
            f_state['last_win'] = tcp.win

    def _handle_udp(self, ts: float, sip: str, dip: str, udp: dpkt.udp.UDP, pkt_len: int):
        sport = udp.sport
        dport = udp.dport
        
        # mDNS
        if sport == 5353 or dport == 5353:
            self.l2_protocols['mDNS'] += 1
            return
        
        # LLMNR
        if sport == 5355 or dport == 5355:
            self.l2_protocols['LLMNR'] += 1
            return

        # NetBIOS
        if sport in (137, 138) or dport in (137, 138):
            self.l2_protocols['NetBIOS'] += 1
            return

        # SSDP (UPnP)
        if sport == 1900 or dport == 1900:
            self.l2_protocols['SSDP'] += 1
            return

        # DNS (Port 53)
        if sport == 53 or dport == 53:
            self._handle_dns(ts, sip, sport, dip, dport, udp.data)
            return

        # DHCP / BOOTP (Port 67 / 68)
        if (sport in (67, 68)) and (dport in (67, 68)):
            self.l2_protocols['DHCP'] += 1
            self._handle_dhcp(ts, sip, dip, udp.data)
            return

    def _handle_dns(self, ts: float, sip: str, sport: int, dip: str, dport: int, data: bytes):
        try:
            dns = dpkt.dns.DNS(data)
        except Exception:
            return

        # DNS Query
        if dns.qr == 0:
            self.dns_client_volume[sip] += 1
            if not is_rfc1918(dip):
                self.dns_external_resolvers[dip] += 1
                
            qname = dns.qd[0].name if dns.qd else "unknown"
            self.dns_top_queries[qname] += 1
            
            query_key = (sip, sport, dip, dns.id)
            self.dns_queries[query_key] = (ts, qname)

        # DNS Response
        elif dns.qr == 1:
            self.dns_rcodes[dns.rcode] += 1
            
            # Match Query Latency
            query_key = (dip, dport, sip, dns.id)
            if query_key in self.dns_queries:
                q_ts, qname = self.dns_queries.pop(query_key)
                latency_ms = (ts - q_ts) * 1000.0
                if 0 <= latency_ms <= 10000:
                    self.dns_latencies.append(latency_ms)
                    
            if dns.rcode == 3: # NXDOMAIN
                qname = dns.qd[0].name if dns.qd else "unknown"
                self.dns_nxdomain_queries[qname] += 1

    def _handle_dhcp(self, ts: float, sip: str, dip: str, data: bytes):
        try:
            dhcp = dpkt.dhcp.DHCP(data)
        except Exception:
            return

        xid = dhcp.xid
        chaddr = format_mac(dhcp.chaddr)
        msg_type = None
        server_id = sip
        
        for opt, opt_val in dhcp.opts:
            if opt == dpkt.dhcp.DHCP_OPT_MSGTYPE and len(opt_val) >= 1:
                msg_type = opt_val[0]
            elif opt == dpkt.dhcp.DHCP_OPT_SERVER_ID and len(opt_val) == 4:
                server_id = socket.inet_ntoa(opt_val)

        type_names = {
            1: 'DISCOVER', 2: 'OFFER', 3: 'REQUEST', 4: 'DECLINE',
            5: 'ACK', 6: 'NAK', 7: 'RELEASE', 8: 'INFORM'
        }
        type_str = type_names.get(msg_type, f"TYPE_{msg_type}")
        self.dhcp_msg_types[type_str] += 1
        
        tx = self.dhcp_transactions[xid]
        if 'mac' not in tx:
            tx['mac'] = chaddr
        if 'servers' not in tx:
            tx['servers'] = set()
            
        if msg_type == 1: # DISCOVER
            tx['discover_ts'] = ts
        elif msg_type == 2: # OFFER
            tx['offer_ts'] = ts
            tx['servers'].add(server_id)
            if len(tx['servers']) > 1:
                self.dhcp_rogue_candidates.append({
                    "xid": hex(xid),
                    "client_mac": chaddr,
                    "servers_detected": list(tx['servers']),
                    "timestamp": ts
                })
        elif msg_type == 3: # REQUEST
            tx['request_ts'] = ts
        elif msg_type == 5: # ACK
            tx['ack_ts'] = ts
        elif msg_type == 6: # NAK
            self.dhcp_nak_loops[chaddr] += 1

    def generate_report(self) -> Dict[str, Any]:
        """Synthesizes all raw counters into structured diagnostic metrics."""
        duration_sec = max(0.001, self.end_timestamp - self.start_timestamp) if self.end_timestamp > self.start_timestamp else 1.0
        non_unicast = self.broadcast_count + self.multicast_count
        non_unicast_pct = (non_unicast / self.total_packets * 100.0) if self.total_packets > 0 else 0.0

        # ARP Unanswered Targets
        unanswered_arp = []
        for target, count in sorted(self.arp_requests_seen.items(), key=lambda x: x[1], reverse=True)[:15]:
            replied = any(target == r[0] for r in self.arp_replies_seen)
            if not replied:
                unanswered_arp.append({"target_ip": target, "unanswered_requests": count})

        # Top ARP Requesters
        top_arp_requesters = [
            {"source_ip": k[0], "source_mac": k[1], "requests": v}
            for k, v in self.arp_requests_by_source.most_common(10)
        ]

        # ARP Rate Spikes
        max_arp_sec = max(self.arp_sec_buckets.values()) if self.arp_sec_buckets else 0
        peak_arp_sec_time = [k for k, v in self.arp_sec_buckets.items() if v == max_arp_sec]
        
        # DNS Latency Metrics
        dns_p50 = 0.0
        dns_p95 = 0.0
        dns_avg = 0.0
        if self.dns_latencies:
            sorted_lat = sorted(self.dns_latencies)
            dns_avg = round(sum(sorted_lat) / len(sorted_lat), 2)
            dns_p50 = round(sorted_lat[int(len(sorted_lat) * 0.50)], 2)
            dns_p95 = round(sorted_lat[int(len(sorted_lat) * 0.95)], 2)

        total_dns_responses = sum(self.dns_rcodes.values())
        dns_error_count = sum(v for k, v in self.dns_rcodes.items() if k != 0)
        dns_failure_rate_pct = round((dns_error_count / total_dns_responses * 100.0), 2) if total_dns_responses > 0 else 0.0

        # DHCP Transaction Timings
        dhcp_dora_timings = []
        for xid, tx in list(self.dhcp_transactions.items())[:20]:
            if 'discover_ts' in tx and 'ack_ts' in tx:
                total_duration = round((tx['ack_ts'] - tx['discover_ts']) * 1000.0, 2)
                dhcp_dora_timings.append({
                    "xid": hex(xid),
                    "client_mac": tx.get('mac'),
                    "dora_latency_ms": total_duration,
                    "servers": list(tx.get('servers', []))
                })

        # Port Sweep Detections
        scanners_detected = []
        for sip, targets in self.syn_sweep_tracker.items():
            if len(targets) >= 15:
                scanners_detected.append({
                    "scanner_ip": sip,
                    "probed_endpoints_count": len(targets),
                    "sample_probed": [f"{t[0]}:{t[1]}" for t in list(targets)[:5]]
                })

        unreplied_syns = len(self.tcp_syn_sent) - len(self.tcp_syn_ack_rcvd)

        # Cross-VLAN / Subnet Flows
        top_routed_flows = [
            {"source_subnet": k[0], "destination_subnet": k[1], "bytes": v, "formatted_mb": round(v / (1024*1024), 2)}
            for k, v in self.cross_subnet_flows.most_common(10)
        ]

        # Top Talkers
        top_talkers = [
            {"ip": k, "bytes": v, "formatted_mb": round(v / (1024*1024), 2), "packets": self.ip_packet_count[k]}
            for k, v in self.ip_bandwidth.most_common(10)
        ]

        report = {
            "metadata": {
                "files_analyzed": self.processed_files,
                "total_packets": self.total_packets,
                "total_volume_mb": round(self.total_bytes / (1024*1024), 2),
                "duration_seconds": round(duration_sec, 2),
                "capture_packet_rate_per_sec": round(self.total_packets / duration_sec, 2)
            },
            "layer2_hygiene": {
                "unicast_frames": self.unicast_count,
                "broadcast_frames": self.broadcast_count,
                "multicast_frames": self.multicast_count,
                "non_unicast_percentage": round(non_unicast_pct, 2),
                "l2_protocol_breakdown": dict(self.l2_protocols),
                "top_arp_requesters": top_arp_requesters,
                "unanswered_arp_targets": unanswered_arp,
                "arp_spikes": {
                    "peak_arp_rate_per_sec": max_arp_sec,
                    "peak_epoch_timestamp": peak_arp_sec_time[0] if peak_arp_sec_time else None
                },
                "stp_rstp_hygiene": {
                    "total_bpdus": self.stp_bpdu_count,
                    "topology_change_notifications_tcn": self.stp_tcn_count,
                    "participating_bridges": dict(self.stp_bridge_ids)
                }
            },
            "transport_link_health": {
                "tcp_retransmissions": self.tcp_retransmissions,
                "tcp_fast_retransmissions": self.tcp_fast_retransmissions,
                "tcp_duplicate_acks": self.tcp_duplicate_acks,
                "tcp_out_of_order": self.tcp_out_of_order,
                "retransmission_rate_pct": round((self.tcp_retransmissions / max(1, self.total_packets) * 100.0), 3),
                "tcp_zero_windows": self.tcp_zero_windows,
                "tcp_zero_window_senders": dict(self.tcp_zero_window_sources.most_common(5)),
                "tcp_window_full": self.tcp_window_full,
                "tcp_resets_rst": self.tcp_resets,
                "top_reset_senders": dict(self.tcp_reset_senders.most_common(5)),
                "failed_handshakes_unanswered_syn": max(0, unreplied_syns),
                "syn_rst_immediate_failures": sum(self.tcp_syn_rst.values()),
                "icmp_frag_needed_mtu_events": len(self.icmp_frag_needed),
                "icmp_frag_samples": self.icmp_frag_needed[:5],
                "tcp_syn_mss_distribution": dict(self.tcp_syn_mss_dist),
                "tcp_mss_clamped_senders_sub_1460": [
                    {"ip": k[0], "advertised_mss": k[1], "syn_count": v}
                    for k, v in self.tcp_mss_clamped_senders.most_common(5)
                ]
            },
            "core_services_performance": {
                "dns": {
                    "total_queries_captured": sum(self.dns_client_volume.values()),
                    "total_responses_captured": total_dns_responses,
                    "latency_avg_ms": dns_avg,
                    "latency_p50_ms": dns_p50,
                    "latency_p95_ms": dns_p95,
                    "failure_rate_pct": dns_failure_rate_pct,
                    "rcode_breakdown": {
                        "NOERROR": self.dns_rcodes[0],
                        "SERVFAIL": self.dns_rcodes[2],
                        "NXDOMAIN": self.dns_rcodes[3],
                        "REFUSED": self.dns_rcodes[5]
                    },
                    "top_queried_domains": [list(x) for x in self.dns_top_queries.most_common(10)],
                    "top_nxdomain_domains": [list(x) for x in self.dns_nxdomain_queries.most_common(5)],
                    "top_requesting_clients": [list(x) for x in self.dns_client_volume.most_common(5)],
                    "external_resolvers_contacted": [list(x) for x in self.dns_external_resolvers.most_common(5)]
                },
                "dhcp": {
                    "message_types": dict(self.dhcp_msg_types),
                    "duplicate_offers_rogue_candidates": self.dhcp_rogue_candidates,
                    "nak_loops_detected": dict(self.dhcp_nak_loops),
                    "dora_latencies_sample": dhcp_dora_timings
                }
            },
            "security_anomalies": {
                "cleartext_protocols": dict(self.cleartext_protocols),
                "cleartext_warnings": self.cleartext_samples[:5],
                "port_sweeps_scanners": scanners_detected,
                "icmp_redirects_detected": len(self.icmp_redirects),
                "icmp_redirect_samples": self.icmp_redirects[:5]
            },
            "conversation_matrix": {
                "top_internal_talkers": top_talkers,
                "vlan_distribution": dict(self.vlan_traffic),
                "inter_subnet_routed_flows": top_routed_flows
            }
        }
        return report


def render_markdown_report(data: Dict[str, Any]) -> str:
    """Formats the JSON report dictionary into an executive engineering Markdown document."""
    meta = data["metadata"]
    l2 = data["layer2_hygiene"]
    trans = data["transport_link_health"]
    core = data["core_services_performance"]
    sec = data["security_anomalies"]
    matrix = data["conversation_matrix"]

    md = []
    md.append("# Enterprise LAN Telemetry & PCAP Diagnostic Report")
    md.append(f"**Files Analyzed**: `{len(meta['files_analyzed'])} capture file(s)` | **Total Packets**: `{meta['total_packets']:,}` | **Volume**: `{meta['total_volume_mb']} MB` | **Span**: `{meta['duration_seconds']}s` (`{meta['capture_packet_rate_per_sec']} pkt/s`)")
    md.append("\n---\n")

    # Section 1: L2 Hygiene
    md.append("## 1. Layer 2 Broadcast/Multicast Hygiene")
    md.append(f"- **Unicast Frames**: `{l2['unicast_frames']:,}`")
    md.append(f"- **Broadcast Frames**: `{l2['broadcast_frames']:,}`")
    md.append(f"- **Multicast Frames**: `{l2['multicast_frames']:,}`")
    md.append(f"- **Non-Unicast Traffic Ratio**: **`{l2['non_unicast_percentage']}%`** " + ("⚠️ *(High LAN chatter)*" if l2['non_unicast_percentage'] > 15 else "✅ *(Normal)*"))
    md.append("\n### Protocol Distribution:")
    for proto, cnt in sorted(l2["l2_protocol_breakdown"].items(), key=lambda x: x[1], reverse=True):
        md.append(f"  - **{proto}**: `{cnt:,}` frames")

    md.append(f"\n### Spanning Tree (STP/RSTP) Health:")
    md.append(f"- Total BPDUs: `{l2['stp_rstp_hygiene']['total_bpdus']:,}`")
    md.append(f"- **Topology Change Notifications (TCN)**: `{l2['stp_rstp_hygiene']['topology_change_notifications_tcn']}` " + ("🚨 *(Topology flapping)*" if l2['stp_rstp_hygiene']['topology_change_notifications_tcn'] > 5 else "✅ *(Stable)*"))
    if l2['stp_rstp_hygiene']['participating_bridges']:
        md.append(f"- Active Bridges: `{', '.join(l2['stp_rstp_hygiene']['participating_bridges'].keys())}`")

    md.append(f"\n### ARP Hygiene & Spikes:")
    md.append(f"- **Peak ARP Burst Rate**: `{l2['arp_spikes']['peak_arp_rate_per_sec']} req/sec`")
    if l2["unanswered_arp_targets"]:
        md.append("- **Top Unanswered ARP Targets** (Dead endpoints or port scans):")
        for item in l2["unanswered_arp_targets"][:5]:
            md.append(f"  - `{item['target_ip']}`: `{item['unanswered_requests']}` unanswered queries")
    md.append("\n---\n")

    # Section 2: Transport & Link Health
    md.append("## 2. Transport & Link Health")
    md.append(f"- **TCP Retransmissions**: `{trans['tcp_retransmissions']:,}` (`{trans['retransmission_rate_pct']}%` of total packets)")
    md.append(f"- **Fast Retransmissions**: `{trans['tcp_fast_retransmissions']:,}`")
    md.append(f"- **Duplicate ACKs**: `{trans['tcp_duplicate_acks']:,}`")
    md.append(f"- **Out-of-Order Packets**: `{trans['tcp_out_of_order']:,}`")
    md.append(f"- **TCP ZeroWindow Events (Buffer Exhaustion)**: `{trans['tcp_zero_windows']:,}` " + ("⚠️ *(Host buffer stall)*" if trans['tcp_zero_windows'] > 0 else "✅"))
    md.append(f"- **TCP Resets (RST)**: `{trans['tcp_resets_rst']:,}` | **Failed Handshakes (Unanswered SYN)**: `{trans['failed_handshakes_unanswered_syn']:,}`")
    md.append(f"- **ICMP Fragmentation Needed (MTU Exceeded)**: `{trans['icmp_frag_needed_mtu_events']}`")
    if trans["tcp_mss_clamped_senders_sub_1460"]:
        md.append("- **Clamped MSS Advertisements (< 1460 bytes)**:")
        for item in trans["tcp_mss_clamped_senders_sub_1460"]:
            md.append(f"  - `{item['ip']}`: MSS `{item['advertised_mss']}` ({item['syn_count']} SYNs)")
    md.append("\n---\n")

    # Section 3: Core Services
    md.append("## 3. Core Services Performance (DNS & DHCP)")
    dns = core["dns"]
    md.append(f"### DNS Diagnostics:")
    md.append(f"- **Captured Queries / Responses**: `{dns['total_queries_captured']:,}` / `{dns['total_responses_captured']:,}`")
    md.append(f"- **Query Latency**: Avg: `{dns['latency_avg_ms']} ms` | p50: `{dns['latency_p50_ms']} ms` | p95: `{dns['latency_p95_ms']} ms`")
    md.append(f"- **Failure Rate**: `{dns['failure_rate_pct']}%` (NXDOMAIN: `{dns['rcode_breakdown']['NXDOMAIN']}`, SERVFAIL: `{dns['rcode_breakdown']['SERVFAIL']}`)")
    if dns["external_resolvers_contacted"]:
        md.append(f"- **External Resolvers Contacted (Bypassing Internal DNS)**:")
        for res, cnt in dns["external_resolvers_contacted"]:
            md.append(f"  - `{res}`: `{cnt:,}` requests")

    dhcp = core["dhcp"]
    md.append(f"\n### DHCP Diagnostics:")
    md.append(f"- **Messages**: `{', '.join(f'{k}: {v}' for k, v in dhcp['message_types'].items())}`")
    if dhcp["duplicate_offers_rogue_candidates"]:
        md.append(f"- 🚨 **ROGUE DHCP CANDIDATES DETECTED**: `{len(dhcp['duplicate_offers_rogue_candidates'])}` instances!")
        for c in dhcp["duplicate_offers_rogue_candidates"][:3]:
            md.append(f"  - Client `{c['client_mac']}` received offers from multiple servers: `{c['servers_detected']}`")
    else:
        md.append("- ✅ **Rogue DHCP**: No dual-offer collisions detected.")
    md.append("\n---\n")

    # Section 4: Security
    md.append("## 4. Security & Protocol Anomalies")
    if sec["cleartext_protocols"]:
        md.append("- **Cleartext Insecure Protocols Detected**:")
        for proto, cnt in sec["cleartext_protocols"].items():
            md.append(f"  - ⚠️ `{proto}`: `{cnt:,}` packets")
    else:
        md.append("- ✅ No cleartext legacy protocols detected.")
    
    if sec["port_sweeps_scanners"]:
        md.append("- 🚨 **Internal Scan / Port Sweep Detections**:")
        for sc in sec["port_sweeps_scanners"]:
            md.append(f"  - Host `{sc['scanner_ip']}` probed `{sc['probed_endpoints_count']}` distinct ports/destinations")
    else:
        md.append("- ✅ No aggressive internal port sweeps detected.")

    if sec["icmp_redirects_detected"] > 0:
        md.append(f"- ⚠️ **ICMP Redirects Detected**: `{sec['icmp_redirects_detected']}` events (potential routing loop or MITM)")
    md.append("\n---\n")

    # Section 5: Matrix
    md.append("## 5. Conversation Matrix & Subnet Flows")
    md.append("### Top 10 Internal Talkers:")
    for t in matrix["top_internal_talkers"]:
        md.append(f"- **{t['ip']}**: `{t['formatted_mb']} MB` (`{t['packets']:,}` packets)")

    if matrix["inter_subnet_routed_flows"]:
        md.append("\n### Top Inter-Subnet / Routed Flows:")
        for f in matrix["inter_subnet_routed_flows"][:5]:
            md.append(f"- `{f['source_subnet']} -> {f['destination_subnet']}`: `{f['formatted_mb']} MB`")
    
    if matrix["vlan_distribution"]:
        md.append("\n### 802.1Q VLAN Tag Distribution:")
        for vid, cnt in sorted(matrix["vlan_distribution"].items(), key=lambda x: x[1], reverse=True):
            md.append(f"- **VLAN {vid}**: `{cnt:,}` packets")

    return "\n".join(md)


def run_docker_tshark_summary(capture_path: str):
    """Executes containerized tshark via Docker to get an expert summary."""
    norm_path = normalize_path(capture_path)
    abs_dir = os.path.dirname(os.path.abspath(norm_path))
    file_name = os.path.basename(norm_path)
    cmd = f'docker run --rm -v "{abs_dir}":/data -w /data wireshark/wireshark:latest tshark -r "/data/{file_name}" -q -z io,phs'
    print(f"[*] Invoking containerized tshark:\n{cmd}\n")
    os.system(cmd)


def main():
    parser = argparse.ArgumentParser(
        description="Enterprise LAN PCAP / PCAPNG Telemetry & Diagnostic Analyzer"
    )
    parser.add_argument("input", nargs="?", default="", help="PCAP/PCAPNG file, directory, or glob pattern")
    parser.add_argument("--json", dest="output_json", help="Path to write JSON telemetry report")
    parser.add_argument("--md", dest="output_md", help="Path to write Markdown diagnostic report")
    parser.add_argument("--max-packets", type=int, default=None, help="Limit total packets analyzed")
    parser.add_argument("--max-files", type=int, default=None, help="Limit number of capture files analyzed")
    parser.add_argument("--docker", action="store_true", help="Run containerized tshark alongside native parser")
    args = parser.parse_args()

    input_arg = args.input or os.environ.get("PCAP_INPUT", "")
    if not input_arg:
        default_dir = normalize_path("C:\\Users\\dtheurer\\Downloads\\Router pcap")
        if os.path.exists(default_dir):
            input_arg = default_dir
        else:
            parser.print_help()
            sys.exit(1)

    norm_input = normalize_path(input_arg)
    target_files = []
    
    if os.path.isdir(norm_input):
        for ext in ('*.pcapng', '*.pcap', '*.cap'):
            target_files.extend(glob.glob(os.path.join(norm_input, ext)))
    elif '*' in norm_input or '?' in norm_input:
        target_files.extend(glob.glob(norm_input))
    elif os.path.isfile(norm_input):
        target_files.append(norm_input)
    else:
        expanded = glob.glob(norm_input + "*")
        if expanded:
            target_files.extend(expanded)

    target_files.sort()
    if not target_files:
        print(f"[-] No capture files found matching: {input_arg}", file=sys.stderr)
        sys.exit(1)

    if args.max_files:
        target_files = target_files[:args.max_files]

    print(f"================================================================================")
    print(f"[*] LAN Diagnostic Engine Initialized")
    print(f"[*] Target Files: {len(target_files)} capture(s)")
    if args.max_packets:
        print(f"[*] Max Packet Limit: {args.max_packets:,}")
    print(f"================================================================================")

    if args.docker:
        run_docker_tshark_summary(target_files[0])

    analyzer = LANPcapAnalyzer(sample_limit=args.max_packets)
    t_start = time.time()
    
    for idx, fpath in enumerate(target_files, 1):
        file_size_mb = os.path.getsize(fpath) / (1024 * 1024)
        print(f"[{idx}/{len(target_files)}] Ingesting {os.path.basename(fpath)} ({file_size_mb:.2f} MB)...", end="", flush=True)
        t_file_start = time.time()
        analyzer.process_file(fpath)
        t_file_elapsed = max(0.001, time.time() - t_file_start)
        print(f" Done ({t_file_elapsed:.2f}s, {analyzer.total_packets:,} total pkts)")
        if args.max_packets and analyzer.total_packets >= args.max_packets:
            break

    t_total = time.time() - t_start
    print(f"\n[+] Analysis complete: {analyzer.total_packets:,} packets processed in {t_total:.2f}s ({analyzer.total_packets/max(0.001, t_total):.1f} pkt/s)\n")

    report_data = analyzer.generate_report()
    md_output = render_markdown_report(report_data)

    # Output Markdown to console or file
    if args.output_md:
        out_md_path = normalize_path(args.output_md)
        os.makedirs(os.path.dirname(os.path.abspath(out_md_path)), exist_ok=True)
        with open(out_md_path, 'w', encoding='utf-8') as f:
            f.write(md_output)
        print(f"[+] Markdown report saved to: {out_md_path}")
    else:
        print(md_output)

    # Output JSON if requested
    if args.output_json:
        out_json_path = normalize_path(args.output_json)
        os.makedirs(os.path.dirname(os.path.abspath(out_json_path)), exist_ok=True)
        with open(out_json_path, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2)
        print(f"[+] JSON telemetry saved to: {out_json_path}")


if __name__ == "__main__":
    main()
