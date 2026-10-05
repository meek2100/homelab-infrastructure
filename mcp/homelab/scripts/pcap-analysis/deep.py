"""Deep single-pass analysis of the router SPAN captures (SW920 1/0/1 mirror, 802.1Q-tagged).

Read-only. Usage: python3 deep.py <dir> <out.pkl> [nfiles]
Every finding keeps references as "c<chunk>#<frame>@<HH:MM:SS PDT>" (frame = Wireshark frame.number in that file).
"""
import sys, os, glob, struct, socket, collections, hashlib, math, pickle, datetime, re
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcapng_fast

ROUTER = bytes.fromhex("143fc391508c")
SW920 = bytes.fromhex("143fc3910f8b")
BCAST = b"\xff" * 6
STP_DST = bytes.fromhex("0180c2000000")
VLAN_NET = {1: "192.168.1.", 10: "192.168.10.", 20: "192.168.20.", 30: "192.168.30.", 40: "192.168.40.",
            150: "192.168.150.", 200: "192.168.200.", 100: "192.168.100."}
ADGUARD = {"192.168.40.185", "192.168.40.186"}
ADMIN_PORTS = {22: "ssh", 23: "telnet", 3389: "rdp", 5985: "winrm", 5986: "winrm-s", 5900: "vnc", 445: "smb", 139: "netbios-ssn",
               135: "msrpc", 21: "ftp", 8006: "proxmox", 8007: "pbs", 9443: "portainer", 81: "npm-admin", 2222: "ssh-alt"}
DB_PORTS = {1433: "mssql", 3306: "mysql", 5432: "postgres", 6379: "redis", 27017: "mongodb", 9200: "elastic", 8086: "influx",
            1883: "mqtt", 5672: "amqp", 11211: "memcached"}
HTTP_METHODS = (b"GET ", b"POST ", b"PUT ", b"HEAD ", b"DELETE ", b"OPTIONS ", b"PATCH ", b"CONNECT ", b"TRACE ", b"PROPFIND ",
                b"M-SEARCH ", b"NOTIFY ", b"SUBSCRIBE ")
DOH_IPS = {"1.1.1.1", "1.0.0.1", "8.8.8.8", "8.8.4.4", "9.9.9.9", "149.112.112.112", "208.67.222.222", "208.67.220.220",
           "94.140.14.14", "94.140.15.15", "2606:4700:4700::1111", "2001:4860:4860::8888"}

def ip4(b): return socket.inet_ntoa(b)
def ip6(b): return socket.inet_ntop(socket.AF_INET6, b)
def mac(b): return b.hex(":")
def pdt(ts): return (datetime.datetime.fromtimestamp(ts, datetime.timezone.utc) - datetime.timedelta(hours=7)).strftime("%H:%M:%S")
def is_local4(a):
    return a.startswith(("192.168.", "10.", "169.254.", "127.")) or (a.startswith("172.") and 16 <= int(a.split(".")[1]) <= 31) \
        or (a.startswith("100.") and 64 <= int(a.split(".")[1]) <= 127) or a == "0.0.0.0" or a == "255.255.255.255" \
        or 224 <= int(a.split(".")[0]) <= 239
def is_local(a):
    if ":" in a:
        return a.startswith(("fe80", "fd", "fc", "ff", "::"))
    return is_local4(a)
def vlan_of_ip(a):
    for v, p in VLAN_NET.items():
        if a.startswith(p): return v
    return None
def entropy(s):
    if not s: return 0.0
    c = collections.Counter(s); n = len(s)
    return -sum(x / n * math.log2(x / n) for x in c.values())
def grease(x): return (x & 0x0f0f) == 0x0a0a and (x >> 8) == (x & 0xff)

class Refs(collections.defaultdict):
    """key -> list of up to 3 refs"""
    def __init__(self): super().__init__(list)
    def add(self, k, r):
        l = self[k]
        if len(l) < 3: l.append(r)

def parse_tls_hello(p):
    """Return dict for ClientHello/ServerHello in TCP payload p (may be truncated)."""
    if len(p) < 11 or p[0] != 0x16: return None
    hs = p[5]
    o = 9
    if hs == 1:
        r = dict(kind="CH", complete=False, sni=None, alpn=[], sv=[], ciphers=[], exts=[], groups=[], ecpf=[], sigs=[])
        try:
            r["cv"] = struct.unpack_from("!H", p, o)[0]; o += 34
            o += 1 + p[o]
            cl = struct.unpack_from("!H", p, o)[0]; o += 2
            if o + cl > len(p): return r
            r["ciphers"] = [struct.unpack_from("!H", p, o + i)[0] for i in range(0, cl, 2)]; o += cl
            o += 1 + p[o]
            el = struct.unpack_from("!H", p, o)[0]; o += 2; end = o + el
            while o + 4 <= min(end, len(p)):
                t, l = struct.unpack_from("!HH", p, o); o += 4
                if o + l > len(p): r["exts"].append(t); return r
                d = p[o:o + l]
                r["exts"].append(t)
                if t == 0 and l > 5: r["sni"] = d[5:5 + struct.unpack_from("!H", d, 3)[0]].decode("ascii", "replace")
                elif t == 16 and l > 3:
                    q = 2
                    while q < l:
                        n = d[q]; r["alpn"].append(d[q + 1:q + 1 + n].decode("ascii", "replace")); q += 1 + n
                elif t == 43 and l > 1: r["sv"] = [struct.unpack_from("!H", d, 1 + i)[0] for i in range(0, d[0], 2)]
                elif t == 10 and l > 2: r["groups"] = [struct.unpack_from("!H", d, 2 + i)[0] for i in range(0, struct.unpack_from("!H", d, 0)[0], 2)]
                elif t == 11 and l > 1: r["ecpf"] = list(d[1:1 + d[0]])
                elif t == 13 and l > 2: r["sigs"] = [struct.unpack_from("!H", d, 2 + i)[0] for i in range(0, struct.unpack_from("!H", d, 0)[0], 2)]
                o += l
            r["complete"] = (o == end)
        except (struct.error, IndexError):
            pass
        return r
    if hs == 2:
        r = dict(kind="SH")
        try:
            r["v"] = struct.unpack_from("!H", p, o)[0]; o += 34
            o += 1 + p[o]
            r["cipher"] = struct.unpack_from("!H", p, o)[0]; o += 3
            el = struct.unpack_from("!H", p, o)[0]; o += 2; end = o + el
            while o + 4 <= min(end, len(p)):
                t, l = struct.unpack_from("!HH", p, o); o += 4
                if t == 43 and l == 2 and o + 2 <= len(p): r["v"] = struct.unpack_from("!H", p, o)[0]
                o += l
        except (struct.error, IndexError):
            pass
        return r
    return None

