# Capture Review — 2026-10-04 23:58 → 10-05 08:00 PDT (router SPAN, files 00003–00030)

Full forensic report for the first overnight capture after the 2026-10-04 network reorganization. Summary and open items: `network-implementation-plan.md` Part 7 ("Capture Review — 2026-10-04 23:58 → 10-05 08:00") and `.agents/docs/network-todo.md`.

**How to read references:** `00003#1405` means Wireshark frame 1405 in `router_baseline_00003_*.pcapng`. All times are PDT (UTC−7).

## Method and capture limits
- **What the capture sees.** It is a SPAN of SW920 1/0/1 (the router trunk, 802.1Q), so it sees router-crossing traffic only. Inter-VLAN packets appear twice (ingress VLAN + egress VLAN). Every TCP and retransmission figure is computed per VLAN.
- **Capture filter (stack 48).** It drops internet packets over 1,200 B and keeps 512 B per frame. Consequences:
  - On-wire bit rates understate WAN volume. TCP volumes are reconstructed from ACK advance, with the tracker reset on SYN/FIN/RST.
  - WAN retransmission rates cover segments ≤ 1,200 B only.
  - TLS ClientHellos over 1,200 B (modern browsers with post-quantum key shares) and QUIC Initials to the internet are not visible.
- **Analyzer.** `mcp/homelab/scripts/pcap-analysis/` (`deep.py`, `targeted.py`, `stormcheck.py`, `framerefs.py` and their reports; see that README). It is stdlib-only Python with its own pcapng reader, because there is no tshark on this PC or in `personal-ai` WSL. It processes the 7,252,262 frames in about 60 s on 4 cores.
- **Revision (2026-10-05, same day).** The first run kept a TCP connection's sequence state when a new connection reused the same ports, which miscounted some reused connections' segments as retransmissions. After the fix:
  - LAN retransmissions 0.884% → 0.583%
  - WAN 1.361% / 2.683% → 1.319% / 2.643%
  - unanswered SYN attempts 7,574 → 7,898

  The numbers below are from the corrected run. Per-host rates and frame references did not change.

## 1. Executive network health & security posture

**No sign of compromise.**
- No command-and-control beaconing, scanning or exfiltration.
- No SSH/RDP/WinRM/Telnet logins, and no NTLM, Kerberos or SMB traffic across the router.
- Every strictly periodic outbound flow maps to a known service.
- Zero inbound TCP connection attempts from the internet all night.

**One real exposure: AdGuard on nexus (`192.168.40.185`) is an open DNS resolver on the internet.** The router forwards WAN UDP/53 to it, and scanners got answers, including:
- Shadowserver
- an `openresolve.rs` probe naming the WAN IP 24.22.108.194
- a `wisc.edu` lookup, a classic test for DNS amplification abuse

**The routed core is healthy:**
- 0 IP fragments and 0 STP topology changes.
- LAN handshake median 0.68 ms.
- LAN TCP retransmissions 0.583%.
- Loss inside the router or the mirror ≤ 0.02%.

**Layer 2 is not healthy.**
- **Broadcast/multicast is 19.82% of frames** (target < 5%).
- **The router drives it.** It sends 36.6 ARP requests/s, mostly a repeating sweep of `192.168.1.2–.154`, and reflects mDNS into all seven VLANs.
- **Storm control on the router port (1/0/1) appears to discard the router's own broadcasts.** In seconds above 200 router broadcasts, ARP answers from hosts known to be up fell from 99.99% to 93.47%.

**Several 2026-10-04 items marked done are not in effect:**
- No LAN-side DNS redirect exists. The "port 53 DNAT" is the WAN forward above.
- `stats.grafana.org` is still answered `0.0.0.0`, not NXDOMAIN.
- The VLAN 1 sweep still runs.
- nexus does not clamp MSS to 1380.

## 2. Core traffic statistics

