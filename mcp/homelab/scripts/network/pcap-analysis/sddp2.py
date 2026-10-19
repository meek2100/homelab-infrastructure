import sys, glob, os, collections, socket, dpkt
D = sys.argv[1]
WATCH = {"192.168.10.108": "vivint", "192.168.1.215": "sw920", "192.168.1.231": "ap830", "192.168.10.200": "director"}
c = collections.Counter(); first = {}
files = sorted(glob.glob(os.path.join(D, "router_baseline_*.pcapng")))
for f in files:
    with open(f, "rb") as fh:
        for ts, buf in dpkt.pcapng.Reader(fh):
            try: eth = dpkt.ethernet.Ethernet(buf)
            except Exception: continue
            ip = eth.data
            if not isinstance(ip, dpkt.ip.IP) or not isinstance(ip.data, dpkt.udp.UDP): continue
            u = ip.data
            if 1902 not in (u.sport, u.dport): continue
            s, d = socket.inet_ntoa(ip.src), socket.inet_ntoa(ip.dst)
            kind = (u.data[:12].split(b" ")[0] or b"?").decode("latin1", "replace")
            for who in (s, d):
                if who in WATCH:
                    key = (WATCH[who], "from" if who == s else "to", kind, d if who == s else s)
                    c[key] += 1
print("files:", [os.path.basename(f) for f in files])
for k, n in sorted(c.items()):
    print(" ", k, n)
seen_src = {k[0] for k in c if k[1] == "from"}
print("SDDP senders seen among watched:", sorted(seen_src), " missing:", sorted(set(WATCH.values()) - seen_src))
