import sys, glob, os, collections, hashlib, datetime, dpkt
D = sys.argv[1]
OWRT = bytes.fromhex("e89f8050582f")
ROUTER = bytes.fromhex("143fc391508c")
def mac(b): return ":".join(f"{x:02x}" for x in b)
def loc(ts): return (datetime.datetime.utcfromtimestamp(ts) - datetime.timedelta(hours=7)).strftime("%H:%M:%S")
seen = {}                       # hash -> last ts
dup_by = collections.Counter()  # (vlan, src) -> dup count
dup_sec = collections.Counter() # second -> dups
bc_sec = collections.Counter()  # (second, vlan) broadcasts/multicast
owrt_vlan = collections.Counter()
owrt_dups = collections.Counter()
total = 0; first = last = None
files = sorted(glob.glob(os.path.join(D, "router_baseline_*.pcapng")))
for f in files:
    with open(f, "rb") as fh:
        for ts, buf in dpkt.pcapng.Reader(fh):
            total += 1; first = first or ts; last = ts
            try: eth = dpkt.ethernet.Ethernet(buf)
            except Exception: continue
            tags = getattr(eth, "vlan_tags", None) or []
            vlan = tags[0].id if tags else 0
            sec = int(ts)
            if eth.dst[0] & 1: bc_sec[(sec, vlan)] += 1
            if eth.src == OWRT: owrt_vlan[vlan] += 1
            h = hashlib.blake2b(buf[:512], digest_size=12).digest()
            p = seen.get(h)
            if p is not None and ts - p < 0.2:
                dup_by[(vlan, mac(eth.src))] += 1; dup_sec[sec] += 1
                if eth.src == OWRT: owrt_dups[vlan] += 1
            seen[h] = ts
            if len(seen) > 400000: seen.clear()
print(f"files={len(files)} frames={total} span={loc(first)}..{loc(last)} PDT")
print("OpenWrt-sourced frames by VLAN (0=native/untagged):", dict(owrt_vlan))
print("OpenWrt duplicate frames (<200ms) by VLAN:", dict(owrt_dups))
print("top duplicate sources (vlan, src):")
for k, n in dup_by.most_common(12): print("  ", k, n)
print("seconds with most duplicates:")
for s, n in sorted(dup_sec.items(), key=lambda x: -x[1])[:10]: print("  ", loc(s), n)
peak = collections.defaultdict(int)
for (s, v), n in bc_sec.items(): peak[v] = max(peak[v], n)
print("peak broadcast+multicast frames/s per VLAN:", dict(sorted(peak.items())))
