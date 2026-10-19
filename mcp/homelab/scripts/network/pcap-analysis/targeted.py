"""Targeted second pass over the router SPAN captures (see README).

Inbound flows from the internet, DNS loop detail, DNAT evidence, ACK-advance volumes, unknown-unicast flooding,
hairpin and martian routing, ARP oddities, exact duplicates, and a per-flow breakdown of chosen peak seconds.

Usage: python3 targeted.py <dir> <out.pkl> [peak-second ...]
       peak-second is ISO 8601 with offset, e.g. 2026-10-05T00:31:47-07:00 (take it from deep_report.py "peak pps").
Report: python3 targeted_report.py <out.pkl> <deep.pkl>
"""
import sys, os, glob, struct, collections, pickle, hashlib, datetime
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcapng_fast
from deep import ip4, mac, pdt, is_local, vlan_of_ip, dns_parse, ROUTER, Refs

WATCHQ = {"stats.grafana.org", "name_query", "name_query.internal", "wpad.internal", "diag.meethue.com", "internal.internal"}
# Private destinations the 520 legitimately routes (static routes: wg-easy, DD-WRT transit, WAN2/storage, OpenWrt P3 subnet)
ROUTED = ("10.8.0.", "10.20.20.", "10.25.25.", "192.168.2.")
LAPTOP = bytes.fromhex("f446377a6a7a")  # MAC whose VLAN presence is tracked in 10-minute bins (work laptop Wi-Fi)
PEAKS = set()  # epoch seconds to break down by flow; set from argv in main() before the worker pool forks

def martian(a):
    """Private or link-local destination that is neither a local VLAN nor a routed range: it can only leave via the WAN."""
    o = a.split(".")
    private = o[0] == "10" or a.startswith(("192.168.", "169.254.")) or (o[0] == "172" and 16 <= int(o[1]) <= 31)
    return private and vlan_of_ip(a) is None and not a.startswith(ROUTED)

