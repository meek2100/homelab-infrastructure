"""Storm-control A/B test on router ARP answers, and window/BDP for the largest downloads.

Usage: python3 stormcheck.py <dir>
For every router ARP request to a VLAN 1 host in ALIVE1, checks for a reply within 1 s and buckets the result by how many
broadcasts the router sent in that second (<=150, 150-200, >200 pps), to test the 200 pps storm control on 920 1/0/1.
FLOWS lists (LAN host, server) pairs for the per-second throughput / window / zero-window breakdown. Edit both sets for the
capture being reviewed (pick FLOWS from targeted_report.py "ACK-INFERRED VOLUME").
"""
import sys, os, glob, struct, pickle, collections
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcapng_fast
from deep import ip4, mac, pdt, ROUTER, BCAST

ALIVE1 = {"192.168.1.226", "192.168.1.231", "192.168.1.236", "192.168.1.237", "192.168.1.240", "192.168.1.244", "192.168.1.245", "192.168.1.250", "192.168.1.215", "192.168.1.220", "192.168.1.150"}
FLOWS = {("192.168.10.130", "199.232.209.133"), ("192.168.10.201", "108.138.94.55"), ("192.168.20.82", "151.101.65.190")}

def work(path):
    bc = collections.Counter(); reqs = []; reps = collections.defaultdict(list)
    fl = collections.defaultdict(lambda: dict(sec=collections.Counter(), win=collections.Counter(), ws=None, last=None, zw=0, rtt=None, syn=None))
    for fr, ts, ol, d in pcapng_fast.read(path):
        if len(d) < 18: continue
        src, dst = d[6:12], d[0:6]
        et = struct.unpack_from("!H", d, 12)[0]; o = 14; v = 1
        if et == 0x8100: v = struct.unpack_from("!H", d, 14)[0] & 0xfff; et = struct.unpack_from("!H", d, 16)[0]; o = 18
        sec = int(ts)
        if src == ROUTER and dst == BCAST: bc[sec] += 1
        if et == 0x0806 and v == 1 and len(d) >= o + 28:
            op = struct.unpack_from("!H", d, o + 6)[0]; spa = ip4(d[o + 14:o + 18]); tpa = ip4(d[o + 24:o + 28])
            if op == 1 and src == ROUTER and tpa in ALIVE1: reqs.append((ts, tpa))
            if op == 2 and dst == ROUTER and spa in ALIVE1: reps[spa].append(ts)
            continue
        if et != 0x0800 or len(d) < o + 40 or d[o + 9] != 6: continue
        ihl = (d[o] & 0xf) * 4; l4 = o + ihl
        s = ip4(d[o + 12:o + 16]); t = ip4(d[o + 16:o + 20])
        if (s, t) not in FLOWS: continue
        sp, dp, seq, ack, offf, win = struct.unpack_from("!HHIIHH", d, l4)
        fls = offf & 0x1ff; thl = (offf >> 12) * 4
        f = fl[(s, t)]
        if fls & 2:
            q = l4 + 20
            while q < min(l4 + thl, len(d)):
                k = d[q]
                if k == 0: break
                if k == 1: q += 1; continue
                if k == 3: f["ws"] = d[q + 2]
                q += max(d[q + 1], 2)
            f["last"] = None; continue
        if fls & 16:
            if f["last"] is not None:
                dl = (ack - f["last"]) & 0xffffffff
                if 0 < dl < 16_000_000: f["sec"][sec] += dl
            f["last"] = ack
            f["win"][win] += 1
            if win == 0: f["zw"] += 1
    return dict(bc=bc, reqs=reqs, reps=dict(reps), fl={k: dict(v) for k, v in fl.items()})

if __name__ == "__main__":
    files = sorted(glob.glob(os.path.join(sys.argv[1], "*.pcapng")))
    with Pool(4) as pool:
        parts = pool.map(work, files, chunksize=1)
    bc = collections.Counter(); reqs = []; reps = collections.defaultdict(list)
    for p in parts:
        bc.update(p["bc"]); reqs += p["reqs"]
        for k, l in p["reps"].items(): reps[k] += l
    for k in reps: reps[k].sort()
    import bisect
    stat = collections.defaultdict(lambda: [0, 0])
    for ts, tpa in reqs:
        b = bc[int(ts)]; bucket = ">200pps" if b > 200 else ("150-200" if b > 150 else "<=150")
        l = reps.get(tpa, []); i = bisect.bisect_left(l, ts)
        ok = i < len(l) and l[i] - ts < 1.0
        stat[bucket][0] += 1; stat[bucket][1] += ok
    print("Router ARP -> known-alive VLAN1 hosts, answered within 1s, by router-broadcast pps of that second:")
    for k, (n, a) in sorted(stat.items()): print(f"  {k}: {a}/{n} = {a/max(n,1)*100:.2f}%")
    for key in FLOWS:
        sec = collections.Counter(); win = collections.Counter(); ws = None; zw = 0
        for p in parts:
            f = p["fl"].get(key)
            if not f: continue
            sec.update(f["sec"]); win.update(f["win"]); zw += f["zw"]; ws = f["ws"] if f["ws"] is not None else ws
        if not sec: print(key, "no data"); continue
        tot = sum(sec.values()); s0, s1 = min(sec), max(sec)
        top = sec.most_common(1)[0]
        w = sorted(win.elements()) if sum(win.values()) < 2_000_000 else []
        print(f"{key}: {tot/1e6:.1f} MB {pdt(s0)}-{pdt(s1)} active-secs {len(sec)} avg-active {tot*8/len(sec)/1e6:.2f} Mbps peak {top[1]*8/1e6:.1f} Mbps @ {pdt(top[0])}; "
              f"wscale {ws}; raw win p50 {w[len(w)//2] if w else '-'} min {w[0] if w else '-'} max {w[-1] if w else '-'}; zero-window {zw}")