| Metric | Observed Value | Baseline Status / Context |
| :--- | :--- | :--- |
| **Total Duration / Packet Count** | 28,922 s (8.03 h); 7,252,262 frames; 1,520,349,711 B on-wire (1,160,152,533 captured) | Avg 250.8 pps / 420.5 kbps captured. Median / p95 / p99: 175 / 696 / 935 pps. Peak 5,751 pps @00:31:47. No gaps > 5 s. |
| **Top 3 Talkers (IP/Port)** | 1) `192.168.40.185` nexus: 991,939 frames sent (Proxmox API :8006 to 3 hosts, SNMP to the 920). 2) `192.168.20.82` ← Fastly `151.101.65.190:443`: 1,441.6 MB, 15.3 Mbps avg while active, 57.8 Mbps peak. 3) `192.168.10.200` Control4 Director: 172,908 frames incl. 85,531 broadcasts. | The router itself sourced 3,664,305 frames (50.5%): routed copies plus 1,058,025 ARP requests. |
| **Dominant Protocols (% Vol)** | IPv4 79.20%, ARP 19.85%, IPv6 0.53% of frames. TCP 40.9% frames / 47.1% bytes; UDP 36.3% / 45.7%; ICMP 2.4%. Top UDP: SNMP 698,236 (262 MB, 72.5 kbps), mDNS 346,249, cloudflared 7844 263,664, QUIC 235,203, SSDP 204,224 (152 MB). | ARP at 19.85% of frames is abnormal (typical LAN < 2%). |
| **TCP Retransmission Rate (%)** | LAN↔LAN 0.583% (1,809 / 310,372 data segments); LAN→internet 1.319%; internet→LAN 2.643% (segments ≤ 1,200 B); out-of-order ≤ 0.091% | Baseline 4.653%, target < 0.50%. Concentrated in sleeping / battery devices (finding 13). |
| Broadcast/multicast share | 19.82% (bc 14.68%, mc 5.14%). VLAN 1 46.5%, VLAN 150 97.2%. | Baseline 33.06%. ≈84% of broadcasts come from the router. |
| Router ARP | 1,058,025 requests = 36.6/s; VLAN 1 25.2/s; peak 252/s @07:41:56 | Baseline 111.9/s, target < 20/s. All senders together: 1,161,520 (router 91.1%, Director 80,958). |
| Handshake RTT | LAN 0.68 / 9.58 / 98.2 ms; WAN 23.8 / 161.0 / 189.6 ms (median / p95 / p99) | |
| RST:SYN | 116,835 / 120,080 = 0.973 | 59% of resets are nexus closing its :8006 polls. |
| DNS | 113,599 query frames (cross-VLAN queries counted twice); NXDOMAIN 13.59%; SERVFAIL 0.07%; AdGuard median 1.34 ms, p99 203.5 ms | The p99 is AdGuard's `.internal` forward to the router (median 206.7 ms). |
| TCP volume (ACK-inferred) | LAN→Internet 185.2 MB; Internet→LAN 2,659.3 MB | |

## 3. Findings (chronological, with frame references)

