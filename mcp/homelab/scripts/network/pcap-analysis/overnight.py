import sys, glob, os, collections, socket, hashlib, datetime, struct, dpkt
from multiprocessing import Pool
D = sys.argv[1]; OUT = sys.argv[2]
ROUTER = bytes.fromhex("143fc391508c"); OWRT = bytes.fromhex("e89f8050582f")
STALE = {"192.168.1.186", "192.168.1.247", "192.168.1.137"}
WATCH = {"192.168.10.108": "vivint", "192.168.1.215": "sw920", "192.168.1.231": "ap830", "192.168.1.236": "ap236", "192.168.1.237": "ap237"}
def loc(ts): return datetime.datetime.fromtimestamp(ts, datetime.UTC) - datetime.timedelta(hours=7)
def ip(b): return socket.inet_ntoa(b)
def mac(b): return ":".join(f"{x:02x}" for x in b)

def work(f):
    r = dict(name=os.path.basename(f), n=0, bytes=0, first=None, last=None,
             flows=collections.Counter(), dup=collections.Counter(), bc=collections.Counter(),
             arp=collections.Counter(), arpt=collections.defaultdict(set), stale=collections.Counter(),
             sddp=collections.Counter(), vivmdns=collections.Counter(), bpdu=collections.Counter(),
             owrt=0, persec=collections.Counter())
    seen = {}
    with open(f, "rb") as fh:
        for ts, buf in dpkt.pcapng.Reader(fh):
            r["n"] += 1; r["bytes"] += len(buf); r["first"] = r["first"] or ts; r["last"] = ts
            r["persec"][int(ts)] += 1
            hour = loc(ts).strftime("%H")
            if buf[0:6] == b"\x01\x80\xc2\x00\x00\x00" and len(buf) >= 14 + 3 + 35:
                b = buf[17:]
                try:
                    ver, typ = b[2], b[3]
                    root = b[5:13].hex(); brid = b[17:25].hex()
                    fd = struct.unpack("!H", b[33:35])[0] / 256 if typ in (0, 2) else None
                    r["bpdu"][(mac(buf[6:12]), f"v{ver}t{typ}", root[:4] + "." + root[4:], brid[:4] + "." + brid[4:], fd)] += 1
                except Exception: pass
                continue
            try: eth = dpkt.ethernet.Ethernet(buf)
            except Exception: continue
            tags = getattr(eth, "vlan_tags", None) or []
            v = tags[0].id if tags else 1
            if eth.dst[0] & 1: r["bc"][v] += 1
            if eth.src == OWRT: r["owrt"] += 1
            h = hashlib.blake2b(buf[:512], digest_size=12).digest()
            if h in seen and ts - seen[h] < 0.2: r["dup"][v] += 1
            seen[h] = ts
            if len(seen) > 300000: seen.clear()
            p = eth.data
            if isinstance(p, dpkt.arp.ARP):
                if eth.src == ROUTER and p.op == 1:
                    r["arp"][(hour, v)] += 1; r["arpt"][(hour, v)].add(ip(p.tpa))
                r["flows"][(mac(eth.src), "ARP", "", 0, v)] += len(buf)
                continue
            if not isinstance(p, dpkt.ip.IP):
                r["flows"][(mac(eth.src), type(p).__name__, "", 0, v)] += len(buf); continue
            s, d = ip(p.src), ip(p.dst); l4 = p.data
            dp = getattr(l4, "dport", 0); sp = getattr(l4, "sport", 0)
            r["flows"][(s, d, type(l4).__name__, dp if dp < 49152 else sp, v)] += len(buf)
            if d in STALE: r["stale"][(hour, d, s, dp)] += 1
            if isinstance(l4, dpkt.udp.UDP):
                if 1902 in (sp, dp):
                    for who in (s, d):
                        if who in WATCH: r["sddp"][(WATCH[who], "from" if who == s else "to")] += 1
                if s == "192.168.10.108" and dp == 5353: r["vivmdns"][hour] += 1
    r["peak"] = max(r["persec"].items(), key=lambda x: x[1]) if r["persec"] else (0, 0)
    del r["persec"]
    r["flows"] = collections.Counter(dict(r["flows"].most_common(8)))
    return r

if __name__ == "__main__":
    files = sorted(glob.glob(os.path.join(D, "router_baseline_*.pcapng")))
    with Pool(4) as pool: res = pool.map(work, files, chunksize=2)
    o = open(OUT, "w")
    P = lambda *a: print(*a, file=o)
    P(f"files={len(res)} frames={sum(r['n'] for r in res)} span={loc(res[0]['first']):%m-%d %H:%M}..{loc(res[-1]['last']):%m-%d %H:%M} PDT")
    P("\n== per-file (start, dur s, frames/s, stored Mbit/s, peak f/s @, dups, top flow)")
    for r in res:
        dur = max(r["last"] - r["first"], 1); top = r["flows"].most_common(1)[0] if r["flows"] else (("",), 0)
        P(f"{r['name'][16:21]} {loc(r['first']):%H:%M:%S} {dur:6.0f} {r['n']/dur:7.0f} {r['bytes']*8/dur/1e6:6.1f} {r['peak'][1]:6d}@{loc(r['peak'][0]):%H:%M:%S} dup={sum(r['dup'].values()):5d}  {top[1]/1e6:5.1f}MB {top[0]}")
    def merge(key):
        c = collections.Counter()
        for r in res: c.update(r[key])
        return c
    P("\n== top flows overall (MB)")
    allf = merge("flows")
    for k, b in allf.most_common(20): P(f"  {b/1e6:8.1f}  {k}")
    P("\n== burst windows 05:30-05:52: top flows")
    bf = collections.Counter()
    for r in res:
        if "0533" <= r["name"][25:29] <= "0551": bf.update(r["flows"])
    for k, b in bf.most_common(12): P(f"  {b/1e6:8.1f}  {k}")
    P("\n== router ARP requests per hour (VLAN: count/distinct)")
    arp = merge("arp"); arpt = collections.defaultdict(set)
    for r in res:
        for k, sset in r["arpt"].items(): arpt[k] |= sset
    for h in sorted({k[0] for k in arp}):
        P("  ", h, {v: f"{arp[(h, v)]}/{len(arpt[(h, v)])}" for v in sorted({k[1] for k in arp}) if arp[(h, v)]})
    P("\n== stale-address traffic per hour (hour, dst, src, dport): count")
    for k, n in sorted(merge("stale").items()): P("  ", k, n)
    P("\n== SDDP (device, direction): count"); P("  ", dict(merge("sddp")))
    P("\n== Vivint mDNS (UDP 5353 from .10.108) per hour:", dict(sorted(merge("vivmdns").items())))
    P("\n== OpenWrt-sourced frames on SPAN:", sum(r["owrt"] for r in res))
    P("\n== BPDUs seen on SPAN (src, ver/type, root, bridge, fwd delay s): count")
    for k, n in merge("bpdu").most_common(10): P("  ", k, n)
    P("\n== duplicate frames (<200ms) by VLAN:", dict(sorted(merge("dup").items())))
    o.close()