def ja3_ja4(r):
    vmap = {0x0304: "13", 0x0303: "12", 0x0302: "11", 0x0301: "10", 0x0300: "s3"}
    ciph = [c for c in r["ciphers"] if not grease(c)]
    exts = [e for e in r["exts"] if not grease(e)]
    grp = [g for g in r["groups"] if not grease(g)]
    ja3s = f"{r.get('cv', 0)},{'-'.join(map(str, ciph))},{'-'.join(map(str, exts))},{'-'.join(map(str, grp))},{'-'.join(map(str, r['ecpf']))}"
    ja3 = hashlib.md5(ja3s.encode()).hexdigest()
    sv = [v for v in r["sv"] if not grease(v)]
    ver = vmap.get(max(sv) if sv else r.get("cv", 0), "00")
    alpn = r["alpn"][0] if r["alpn"] else ""
    a = f"t{ver}{'d' if r['sni'] else 'i'}{min(len(ciph), 99):02d}{min(len(exts), 99):02d}{(alpn[0] + alpn[-1]) if alpn else '00'}"
    b = hashlib.sha256(",".join(sorted(f"{c:04x}" for c in ciph)).encode()).hexdigest()[:12]
    ce = ",".join(sorted(f"{e:04x}" for e in exts if e not in (0, 16)))
    sg = ",".join(f"{s:04x}" for s in r["sigs"])
    c = hashlib.sha256((ce + ("_" + sg if sg else "")).encode()).hexdigest()[:12]
    return ja3, f"{a}_{b}_{c}"

def dns_parse(p):
    """Header + first question + (for responses) rough answers. Tolerates truncation."""
    if len(p) < 12: return None
    tid, fl, qd, an, ns, ar = struct.unpack_from("!HHHHHH", p, 0)
    r = dict(id=tid, qr=fl >> 15, op=(fl >> 11) & 0xf, aa=(fl >> 10) & 1, tc=(fl >> 9) & 1, rd=(fl >> 8) & 1, ra=(fl >> 7) & 1,
             ad=(fl >> 5) & 1, cd=(fl >> 4) & 1, rcode=fl & 0xf, qd=qd, an=an, ns=ns, ar=ar, q=None, qt=None, ans=[], edns=None, do=0)
    def name(o, depth=0):
        labels = []
        while o < len(p):
            l = p[o]
            if l == 0: return ".".join(labels), o + 1
            if l & 0xc0 == 0xc0:
                if depth > 5 or o + 1 >= len(p): return ".".join(labels), o + 2
                ptr = ((l & 0x3f) << 8) | p[o + 1]
                n2, _ = name(ptr, depth + 1)
                return ".".join(labels + ([n2] if n2 else [])), o + 2
            labels.append(p[o + 1:o + 1 + l].decode("ascii", "replace")); o += 1 + l
        raise IndexError
    try:
        o = 12
        if qd:
            r["q"], o = name(o)
            r["qt"] = struct.unpack_from("!H", p, o)[0]; o += 4
        for sect, cnt in (("an", an), ("ns", ns), ("ar", ar)):
            for _ in range(cnt):
                nm, o = name(o)
                t, c, ttl, rl = struct.unpack_from("!HHIH", p, o); o += 10
                if o + rl > len(p): raise IndexError
                d = p[o:o + rl]; o += rl
                if t == 41:
                    r["edns"] = c; r["do"] = (ttl >> 15) & 1
                elif sect == "an":
                    if t == 1 and rl == 4: r["ans"].append((t, nm, ip4(d), ttl))
                    elif t == 28 and rl == 16: r["ans"].append((t, nm, ip6(d), ttl))
                    elif t == 16: r["ans"].append((t, nm, rl, ttl))
                    elif t == 5: r["ans"].append((t, nm, None, ttl))
    except (IndexError, struct.error):
        r["trunc"] = True
    return r

def new():
    D = collections.defaultdict
    C = collections.Counter
    return dict(
        n=0, bytes=0, cap=0, first=None, last=None, maxlen=0, lens=C(),
        persec=C(), persecb=C(), vlan_p=C(), vlan_b=C(), cast=C(), castb=C(), etype=C(), mac_vlans=D(set), srcmac=C(),
        bc_src=C(), bc_persec=C(), rtr_bc_persec=C(), mc_dst=C(),
        arp_op=C(), arp_req_src=C(), arp_rep_src=C(), garp=C(), arp_probe=C(), ip2mac=D(C), rtr_arp_min=C(),
        rtr_arp_tgt=D(C), arp_answered=D(set), arp_unsol_rep=C(), arp_storm_sec=C(),
        stp=C(), stp_tc=C(), stp_refs=Refs(), dup=C(), dup_src=C(), dup_refs=Refs(),
        ip4=0, ip4b=0, ip6=0, ip6b=0, frag=C(), frag_refs=Refs(), frag_overlap=0, frag_tiny=0, frag_df_mf=0,
        ttl=D(C), loop=C(), loop_refs=Refs(), ecn=C(), ipopt=C(),
        icmp=C(), icmp_detail=C(), icmp_refs=Refs(), echo=C(), echo_big=C(), echo_ts=D(list), icmp6=C(), ra=C(), ra_refs=Refs(),
        l4=C(), l4b=C(), tcpflags=C(), tcp_anom_refs=Refs(),
        conv=D(lambda: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0.0, 0.0]),  # see CONV_FIELDS
        hs_rtt=D(list), syn_unans=C(), syn_retry=C(), synack_unacked=C(), rst_src=C(), rst_pair=C(),
        mss=C(), mss_src=D(C), wscale=C(), sackperm=C(), tsopt=C(), ecn_setup=C(),
        cls=D(lambda: [0, 0, 0, 0, 0, 0, 0]),  # class -> data,retrans,fast,ooo,gap,dupack,zerowin
        bigflows=[],
        http=C(), http_refs=Refs(), http_auth=C(), http_status=C(), http_lat=D(list), http_ua=C(),
        tls_ch=C(), tls_sni=C(), tls_ja=C(), tls_ver=C(), tls_sh=C(), tls_nonstd=C(), tls_cov=C(), ssh=C(),
        smb=C(), ntlm=C(), krb=C(), telnet=C(), ftp=C(), snmp=C(), dbq=C(), admin=D(lambda: [0, 0, 0, 0, 0.0]),
        udp=C(), udpb=C(), udp_flows=D(lambda: [0, 0, 0.0, 0.0]),
        dns_q=0, dns_r=0, dns_rcode=C(), dns_qt=C(), dns_srv=C(), dns_lat=D(list), dns_unans=C(), dns_bypass=C(), dns_bypass_refs=Refs(),
        dns_nx=C(), dns_client=C(), dns_name=C(), dns_edns=C(), dns_do=0, dns_ad=0, dns_tc=0, dns_txt=C(), dns_long=C(), dns_long_refs=Refs(),
        dns_sub=D(set), ipname={}, dns_qts=D(list), doh=C(), dot=C(),
        mdns=C(), mdns_big=C(), ssdp=C(), sddp=C(), llmnr=C(), nbns=C(), wsd=C(),
        dhcp=[], ntp=C(), ntp_off=D(list), ntp_odd=C(),
        syn_ts=D(list), udp_ts=D(list), hscan=D(set), vscan=D(set), uscan=D(set), escan=D(set),
        gaps=[], files=[])