1. **[00003#83 · 23:58:03] [L7] [SNMPv2c]** nexus polls the 920, router, APs and printers every 15.0 s with the cleartext v2c community (fingerprint `ed624588f84b`, 15 characters).
   - Volume: 698,236 frames, 24.1 frames/s, 72.5 kbps = 9.6% of all frames.
   - Home Assistant on luna polls the Brother with SNMPv1 `public` (first 00006#237204): 132 requests, 0 replies. That integration is broken.
2. **[00003#134 · 23:58:03] [L3] [ICMP 3/3]** The router rejects CA1 `.150.201` → Director `.10.200` UDP 6002 (384 rejections); 42 SYNs to `.10.200:8883` go unanswered. Testbench isolation works.
3. **[00003#198 → #200 · 23:58:03] [L7] [DNS]** `stats.grafana.org` from the Director, Core-1 and Core-3, plus `.204/.206/.160/.207` at ≤ 70 each.
   - AdGuard answers NOERROR `0.0.0.0` (A) / empty AAAA, not NXDOMAIN.
   - ≈14,783 unique queries in 8 h ≈ 44k/day (−77% vs baseline).
   - Each controller re-asks every ~12 s per record type, which matches AdGuard's default 10 s TTL for blocked answers.
4. **[00003#270 · 23:58:04] [L7] [NTP]** Clients pointed at a router that serves no NTP; each request gets port-unreachable.
   - HP `.10.181` → `192.168.1.1:123`: 233 requests, flagged unsynchronized.
   - Hue `.10.150` → the same server every 545.4 s.
   - The capture clock is within ~10 ms of time.google.com (stratum 1).
5. **[00003#325 · 23:58:04] [L4] [TCP options]** 0 of 85,111 nexus SYNs carry MSS 1380; all carry 1460. The TASK_008 clamp is not in effect, and it isn't needed (finding 21).
6. **[00003#441 · 23:58:04] [L3] [IPv4 routing]** SA-1 `.200.100` → non-existent `192.168.80.150`:
   - MQTT-TLS 8883: 2,268 attempts + 9,311 SYN retries
   - UDP 6002: 18,558 frames
   - syslog: 6,695 frames (00003#52874)
   - NTP: 344 requests

   None of it reappears on another VLAN, so it leaves via the WAN. SA-1 is still at `.200.100` (reservation `.200.201`). It also sends DNS to 1.1.1.1 (1,432) and 8.8.4.4 (472), probes 169.254.169.254:80 (52), and pulled 341 MB from AWS with 17.97% retransmissions toward it.
7. **[00003#570 · 23:58:05] [L2] [ARP]** `192.168.1.237` (office bridge AP) is claimed by two MACs.
   - `36:3f:c3:e8:b9:23` sends ARP requests as `.1.237` every 34.3 s (105/h).
   - The router learns `14:3f:c3:e8:b9:20` from ~725 replies/h.
   - The router's ARP entry alternates. This is not switch MAC flapping (different MACs, not one MAC on two ports); both MACs belong to the same AP.
8. **[00003#707 · 23:58:05] [L7] [SSDP]** The three Sonos speakers send unicast SSDP to the Director: 96,230 frames per VLAN copy, ~1.1/s per speaker, 152.3 MB total (42.1 kbps). The Control4 Sonos driver's discovery is too chatty.
9. **[00003#1192 · 23:58:08] [L2] [ARP]** The router keeps polling stale client entries, never answered:
   - `10.25.25.1` on VLAN 40: 4,355 requests. 10.25.25.1 is the DD-WRT on WAN2, not a VLAN 40 host.
   - `192.168.40.185` on VLAN 10: 4,284 requests (00003#156539).
10. **[00003#1238 · 23:58:08] [L7] [mDNS]** The router's Bonjour reflector sends 42,641 frames into VLAN 150 and 41,637 into VLAN 200 (~1.45/s each). The home service list still leaks into the work testbench VLANs; the c609f26 ACLs block inbound only.
11. **[00003#1405 · 23:58:08] [L2] [ARP]** The VLAN 1 sweep.
    - The router ARPs every address `.2–.154`, plus known hosts, every 6.4–6.7 s. 151 of 165 targets never answer.
    - Volume: 727,913 requests (25.2/s); 694,186 router broadcasts on VLAN 1 (24.0/s). Peak minute 1,568 (07:46); peak second 252 (07:41:56).
    - The range doesn't match the `.20–.99` DHCP pool, so it's an OvrC/agent scan range.
12. **[00003#1437 · 23:58:08] [L4] [TCP 1443]** Pixel `.10.110` → Sonos `.20.201`: 79.5% retransmissions (213/268); `.20.202`: 66.4% (194/292). Counts are identical on the VLAN 10 and VLAN 20 copies, so the loss is on the speakers' Wi-Fi side (Move 2 power-save), not in the core.
13. **Endpoint-side loss, not the core.** Pixel → Sonos (finding 12); SA-1 ← AWS 17.97%; desktop ← relay `192.73.240.121:443` 18.9% while asleep. Office hosts other than the desktop see 0.24% WAN→LAN retransmissions. Router or SPAN loss between the two VLAN copies of nexus↔PVE flows is ≤ 14 frames per ~72k (≤ 0.02%).
14. **[00003#3968 · 23:58:14] [L3] [ICMP 3/1]** mainsail `.30.90` was offline all night: 8,049 host-unreachable replies to nexus probes, 3,858 probe connects unanswered, 16,240 router ARPs.
15. **[00003#4125 · 23:58:15] [L4] [NAT-PMP/UPnP]** Tailscale's port-mapping probes (5351/1900) get port-unreachable: nexus 5,614 + 1,517, desktop 1,279 + 346. Expected with UPnP off.
    - Hairpin attempts to the WAN IP also get port-unreachable (00003#148635): nexus :41641 (4,313), desktop :58997 (3,873), Syncthing :22000 (1,592).
    - For these replies the router uses 24.22.108.194 as its ARP sender IP on VLANs 10 and 40.
16. **[00003#5775 · 23:58:19] [L2] [Ethernet]** 62,948 exact duplicate frames within 200 ms.
    - ≈17,300 originate on nexus (the VLAN 40 copy carries nexus's MAC), mostly the :8006 polls. This is the known nexus duplicate issue, now measured.
    - Not a loop: TTL drops once, and no packet appears three times.
    - The :8006 polling opens 12 new TLS sessions per host per 60 s scrape, with no reuse.
17. **[00003#12095 · 23:58:38] [L7] [DNS]** DNS bypass: 9,995 query frames to 8.8.8.8 / 8.8.4.4 / 1.1.1.1.
    - VLAN 20 Google speakers and Nest Hubs (00003#13876): 5,550 frames.
    - APs `.1.231/.236` send every query to four resolvers at once (254 transaction IDs seen at all four), and ping 1.1.1.1 and 8.8.8.8 every 20.1 s.
    - 8.8.8.8 answers at a median 16.88 ms, i.e. real Google. No bypass query is ever redirected to AdGuard.
18. **[00003#59137 · 00:00:50] [L7] [DoH]** The Vivint panel `.10.151` uses DNS-over-HTTPS to 1.1.1.1:443 (198 connections) and pings 8.8.8.8 every ~10 s. Port-53 rules can't catch it.
19. **[00003#160400 · 00:05:11] [L7] [DNS]** Lookups that are never answered, so clients keep retrying:
    - Director asks for the literal names `name_query` / `name_query.internal` every ~5 s: 22,052 frames, 0 answers. A Control4 driver has an unfilled hostname.
    - Desktop asks for `wpad.internal` every ~2 s (00003#182418): 2,827 frames, unanswered.
    - Hue gets NXDOMAIN for `diag.meethue.com` 3,948 times.
20. **[00004#31187 · 00:12:49] [L2/L7] [DHCP]** The work laptop Wi-Fi `f4:46:37:7a:6a:7a` (`011PRD-HKWJBK3`) leased `192.168.1.41` from the management VLAN pool. It is back on VLAN 10 `.10.103` from 07:40, so some SSID/AP puts clients on VLAN 1.
21. **[00014#73211 · 02:59:59] [L3] [ICMP 3/4]** 12 frag-needed messages in 8 h:
    - 11 with MTU 1420 from `192.73.240.128`, all about AdGuard DNS-over-QUIC (UDP 853) to `76.76.2.11`, from both AdGuards
    - 1 with MTU 1480 from a Vivint server

    0 IP fragments overall; max frame 1,518 B; 0 mDNS over 1,500 B (the HA/Homebridge fix holds).
22. **[00004#48738 · 00:13:13] [L3] [UDP 58997]** More private and link-local destinations sent out the WAN:
    - Desktop Tailscale → nexus Docker bridge IPs `172.17–24.0.1`: 40,632 frames.
    - luna Syncthing → `169.254.83.107:22000`: 2,606 frames (00003#99).
    - iPhone `.10.111` → `10.0.0.42` / `10.0.0.111:7000`.
23. **[00004#124446 → #124454 · 00:16:10] [L7] [DNS — exposure]** The internet queried AdGuard: 13 sources, 7 answered.
    - Openresolve.rs: 00021#91495 → #91582 (05:16:21).
    - `wisc.edu`: 00029#235495 → #235496 (07:46:32).
    - This confirms a WAN UDP/53 forward to `.40.185`.
24. **[00005#129166 · 00:31:24] [L4] [TCP window]** Nintendo Switch `.10.130` ← Fastly: 118.1 MB, peak 114.3 Mbps @00:31:47 (5,313 ACKs in that second — the capture peak).
    - RTT 15.2 ms → BDP ≈ 217 KB.
    - Receive window: median 130 KB (60% of BDP), max 262 KB.
    - 52 zero-windows → the console was the limit, not the network.
25. **[00007#247228 · 01:01:26] [L4] [TCP]** SA-1 probes its gateway on TCP 22, 23, 80, 443, 5000, 8008, 8080, 8443 and 8888 (one attempt each), plus SNMP `public` over v1 and v2c (4 each). This looks like OvrC device discovery. No other scans; 0 internal SSH/RDP/WinRM/Telnet sessions.
26. **[00013#219541 · 02:51:21] [L7] [DHCP]** One NAK (`halo-tactile`, then leased `.10.34`), expected after the renumbering. All 9 offers and 180 ACKs come from the router MAC `14:3f:c3:91:50:8c`; no rogue DHCP.
27. **[00017#151168 · 04:04:02] [L4] [TCP]** T5 `.10.201` firmware download from update.control4.com: 163.6 MB in 21 active seconds (62.3 Mbps avg, 100.5 Mbps peak). RTT 18.5 ms → BDP 232 KB vs a 1.57 MB window (15% used), so the cap near 100 Mbps comes from the path, not the window.
28. **[00027#54579 · 07:04:43] [L7] [DNS]** The desktop's Tailscale fired 2,524 lookups for `controlplane.tailscale.com` in 6 s (peak 523/s @07:04:48). AdGuard answered 625 (24.8%).
29. **[05:44:52 · 649 seconds] [L2] [storm control]** Router broadcasts exceeded 200/s in 649 seconds (max 231). Router ARPs to known-up VLAN 1 hosts were answered within 1 s at these rates:
    - ≤ 150/s: 14,857 / 14,859 (99.99%)
    - 150–200/s: 28,230 / 29,160 (96.81%)
    - over 200/s: 6,714 / 7,183 (93.47%)

    This is consistent with the 200/s broadcast limit on 1/0/1 discarding router broadcasts.
30. **[whole window] [L2] [RSTP]** Stable: 14,455 BPDUs from the 920 (root 4096, hello 2 s, forward delay 15 s), 0 topology-change flags.
31. **[whole window] [L7] [TLS]** 57,633 ClientHellos; 14,366 fully captured, 93.0% of those offering TLS 1.3.
    - TLS 1.2-only clients: Director (`apis.control4.com`), Flo `.30.83`, Tuya `.30.x` (no SNI), T4 `.20.73`, iPhone (no SNI).
    - 90 distinct JA4/JA3 fingerprints, all tied to known clients.
32. **[whole window] [L7] [beaconing / exfiltration]** Interval analysis covered 176 TCP, 571 UDP and 123 ICMP flow keys.
    - Every strictly periodic external flow is attributed: blackbox SMTP/IMAP to 35.212.229.212 every 15.0 s, mail.smtp2go.com:465 (2,960), Tailscale relay checks every 304.3 s, Control4 weather every 900 s, IoT clouds every 1,500 s.
    - Upload 185.2 MB vs download 2,659.3 MB. Largest uploads: 920 → OvrC 16.0 MB; WeatherFlow hub over cleartext MQTT :1883 6.4 MB.
    - No ICMP payloads over 120 B, no DNS tunnelling.
33. **[whole window] [L3] [ICMP 11/0]** 44 time-exceeded messages:
    - 26 desktop traceroutes (Comcast hops)
    - 13 the router dropping HP `.10.181` → nexus packets that arrive with TTL ≤ 1
    - 5 Google speakers and a Comcast hop

## 4. Root cause narrative

This was not an attack. It is a chain of side effects from configuration.

1. **The sweep and reflector make Layer 2 noisy.** After the 10-04 reorganization the router's discovery engine still ARPs `192.168.1.2–.154` and every known client every ~6.6 s, and reflects mDNS into all seven VLANs. That puts broadcast/multicast at 19.82% (VLAN 1 at 46.5%).
2. **Storm control turns noise into loss.** The 200/s broadcast limit was applied to 1/0/1–1/0/24, but 1/0/1 is the router's port. The sweep's bursts exceed it in 649 seconds, the switch discards some of the router's broadcasts, and polled hosts answer less often (93.47%). The same limit can also drop broadcast DHCP offers and ACKs.
3. **The DNS redirect landed on the WAN side.** The 520's port forwarding only acts on WAN ingress. Hard-coded DNS devices were never redirected (9,995 queries still reach Google/Cloudflare), while internet scanners reached AdGuard.
4. **The DNS loops are driven by TTLs or missing answers.** `stats.grafana.org` comes back with a 10 s TTL, so it is re-asked every ~12 s. `name_query` and `wpad.internal` get no answer, so clients retry every 2–5 s.
5. **Private destinations leak to the ISP.** SA-1 carries another lab's settings (`192.168.80.150`). Tailscale and Syncthing advertise Docker-bridge and link-local addresses. All of it follows the default route out the WAN.

**Security posture:** one exposure (the open resolver) plus private-address leakage to the ISP. No indicators of compromise.

## 5. Diagnostic filters

```wireshark
// 1. VLAN 1 sweep: router ARP requests to the .2-.154 range
vlan.id == 1 && eth.src == 14:3f:c3:91:50:8c && arp.opcode == 1 && arp.dst.proto_ipv4 in {192.168.1.2..192.168.1.154}

// 2. Router broadcast bursts (Statistics > I/O Graphs, 1 s interval, compare with 200/s)
eth.src == 14:3f:c3:91:50:8c && eth.dst == ff:ff:ff:ff:ff:ff

// 3. Open resolver: internet queries to AdGuard, and AdGuard answering the internet
(udp.dstport == 53 && ip.dst in {192.168.40.185 192.168.40.186} && !(ip.src == 10.0.0.0/8 || ip.src == 172.16.0.0/12 || ip.src == 192.168.0.0/16 || ip.src == 100.64.0.0/10)) || (udp.srcport == 53 && ip.src in {192.168.40.185 192.168.40.186} && !(ip.dst == 10.0.0.0/8 || ip.dst == 172.16.0.0/12 || ip.dst == 192.168.0.0/16 || ip.dst == 100.64.0.0/10))

// 4. DNS bypass, including DoT and DoH to well-known resolvers
(dns.flags.response == 0 && !mdns && !llmnr && !(ip.dst == 192.168.0.0/16)) || (tcp.flags.syn == 1 && tcp.flags.ack == 0 && (tcp.dstport == 853 || (tcp.dstport == 443 && ip.dst in {1.1.1.1 1.0.0.1 8.8.8.8 8.8.4.4 9.9.9.9})))

// 5. DNS loops
dns.qry.name in {"stats.grafana.org" "name_query" "name_query.internal" "wpad.internal" "diag.meethue.com"}

// 6. Private or link-local destinations leaving through the router
ip.dst == 192.168.80.0/24 || ip.dst == 172.16.0.0/12 || (ip.dst == 169.254.0.0/16 && !(ip.src == 169.254.0.0/16)) || ip.dst == 10.0.0.0/24

// 7. .1.237 answered by the second MAC
arp.src.proto_ipv4 == 192.168.1.237 && arp.src.hw_mac != 14:3f:c3:e8:b9:20

// 8. MSS audit (nexus sends 1460; the 1380 clamp is not active)
tcp.flags.syn == 1 && ip.src == 192.168.40.185 && tcp.options.mss_val != 1380

// 9. Management-VLAN client, mDNS reflected into the testbench VLANs, cleartext SNMP
(eth.addr == f4:46:37:7a:6a:7a && vlan.id == 1) || (mdns && vlan.id in {150 200} && eth.src == 14:3f:c3:91:50:8c) || (snmp && snmp.version != 3)

// 10. Retransmissions: always pin a VLAN, or Wireshark flags the routed copy as a retransmission
vlan.id == 200 && ip.dst == 192.168.200.100 && tcp.analysis.retransmission
```

**tshark commands.** Run on a workstation with Wireshark 4.x, from the `Router pcap` folder.

Merge the chunks:
```bash
mergecap -w overnight.pcapng router_baseline_*.pcapng
```
Open-resolver evidence (expect ≥ 7 response rows going to internet IPs):
```bash
tshark -r overnight.pcapng -Y "udp.port == 53 && ip.addr == 192.168.40.185 && !(ip.src == 192.168.0.0/16 && ip.dst == 192.168.0.0/16) && !(ip.addr == 1.1.1.1)" -T fields -e frame.number -e frame.time -e vlan.id -e ip.src -e ip.dst -e dns.flags.response -e dns.flags.rcode -e dns.qry.name -E header=y -E separator=,
```
VLAN 1 sweep targets:
```bash
tshark -r overnight.pcapng -Y "vlan.id == 1 && eth.src == 14:3f:c3:91:50:8c && arp.opcode == 1" -T fields -e frame.number -e frame.time_epoch -e arp.dst.proto_ipv4 -E header=y -E separator=,
```
Router broadcasts per second (look for rows over 200):
```bash
tshark -r overnight.pcapng -q -z "io,stat,1,eth.src == 14:3f:c3:91:50:8c && eth.dst == ff:ff:ff:ff:ff:ff"
```
DNS loops, with answer codes and TTLs:
```bash
tshark -r overnight.pcapng -Y 'dns.qry.name in {"stats.grafana.org" "name_query" "name_query.internal" "wpad.internal"}' -T fields -e frame.number -e frame.time -e ip.src -e ip.dst -e dns.flags.response -e dns.flags.rcode -e dns.a -e dns.resp.ttl -E header=y -E separator=,
```
Private destinations leaving through the router:
```bash
tshark -r overnight.pcapng -Y "ip.dst == 192.168.80.0/24 || ip.dst == 172.16.0.0/12 || (ip.dst == 169.254.0.0/16 && !(ip.src == 169.254.0.0/16)) || ip.dst == 10.0.0.0/24" -T fields -e frame.number -e frame.time -e vlan.id -e eth.src -e ip.src -e ip.dst -e ip.proto -e tcp.dstport -e udp.dstport -E header=y -E separator=,
```
Split one VLAN out before any TCP analysis:
```bash
tshark -r overnight.pcapng -Y "vlan.id == 200" -w vlan200.pcapng
```
```bash
tshark -r vlan200.pcapng -Y "tcp.analysis.retransmission && ip.dst == 192.168.200.100" -T fields -e frame.number -e frame.time -e ip.src -e tcp.srcport -e tcp.seq -e tcp.len -E header=y -E separator=,
```

## 6. Remediation playbook

### P0-1. Close the open resolver
1. **Run on: Araknis 520 web UI / OvrC (admin).** Delete the port-forward that sends UDP/TCP 53 to `192.168.40.185`. Do **not** apply Phase 3.1 of `lan-hygiene-pcap-remediation-plan.md`; it describes this same forward.
2. **Run on: AdGuard UI on nexus-server and nexus-server2.** Go to Settings → DNS settings → Access settings → Allowed clients:
   ```text
   192.168.0.0/16
   10.0.0.0/8
   172.16.0.0/12
   100.64.0.0/10
   127.0.0.1
   ```
3. **Run on: a phone on cellular (Wi-Fi off) or the cloud VPS.**
   ```bash
   dig @24.22.108.194 example.com +time=2 +tries=1
   ```
   Expected: `connection timed out; no servers could be reached`.

### P0-2. Lift the broadcast limit on the router's switch port
1. **Run on: Araknis 920 CLI (SSH as meek2100).** Check the setting:
   ```text
   show running-config interface 1/0/1
   ```
   Expected: a `storm-control broadcast …` line.
2. **Same session.** Remove it from 1/0/1 only and keep it on access ports. If the syntax is rejected, check `storm-control ?`.
   ```text
   configure
   interface 1/0/1
   no storm-control broadcast
   exit
   exit
   write memory
   ```
3. Refresh `infrastructure/network/configs/araknis-920-running.cfg`; the current backup has no storm-control lines. Success in the next capture: ARP answers in seconds over 200 broadcasts/s reach ≥ 99.9%.

### P1-3. Stop the VLAN 1 sweep
- **Run on: OvrC → the 520's network-scan/discovery settings.** Take `192.168.1.2–.154` out of scanning (or scan once a day at most).
- Delete the stale client entries (`.40.185` on VLAN 10, `10.25.25.1` on VLAN 40).
- Success: filter 1 shows < 1 request/s. Router VLAN 1 broadcasts alone are 9.6% of all frames today, so the non-unicast share should fall by ~10 points.

### P1-4. Break the DNS loops (both AdGuard instances)
Filters → Custom filtering rules. Remove whatever rule now returns `0.0.0.0` for grafana and add:
```text
||stats.grafana.org^$dnsrewrite=NXDOMAIN
||name_query^$dnsrewrite=NXDOMAIN
||name_query.internal^$dnsrewrite=NXDOMAIN
||wpad.internal^$dnsrewrite=NXDOMAIN
```
Then:
- DNS settings → **Blocked response TTL** = 3600, so clients cache the answer.
- On the desktop: Settings → Network & internet → Proxy → turn off **Automatically detect settings**.
- In Composer: find the Director driver whose hostname is literally `name_query`.

### P1-5. Enforce DNS with ACLs, not port forwarding
- On the 520, per VLAN, starting with VLAN 20: permit 53 to `.40.185/.186`, then deny UDP/TCP 53 and 853 to anything else.
- Deny TCP 443 to 1.1.1.1 / 1.0.0.1 from the Vivint panel `.10.151`.
- Keep VLAN 40's outbound UDP 853 open; AdGuard's DoQ upstreams use it.
- Set the APs' DNS to AdGuard only. Watch Cast/Nest devices for 24 h.

### P1-6. Stop private destinations leaving the WAN
- Add a 520 ACL, after the inter-VLAN permits, denying `172.16.0.0/12`, `169.254.0.0/16`, non-local `192.168.0.0/16` and `10.0.0.0/8`.
- **Exempt the routed private ranges** recorded in Part 7 ("520 static routes"): `10.8.0.0/24` (wg-easy), `10.20.20.0/24` and `10.25.25.0/24` (WAN2 / DD-WRT), `100.64.0.0/10` (Tailscale), `192.168.2.0/24` (OpenWrt P3).
- Re-provision SA-1: its MQTT, syslog and NTP all point at `192.168.80.150`, and it should be on its `.200.201` reservation.

### P2. Remaining items
- Find the SSID that lands clients on VLAN 1.
- Limit the 520 Bonjour reflector to VLANs 10/20/30.
- Check the `.1.237` office-bridge AP settings.
- Confirm the MSS clamp really is absent, then correct the docs rather than re-adding it:

  **Run on: nexus-server (your user; needs sudo):**
  ```bash
  sudo iptables -t mangle -S
  ```
  Expected: no `TCPMSS` lines.

### P3. Monitoring churn and cleartext management
- The :8006 polling opens 12 TLS sessions per host every 60 s; enable connection reuse or lengthen the interval.
- Slow the external SMTP/IMAP blackbox probes from 15 s to ≥ 5 min.
- Move to SNMPv3 where devices support it, and fix Home Assistant's Brother integration (uses `public`).
- Bring mainsail back up or pause its probes.

## Corrections to the 2026-10-05 rewrite of `lan-hygiene-pcap-remediation-plan.md`
Another tool rewrote that plan from the same captures (last edit 08:13). This data contradicts it on these points:
- **Phase 3.1** ("Port Forwarding" 53 → `.40.185`) is the open-resolver cause. The 520's port forwarding acts on WAN ingress.
- **"Router ARP 1,161,520 / 40.2 per s"** counts all ARP senders. The router's share is 1,058,025 = 36.6/s; the Director adds 80,958.
- **`.10.204–.207` and `.10.160` are not offline.** All answered the router's ARPs. `.204–.206` are Core-5 / EA-1 / Core Lite, not Triad amps.
- **stats.grafana.org:** ≈14.8k unique queries, not 59,038. The loopers are `.200/.202/.203`, not `.207`. The cadence is ~12 s per qtype, not 0.49 s.
- **ICMP 3/4 is not a "Cloudflare Tunnel black hole".** All 11 relate to UDP DoQ to 76.76.2.11; cloudflared uses 198.41.x:7844. An MSS clamp (TCP) cannot affect it.
- **ICMP 11/0:** only 13 of 44 come from the HP. A TTL mangle on Proxmox would not see printer → router packets.
- **RustDesk is not the nexus RST source.** `.1.41 → :21114` is 58 unanswered SYN attempts; nexus RSTs are :8006 (69,334). `.1.41` is the work laptop, not the desktop.
- **`.1.237` causes no switch MAC flapping.** It is router ARP-cache alternation.
- **"Telnet / FTP sessions":** Telnet is one SYN → RST (SA-1 probing its gateway). FTP shows no credentials (372/380 B control sessions).
