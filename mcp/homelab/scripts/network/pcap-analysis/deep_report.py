"""Report for deep.py output.

Usage: python3 deep_report.py <deep.pkl> [all|basic|l2|l3|l4|app]
  basic = volume, rates, VLANs, broadcast/multicast, ethertypes, talkers
  l2    = ARP (router sweep, conflicts, GARP), STP, exact duplicates
  l3    = IPv4/IPv6, fragments, TTL, routing loops, ICMP, IPv6 RAs
  l4    = TCP flags, MSS/window options, retransmissions per class, RTT, unanswered SYNs, RSTs, ACK-inferred big flows
  app   = DNS, mDNS/SSDP/SDDP, DHCP, NTP, HTTP, TLS (JA3/JA4), SMB/NTLM/Kerberos/Telnet/FTP/SNMP, admin ports
Counts are frames as mirrored: inter-VLAN traffic appears once per VLAN.
"""
import sys, os, pickle, collections, statistics, datetime, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from deep import pdt, is_local, vlan_of_ip, ADGUARD
C = collections.Counter
parts = pickle.load(open(sys.argv[1], "rb"))
SECTION = sys.argv[2] if len(sys.argv) > 2 else "all"
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
def refs(k):
    d = collections.defaultdict(list)
    for p in parts:
        for kk, v in p[k].items():
            if len(d[kk]) < 3: d[kk].extend(v[:3 - len(d[kk])])
    return d
def q(l, f):
    l = sorted(l); return l[min(len(l) - 1, int(len(l) * f))] if l else None
N = sum(p["n"] for p in parts); B = sum(p["bytes"] for p in parts); CAP = sum(p["cap"] for p in parts)
t0 = min(p["first"] for p in parts); t1 = max(p["last"] for p in parts); dur = t1 - t0
persec = mergeC("persec"); persecb = mergeC("persecb")

if SECTION in ("all", "basic"):
    H("BASIC")
    print(f"frames {N:,}  orig bytes {B:,}  captured bytes {CAP:,}  start {pdt(t0)} end {pdt(t1)} dur {dur:.0f}s ({dur/3600:.2f} h)")
    print(f"avg pps {N/dur:.1f}  avg bps {B*8/dur:,.0f}")
    pk = persec.most_common(5); print("peak pps", [(pdt(s), n) for s, n in pk])
    pb = persecb.most_common(3); print("peak Bps", [(pdt(s), n, f'{n*8/1e6:.2f} Mbps') for s, n in pb])
    secs = sorted(persec); missing = (int(t1) - int(t0) + 1) - len(secs)
    print("seconds w/o frames", missing)
    pv = sorted(persec.values()); print("pps p50/p95/p99", q(pv, .5), q(pv, .95), q(pv, .99))
    gaps = [g for p in parts for g in p["gaps"]]; print("gaps>5s", gaps[:10])
    for p in parts: print(" ", p["files"][0][16:21], pdt(p["first"]), pdt(p["last"]), p["n"], round(p["bytes"]/1e6, 1), "MB")
    lens = mergeC("lens"); print("len hist", sorted(lens.items()))
    print("maxlen", max(p["maxlen"] for p in parts))
    H("VLAN")
    vp, vb = mergeC("vlan_p"), mergeC("vlan_b")
    for v in sorted(vp): print(f"  vlan {v}: {vp[v]:,} frames ({vp[v]/N*100:.1f}%) {vb[v]/1e6:.1f} MB")
    H("CAST")
    cast, castb = mergeC("cast"), mergeC("castb")
    tot = C(); totb = C()
    for (v, c), n in cast.items(): tot[c] += n; totb[c] += castb[(v, c)]
    print(" totals", dict(tot), {k: f"{x/N*100:.2f}%" for k, x in tot.items()}, "bytes%", {k: f"{x/B*100:.2f}%" for k, x in totb.items()})
    for v in sorted(vp): print(f"  vlan {v}", {c: cast[(v, c)] for c in ("bc", "mc", "uc")}, f"nonuc% {(cast[(v,'bc')]+cast[(v,'mc')])/vp[v]*100:.1f}")
    H("ETHERTYPE"); print(mergeC("etype").most_common())
    H("TOP BC/MC SENDERS");
    for k, n in mergeC("bc_src").most_common(25): print(" ", k, n, f"{n/dur:.2f}/s")
    H("MC DST"); print(mergeC("mc_dst").most_common(20))
    bcs = mergeC("bc_persec")
    H("BCAST PPS PER VLAN PEAK")
    pervl = collections.defaultdict(list)
    for (s, v), n in bcs.items(): pervl[v].append((n, s))
    for v, l in sorted(pervl.items()):
        l.sort(reverse=True); print(f"  vlan {v} peak {l[0][0]} at {pdt(l[0][1])}; secs>200pps {sum(1 for n,_ in l if n>200)}; >50 {sum(1 for n,_ in l if n>50)}")
    rb = mergeC("rtr_bc_persec"); vals = sorted(rb.values())
    print(" router bcast pps: max", rb.most_common(3) and [(pdt(s), n) for s, n in rb.most_common(3)], "p99", q(vals, .99), "secs>200", sum(1 for x in vals if x > 200))
    H("MULTI-VLAN MACS")
    mv = collections.defaultdict(set)
    for p in parts:
        for m, vs in p["mac_vlans"].items(): mv[m] |= vs
    for m, vs in sorted(mv.items(), key=lambda x: -len(x[1])):
        if len(vs) > 1: print(" ", m, sorted(vs))
    print(" distinct src macs", len(mv))
    H("TOP SRC MACS"); print(mergeC("srcmac").most_common(15))

