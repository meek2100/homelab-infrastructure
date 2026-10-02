"""Check DHCP options 119 (domain search) / 42 (NTP) / 15 / 6 handed out per VLAN, and where NTP goes.
Usage: python3 dhcpntp.py <capture dir>"""
import sys, glob, os, collections, socket, dpkt
D = sys.argv[1]
def ip(b): return socket.inet_ntoa(b)
def dec119(v):
    out, cur, i = [], [], 0
    while i < len(v):
        n = v[i]; i += 1
        if n == 0: out.append(".".join(cur)); cur = []; continue
        if n & 0xC0 == 0xC0: cur.append("<ptr>"); i += 1; out.append(".".join(cur)); cur = []; continue
        cur.append(v[i:i + n].decode("latin1", "replace")); i += n
    return out
offers = collections.defaultdict(collections.Counter); ntp = collections.Counter(); ntp_reply = collections.Counter()
for f in sorted(glob.glob(os.path.join(D, "router_baseline_*.pcapng"))):
    with open(f, "rb") as fh:
        for ts, buf in dpkt.pcapng.Reader(fh):
            try: eth = dpkt.ethernet.Ethernet(buf)
            except Exception: continue
            tags = getattr(eth, "vlan_tags", None) or []
            v = tags[0].id if tags else 1
            p = eth.data
            if not isinstance(p, dpkt.ip.IP) or not isinstance(p.data, dpkt.udp.UDP): continue
            u = p.data
            if u.sport == 67 and u.dport == 68:
                try: dh = dpkt.dhcp.DHCP(u.data)
                except Exception: offers[v]["<truncated/unparsable DHCP>"] += 1; continue
                o = dict(dh.opts)
                mt = o.get(53, b"\x00")[0]
                if mt not in (2, 5): continue
                desc = []
                if 15 in o: desc.append("15=" + o[15].decode("latin1", "replace").strip("\x00"))
                if 6 in o: desc.append("6=" + ",".join(ip(o[6][i:i + 4]) for i in range(0, len(o[6]), 4)))
                desc.append("119=" + ("|".join(dec119(o[119])) if 119 in o else "absent"))
                desc.append("42=" + (",".join(ip(o[42][i:i + 4]) for i in range(0, len(o[42]), 4)) if 42 in o else "absent"))
                offers[v][" ".join(desc)] += 1
            elif u.dport == 123:
                ntp[(v, ip(p.src), ip(p.dst))] += 1
            elif u.sport == 123 and ip(p.src).endswith(".1"):
                ntp_reply[(v, ip(p.src), ip(p.dst))] += 1
print("== DHCP OFFER/ACK options by VLAN")
for v in sorted(offers):
    for k, n in offers[v].most_common(4): print(f"  VLAN {v}: {n:4}x  {k}")
print("\n== NTP requests (vlan, src, dst) — VLAN 30 should go to 192.168.30.1")
for k, n in sorted(ntp.items(), key=lambda x: (x[0][0], -x[1]))[:40]: print("  ", n, k)
print("\n== NTP replies from a gateway (.1):", sum(ntp_reply.values()), dict(list(ntp_reply.items())[:10]))
