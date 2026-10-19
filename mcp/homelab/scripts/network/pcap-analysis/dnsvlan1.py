import sys, glob, os, collections, socket, dpkt
from multiprocessing import Pool
D, OUT = sys.argv[1], sys.argv[2]
ADGUARD = {"192.168.40.185", "192.168.40.186"}
DOH = {"8.8.8.8", "8.8.4.4", "1.1.1.1", "1.0.0.1", "9.9.9.9", "149.112.112.112", "208.67.222.222", "208.67.220.220",
       "94.140.14.14", "94.140.15.15", "76.76.2.0", "76.76.10.0", "185.228.168.9", "45.90.28.0", "45.90.30.0"}
def ip(b): return socket.inet_ntoa(b)
def mac(b): return ":".join(f"{x:02x}" for x in b)
def work(f):
    dns = collections.Counter(); doh = collections.Counter(); v1 = {}
    with open(f, "rb") as fh:
        for ts, buf in dpkt.pcapng.Reader(fh):
            try: eth = dpkt.ethernet.Ethernet(buf)
            except Exception: continue
            tags = getattr(eth, "vlan_tags", None) or []
            v = tags[0].id if tags else 1
            p = eth.data
            if v == 1 and isinstance(p, dpkt.arp.ARP) and p.op == 2:
                v1[ip(p.spa)] = mac(p.sha)
            if not isinstance(p, dpkt.ip.IP): continue
            s, d = ip(p.src), ip(p.dst); l4 = p.data
            dp = getattr(l4, "dport", 0)
            if v == 1 and s.startswith("192.168.1."): v1.setdefault(s, mac(eth.src))
            if dp in (53, 853) and d not in ADGUARD and not d.endswith(".1") and s.startswith(("192.168.", "10.")):
                dns[(s, d, dp, type(l4).__name__)] += 1
            if d in DOH and dp == 443 and s.startswith(("192.168.", "10.")):
                doh[(s, d)] += 1
    return dns, doh, v1
if __name__ == "__main__":
    files = sorted(glob.glob(os.path.join(D, "router_baseline_*.pcapng")))
    with Pool(4) as pool: res = pool.map(work, files, chunksize=2)
    dns = collections.Counter(); doh = collections.Counter(); v1 = {}
    for a, b, c in res: dns.update(a); doh.update(b); v1.update(c)
    o = open(OUT, "w")
    print("== plain DNS / DoT (53, 853) NOT to AdGuard or a gateway (src, dst, port, proto): count", file=o)
    for k, n in dns.most_common(40): print("  ", n, k, file=o)
    print("\n== HTTPS to well-known public DoH resolvers (src, dst): count", file=o)
    for k, n in doh.most_common(30): print("  ", n, k, file=o)
    print("\n== hosts active on VLAN 1 (ip, mac)", file=o)
    for k in sorted(v1, key=lambda x: int(x.split(".")[-1]) if x.count(".") == 3 and x.split(".")[-1].isdigit() else 0):
        print("  ", k, v1[k], file=o)
    o.close()