if SECTION in ("all", "l2"):
    H("ARP")
    print(" ops", sorted(mergeC("arp_op").items()))
    print(" req src", mergeC("arp_req_src").most_common(15))
    print(" rep src", mergeC("arp_rep_src").most_common(10))
    print(" garp", mergeC("garp").most_common(15))
    print(" unsolicited bcast replies", mergeC("arp_unsol_rep").most_common(10))
    print(" probes", len(mergeC("arp_probe")), mergeC("arp_probe").most_common(5))
    ipm = collections.defaultdict(C)
    for p in parts:
        for k, c in p["ip2mac"].items(): ipm[k].update(c)
    conflicts = {k: c for k, c in ipm.items() if len(c) > 1}
    print(" IP->multiple MAC conflicts", len(conflicts))
    for k, c in sorted(conflicts.items(), key=lambda x: -sum(x[1].values()))[:20]: print("   ", k, dict(c))
    macip = collections.defaultdict(set)
    for (v, ip), c in ipm.items():
        for m in c: macip[(v, m)].add(ip)
    print(" MAC->many IPs:", [(k, sorted(x)) for k, x in macip.items() if len(x) > 2][:15])
    ram = mergeC("rtr_arp_min")
    tot = C(); mx = {}
    for (m, v), n in ram.items(): tot[v] += n; mx[v] = max(mx.get(v, (0, 0)), (n, m))
    print(" router ARP req total per vlan", dict(tot), "rate/s", {v: round(n/dur, 2) for v, n in tot.items()})
    print(" router ARP peak min", {v: (n, pdt(m*60)) for v, (n, m) in mx.items()})
    tg = collections.defaultdict(C)
    for p in parts:
        for v, c in p["rtr_arp_tgt"].items(): tg[v].update(c)
    ans = collections.defaultdict(set)
    for p in parts:
        for v, sset in p["arp_answered"].items(): ans[v] |= sset
    for v in sorted(tg):
        un = [(ip, n) for ip, n in tg[v].most_common() if ip not in ans[v]]
        print(f"  vlan {v}: distinct targets {len(tg[v])}, answered {len(ans[v] & set(tg[v]))}, unanswered {len(un)}; top unanswered {un[:12]}")
        print(f"      top targets {tg[v].most_common(8)}")
    ass = mergeC("arp_storm_sec"); per = collections.defaultdict(list)
    for (s, v), n in ass.items(): per[v].append((n, s))
    print(" ARP pps peak per vlan", {v: (max(l)[0], pdt(max(l)[1])) for v, l in per.items()})
    H("STP")
    for k, n in mergeC("stp").most_common(20): print(" ", k, n)
    print(" TC", mergeC("stp_tc"), dict(refs("stp_refs")))
    H("DUPLICATES"); print(" per vlan", mergeC("dup")); print(" src", mergeC("dup_src").most_common(12));
    dr = refs("dup_refs"); print(" refs", {k: dr[k] for k, _ in mergeC("dup_src").most_common(6)})

