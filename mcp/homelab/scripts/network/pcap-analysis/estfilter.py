import sys, glob, os, ipaddress, dpkt
D = sys.argv[1]
L4S = [ipaddress.ip_network(n) for n in ("192.168.0.0/16", "10.0.0.0/8", "172.16.0.0/12", "100.64.0.0/10", "169.254.0.0/16")]
L4D = L4S + [ipaddress.ip_network("224.0.0.0/4"), ipaddress.ip_network("255.255.255.255/32")]
L6S = [ipaddress.ip_network(n) for n in ("fc00::/7", "fe80::/10")]
L6D = L6S + [ipaddress.ip_network("ff00::/8")]
inn = lambda a, nets: any(a in n for n in nets)
tot = drop = 0; tf = df = 0
for f in sorted(glob.glob(os.path.join(D, "router_baseline_*.pcapng"))):
    if not any(t in f for t in sys.argv[2:]): continue
    with open(f, "rb") as fh:
        for ts, buf in dpkt.pcapng.Reader(fh):
            tot += len(buf); tf += 1
            try: eth = dpkt.ethernet.Ethernet(buf)
            except Exception: continue
            p = eth.data; vl = 4 if getattr(eth, "vlan_tags", None) else 0
            if isinstance(p, dpkt.ip.IP):
                wire = p.len + 14 + vl
                s, d = ipaddress.ip_address(p.src), ipaddress.ip_address(p.dst)
                bulk = wire > 1200 and not (inn(s, L4S) and inn(d, L4D))
            elif isinstance(p, dpkt.ip6.IP6):
                wire = p.plen + 40 + 14 + vl
                s, d = ipaddress.ip_address(p.src), ipaddress.ip_address(p.dst)
                bulk = wire > 1200 and not (inn(s, L6S) and inn(d, L6D))
            else: bulk = False
            if bulk: drop += len(buf); df += 1
print(f"sample stored bytes {tot/1e6:.0f} MB, would drop {drop/1e6:.0f} MB = {100*drop/max(tot,1):.0f}% of bytes ({100*df/max(tf,1):.0f}% of frames)")
