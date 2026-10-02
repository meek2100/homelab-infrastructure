# pcap-analysis: read-only scripts for the router SPAN captures

These are offline analysis helpers for the `router_baseline_*.pcapng` files produced by the luna capture stack (stack 48, SPAN of SW920 1/0/1 = the 520 router port, VLAN-tagged). They only read pcaps. Requires Python 3 + `dpkt`; run them from WSL, e.g.:

```bash
python3 -W ignore overnight.py "/mnt/c/Users/dtheurer/Downloads/Router pcap" /tmp/report.txt
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