if SECTION in ("all", "l3"):
    H("L3")
    i4 = sum(p["ip4"] for p in parts); i6 = sum(p["ip6"] for p in parts)
    print(f" ipv4 {i4:,} ({i4/N*100:.2f}%) {sum(p['ip4b'] for p in parts)/1e6:.1f}MB; ipv6 {i6:,} ({i6/N*100:.2f}%) {sum(p['ip6b'] for p in parts)/1e6:.1f}MB")
    print(" frags", mergeC("frag").most_common(15)); print(" frag refs", dict(list(refs("frag_refs").items())[:8]))
    print(" overlap", sum(p["frag_overlap"] for p in parts), "tiny", sum(p["frag_tiny"] for p in parts), "DF+MF", sum(p["frag_df_mf"] for p in parts))
    print(" loops", mergeC("loop").most_common(10), dict(list(refs("loop_refs").items())[:6]))
    print(" ECN", mergeC("ecn")); print(" ipopts", mergeC("ipopt").most_common(5))
    # TTL anomalies: hosts with >2 distinct TTLs on same vlan
    tt = collections.defaultdict(C)
    for p in parts:
        for k, c in p["ttl"].items(): tt[k].update(c)
    multi = [(k, dict(c.most_common(4))) for k, c in tt.items() if len([x for x, n in c.items() if n > 5]) > 2 and ":" not in k[1]]
    print(" multi-TTL sources", len(multi)); [print("   ", m) for m in sorted(multi, key=lambda x: -sum(x[1].values()))[:15]]
    H("ICMP"); print(" types", sorted(mergeC("icmp").items(), key=lambda x: -x[1]))
    for k, n in mergeC("icmp_detail").most_common(30): print("  ", k, n)
    print(" refs", dict(list(refs("icmp_refs").items())[:15]))
    print(" echo pairs", mergeC("echo").most_common(12))
    print(" big echo", mergeC("echo_big").most_common(10))
    print(" icmp6", sorted(mergeC("icmp6").items(), key=lambda x: -x[1])[:15])
    print(" RA", mergeC("ra").most_common(10), dict(refs("ra_refs")))