def work(path):
    chunk = "c" + os.path.basename(path).split("_")[2].lstrip("0")
    C = collections.Counter
    R = dict(inb_syn=C(), inb_synack=C(), inb_refs=Refs(), inb_udp=C(), inb_dns=C(),
             dnsw=C(), dns_rtr=C(), dnat_keys={}, ack=collections.defaultdict(int), dup=C(), flood=C(), flood_refs=Refs(),
             peak=C(), nexus_mss=C(), rtr_arp_spa=C(), hairpin=C(), hairpin_refs=Refs(), martian=C(), martian_refs=Refs(),
             arp237=C(), laptop=C(), ttl1=C(), dns_unans=C())
    acks = {}
    udpseen = {}
    seen = {}
    dq = {}
    for fr, ts, ol, d in pcapng_fast.read(path):
        if len(d) < 14: continue
        ref = f"{chunk}#{fr}@{pdt(ts)}"
        dst, src = d[0:6], d[6:12]
        et = struct.unpack_from("!H", d, 12)[0]; o = 14; v = 1
        if et == 0x8100:
            v = struct.unpack_from("!H", d, 14)[0] & 0xfff; et = struct.unpack_from("!H", d, 16)[0]; o = 18
        sec = int(ts)
        if src == LAPTOP: R["laptop"][(int(ts // 600) * 600, v)] += 1
        h = hashlib.blake2b(d, digest_size=12).digest(); prev = seen.get(h); dupf = prev is not None and ts - prev < 0.2; seen[h] = ts
        if len(seen) > 400000: seen.clear()
        if et == 0x0806 and len(d) >= o + 28:
            op = struct.unpack_from("!H", d, o + 6)[0]; sha = mac(d[o + 8:o + 14]); spa = ip4(d[o + 14:o + 18]); tpa = ip4(d[o + 24:o + 28])
            if src == ROUTER and op == 1 and not tpa.startswith(f"192.168.{v}."): R["rtr_arp_spa"][(v, spa, tpa)] += 1
            if src == ROUTER and op == 1 and v == 1 and tpa == "192.168.1.237": R["arp237"][(pdt(ts)[:2], "req")] += 1
            if spa == "192.168.1.237" or (op == 2 and tpa == "192.168.1.237"): R["arp237"][(pdt(ts)[:2], op, sha, mac(dst) if op == 2 else tpa)] += 1
            if dupf: R["dup"][(v, mac(src), "arp", op, tpa)] += 1
            continue
        if et != 0x0800 or len(d) < o + 20: continue
        ihl = (d[o] & 0xf) * 4; ttl = d[o + 8]; proto = d[o + 9]
        s = ip4(d[o + 12:o + 16]); t = ip4(d[o + 16:o + 20]); l4 = o + ihl
        sl, tl = is_local(s), is_local(t)
        ingress = src != ROUTER
        sp = dp = 0
        if proto in (6, 17) and len(d) >= l4 + 4: sp, dp = struct.unpack_from("!HH", d, l4)
        if dupf: R["dup"][(v, mac(src), proto, s, t, min(sp, dp) if proto in (6, 17) else 0)] += 1
        if sec in PEAKS: R["peak"][(sec, v, s, t, proto, dp if dp < sp else sp)] += 1
        # unknown-unicast flooding: unicast frame neither from nor to the router seen on the router port
        if not (dst[0] & 1) and dst != ROUTER and src != ROUTER:
            R["flood"][(v, s, t, proto, min(sp, dp))] += 1; R["flood_refs"].add((v, s, t), ref)
        # router re-emits into the same VLAN a packet whose source and destination are both on that VLAN
        if not ingress and vlan_of_ip(s) == v and vlan_of_ip(t) == v:
            R["hairpin"][(v, s, t, proto, min(sp, dp))] += 1; R["hairpin_refs"].add((v, s, t), ref)
        if martian(t):
            R["martian"][(v, "egress" if not ingress else "ingress", s, t, proto, dp)] += 1; R["martian_refs"].add((s, t), ref)
        if ttl <= 1 and not t.startswith("224.") and t != "255.255.255.255": R["ttl1"][(v, s, t, proto, dp)] += 1
        if proto == 6 and len(d) >= l4 + 20:
            seq, ack, offf, win = struct.unpack_from("!IIHH", d, l4 + 4)
            fl = offf & 0x1ff; thl = (offf >> 12) * 4
            SYN, ACK, FIN, RST = fl & 2, fl & 16, fl & 1, fl & 4
            if SYN and not ACK and not sl and tl: R["inb_syn"][(s, t, dp)] += 1; R["inb_refs"].add((s, t, dp), ref)
            if SYN and ACK and sl and not tl: R["inb_synack"][(t, s, sp)] += 1
            if SYN and s == "192.168.40.185":
                q = l4 + 20; e = min(l4 + thl, len(d))
                while q < e:
                    k = d[q]
                    if k == 0: break
                    if k == 1: q += 1; continue
                    if q + 1 >= e: break
                    ln = d[q + 1]
                    if ln < 2: break
                    if k == 2 and ln == 4: R["nexus_mss"][("SA" if ACK else "S", vlan_of_ip(t) or "wan", struct.unpack_from("!H", d, q + 2)[0])] += 1
                    q += ln
            # ACK-advance volume: one copy per direction (ingress, or the egress copy when the ACKer is remote).
            # SYN/RST start or end a connection on this 5-tuple, so the baseline is dropped (ports get reused).
            if ingress or not sl:
                fk = (v, s, sp, t, dp)
                if SYN or RST:
                    acks.pop(fk, None)
                elif ACK:
                    last = acks.get(fk)
                    if last is not None:
                        dl = (ack - last) & 0xffffffff
                        if 0 < dl < 16_000_000: R["ack"][(t, s, dp if dp < sp else sp, v)] += dl  # bytes sent by t to s
                    if FIN: acks.pop(fk, None)
                    else: acks[fk] = ack
                    if len(acks) > 500000: acks.clear()
        elif proto == 17 and len(d) >= l4 + 8:
            p = d[l4 + 8:]
            # inbound UDP: first packet of a 4-tuple comes from the internet with no earlier outbound packet
            if not sl and tl and not t.startswith("224.") and dp != 41641 and t != "255.255.255.255":
                if (t, dp, s, sp) not in udpseen:
                    R["inb_udp"][(s, t, dp)] += 1; R["inb_refs"].add(("udp", s, t, dp), ref)
            if sl and not tl: udpseen[(s, sp, t, dp)] = ts
            if dp == 53 or sp == 53:
                r = dns_parse(p)
                if r is None: continue
                q = (r["q"] or "").lower()
                if not sl and dp == 53: R["inb_dns"][(s, t, q, r["qr"], r["rcode"])] += 1; R["inb_refs"].add(("dns", s, t), ref)
                if r["qr"] == 0:
                    if t.startswith("192.168.") and t.endswith(".1"): R["dns_rtr"][(v, s, t, q[:50])] += 1
                    R["dnat_keys"].setdefault((s, sp, r["id"]), set()).add((v, t))
                    dq[(v, s, sp, t, r["id"])] = (ts, q)
                    if len(dq) > 200000: dq.clear()
                else:
                    if q in WATCHQ:
                        a = r["ans"][0][2] if r["ans"] else None
                        R["dnsw"][(t, s, q, r["rcode"], a, r["an"])] += 1
                    dq.pop((v, t, dp, s, r["id"]), None)
                if len(R["dnat_keys"]) > 400000: R["dnat_keys"] = {}
    for (v, c, cp, srv, i), (ts0, q) in dq.items():
        R["dns_unans"][(c, srv, q[:60])] += 1
    # keep only DNAT-relevant keys (same client/port/txid sent to more than one destination)
    R["dnat_keys"] = {k: x for k, x in R["dnat_keys"].items() if len({d_ for _, d_ in x}) > 1}
    R["inb_refs"] = dict(R["inb_refs"]); R["flood_refs"] = dict(R["flood_refs"]); R["hairpin_refs"] = dict(R["hairpin_refs"]); R["martian_refs"] = dict(R["martian_refs"])
    R["ack"] = dict(R["ack"])
    return R

def main():
    PEAKS.update(int(datetime.datetime.fromisoformat(x).timestamp()) for x in sys.argv[3:])
    files = sorted(glob.glob(os.path.join(sys.argv[1], "*.pcapng")))
    with Pool(4) as pool:
        parts = pool.map(work, files, chunksize=1)
    with open(sys.argv[2], "wb") as fh:
        pickle.dump(parts, fh, protocol=pickle.HIGHEST_PROTOCOL)
    print("done", len(parts))

if __name__ == "__main__":
    main()
