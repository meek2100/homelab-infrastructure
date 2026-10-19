"""Behaviour report for deep.py output: ICMP error detail, UDP flows on chosen ports, beaconing, scans, SNMP fingerprints.

Usage: python3 deep_behavior.py <deep.pkl>
Beaconing: a key is periodic when >= 80% of its intervals fall within +/-20% of the median (>= 12 events over >= 30 min).
SNMP communities are compared by SHA-256 prefix only; the values are never printed.
"""
import sys, os, pickle, collections, statistics, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from deep import pdt, is_local
C = collections.Counter
parts = pickle.load(open(sys.argv[1], "rb"))
def H(t): print("\n==== " + t)
def mergeC(k):
    c = C()
    for p in parts: c.update(p[k])
    return c
def mergeL(k):
    d = collections.defaultdict(list)
    for p in parts:
        for kk, v in p[k].items(): d[kk].extend(v)
    return d
ipname = {}
for p in parts:
    for k, v in p["ipname"].items(): ipname.setdefault(k, v)
def nm(ip): return ipname.get(ip, "")
t0 = min(p["first"] for p in parts); t1 = max(p["last"] for p in parts); dur = t1 - t0

H("ICMP 3/4, 11, 3/13, 5")
for k, n in mergeC("icmp_detail").most_common():
    if k[2] in (11, 5) or (k[2], k[3]) in ((3, 4), (3, 13), (3, 10), (3, 9), (3, 2)): print(" ", k, n)
H("UDP flows for selected ports")
uf = collections.defaultdict(lambda: [0, 0, 0.0, 0.0])
for p in parts:
    for k, l in p["udp_flows"].items():
        a = uf[k]; a[0] += l[0]; a[1] += l[1]; a[2] = l[2] if a[2] == 0 else min(a[2], l[2]); a[3] = max(a[3], l[3])
for port in (853, 7844, 9052, 9030, 15052, 15030, 514, 1188, 9999, 9478, 3478, 41641, 443, 6667, 58997, 1900, 6002, 161):
    rows = sorted(((k, a) for k, a in uf.items() if k[2] == port), key=lambda x: -x[1][0])[:6]
    print(f" port {port}:", [(k[0], k[1], f"v{k[3]}", a[0], f"{a[1]/1e6:.1f}MB", nm(k[1]) or nm(k[0])) for k, a in rows])
H("IP names of interest")
for ip in ("146.235.203.133", "35.212.229.212", "192.73.240.121", "192.73.240.161", "192.200.0.107", "192.200.0.116", "199.165.136.100", "172.64.151.205",
           "151.101.65.190", "199.232.209.133", "54.81.39.221", "3.229.47.208", "76.223.31.44", "172.236.61.9", "34.241.34.42", "65.49.20.70", "100.29.192.5",
           "46.162.192.181", "104.16.11.34", "2.22.234.142", "129.134.133.17", "108.138.94.55", "45.150.238.224", "216.45.50.27"):
    print("  ", ip, nm(ip))
H("BEACONING (TCP SYN starts, UDP session starts, ICMP echo, DNS per name)")
def beacon(events, label, minn=12, mindur=1800):
    out = []
    for k, ts in events.items():
        ts = sorted(set(round(x, 2) for x in ts))
        if len(ts) < minn or ts[-1] - ts[0] < mindur: continue
        iv = [b - a for a, b in zip(ts, ts[1:]) if b - a > 0.5]
        if len(iv) < minn - 1: continue
        med = statistics.median(iv); mean = statistics.mean(iv); sd = statistics.pstdev(iv)
        within = sum(1 for x in iv if abs(x - med) <= 0.2 * med) / len(iv)
        out.append((within, round(med, 1), round(sd / mean, 3), len(ts), k))
    out.sort(key=lambda x: (-x[0], -x[3]))
    print(f" {label}: {len(out)} candidate keys; periodic (>=80% of intervals within ±20% of median):")
    for w, med, cv, n, k in out:
        if w >= 0.8:
            ext = [x for x in k if isinstance(x, str) and not is_local(x)] if isinstance(k, tuple) else []
            print(f"   {k} n={n} median={med}s cv={cv} within={w:.2f} {'EXT ' + nm(ext[0]) if ext else ''}")
    return out
b1 = beacon(mergeL("syn_ts"), "TCP")
b2 = beacon(mergeL("udp_ts"), "UDP", minn=8)
b3 = beacon(mergeL("echo_ts"), "ICMP")
dq = mergeL("dns_qts")
H("DNS per-name periodicity (top 25 by volume)")
rows = []
for (cl, q), ts in dq.items():
    ts = sorted(ts)
    if len(ts) < 50: continue
    iv = [b - a for a, b in zip(ts, ts[1:]) if b - a > 0.05]
    if len(iv) < 20: continue
    med = statistics.median(iv); within = sum(1 for x in iv if abs(x - med) <= 0.2 * med) / len(iv)
    rows.append((len(ts), cl, q, round(med, 2), round(within, 2)))
for r in sorted(rows, reverse=True)[:25]: print("  ", r)
H("SCANS")
hs = collections.defaultdict(set); vs = collections.defaultdict(set); us = collections.defaultdict(set); es = collections.defaultdict(set)
for p in parts:
    for d_, src in ((hs, "hscan"), (vs, "vscan"), (us, "uscan"), (es, "escan")):
        for k, x in p[src].items():
            if isinstance(x, int): d_[k] |= {f"__{i}_{id(p)}" for i in range(x)}
            else: d_[k] |= x
print(" horizontal (src,port)->#dst >=8:", sorted(((len(x), k) for k, x in hs.items() if len(x) >= 8), reverse=True)[:20])
print(" vertical (src,dst)->#tcp ports >=8:", sorted(((len(x), k, sorted(p for p in x if isinstance(p, int))[:25]) for k, x in vs.items() if len(x) >= 8), reverse=True)[:12])
print(" udp (src,dst)->#ports >=15:", sorted(((len(x), k) for k, x in us.items() if len(x) >= 15), reverse=True)[:12])
print(" icmp echo src->#dst >=6:", sorted(((len(x), k) for k, x in es.items() if len(x) >= 6), reverse=True)[:12])
H("SNMP communities (SHA-256 prefix, length) — compare with your own fingerprint, never with the value")
DEFAULTS = {hashlib.sha256(w.encode()).hexdigest()[:12]: w for w in ("public", "private")}  # vendor defaults, not secrets
sn = mergeC("snmp")
fp = C()
for (s, t, ver, h, ln), n in sn.items(): fp[(ver, h, ln)] += n
for (ver, h, ln), n in fp.most_common():
    print(f"  {ver} {h} len={ln} frames={n}" + (f"  <- DEFAULT '{DEFAULTS[h]}'" if h in DEFAULTS else ""))
print(" senders using a default community:", [(k[:3], n) for k, n in sn.items() if k[3] in DEFAULTS])
H("HS RTT for 465/587")
hr = mergeL("hs_rtt")
print(sorted(((len(l), k) for k, l in hr.items() if k[2] in (465, 587)), reverse=True)[:12])