if SECTION in ("all", "l4"):
    H("L4")
    l4, l4b = mergeC("l4"), mergeC("l4b")
    tt = C(); tb = C()
    for (pr, v), n in l4.items(): tt[pr] += n; tb[pr] += l4b[(pr, v)]
    print(" ", dict(tt), {k: f"{x/N*100:.1f}%" for k, x in tt.items()}, {k: f"{x/B*100:.1f}% bytes" for k, x in tb.items()})
    fl = mergeC("tcpflags")
    print(" flags", [(k, n) for k, n in fl.most_common() if isinstance(k, str)][:20])
    an = [(k, n) for k, n in fl.most_common() if isinstance(k, tuple)]
    agg = C()
    for k, n in an: agg[k[1] if k[0] == "ANOM" else k[0]] += n
    print(" anomalies", agg); print("  ", an[:25])
    ar = refs("tcp_anom_refs"); print(" anom refs", dict(list(ar.items())[:25]))
    syn = fl.get("S", 0); sa = fl.get("SA", 0) + fl.get("SAE", 0); rst = sum(n for k, n in fl.items() if isinstance(k, str) and "R" in k)
    print(f" SYN {syn} SYNACK {sa} RST {rst} RST:SYN {rst/max(syn,1):.3f}")
    print(" ECN setup", mergeC("ecn_setup").most_common(10))
    print(" MSS", mergeC("mss").most_common(20))
    ms = collections.defaultdict(C)
    for p in parts:
        for k, c in p["mss_src"].items(): ms[k].update(c)
    print(" MSS by src (non-1460)", [(k, dict(c)) for k, c in sorted(ms.items(), key=lambda x: -sum(x[1].values())) if set(c) - {1460, 8960, 65495}][:30])
    print(" wscale", sorted(mergeC("wscale").items()), "sackperm", mergeC("sackperm"), "ts", mergeC("tsopt"))
    H("TCP CLASS RATES (data,retrans,fast,ooo,gap,dupack,zerowin)")
    cls = collections.defaultdict(lambda: [0]*7)
    for p in parts:
        for k, l in p["cls"].items():
            for i in range(7): cls[k][i] += l[i]
    for k, l in cls.items(): print(f"  {k}: data {l[0]:,} retrans {l[1]:,} ({l[1]/max(l[0],1)*100:.3f}%) fast {l[2]} ooo {l[3]} ({l[3]/max(l[0],1)*100:.3f}%) gap {l[4]:,} ({l[4]/max(l[0],1)*100:.2f}%) dupack {l[5]:,} zerowin {l[6]}")
    conv = collections.defaultdict(lambda: [0]*11 + [0.0, 0.0])
    for p in parts:
        for k, l in p["conv"].items():
            c = conv[k]
            for i in range(11): c[i] += l[i]
            c[11] = l[11] if c[11] == 0 else min(c[11], l[11]); c[12] = max(c[12], l[12])
    H("TOP RETRANS CONVERSATIONS (ingress/any vlan)")
    rows = sorted(conv.items(), key=lambda x: -x[1][3])[:30]
    for (v, cli, srv, svc, dr), c in rows:
        print(f"  v{v} {cli} -> {srv}:{svc} {dr} pkts {c[0]} data {c[2]} retr {c[3]} ({c[3]/max(c[2],1)*100:.1f}%) ooo {c[5]} gap {c[6]} dupack {c[7]} zw {c[8]} ka {c[9]}")
    H("ZERO WINDOW")
    for (v, cli, srv, svc, dr), c in sorted(conv.items(), key=lambda x: -x[1][8])[:12]:
        if c[8]: print(f"  v{v} {cli}->{srv}:{svc} {dr} zerowin {c[8]} pkts {c[0]}")
    H("KEEPALIVES");
    for (v, cli, srv, svc, dr), c in sorted(conv.items(), key=lambda x: -x[1][9])[:8]: print(f"  v{v} {cli}->{srv}:{svc} {dr} ka {c[9]}")
    H("TOP TCP CONVERSATIONS BY PKTS")
    for (v, cli, srv, svc, dr), c in sorted(conv.items(), key=lambda x: -x[1][0])[:25]:
        print(f"  v{v} {cli}->{srv}:{svc} {dr} pkts {c[0]:,} bytes {c[1]/1e6:.1f}MB psh {c[10]} {pdt(c[11])}-{pdt(c[12])}")
    H("HANDSHAKE RTT")
    hr = mergeL("hs_rtt")
    allr = collections.defaultdict(list)
    for (cl, srv, port), l in hr.items():
        for a, b in l: allr[cl].append((a, b))
    for cl, l in allr.items():
        sa_ = [x[0]*1000 for x in l]; ca = [x[1]*1000 for x in l]
        print(f"  {cl}: n={len(l)} server-side ms p50 {q(sa_,.5):.2f} p95 {q(sa_,.95):.2f} p99 {q(sa_,.99):.1f}; client-side ms p50 {q(ca,.5):.2f} p95 {q(ca,.95):.2f} p99 {q(ca,.99):.1f}")
    worst = sorted(((statistics.median([x[0] for x in l])*1000, k, len(l)) for k, l in hr.items() if len(l) >= 5), reverse=True)[:15]
    print(" worst server-side median", [(round(a, 1), k, n) for a, k, n in worst])
    worstc = sorted(((statistics.median([x[1] for x in l])*1000, k, len(l)) for k, l in hr.items() if len(l) >= 5), reverse=True)[:15]
    print(" worst client-side median", [(round(a, 1), k, n) for a, k, n in worstc])
    H("UNANSWERED SYN (by client,server,port)")
    su = mergeC("syn_unans"); print(" total", sum(su.values()));
    for k, n in su.most_common(30): print("  ", k, n)
    print(" synack unacked", mergeC("synack_unacked").most_common(10))
    print(" syn retries", mergeC("syn_retry").most_common(15))
    H("RST SOURCES"); print(mergeC("rst_src").most_common(15))
    H("BIG FLOWS (ACK-inferred bytes delivered by peer)")
    bf = [b for p in parts for b in p["bigflows"]]
    agg = collections.defaultdict(lambda: [0, 0, 0.0, 0.0, 0, 0])
    for v, s, sp, t, dp, nb, f0, f1, mw, pk, rt in [x[:11] for x in bf]:
        a = agg[(v, s, sp, t, dp)]; a[0] += nb; a[1] = max(a[1], mw); a[2] = f0 if a[2] == 0 else min(a[2], f0); a[3] = max(a[3], f1); a[4] += pk; a[5] += rt
    for k, a in sorted(agg.items(), key=lambda x: -x[1][0])[:25]:
        d_ = max(a[3] - a[2], 1)
        print(f"  {k} peer-delivered {a[0]/1e6:.1f}MB over {d_:.0f}s = {a[0]*8/d_/1e6:.2f} Mbps; maxwin(raw) {a[1]}; pkts {a[4]} retr {a[5]} {pdt(a[2])}-{pdt(a[3])}")

