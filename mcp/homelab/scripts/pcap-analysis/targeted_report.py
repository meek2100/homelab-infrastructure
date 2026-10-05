"""Report for targeted.py output (needs the deep.py pickle too, for DNS names and per-conversation retransmissions).

Usage: python3 targeted_report.py <targeted.pkl> <deep.pkl>
"""
import sys, os, pickle, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from deep import pdt, is_local, vlan_of_ip
C = collections.Counter
P = pickle.load(open(sys.argv[1], "rb"))
A = pickle.load(open(sys.argv[2], "rb"))
ipname = {}
for p in A:
    for k, v in p["ipname"].items(): ipname.setdefault(k, v)
def nm(ip): return ipname.get(ip, "")
def H(t): print("\n==== " + t)
def M(k):
    c = C()
    for p in P: c.update(p[k])
    return c
def MR(k):
    d = collections.defaultdict(list)
    for p in P:
        for kk, v in p[k].items():
            if len(d[kk]) < 2: d[kk].extend(v[:2 - len(d[kk])])
    return d
t0 = min(p["first"] for p in A); t1 = max(p["last"] for p in A); dur = t1 - t0
H("INBOUND TCP SYN from internet")
syn = M("inb_syn"); sa = M("inb_synack"); r = MR("inb_refs")
for k, n in syn.most_common(25): print(" ", k, n, "answered" if sa.get(k) else "NO-SYNACK", sa.get(k, 0), r.get(k), nm(k[0]))
print(" total inbound SYNs", sum(syn.values()), "distinct src", len({k[0] for k in syn}), "dst ports", C(k[2] for k in syn.elements()).most_common(10))
H("INBOUND UDP first-from-internet (no prior outbound)")
iu = M("inb_udp")
for k, n in iu.most_common(25): print(" ", k, n, r.get(("udp",) + k), nm(k[0]))
H("INBOUND DNS")
for k, n in M("inb_dns").most_common(20): print(" ", k, n, r.get(("dns", k[0], k[1])))
H("WATCHED DNS RESPONSES (client,server,q,rcode,first answer,ancount)")
for k, n in M("dnsw").most_common(25): print(" ", k, n)
H("UNANSWERED DNS (client,server,qname) top")
for k, n in M("dns_unans").most_common(20): print(" ", k, n)
H("QUERIES TO ROUTER x.1 DNS")
dr = M("dns_rtr"); agg = C()
for (v, s, t, q), n in dr.items(): agg[(v, s, t)] += n
print(agg.most_common(15)); print(" top names", C({q: n for (v, s, t, q), n in dr.items()}).most_common(10))
H("DNAT EVIDENCE (same client/sport/txid sent to >1 destination)")
dk = {}
for p in P:
    for k, x in p["dnat_keys"].items(): dk.setdefault(k, set()).update(x)
pat = C()
for k, x in dk.items():
    dsts = tuple(sorted({d for _, d in x})); vl = tuple(sorted({v for v, _ in x}))
    pat[(dsts, vl)] += 1
for k, n in pat.most_common(15): print(" ", k, n)
H("ACK-INFERRED VOLUME (bytes sent by A to B)")
vol = C()
for p in P:
    for (snd, rcv, svc, v), b in p["ack"].items(): vol[(snd, rcv, svc)] += b
tot_up = C(); tot_dn = C()
for (snd, rcv, svc), b in vol.items():
    if is_local(snd) and not is_local(rcv): tot_up[snd] += b
    if not is_local(snd) and is_local(rcv): tot_dn[rcv] += b
