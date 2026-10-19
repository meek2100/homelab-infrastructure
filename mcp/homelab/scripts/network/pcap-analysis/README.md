# pcap-analysis: read-only scripts for the router SPAN captures

These are offline analysis helpers for the `router_baseline_*.pcapng` files produced by the luna capture stack (stack 48, SPAN of SW920 1/0/1 = the 520 router port, VLAN-tagged). They only read pcaps. Requires Python 3 + `dpkt`; run them from WSL, e.g.:

```bash
python3 -W ignore overnight.py "/mnt/n/wireshark-captures" /tmp/report.txt
```

Times are printed in **PDT (UTC−7)**. Untagged frames are reported as VLAN 1 (or 0 in `loopcheck.py`).

| Script | Args | What it answers |
|---|---|---|
| `overnight.py` | `<dir> <report.txt>` | One parallel pass over every file: per-file volume/peak/top flow, top flows, router ARP sweep per hour per VLAN, stale-address traffic (`.1.186/.247/.137`), SDDP senders (Vivint/920/APs), Vivint mDNS per hour, OpenWrt frames, BPDUs seen, duplicate frames by VLAN |
| `dnsvlan1.py` | `<dir> <report.txt>` | DNS/DoT (53/853) **not** sent to AdGuard (`.40.185/.186`) or a gateway; HTTPS to well-known public DoH resolvers; hosts active on VLAN 1 |
| `dhcpntp.py` | `<dir>` | DHCP OFFER/ACK options per VLAN (15, 6, **119** decoded, **42**); NTP requests by VLAN/src/dst; NTP replies from a `.1` gateway |
| `estfilter.py` | `<dir> <file-substrings...>` | Replays the capture's `INTERNET_BULK` exclusion over sample files and prints the % of bytes/frames it would drop |
| `findmac.py` | `<dir> <mac>` | VLANs, IPs and hints (DHCP/SDDP/mDNS) for one MAC |
| `loopcheck.py` | `<dir>` | Exact-duplicate frames within 200 ms (loop evidence), OpenWrt-sourced frames, peak broadcast/multicast per VLAN |
| `arpsweep.py` | `<dir>` | Router ARP requests per minute per VLAN + distinct targets (OvrC sweep check) |
| `sddp2.py` | `<dir>` | SDDP (UDP 1902) to/from the Director, Vivint, the 920 and the 830 AP |

Notes:
- The SPAN only sees traffic crossing the router port, so same-VLAN traffic between two devices (e.g. Vivint ↔ Director on VLAN 10) is invisible; multicast may also be pruned by IGMP snooping.
- Created during the 2026-09-30/10-01 network work; see `docs/roadmaps/network-implementation-plan.md` for the findings they produced.

## Full forensic pipeline (added 2026-10-05)

Stdlib-only (no `dpkt`): `pcapng_fast.py` reads pcapng blocks directly, and each pass runs 4 worker processes (one file each). A full pass over 28 × 50 MB files (7.25M frames) takes about 60 s. These scripts produced [`docs/roadmaps/capture-review-2026-10-05.md`](../../../../docs/roadmaps/capture-review-2026-10-05.md).

```bash
cd /home/agentsvc/repos/homelab-infrastructure/mcp/homelab/scripts/pcap-analysis
D="/mnt/n/wireshark-captures"
python3 -W ignore deep.py "$D" /tmp/deep.pkl
python3 -W ignore deep_report.py /tmp/deep.pkl basic     # also: l2, l3, l4, app, all
python3 -W ignore deep_behavior.py /tmp/deep.pkl
python3 -W ignore targeted.py "$D" /tmp/targeted.pkl 2026-10-05T00:31:47-07:00   # optional peak seconds to break down
python3 -W ignore targeted_report.py /tmp/targeted.pkl /tmp/deep.pkl
python3 -W ignore stormcheck.py "$D"
python3 -W ignore framerefs.py "$D"
```

| Script | Args | What it answers |
|---|---|---|
| `pcapng_fast.py` | (library) | `read(path)` yields `(frame_no, ts, orig_len, data)`; frame numbers match Wireshark's `frame.number` |
| `deep.py` | `<dir> <out.pkl> [nfiles]` | One pass, all layers, saved as a pickle with frame references (`c<chunk>#<frame>@<time>`): rates, VLAN and broadcast/multicast shares, ARP (router sweep, conflicts, GARP), STP, duplicates, fragments, TTL/loops, ICMP, IPv6 RAs, TCP flags/options/RTT/retransmissions per class, DNS, DHCP, NTP, HTTP, TLS JA3/JA4, SMB/NTLM/Kerberos/Telnet/FTP/SNMP, admin ports, beaconing and scan inputs |
| `deep_report.py` | `<deep.pkl> [all\|basic\|l2\|l3\|l4\|app]` | Prints the `deep.py` results by layer |
| `deep_behavior.py` | `<deep.pkl>` | ICMP error detail, UDP flows on chosen ports, beaconing (periodicity), horizontal/vertical scans, SNMP community fingerprints (SHA-256 prefix only) |
| `targeted.py` | `<dir> <out.pkl> [peak ISO time ...]` | Inbound flows from the internet (open-resolver check), DNS loop answers, DNAT evidence, ACK-inferred TCP volumes, unknown-unicast flooding, hairpin and martian destinations, nexus MSS, `.1.237` ARP, laptop VLAN presence |
| `targeted_report.py` | `<targeted.pkl> <deep.pkl>` | Prints the `targeted.py` results, plus per-destination retransmission rates (office vs house) and AdGuard answers sent to the internet |
| `stormcheck.py` | `<dir>` | Router ARP answer rate bucketed by router broadcasts per second (storm control on 1/0/1), plus window/BDP for chosen big flows; edit `ALIVE1` / `FLOWS` per capture |
| `framerefs.py` | `<dir>` | First frame reference for each finding; edit the predicates per review |

How the numbers are computed (read before comparing reviews):
- **Per VLAN.** Inter-VLAN traffic is mirrored twice (ingress VLAN + egress VLAN). TCP state is keyed by `(vlan, 5-tuple)` so the routed copy is never counted as a retransmission. Frame counts in the reports are "as mirrored".
- **Retransmissions only where the capture is complete.** The stack 48 filter drops internet packets over 1200 B and keeps 512 B per frame. WAN retransmission rates therefore cover segments ≤ 1200 B only, and sequence gaps on WAN flows are expected.
- **WAN volumes from ACK advance.** The tracker resets on SYN/FIN/RST and caps each step at 16 MB. A SYN also resets the sequence state, because ports get reused. The first version lacked this reset and overstated LAN retransmissions (0.884% → 0.583% on the 10-05 set).
- **Router MAC `14:3f:c3:91:50:8c`.** Frames from it are the router's egress copies.