if SECTION in ("all", "app"):
    H("DNS")
    nq = sum(p["dns_q"] for p in parts); nr = sum(p["dns_r"] for p in parts)
    print(f" queries {nq:,} responses {nr:,}  qps {nq/dur:.2f}")
    rc = mergeC("dns_rcode"); print(" rcodes", rc, f"NX ratio {rc[3]/max(nr,1)*100:.2f}%  SERVFAIL {rc[2]/max(nr,1)*100:.2f}%")
    print(" qtypes", mergeC("dns_qt").most_common(12))
    print(" servers", mergeC("dns_srv").most_common(15))
    print(" edns", mergeC("dns_edns").most_common(5), "DO", sum(p["dns_do"] for p in parts), "AD", sum(p["dns_ad"] for p in parts), "TC", sum(p["dns_tc"] for p in parts))
    dl = mergeL("dns_lat")
    for k, l in sorted(dl.items(), key=lambda x: -len(x[1]))[:10]:
        l = [x*1000 for x in l]; print(f"  latency {k}: n={len(l)} p50 {q(l,.5):.2f}ms p95 {q(l,.95):.2f} p99 {q(l,.99):.1f} max {max(l):.0f}")
    print(" top clients", mergeC("dns_client").most_common(15))
    print(" top names", mergeC("dns_name").most_common(30))
    print(" NX top", mergeC("dns_nx").most_common(20))
    print(" bypass", mergeC("dns_bypass").most_common(25)); br = refs("dns_bypass_refs"); print(" bypass refs", dict(list(br.items())[:12]))
    print(" long/entropy", mergeC("dns_long").most_common(15)); print("  refs", dict(list(refs("dns_long_refs").items())[:10]))
    print(" TXT/NULL", mergeC("dns_txt").most_common(15))
    sub = collections.defaultdict(set)
    for p in parts:
        for k, x in p["dns_sub"].items(): sub[k] |= x
    print(" bases by unique subdomains", sorted(((len(x), k) for k, x in sub.items()), reverse=True)[:15])
    print(" DoT", mergeC("dot").most_common(10)); print(" DoH-ip SYNs", mergeC("doh").most_common(15))
    H("MDNS/SSDP/SDDP/LLMNR/NBNS")
    md = mergeC("mdns"); print(" mdns total", sum(md.values()), md.most_common(12)); print(" mdns >1500", mergeC("mdns_big").most_common(10))
    print(" ssdp", sum(mergeC("ssdp").values()), mergeC("ssdp").most_common(10))
    print(" sddp", sum(mergeC("sddp").values()), mergeC("sddp").most_common(10))
    print(" llmnr", mergeC("llmnr").most_common(5), " nbns", mergeC("nbns").most_common(8), " wsd", mergeC("wsd").most_common(5))
    H("UDP services");
    u, ub = mergeC("udp"), mergeC("udpb"); us = C(); ubs = C()
    for (s, v), n in u.items(): us[s] += n; ubs[s] += ub[(s, v)]
    print(" ", [(s, n, f"{ubs[s]/1e6:.1f}MB") for s, n in us.most_common(25)])
    H("DHCP")
    dh = sorted([e for p in parts for e in p["dhcp"]], key=lambda e: e["ts"])
    mt = C((e["mt"], e["v"]) for e in dh); print(" msgtypes(mt,vlan)", sorted(mt.items()))
    srv = C((e["mt"], e["src"], e["smac"], e["sid"]) for e in dh if e["mt"] in (2, 5, 6)); print(" server msgs", srv.most_common(15))
    rog = [e for e in dh if e["mt"] in (2, 5, 6) and e["smac"] != "14:3f:c3:91:50:8c"]; print(" non-router offers/acks", len(rog), [(e["ref"], e["smac"], e["src"]) for e in rog[:5]])
    print(" NAKs", [(e["ref"], e["v"], e["ch"], e["req"], e["sid"]) for e in dh if e["mt"] == 6][:20])
    print(" declines", [(e["ref"], e["v"], e["ch"], e["req"]) for e in dh if e["mt"] == 4][:10])
    acks = [e for e in dh if e["mt"] == 5]
    print(" ACK opts: dns", C(tuple(e["dns"]) for e in acks).most_common(8), "dom", C(e["dom"] for e in acks).most_common(5), "o42", C(e["o42"] for e in acks), "o119", C(e["o119"] for e in acks), "lease", C(e["lease"] for e in acks).most_common(5))
    print(" ACKs", [(e["ref"].split("@")[1], e["v"], e["ch"], e["yi"], e["host"]) for e in acks][:80])
    pool = [(e["v"], e["ch"], e["yi"], e["host"]) for e in acks if e["yi"].split(".")[-1].isdigit() and 20 <= int(e["yi"].split(".")[-1]) <= 99]
    print(" ACKs in dynamic pool .20-.99:", len(set(pool)), sorted(set(pool)))
    disc = C((e["v"], e["ch"], e["host"]) for e in dh if e["mt"] == 1); print(" DISCOVER heavy", disc.most_common(12))
    req = C((e["v"], e["ch"], e["host"], e["req"]) for e in dh if e["mt"] == 3); print(" REQUEST heavy", req.most_common(12))
    H("NTP")
    nt = mergeC("ntp")
    for k, n in nt.most_common(25): print("  ", k, n)
    no = mergeL("ntp_off"); print(" offsets(s) by server", {k: (len(l), round(statistics.median(l), 4), round(min(l), 4), round(max(l), 4)) for k, l in no.items()})
    print(" odd sizes", mergeC("ntp_odd").most_common(10))
    H("HTTP");
    for k, n in mergeC("http").most_common(30): print("  ", k, n)
    print(" methods", C(k[0] for k in mergeC("http").elements()))
    print(" AUTH", mergeC("http_auth").most_common(10)); hr_ = refs("http_refs"); print(" auth refs", {k: v for k, v in hr_.items() if k[0] == "AUTH"})
    print(" UA", mergeC("http_ua").most_common(20))
    print(" status", mergeC("http_status").most_common(15))
    hl = mergeL("http_lat"); print(" latency", [(k, len(l), round(q(l,.5)*1000, 1), round(q(l,.95)*1000, 1)) for k, l in sorted(hl.items(), key=lambda x: -len(x[1]))[:12]])
    H("TLS")
    print(" coverage", mergeC("tls_cov")); print(" offer-max", mergeC("tls_ver"));
    tc = mergeC("tls_ch"); print(" weak offered", {k: n for k, n in tc.items() if k[0] == "weak-cipher-offered"}); print(" no-tls13", [(k, n) for k, n in tc.most_common() if k[0] == "no-tls13"][:20])
    print(" SH", mergeC("tls_sh").most_common(20))
    ja = mergeC("tls_ja"); jac = C()
    for (j4, j3, s, sni), n in ja.items(): jac[(j4, j3)] += n
    print(" JA4/JA3 distinct", len(jac));
    for k, n in jac.most_common(20):
        ex = [(s, sni) for (j4, j3, s, sni), m in ja.most_common() if (j4, j3) == k][:3]; print("  ", k, n, ex)
    print(" SNI top", mergeC("tls_sni").most_common(30))
    print(" TLS non-std ports", mergeC("tls_nonstd").most_common(15))
    print(" SSH banners", mergeC("ssh").most_common(15))
    H("ENTERPRISE")
    print(" smb", mergeC("smb").most_common(15)); print(" ntlm", mergeC("ntlm").most_common(10)); print(" krb", mergeC("krb").most_common(10))
    print(" telnet", mergeC("telnet").most_common(10)); print(" ftp", mergeC("ftp").most_common()); print(" snmp", mergeC("snmp").most_common(15)); print(" db", mergeC("dbq").most_common(10))
    adm = collections.defaultdict(lambda: [0, 0, 0, 0])
    for p in parts:
        for k, l in p["admin"].items():
            for i in range(4): adm[k][i] += l[i]
    print(" admin (syn, synack, rst, bytes)");
    for k, l in sorted(adm.items(), key=lambda x: -x[1][0])[:30]: print("   ", k, l[:4])