print(" total LAN->Internet MB", round(sum(tot_up.values()) / 1e6, 1), " Internet->LAN MB", round(sum(tot_dn.values()) / 1e6, 1))
print(" top uploaders", [(h, round(b / 1e6, 1)) for h, b in tot_up.most_common(10)])
print(" top downloaders", [(h, round(b / 1e6, 1)) for h, b in tot_dn.most_common(10)])
for k, b in vol.most_common(30): print(f"  {k[0]:>16} -> {k[1]:<16}:{k[2]:<6} {b/1e6:9.1f} MB  {nm(k[0]) or nm(k[1])}")
up = sorted(((b, k) for k, b in vol.items() if is_local(k[0]) and not is_local(k[1])), reverse=True)[:12]
print(" top UPLOAD flows", [(round(b / 1e6, 1), k, nm(k[1])) for b, k in up])
H("DUPLICATE FRAMES classified")
for k, n in M("dup").most_common(15): print(" ", k, n)
H("UNKNOWN-UNICAST FLOOD seen on router port")
fl = M("flood"); print(" total", sum(fl.values())); fr = MR("flood_refs")
for k, n in fl.most_common(15): print(" ", k, n, fr.get(k[:3]))
H("HAIRPIN (router re-emits into same VLAN)")
hp = M("hairpin"); print(" total", sum(hp.values())); hr = MR("hairpin_refs")
for k, n in hp.most_common(15): print(" ", k, n, hr.get(k[:3]))
H("MARTIAN / non-local private destinations")
mt = M("martian"); mr = MR("martian_refs")
for k, n in mt.most_common(20): print(" ", k, n, mr.get((k[2], k[3])))
H("TTL<=1 unicast"); print(M("ttl1").most_common(10))
H("NEXUS SYN MSS"); print(M("nexus_mss").most_common(10))
H("ROUTER ARP with off-subnet target/sender"); print(M("rtr_arp_spa").most_common(12))
H("ARP .1.237 by hour");
for k, n in sorted(M("arp237").items(), key=lambda x: str(x[0])): print(" ", k, n)
H("LAPTOP f4:46:37:7a:6a:7a presence (10-min bins)")
lp = M("laptop"); rows = collections.defaultdict(dict)
for (b, v), n in lp.items(): rows[b][v] = n
for b in sorted(rows): print(" ", pdt(b), rows[b])
H("PEAK SECONDS")
pk = M("peak"); bysec = collections.defaultdict(C)
for (sec, v, s, t, pr, dp), n in pk.items(): bysec[sec][(v, s, t, pr, dp)] += n
for sec in sorted(bysec): print(" ", pdt(sec), sum(bysec[sec].values()), bysec[sec].most_common(5))
H("ROUTER ARP VLAN1 TARGETS (sorted by last octet)")
tg = C(); ans = set()
for p in A:
    tg.update(p["rtr_arp_tgt"].get(1, {})); ans |= p["arp_answered"].get(1, set())
lst = sorted(tg.items(), key=lambda x: int(x[0].split(".")[-1]) if x[0].startswith("192.168.1.") else 999)
print(" ", [(ip.split(".")[-1] if ip.startswith("192.168.1.") else ip) + ("*" if ip in ans else "") for ip, n in lst])
print(" counts", sorted(set(n for _, n in lst))[:10], "...")
H("PER-DESTINATION RETRANS (copy on destination VLAN)")
conv = collections.defaultdict(lambda: [0] * 11)
for p in A:
    for k, l in p["conv"].items():
        for i in range(11): conv[k][i] += l[i]
dest = collections.defaultdict(lambda: [0, 0, 0])
for (v, cli, srv, svc, dr), c in conv.items():
    to = cli if dr == "s2c" else srv
    if vlan_of_ip(to) != v: continue
    frm = srv if dr == "s2c" else cli
    cls = "lan" if is_local(frm) else "wan"
    a = dest[(to, cls)]; a[0] += c[2]; a[1] += c[3]; a[2] += c[7]
rows = sorted(((a[1] / a[0] * 100, k, a) for k, a in dest.items() if a[0] >= 500), reverse=True)
for pct, k, a in rows[:30]: print(f"  {k} data {a[0]} retrans {a[1]} ({pct:.2f}%) dupack-seen {a[2]}")
OFFICE = {"192.168.10.102", "192.168.10.181", "192.168.10.182", "192.168.10.201", "192.168.10.202", "192.168.10.203"}
og = [0, 0]; hg = [0, 0]
for (to, cls), a in dest.items():
    if cls != "lan": continue
    g = og if to in OFFICE else hg
    g[0] += a[0]; g[1] += a[1]
print(f" LAN-sourced data toward OFFICE hosts: {og[1]}/{og[0]} = {og[1]/max(og[0],1)*100:.2f}%  toward HOUSE hosts: {hg[1]}/{hg[0]} = {hg[1]/max(hg[0],1)*100:.2f}%")
og = [0, 0]; hg = [0, 0]
for (to, cls), a in dest.items():
    if cls != "wan": continue
    g = og if to in OFFICE else hg
    g[0] += a[0]; g[1] += a[1]
print(f" WAN-sourced (<=1200B) data toward OFFICE hosts: {og[1]}/{og[0]} = {og[1]/max(og[0],1)*100:.2f}%  toward HOUSE hosts: {hg[1]}/{hg[0]} = {hg[1]/max(hg[0],1)*100:.2f}%")
H("ADGUARD RESPONSES TO INTERNET (udp_flows src=.40.185/.186 svc 53, ext dst)")
for p_ in [0]:
    agg = C()
    for p in A:
        for (s, t, svc, v), l in p["udp_flows"].items():
            if svc == 53 and s in ("192.168.40.185", "192.168.40.186") and not is_local(t): agg[(s, t, v)] += l[0]
            if svc == 53 and t in ("192.168.40.185", "192.168.40.186") and not is_local(s): agg[("IN", s, t, v)] += l[0]
    for k, n in agg.most_common(30): print(" ", k, n)
H("DIRECTOR / ALL UPLOAD FLOWS >=1MB")
for k, b in sorted(vol.items(), key=lambda x: -x[1]):
    if is_local(k[0]) and not is_local(k[1]) and b >= 1e6: print(f"  {k} {b/1e6:.1f} MB {nm(k[1])}")
