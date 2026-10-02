import sys, glob, os, collections, socket, datetime, dpkt
D = sys.argv[1]
ROUTER = bytes.fromhex("143fc391508c")
def loc(ts): return (datetime.datetime.fromtimestamp(ts, datetime.UTC) - datetime.timedelta(hours=7)).strftime("%H:%M")
req = collections.Counter(); tgt = collections.defaultdict(set); per_min = collections.Counter()
for f in sorted(glob.glob(os.path.join(D, "router_baseline_*.pcapng"))):
    with open(f, "rb") as fh:
        for ts, buf in dpkt.pcapng.Reader(fh):
            try: eth = dpkt.ethernet.Ethernet(buf)
            except Exception: continue
            if eth.src != ROUTER or not isinstance(eth.data, dpkt.arp.ARP) or eth.data.op != 1: continue
            tags = getattr(eth, "vlan_tags", None) or []
            v = tags[0].id if tags else 1
            req[v] += 1; tgt[v].add(socket.inet_ntoa(eth.data.tpa)); per_min[(loc(ts), v)] += 1
print("router ARP requests by VLAN: total / distinct targets")
for v in sorted(req): print(f"  VLAN {v}: {req[v]} / {len(tgt[v])}")
print("per minute (VLAN: count):")
for m in sorted({k[0] for k in per_min}):
    print("  ", m, {v: per_min[(m, v)] for v in sorted(req) if per_min[(m, v)]})
