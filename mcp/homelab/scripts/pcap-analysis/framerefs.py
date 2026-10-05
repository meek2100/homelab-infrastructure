"""Find the first frame reference (file#frame @time PDT) for each finding.

Usage: python3 framerefs.py <dir>
The predicates in preds() are the ones used for docs/roadmaps/capture-review-2026-10-05.md; copy and edit them for a new
review. Each predicate gets a dict with v (VLAN), src (MAC bytes), arp/sha/tpa, s/t (IPs), p (IP proto), sp/dp, syn,
icmp (type, code), q/qr/a (DNS), yi/mt (DHCP) and dupe (exact duplicate within 200 ms).
"""
import sys, os, glob, struct, pickle, collections
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcapng_fast
from deep import ip4, mac, pdt, dns_parse, ROUTER

def preds():
    return {
        "rtr_arp_unans_1.30": lambda f: f["arp"] and f["src"] == ROUTER and f["tpa"] == "192.168.1.30",
        "rtr_arp_v10_40.185": lambda f: f["arp"] and f["src"] == ROUTER and f["v"] == 10 and f["tpa"] == "192.168.40.185",
        "rtr_arp_v40_10.25.25.1": lambda f: f["arp"] and f["src"] == ROUTER and f["v"] == 40 and f["tpa"] == "10.25.25.1",
        "arp_237_from_23": lambda f: f["arp"] and f["sha"] == "36:3f:c3:e8:b9:23",
        "grafana_q": lambda f: f.get("q") == "stats.grafana.org" and f["qr"] == 0,
        "grafana_r_0000": lambda f: f.get("q") == "stats.grafana.org" and f["qr"] == 1 and f.get("a") == "0.0.0.0",
        "name_query": lambda f: f.get("q") == "name_query" and f["qr"] == 0,
        "wpad": lambda f: f.get("q") == "wpad.internal" and f["qr"] == 0,
        "hue_nx": lambda f: f.get("q") == "diag.meethue.com" and f["qr"] == 1,
        "inet_dns_q_wisc": lambda f: f.get("q") == "wisc.edu" and f["s"] == "151.243.11.230",
        "inet_dns_r_wisc": lambda f: f.get("q") == "wisc.edu" and f["t"] == "151.243.11.230",
        "inet_dns_r_shadow": lambda f: f.get("q") == "dnsscan.shadowserver.org" and f["qr"] == 1,
        "inet_dns_q_openresolve": lambda f: (f.get("q") or "").endswith("openresolve.rs") and f["qr"] == 0,
        "inet_dns_r_openresolve": lambda f: (f.get("q") or "").endswith("openresolve.rs") and f["qr"] == 1,
        "bypass_20.211_8888": lambda f: f.get("q") is not None and f["s"] == "192.168.20.211" and f["t"] == "8.8.8.8",
        "sa1_80.150_mqtt": lambda f: f["s"] == "192.168.200.100" and f["t"] == "192.168.80.150" and f["p"] == 6,
        "sa1_80.150_syslog": lambda f: f["s"] == "192.168.200.100" and f["t"] == "192.168.80.150" and f["dp"] == 514,
        "sa1_gw_portprobe": lambda f: f["s"] == "192.168.200.100" and f["t"] == "192.168.200.1" and f["p"] == 6 and f["dp"] == 23,
        "desk_docker_ip": lambda f: f["s"] == "192.168.10.102" and f["t"] == "172.17.0.1",
        "luna_linklocal": lambda f: f["s"] == "192.168.40.249" and f["t"] == "169.254.83.107",
        "nexus_syn_mss1460": lambda f: f["s"] == "192.168.40.185" and f["p"] == 6 and f.get("syn") and f["v"] == 40,
        "mainsail_hostunreach": lambda f: f["p"] == 1 and f["s"] == "192.168.40.1" and f.get("icmp") == (3, 1),
        "snmp_v1_public_luna": lambda f: f["s"] == "192.168.40.249" and f["dp"] == 161,
        "snmp_v2c_920": lambda f: f["s"] == "192.168.40.185" and f["t"] == "192.168.1.215" and f["dp"] == 161,
        "hp_ntp_rtr": lambda f: f["s"] == "192.168.10.181" and f["dp"] == 123,
        "vivint_doh": lambda f: f["s"] == "192.168.10.151" and f["t"] == "1.1.1.1" and f["dp"] == 443 and f.get("syn"),
        "pixel_sonos_1443": lambda f: f["s"] == "192.168.10.110" and f["dp"] == 1443 and f["v"] == 10,
        "tailscale_natpmp": lambda f: f["s"] == "192.168.40.185" and f["dp"] == 5351,
        "laptop_v1_dhcp": lambda f: f["dp"] == 68 and f["v"] == 1 and f.get("yi") == "192.168.1.41",
        "sonos_ssdp": lambda f: f["s"] == "192.168.20.201" and f["t"] == "192.168.10.200" and f["dp"] == 1900,
        "weatherflow_mqtt": lambda f: f["s"] == "192.168.30.163" and f["dp"] == 1883 and f.get("syn"),
        "brother_dup": lambda f: f["s"] == "192.168.10.182" and f["t"] == "192.168.40.185" and f.get("dupe"),
        "nexus_dup_8006": lambda f: f["s"] == "192.168.40.185" and f["dp"] == 8006 and f.get("dupe") and f["v"] == 40,
        "switch_dl": lambda f: f["s"] == "192.168.10.130" and f["t"] == "199.232.209.133",
        "t5_update": lambda f: f["s"] == "192.168.10.201" and f["t"] == "108.138.94.55",
        "hulu_dl": lambda f: f["s"] == "192.168.20.82" and f["t"] == "151.101.65.190",
        "ap_dns_bypass": lambda f: f["s"] == "192.168.1.231" and f["t"] == "8.8.8.8" and f["dp"] == 53,
        "icmp_fragneeded": lambda f: f["p"] == 1 and f.get("icmp") == (3, 4),
        "rtr_hairpin_unreach": lambda f: f["p"] == 1 and f["s"] == "24.22.108.194" and f.get("icmp") == (3, 3),
        "mdns_rtr_v150": lambda f: f["s"] == "192.168.150.1" and f["dp"] == 5353,
        "ca1_blocked_6002": lambda f: f["p"] == 1 and f["s"] == "192.168.150.1" and f.get("icmp") == (3, 3),
        "halo_nak": lambda f: f["dp"] == 68 and f.get("mt") == 6,
    }

