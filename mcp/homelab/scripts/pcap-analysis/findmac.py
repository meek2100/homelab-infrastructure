import sys, glob, os, collections, socket, dpkt
D, M = sys.argv[1], bytes.fromhex(sys.argv[2].replace(":", ""))
ips = collections.Counter(); vl = collections.Counter(); names = set(); n = 0
for f in sorted(glob.glob(os.path.join(D, "router_baseline_*.pcapng"))):
    with open(f, "rb") as fh:
        for ts, buf in dpkt.pcapng.Reader(fh):
            try: eth = dpkt.ethernet.Ethernet(buf)
            except Exception: continue
            if eth.src != M: continue
            n += 1
            tags = getattr(eth, "vlan_tags", None) or []
            vl[tags[0].id if tags else 1] += 1
            p = eth.data
            if isinstance(p, dpkt.ip.IP):
                ips[socket.inet_ntoa(p.src)] += 1
                u = p.data
                if isinstance(u, dpkt.udp.UDP) and u.dport in (67, 1902, 5353):
                    for key in (b"Host", b"hostname", b"Name:", b"From:", b"Type:"):
                        i = u.data.find(key)
                        if i >= 0: names.add(u.data[i:i+60].split(b"\r\n")[0].decode("latin1", "replace"))
            elif isinstance(p, dpkt.arp.ARP):
                ips["arp:" + socket.inet_ntoa(p.spa)] += 1
print("frames:", n, "vlans:", dict(vl)); print("ips:", ips.most_common(5)); print("hints:", sorted(names)[:10])