CONV_FIELDS = ["pkts", "bytes", "data_segs", "retrans", "fast", "ooo", "gap", "dupack", "zerowin", "keepalive", "psh", "first", "last"]

def work(path):
    R = new()
    chunk = "c" + os.path.basename(path).split("_")[2].lstrip("0")
    R["files"].append(os.path.basename(path))
    tcpst = {}          # (vlan,src,sport,dst,dport) -> state list
    hs = {}             # (vlan,cli,cport,srv,sport) -> [syn_ts, synack_ts, nsyn, ref]
    dnsq = {}           # (vlan,client,cport,id) -> (ts, server, qname, ref)
    httpq = {}          # flowkey -> (ts)
    seen = {}           # dup detection
    loopk = {}          # loop detection
    frags = {}
    udpsess = {}
    echo_last = {}
    lastts = None
    for fr, ts, ol, d in pcapng_fast.read(path):
        R["n"] += 1; R["bytes"] += ol; R["cap"] += len(d)
        if R["first"] is None: R["first"] = ts
        if lastts is not None and ts - lastts > 5: R["gaps"].append((pdt(lastts), round(ts - lastts, 1), f"{chunk}#{fr}"))
        lastts = ts; R["last"] = ts
        if ol > R["maxlen"]: R["maxlen"] = ol
        R["lens"][min(ol, 1600) // 100 * 100] += 1
        sec = int(ts); R["persec"][sec] += 1; R["persecb"][sec] += ol
        ref = f"{chunk}#{fr}@{pdt(ts)}"
        if len(d) < 14: continue
        dst = d[0:6]; src = d[6:12]
        et = struct.unpack_from("!H", d, 12)[0]; o = 14; v = 1
        if et == 0x8100 or et == 0x88a8:
            v = struct.unpack_from("!H", d, 14)[0] & 0xfff; et = struct.unpack_from("!H", d, 16)[0]; o = 18
            if et == 0x8100:
                et = struct.unpack_from("!H", d, 20)[0]; o = 22
        R["vlan_p"][v] += 1; R["vlan_b"][v] += ol
        smac = mac(src)
        R["srcmac"][smac] += 1
        R["mac_vlans"][smac].add(v)
        cast = "bc" if dst == BCAST else ("mc" if dst[0] & 1 else "uc")
        R["cast"][(v, cast)] += 1; R["castb"][(v, cast)] += ol
        if cast != "uc":
            R["bc_src"][(v, smac, cast)] += 1
            R["mc_dst"][(v, mac(dst))] += 1
            if cast == "bc":
                R["bc_persec"][(sec, v)] += 1
                if src == ROUTER: R["rtr_bc_persec"][sec] += 1
        R["etype"][et if et >= 0x600 else "llc"] += 1
        # exact duplicate frames on same VLAN within 200 ms (loop / mirror duplication evidence)
        h = hashlib.blake2b(d, digest_size=12).digest()
        prev = seen.get(h)
        if prev is not None and ts - prev < 0.2:
            R["dup"][v] += 1; R["dup_src"][(v, smac)] += 1; R["dup_refs"].add((v, smac), ref)
        seen[h] = ts
        if len(seen) > 400000: seen.clear()
        # ---------------- L2: STP
        if et < 0x600:
            if dst == STP_DST and len(d) >= o + 3 + 35 and d[o] == 0x42:
                b = d[o + 3:]
                ver, typ = b[2], b[3]
                if typ in (0x00, 0x02):
                    flags = b[4]; root = b[5:13].hex(); cost = struct.unpack_from("!I", b, 13)[0]; brid = b[17:25].hex()
                    port = struct.unpack_from("!H", b, 25)[0]; mage, hello, fwd = [struct.unpack_from("!H", b, x)[0] / 256 for x in (29, 31, 33)]
                    R["stp"][(smac, v, ver, root, brid, cost, port, mage, hello, fwd)] += 1
                    if flags & 1:
                        R["stp_tc"][(smac, v)] += 1; R["stp_refs"].add((smac, v), ref)
                else:
                    R["stp"][(smac, v, ver, "TCN", "", 0, 0, 0, 0, 0)] += 1; R["stp_tc"][(smac, v, "TCN")] += 1
            continue
        # ---------------- ARP
        if et == 0x0806:
            if len(d) < o + 28: continue
            op = struct.unpack_from("!H", d, o + 6)[0]
            sha = mac(d[o + 8:o + 14]); spa = ip4(d[o + 14:o + 18]); tpa = ip4(d[o + 24:o + 28])
            R["arp_op"][(v, op)] += 1
            R["arp_storm_sec"][(sec, v)] += 1
            if sha != smac: R["tcp_anom_refs"].add(("arp-sha-mismatch", smac, sha), ref); R["tcpflags"][("ARP sha!=eth.src", smac, sha)] += 1
            if spa == "0.0.0.0": R["arp_probe"][(v, sha, tpa)] += 1
            else: R["ip2mac"][(v, spa)][sha] += 1
            if spa == tpa and spa != "0.0.0.0": R["garp"][(v, sha, spa, op)] += 1
            if op == 1:
                R["arp_req_src"][(v, smac)] += 1
                if src == ROUTER:
                    R["rtr_arp_min"][(sec // 60, v)] += 1; R["rtr_arp_tgt"][v][tpa] += 1
            elif op == 2:
                R["arp_rep_src"][(v, smac)] += 1
                if dst == ROUTER: R["arp_answered"][v].add(spa)
                if dst == BCAST and spa != tpa: R["arp_unsol_rep"][(v, sha, spa)] += 1
            continue
        # ---------------- IP
        if et == 0x0800:
            if len(d) < o + 20: continue
            vihl = d[o]; ihl = (vihl & 0xf) * 4
            tos, tlen, ipid, ffo, ttl, proto = struct.unpack_from("!BHHHBB", d, o + 1)
            s = ip4(d[o + 12:o + 16]); t = ip4(d[o + 16:o + 20])
            R["ip4"] += 1; R["ip4b"] += ol
            if tos & 3: R["ecn"][tos & 3] += 1
            if ihl > 20: R["ipopt"][(s, t, d[o + 20] if len(d) > o + 20 else -1)] += 1
            df = ffo & 0x4000; mf = ffo & 0x2000; foff = (ffo & 0x1fff) * 8
            if mf or foff:
                R["frag"][(v, s, t, proto)] += 1; R["frag_refs"].add((v, s, t, proto), ref)
                if df: R["frag_df_mf"] += 1
                if foff == 0 and mf and tlen - ihl < 24 and proto == 6: R["frag_tiny"] += 1
                fk = (v, s, t, ipid, proto); lst = frags.setdefault(fk, [])
                a0, a1 = foff, foff + tlen - ihl
                for b0, b1 in lst:
                    if a0 < b1 and b0 < a1: R["frag_overlap"] += 1; R["frag_refs"].add(("overlap", s, t), ref); break
                lst.append((a0, a1))
                if len(frags) > 50000: frags.clear()
            R["ttl"][(v, s)][ttl] += 1
            # routing-loop detection: same IP datagram seen >=3x, or twice on the same VLAN with lower TTL
            if ipid and not (mf or foff):
                lk = (s, t, ipid, proto, tlen)
                e = loopk.get(lk)
                if e and ts - e[0] < 2.0:
                    e[1].append((v, ttl))
                    if len(e[1]) == 3 or (len(e[1]) == 2 and e[1][0][0] == v and e[1][0][1] != ttl):
                        R["loop"][(s, t, proto)] += 1; R["loop_refs"].add((s, t, proto), ref + f" seq={e[1]}")
                else:
                    loopk[lk] = [ts, [(v, ttl)]]
                if len(loopk) > 300000: loopk.clear()
            if foff: continue
            l4o = o + ihl
            plen_ip = tlen - ihl
            src_s, dst_s = s, t
        elif et == 0x86dd:
            if len(d) < o + 40: continue
            plen, nh, hl = struct.unpack_from("!HBB", d, o + 4)
            s = ip6(d[o + 8:o + 24]); t = ip6(d[o + 24:o + 40])
            R["ip6"] += 1; R["ip6b"] += ol
            R["ttl"][(v, s)][hl] += 1
            l4o = o + 40; proto = nh
            while proto in (0, 43, 60, 44) and l4o + 8 <= len(d):
                if proto == 44: R["frag"][(v, s, t, d[l4o])] += 1
                proto = d[l4o]; l4o += 8 if proto == 44 else (d[l4o + 1] + 1) * 8
            plen_ip = plen - (l4o - o - 40)
            src_s, dst_s = s, t
            ipid = 0
        else:
            continue
        s, t = src_s, dst_s
        sl, tl_ = is_local(s), is_local(t)
        ingress = src != ROUTER
        # ---------------- ICMP
        if proto == 1 and len(d) >= l4o + 8:
            ty, co = d[l4o], d[l4o + 1]
            R["icmp"][(ty, co)] += 1
            if ty in (3, 5, 11, 12):
                io = l4o + 8; inner = ("?", "?", 0, 0)
                if len(d) >= io + 20:
                    ih = (d[io] & 0xf) * 4; ip_ = d[io + 9]
                    dp = struct.unpack_from("!H", d, io + ih + 2)[0] if len(d) >= io + ih + 4 and ip_ in (6, 17) else 0
                    inner = (ip4(d[io + 12:io + 16]), ip4(d[io + 16:io + 20]), ip_, dp)
                mtu = struct.unpack_from("!H", d, l4o + 6)[0] if (ty, co) == (3, 4) else None
                gw = ip4(d[l4o + 4:l4o + 8]) if ty == 5 else None
                k = (v, s, ty, co) + inner + (mtu, gw)
                R["icmp_detail"][k] += 1; R["icmp_refs"].add((ty, co, s), ref)
            elif ty in (0, 8):
                dl = plen_ip - 8
                R["echo"][(v, s, t, ty)] += 1
                if dl > 120: R["echo_big"][(s, t, ty, dl)] += 1
                if ty == 8:
                    k = (s, t); lt = echo_last.get(k)
                    if lt is None or ts - lt > 0.9: R["echo_ts"][k].append(ts)
                    echo_last[k] = ts
                    R["escan"][s].add(t)
            continue
        if proto == 58 and len(d) >= l4o + 4:
            ty, co = d[l4o], d[l4o + 1]
            R["icmp6"][(ty, co)] += 1
            if ty == 134:
                pref = []
                q = l4o + 16
                while q + 8 <= len(d):
                    ot, ol8 = d[q], d[q + 1] * 8
                    if ol8 == 0: break
                    if ot == 3 and q + 32 <= len(d): pref.append(ip6(d[q + 16:q + 32]) + "/" + str(d[q + 2]))
                    q += ol8
                R["ra"][(v, smac, s, d[l4o + 5], tuple(pref))] += 1; R["ra_refs"].add((v, smac, s), ref)
            continue
        # ---------------- TCP
        if proto == 6 and len(d) >= l4o + 20:
            sp, dp, seq, ack, offf, win = struct.unpack_from("!HHIIHH", d, l4o)
            thl = (offf >> 12) * 4; fl = offf & 0x1ff
            pl = plen_ip - thl
            if pl < 0: pl = 0
            R["l4"][("tcp", v)] += 1; R["l4b"][("tcp", v)] += ol
            SYN, ACK, FIN, RST, PSH, URG, ECE, CWR = fl & 2, fl & 16, fl & 1, fl & 4, fl & 8, fl & 32, fl & 64, fl & 128
            fstr = "".join(c for c, b in (("S", SYN), ("A", ACK), ("F", FIN), ("R", RST), ("P", PSH), ("U", URG), ("E", ECE), ("C", CWR)) if b)
            R["tcpflags"][fstr or "NULL"] += 1
            anom = None
            if fl & 0x3f == 0: anom = "NULL"
            elif FIN and PSH and URG: anom = "XMAS(FPU)"
            elif SYN and FIN: anom = "SYN+FIN"
            elif SYN and RST: anom = "SYN+RST"
            elif FIN and not ACK: anom = "FIN-noACK"
            elif URG: anom = "URG"
            if anom: R["tcp_anom_refs"].add((anom, s, t, dp), ref); R["tcpflags"][("ANOM", anom, s, t, dp)] += 1
            if ECE or CWR:
                R["ecn_setup"][(fstr, s if SYN else "-")] += 1
            # options on SYN
            if SYN:
                q = l4o + 20; e = min(l4o + thl, len(d))
                while q < e:
                    k = d[q]
                    if k == 0: break
                    if k == 1: q += 1; continue
                    if q + 1 >= e: break
                    ln = d[q + 1]
                    if ln < 2: break
                    if k == 2 and ln == 4: m = struct.unpack_from("!H", d, q + 2)[0]; R["mss"][(m, "SA" if ACK else "S")] += 1; R["mss_src"][s][m] += 1
                    elif k == 3 and ln == 3: R["wscale"][d[q + 2]] += 1
                    elif k == 4: R["sackperm"][1] += 1
                    elif k == 8: R["tsopt"][1] += 1
                    q += ln
            fk = (v, s, sp, t, dp)
            st = tcpst.get(fk)
            if st is None:
                # [max_end, last_ts_maxend, recent_seqs(list), last_ack, last_win, dupcnt, cum_acked, last_ack_seen, pkts, bytes, first, last,
                #  data, retrans, fast, ooo, gap, dupack, zerowin, keepalive, psh, synseen, maxwin, wsc, svcport, rst]
                st = [None, 0.0, [], None, None, 0, 0, None, 0, 0, ts, ts, 0, 0, 0, 0, 0, 0, 0, 0, 0, bool(SYN), 0, None, None, 0]
                tcpst[fk] = st
                if len(tcpst) > 400000:
                    _flush_tcp(R, tcpst, chunk); tcpst.clear(); tcpst[fk] = st
            st[8] += 1; st[9] += ol; st[11] = ts
            if PSH: st[20] += 1
            if RST: st[25] += 1; R["rst_src"][(s, sp if sp < dp else dp)] += 1; R["rst_pair"][(s, t, dp, sp)] += 1
            if win > st[22]: st[22] = win
            if win == 0 and not RST and not SYN: st[18] += 1
            # service port
            if st[24] is None:
                st[24] = dp if SYN and not ACK else (sp if SYN and ACK else (dp if dp < sp else sp))
            # a SYN starts a new connection on this 5-tuple (ports get reused): drop the old sequence/ACK state
            if SYN:
                st[0] = None; st[1] = 0.0; st[2] = []; st[3] = None; st[4] = None; st[5] = 0; st[7] = None
            # handshake
            if SYN and not ACK:
                hk = (v, s, sp, t, dp)
                h0 = hs.get(hk)
                if h0 is not None and h0[1] is None and ts - h0[0] < 75:
                    # SYN retransmission (backoff 1, 2, 4, 8, 16, 32 s) of an unanswered attempt
                    h0[2] += 1
                    R["syn_retry"][(s, t, dp)] += 1
                else:
                    if h0 is not None:
                        _close_hs(R, hk, h0)
                    hs[hk] = [ts, None, 1, ref]
                    R["syn_ts"][(s, t, dp)].append(ts)
                    R["hscan"][(s, dp)].add(t); R["vscan"][(s, t)].add(dp)
            elif SYN and ACK:
                hk = (v, t, dp, s, sp)
                h0 = hs.get(hk)
                if h0 and h0[1] is None: h0[1] = ts
            elif ACK and not (SYN or RST):
                hk = (v, s, sp, t, dp)
                h0 = hs.get(hk)
                if h0 and h0[1] is not None and len(h0) == 4:
                    cls = "lan" if (sl and tl_) else "wan"
                    R["hs_rtt"][(cls, t, dp)].append((h0[1] - h0[0], ts - h0[1]))
                    h0.append(ts)
            # ack-advance accounting (bytes the peer delivered); RST/SYN carry no usable ACK baseline
            if RST:
                st[7] = None
            elif ACK:
                if st[7] is not None:
                    dlt = (ack - st[7]) & 0xffffffff
                    if dlt < 0x80000000:
                        if dlt < 16_000_000: st[6] += dlt
                        st[7] = ack
                else:
                    st[7] = ack
            # sequence analysis
            if pl > 0:
                st[12] += 1
                end = (seq + pl) & 0xffffffff
                me = st[0]
                cls = ("lan" if (sl and tl_) else "wan") + ("" if ingress else "-egress")
                cr = R["cls"][cls]
                cr[0] += 1
                if me is None:
                    st[0] = end; st[1] = ts
                else:
                    behind = (me - end) & 0xffffffff
                    if behind < 0x80000000:  # end <= max_end -> old data
                        if pl == 1 and ((me - seq) & 0xffffffff) == 1:
                            st[19] += 1
                        elif seq in st[2]:
                            st[13] += 1; cr[1] += 1
                            rev = tcpst.get((v, t, dp, s, sp))
                            if rev is not None and rev[3] == seq and rev[5] >= 2: st[14] += 1; cr[2] += 1
                        elif ts - st[1] < 0.003:
                            st[15] += 1; cr[3] += 1
                        else:
                            st[13] += 1; cr[1] += 1
                    else:
                        ahead = (seq - me) & 0xffffffff
                        if 0 < ahead < 0x80000000: st[16] += 1; cr[4] += 1
                        st[0] = end; st[1] = ts
                rs = st[2]; rs.append(seq)
                if len(rs) > 48: del rs[:16]
            elif ACK and not (SYN or FIN or RST):
                if st[3] == ack and st[4] == win:
                    st[5] += 1
                    if st[5] >= 1: st[17] += 1
                    if st[5] == 1: pass
                else:
                    st[5] = 0
                cls = ("lan" if (sl and tl_) else "wan") + ("" if ingress else "-egress")
                if st[5] >= 1: R["cls"][cls][5] += 1
                if win == 0: R["cls"][cls][6] += 1
            st[3] = ack; st[4] = win
            # ---- application layer peeks
            po = l4o + thl
            p = d[po:]
            if p and pl > 0:
                svc = dp if dp < sp else sp
                if p.startswith(HTTP_METHODS):
                    line = p.split(b"\r\n", 1)[0][:200].decode("latin1", "replace")
                    meth = line.split(" ", 1)[0]
                    host = ua = auth = ""
                    for hl_ in p.split(b"\r\n")[1:40]:
                        ll = hl_.lower()
                        if ll.startswith(b"host:"): host = hl_[5:].strip().decode("latin1", "replace")
                        elif ll.startswith(b"user-agent:"): ua = hl_[11:].strip().decode("latin1", "replace")[:90]
                        elif ll.startswith(b"authorization:"): auth = hl_[14:].strip().split(b" ")[0].decode("latin1", "replace")
                    path = line.split(" ")[1][:60] if " " in line else ""
                    path = re.sub(r"(?i)(token|key|password|passwd|secret|auth|sig)=[^&]*", r"\1=<redacted>", path)
                    R["http"][(meth, s, t, dp, host, path)] += 1; R["http_refs"].add((meth, s, t, dp, host), ref)
                    R["http_ua"][(ua, s)] += 1
                    if auth: R["http_auth"][(auth, s, t, dp, host)] += 1; R["http_refs"].add(("AUTH", auth, s, t, dp), ref)
                    httpq[(v, s, sp, t, dp)] = ts
                elif p.startswith(b"HTTP/1."):
                    code = p[9:12].decode("latin1", "replace")
                    R["http_status"][(s, sp, code)] += 1
                    q0 = httpq.pop((v, t, dp, s, sp), None)
                    if q0: R["http_lat"][(s, sp)].append(ts - q0)
                elif p[0] == 0x16 and len(p) > 5 and p[1] == 3:
                    r = parse_tls_hello(p)
                    if r and r["kind"] == "CH":
                        R["tls_cov"][("CH", "complete" if r["complete"] else "truncated")] += 1
                        sni = r["sni"] or "-"
                        R["tls_sni"][(s, sni, dp)] += 1
                        if dp not in (443, 8443, 853, 993, 995, 465, 5223, 8883, 636, 9443, 4433):
                            R["tls_nonstd"][(s, t, dp, sni)] += 1
                        if r["complete"]:
                            ja3, ja4 = ja3_ja4(r)
                            R["tls_ja"][(ja4, ja3, s, sni if len(sni) < 60 else sni[:60])] += 1
                            sv = [x for x in r["sv"] if not grease(x)]
                            R["tls_ver"][("offer-max", hex(max(sv) if sv else r.get("cv", 0)))] += 1
                            R["tls_ch"][("weak-cipher-offered", any(c in (0x0004, 0x0005, 0x000a, 0x002f, 0x0035, 0x003c, 0x003d) or c < 0x0010 for c in r["ciphers"]))] += 1
                            if not sv or max(sv) < 0x0304: R["tls_ch"][("no-tls13", s, sni)] += 1
                    elif r and r["kind"] == "SH":
                        R["tls_sh"][(s, sp, hex(r.get("v", 0)), hex(r.get("cipher", 0)))] += 1
                elif p.startswith(b"SSH-"):
                    R["ssh"][(s, sp, dp, p.split(b"\r\n")[0][:60].decode("latin1", "replace"))] += 1
                if svc in (445, 139):
                    q = p[4:] if len(p) > 8 else b""
                    if q.startswith(b"\xffSMB"): R["smb"][("SMB1", s, t)] += 1; R["tcp_anom_refs"].add(("SMB1", s, t, svc), ref)
                    elif q.startswith(b"\xfeSMB") and len(q) >= 64:
                        cmd = struct.unpack_from("<H", q, 12)[0]; resp = struct.unpack_from("<I", q, 16)[0] & 1
                        if cmd == 0 and not resp and len(q) >= 100:
                            nd = struct.unpack_from("<H", q, 66)[0]
                            dl = [hex(struct.unpack_from("<H", q, 100 + 2 * i)[0]) for i in range(nd) if 100 + 2 * i + 2 <= len(q)]
                            R["smb"][("NEG-req", s, t, tuple(dl))] += 1
                        elif cmd == 0 and resp and len(q) >= 70:
                            R["smb"][("NEG-resp", s, t, hex(struct.unpack_from("<H", q, 68)[0]))] += 1
                        else:
                            R["smb"][("cmd", s, t, cmd)] += 1
                    if b"I\x00P\x00C\x00$\x00" in p: R["smb"][("IPC$", s, t)] += 1
                i = p.find(b"NTLMSSP\x00")
                if i >= 0 and len(p) >= i + 12:
                    mt = struct.unpack_from("<I", p, i + 8)[0]
                    ntl = struct.unpack_from("<H", p, i + 20)[0] if mt == 3 and len(p) >= i + 22 else None
                    R["ntlm"][(s, t, svc, mt, "NTLMv1" if ntl == 24 else ("NTLMv2" if ntl else "-"))] += 1
                if svc == 88: R["krb"][("tcp", s, t, p[4] if len(p) > 4 else -1)] += 1
                if svc == 23:
                    R["telnet"][(s, t, "server" if sp == 23 else "client")] += 1
                    if sp == 23 and (b"ogin:" in p or b"sername" in p): R["telnet"][(s, t, "login-prompt")] += 1
                    if sp == 23 and b"assword" in p: R["telnet"][(s, t, "password-prompt")] += 1; R["tcp_anom_refs"].add(("telnet-password-prompt", s, t, 23), ref)
                if svc == 21:
                    if p.startswith((b"USER ", b"PASS ")): R["ftp"][(s, t, p[:4].decode())] += 1
                if svc in DB_PORTS:
                    up = p[:200].upper()
                    if any(k in up for k in (b"SELECT ", b"INSERT ", b"UPDATE ", b"DELETE ", b"CREATE ", b"DROP ")):
                        R["dbq"][(DB_PORTS[svc], s, t)] += 1
            if svc_admin := (dp if dp in ADMIN_PORTS else (sp if sp in ADMIN_PORTS else None)):
                a = R["admin"][(s if dp == svc_admin else t, t if dp == svc_admin else s, svc_admin)]
                if SYN and not ACK and dp == svc_admin: a[0] += 1
                if SYN and ACK and sp == svc_admin: a[1] += 1
                if RST: a[2] += 1
                a[3] += ol
            if dp == 853: R["dot"][(v, s, t)] += 1
            if dp == 443 and t in DOH_IPS and SYN and not ACK: R["doh"][(v, s, t)] += 1
            if dp == 53 and SYN and not ACK: R["dns_srv"][("tcp", t)] += 1
            continue
        # ---------------- UDP
        if proto == 17 and len(d) >= l4o + 8:
            sp, dp, ulen = struct.unpack_from("!HHH", d, l4o)
            R["l4"][("udp", v)] += 1; R["l4b"][("udp", v)] += ol
            svc = dp if dp < sp else sp
            if dp in (53, 5353, 1900, 1902, 67, 68, 123, 137, 138, 5355, 3702, 161, 162, 514, 4789, 41641, 51820, 443, 3478, 8009) or sp in (53, 123, 67, 161, 443, 41641, 51820, 4789):
                svc = dp if dp in (53, 5353, 1900, 1902, 67, 68, 123, 137, 138, 5355, 3702, 161, 162, 514, 4789, 41641, 51820, 443, 3478, 8009) else sp
            R["udp"][(svc, v)] += 1; R["udpb"][(svc, v)] += ol
            p = d[l4o + 8:]
            uf = R["udp_flows"][(s, t, dp if dp == svc else sp, v)]
            uf[0] += 1; uf[1] += ol
            if uf[2] == 0: uf[2] = ts
            uf[3] = ts
            # session starts for beaconing (unicast only)
            if cast == "uc" and svc not in (53, 5353, 1900, 1902):
                sk = (s, sp, t, dp); lt = udpsess.get(sk)
                if lt is None or ts - lt > 60: R["udp_ts"][(s, t, dp if dp == svc else sp)].append(ts)
                udpsess[sk] = ts
                R["uscan"][(s, t)].add(dp)
            if svc == 53 and (dp == 53 or sp == 53):
                r = dns_parse(p)
                if r is None: continue
                if r["qr"] == 0:
                    R["dns_q"] += 1
                    R["dns_qt"][r["qt"]] += 1; R["dns_client"][(v, s)] += 1; R["dns_srv"][("udp", t)] += 1
                    q = (r["q"] or "").lower()
                    R["dns_name"][q] += 1
                    if r["edns"] is not None: R["dns_edns"][("q-edns", r["edns"])] += 1
                    if r["do"]: R["dns_do"] += 1
                    if r["qt"] in (16, 10): R["dns_txt"][(s, q, r["qt"])] += 1
                    labels = q.split(".")
                    base = ".".join(labels[-2:]) if len(labels) >= 2 else q
                    if len(labels) > 2: R["dns_sub"][base].add(labels[0][:63])
                    mx = max((len(x) for x in labels), default=0)
                    if mx > 40 or len(q) > 120 or (len(labels[0]) > 20 and entropy(labels[0]) > 3.8):
                        R["dns_long"][(s, base, mx, round(entropy(labels[0]), 2))] += 1; R["dns_long_refs"].add((s, base), ref + " " + q[:90])
                    if t not in ADGUARD and not t.startswith("192.168.") and src != ROUTER:
                        R["dns_bypass"][(v, s, t)] += 1; R["dns_bypass_refs"].add((v, s, t), ref)
                    key = (s, sp, r["id"])
                    dnsq[(v,) + key] = (ts, t, q, ref)
                    if len(R["dns_qts"][(s, q)]) < 4000: R["dns_qts"][(s, q)].append(ts)
                    if len(dnsq) > 300000: dnsq.clear()
                else:
                    R["dns_r"] += 1
                    R["dns_rcode"][r["rcode"]] += 1
                    if r["ad"]: R["dns_ad"] += 1
                    if r["tc"]: R["dns_tc"] += 1
                    if r["rcode"] == 3: R["dns_nx"][(t, (r["q"] or "").lower())] += 1
                    for a in r["ans"]:
                        if a[0] in (1, 28) and a[2] not in R["ipname"]: R["ipname"][a[2]] = (r["q"] or a[1]).lower()
                        if a[0] == 16: R["dns_txt"][(t, (r["q"] or "").lower(), "TXT-resp", ol)] += 1
                    q0 = dnsq.pop((v, t, dp, r["id"]), None)
                    if q0: R["dns_lat"][(q0[1], "lan" if q0[1].startswith("192.168.") else "ext")].append(ts - q0[0])
                continue
            if svc == 5353:
                R["mdns"][(v, s)] += 1
                if ol > 1500 or (ulen > 1472): R["mdns_big"][(v, s)] += 1
                continue
            if svc == 1900: R["ssdp"][(v, s, t)] += 1; continue
            if svc == 1902: R["sddp"][(v, s, t)] += 1; continue
            if svc == 5355: R["llmnr"][(v, s)] += 1; continue
            if svc in (137, 138): R["nbns"][(v, s, svc)] += 1; continue
            if svc == 3702: R["wsd"][(v, s)] += 1; continue
            if svc in (67, 68) and len(p) >= 240 and p[236:240] == b"\x63\x82\x53\x63":
                op_, xid = p[0], struct.unpack_from("!I", p, 4)[0]
                ci, yi = ip4(p[12:16]), ip4(p[16:20]); ch = mac(p[28:34])
                opts = {}; q = 240
                while q < len(p) and p[q] != 255:
                    if p[q] == 0: q += 1; continue
                    if q + 1 >= len(p): break
                    c, l = p[q], p[q + 1]; opts[c] = p[q + 2:q + 2 + l]; q += 2 + l
                mt = opts.get(53, b"\x00")[0]
                R["dhcp"].append(dict(ts=ts, ref=ref, v=v, mt=mt, xid=xid, ch=ch, ci=ci, yi=yi, src=s, smac=smac,
                                      sid=ip4(opts[54]) if len(opts.get(54, b"")) == 4 else None,
                                      req=ip4(opts[50]) if len(opts.get(50, b"")) == 4 else None,
                                      host=opts.get(12, b"").decode("latin1", "replace")[:40],
                                      vc=opts.get(60, b"").decode("latin1", "replace")[:40],
                                      dns=[ip4(opts[6][i:i + 4]) for i in range(0, len(opts.get(6, b"")) // 4 * 4, 4)],
                                      rtr=ip4(opts[3][:4]) if len(opts.get(3, b"")) >= 4 else None,
                                      lease=struct.unpack("!I", opts[51])[0] if len(opts.get(51, b"")) == 4 else None,
                                      dom=opts.get(15, b"").decode("latin1", "replace"), o42=bool(opts.get(42)), o119=bool(opts.get(119)),
                                      prl=list(opts.get(55, b""))))
                continue
            if svc == 123 and len(p) >= 48:
                li, vn, mode = p[0] >> 6, (p[0] >> 3) & 7, p[0] & 7
                strat = p[1]
                refid = ip4(p[12:16]) if strat >= 2 else p[12:16].decode("latin1", "replace").strip("\x00")
                R["ntp"][(v, s, t, mode, strat, vn, li, refid if mode == 4 else "")] += 1
                if ulen - 8 != 48: R["ntp_odd"][(s, t, ulen - 8)] += 1
                if mode == 4:
                    txs, txf = struct.unpack_from("!II", p, 40)
                    if txs: R["ntp_off"][s].append((txs - 2208988800 + txf / 2**32) - ts)
                continue
            if svc == 161 and len(p) > 7 and p[0] == 0x30:
                try:
                    q = 2 if p[1] < 0x80 else 2 + (p[1] & 0x7f)
                    if p[q] == 2:
                        ver = p[q + 2]; q += 3
                        if p[q] == 4:
                            cl = p[q + 1]; comm = p[q + 2:q + 2 + cl]
                            R["snmp"][(s, t, {0: "v1", 1: "v2c", 3: "v3"}.get(ver, ver), hashlib.sha256(comm).hexdigest()[:12] if ver != 3 else "-", len(comm))] += 1
                except IndexError:
                    pass
                continue
            if svc == 88: R["krb"][("udp", s, t, p[0] if p else -1)] += 1
            continue
    _flush_tcp(R, tcpst, chunk)
    # handshake summaries: SYN never answered / SYN-ACK never acked
    for hk, h0 in hs.items():
        _close_hs(R, hk, h0)
    # convert sets to sizes where big
    R["hscan"] = {k: len(x) if len(x) > 20 else x for k, x in R["hscan"].items()}
    R["vscan"] = {k: len(x) if len(x) > 20 else x for k, x in R["vscan"].items()}
    R["uscan"] = {k: len(x) if len(x) > 20 else x for k, x in R["uscan"].items()}
    R["escan"] = {k: len(x) if len(x) > 20 else x for k, x in R["escan"].items()}
    R["arp_answered"] = {k: x for k, x in R["arp_answered"].items()}
    R["dns_sub"] = {k: x if len(x) <= 50 else set(list(x)[:50]) | {f"__n={len(x)}"} for k, x in R["dns_sub"].items()}
    for k in ("mac_vlans",):
        R[k] = dict(R[k])
    for k in ("conv", "cls", "admin", "udp_flows", "hs_rtt", "http_lat", "dns_lat", "ntp_off", "syn_ts", "udp_ts", "echo_ts", "dns_qts",
              "ttl", "ip2mac", "rtr_arp_tgt"):
        R[k] = dict(R[k])
    R["stp_refs"] = dict(R["stp_refs"]); R["dup_refs"] = dict(R["dup_refs"]); R["frag_refs"] = dict(R["frag_refs"])
    R["loop_refs"] = dict(R["loop_refs"]); R["icmp_refs"] = dict(R["icmp_refs"]); R["ra_refs"] = dict(R["ra_refs"])
    R["tcp_anom_refs"] = dict(R["tcp_anom_refs"]); R["http_refs"] = dict(R["http_refs"]); R["dns_bypass_refs"] = dict(R["dns_bypass_refs"])
    R["dns_long_refs"] = dict(R["dns_long_refs"])
    return R

def _close_hs(R, hk, h0):
    """Record how a connection attempt ended: SYN never answered, or SYN-ACK never acknowledged."""
    v, c, cp, sv, spp = hk
    if h0[1] is None: R["syn_unans"][(c, sv, spp)] += 1
    elif len(h0) == 4: R["synack_unacked"][(c, sv, spp)] += 1

def _flush_tcp(R, tcpst, chunk):
    conv = R["conv"]
    for (v, s, sp, t, dp), st in tcpst.items():
        svc = st[24] if st[24] is not None else min(sp, dp)
        cli, srv = (s, t) if svc == dp else (t, s)
        direction = "c2s" if svc == dp else "s2c"
        c = conv[(v, cli, srv, svc, direction)]
        c[0] += st[8]; c[1] += st[9]; c[2] += st[12]; c[3] += st[13]; c[4] += st[14]; c[5] += st[15]; c[6] += st[16]
        c[7] += st[17]; c[8] += st[18]; c[9] += st[19]; c[10] += st[20]
        c[11] = st[10] if c[11] == 0 else min(c[11], st[10]); c[12] = max(c[12], st[11])
        # bytes delivered by the peer, inferred from this side's ACK advance
        if st[6] > 2_000_000:
            R["bigflows"].append((v, s, sp, t, dp, st[6], st[10], st[11], st[22], st[8], st[13], chunk))

def main():
    D = sys.argv[1]; out = sys.argv[2]
    files = sorted(glob.glob(os.path.join(D, "*.pcapng")))
    if len(sys.argv) > 3: files = files[:int(sys.argv[3])]
    with Pool(4) as pool:
        parts = pool.map(work, files, chunksize=1)
    with open(out, "wb") as fh:
        pickle.dump(parts, fh, protocol=pickle.HIGHEST_PROTOCOL)
    print("done", len(parts), sum(p["n"] for p in parts))

if __name__ == "__main__":
    main()