def work(path):
    chunk = "c" + os.path.basename(path).split("_")[2].lstrip("0")
    P = preds(); found = {}
    seen = {}
    for fr, ts, ol, d in pcapng_fast.read(path):
        if len(found) == len(P): break
        if len(d) < 14: continue
        src = d[6:12]; et = struct.unpack_from("!H", d, 12)[0]; o = 14; v = 1
        if et == 0x8100: v = struct.unpack_from("!H", d, 14)[0] & 0xfff; et = struct.unpack_from("!H", d, 16)[0]; o = 18
        f = dict(v=v, src=src, arp=False, s="", t="", p=0, dp=0, sp=0)
        import hashlib
        h = hashlib.blake2b(d, digest_size=12).digest(); pr = seen.get(h); f["dupe"] = pr is not None and ts - pr < 0.2; seen[h] = ts
        if len(seen) > 300000: seen.clear()
        if et == 0x0806 and len(d) >= o + 28:
            f.update(arp=True, sha=mac(d[o + 8:o + 14]), tpa=ip4(d[o + 24:o + 28]))
        elif et == 0x0800 and len(d) >= o + 20:
            ihl = (d[o] & 0xf) * 4; p = d[o + 9]; l4 = o + ihl
            f.update(s=ip4(d[o + 12:o + 16]), t=ip4(d[o + 16:o + 20]), p=p)
            if p in (6, 17) and len(d) >= l4 + 4:
                sp, dp = struct.unpack_from("!HH", d, l4); f.update(sp=sp, dp=dp)
                if p == 6 and len(d) >= l4 + 14: f["syn"] = bool(d[l4 + 13] & 2) and not (d[l4 + 13] & 16)
                if p == 17 and 53 in (sp, dp):
                    r = dns_parse(d[l4 + 8:])
                    if r: f.update(q=(r["q"] or "").lower(), qr=r["qr"], a=r["ans"][0][2] if r["ans"] else None)
                if p == 17 and dp == 68 and len(d) >= l4 + 8 + 240:
                    b = d[l4 + 8:]; f["yi"] = ip4(b[16:20])
                    q = 240
                    while q + 2 < len(b) and b[q] != 255:
                        if b[q] == 0: q += 1; continue
                        if b[q] == 53: f["mt"] = b[q + 2]
                        q += 2 + b[q + 1]
            if p == 1 and len(d) >= l4 + 2: f["icmp"] = (d[l4], d[l4 + 1])
        else:
            continue
        for k, fn in P.items():
            if k in found: continue
            try:
                if fn(f): found[k] = f"{chunk}#{fr}@{pdt(ts)}"
            except Exception:
                pass
    return found

if __name__ == "__main__":
    files = sorted(glob.glob(os.path.join(sys.argv[1], "*.pcapng")))
    with Pool(4) as pool:
        res = pool.map(work, files, chunksize=1)
    first = {}
    for r in res:
        for k, v in r.items(): first.setdefault(k, v)
    for k in preds():
        print(f"{k:28} {first.get(k, '-')}")
