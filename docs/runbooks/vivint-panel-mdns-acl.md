# Vivint Panel mDNS Block (SW920 port 1/0/17)

**Applied:** 2026-09-30 · **Where:** Araknis AN-920 core switch `192.168.1.215`, port `1/0/17` ("Vivint Security Panel") · **Direction:** inbound (traffic *from* the panel only)

> **If something Vivint-related stops working, first run the quick test in [§5](#5-quick-test-is-the-block-the-cause):
> remove the block, retest, and put it back.** Unless you run `write memory` while it's off, a switch reboot restores the saved state.

---

## 1. What it does, in one sentence

It drops the panel's **mDNS** traffic (UDP port 5353, the "Bonjour" local-discovery protocol). Everything else the panel sends passes normally.

## 2. Why

The Vivint panel (`192.168.10.108`, migrating to `192.168.10.151` in Part 7.5, MAC `88:6a:e3:d8:eb:1c`) sent mDNS queries non-stop, looking for Chromecast/Google/Nest, Spotify, Hue, HomeKit, Matter and Thread devices:

- about **13.5 packets/s** in the evening and about **4.6/s** overnight, split roughly half IPv4 and half IPv6 (SPAN captures 2026-09-29/30);
- the Araknis 520's Bonjour repeater copied it into **every VLAN** (1, 10, 20, 30, 40, 150, 200) at about 2–3.5 packets/s each;
- the access points then broadcast those copies over the air on every SSID.

The panel only needs cloud arm/disarm (phone and panel), its cameras (now on the panel's own AP, not the LAN) and the Control4 integration. None of these use mDNS. Local Nest, Spotify and Hue integrations are **deliberately not used** (owner's decision, 2026-09-30).

Result: the panel's mDNS seen on the router port fell from **290 packets per 30 s to 1**.

## 3. What is configured

```
ip access-list VIVINT_NO_MDNS          <- IPv4 list
  deny udp any any eq 5353             <- sequence 10: drop mDNS
  permit every                         <- sequence 20: allow everything else
ipv6 access-list VIVINT_NO_MDNS6       <- IPv6 list (same two rules)
  deny udp any any eq 5353
  permit every

interface 1/0/17
  ipv6 traffic-filter VIVINT_NO_MDNS6 in 1   <- IPv6 list, checked 1st
  ip access-group VIVINT_NO_MDNS in 2        <- IPv4 list, checked 2nd
  (ip access-group EXC_initial_list in 4294967295  <- Araknis built-in, checked last; on every port)
```

### Not affected (still allowed)

| Traffic | Purpose |
|---|---|
| Panel → cloud (`app.vivintsky.com`, `grpc.vivintsky.com`, `signaling.access.vivint.ai`, `*.run.vivint.ai`) | Arm/disarm from the app, notifications, firmware updates |
| Control4 Director `192.168.10.200` (port 1/0/11) ↔ panel `192.168.10.108` (migrating to `192.168.10.151` in Part 7.5) **TCP 8765** | Control4 integration. Both are on VLAN 10, so the switch forwards this directly and it never passes through the router |
| DNS to AdGuard `192.168.40.185` / `.186`, DHCP, NTP, ICMP, SSDP | Normal operation |
| Anything *to* the panel | The block only filters what the panel **sends** |

## 4. How to read the switch output

SSH to the 920 (`ssh meek2100@192.168.1.215`) and run:

```
show access-lists interface 1/0/17 in
```

What it should show:

```
ACL Type             ACL ID              Sequence Number
-------- ------------------------------- ---------------
IPv6     VIVINT_NO_MDNS6                 1
IP       VIVINT_NO_MDNS                  2
IP       EXC_initial_list                4294967295
```

- The switch checks lists in **ascending sequence number**, and within a list checks rules top to bottom. **The first matching rule wins.**
- `EXC_initial_list` is Araknis's built-in list on every port. It contains only *permit* rules for well-known multicast groups, plus a final permit-everything rule. It never blocks anything. Leave it alone.

```
show ip access-lists VIVINT_NO_MDNS
show ipv6 access-lists VIVINT_NO_MDNS6
```

| Field | Meaning |
|---|---|
| `Inbound Interface(s): 1/0/17` | The list is attached to the panel's port. **If this line is missing, the list isn't active.** |
| `Sequence Number: 10`, `Action: deny`, `Protocol: 17(udp)`, `Destination L4 Port Keyword: 5353` | The mDNS drop rule |
| `Sequence Number: 20`, `Action: permit`, `Match All/Match Every: TRUE` | "Permit everything else" (`permit every`) |
| `ACL Hit Count` | Packets that matched that rule. Rule 10's count should keep rising slowly. That's the block working. |

## 5. Quick test: is the block the cause?

1. **Remove the block**, without saving:
   ```
   configure
   interface 1/0/17
   no ip access-group VIVINT_NO_MDNS in
   no ipv6 traffic-filter VIVINT_NO_MDNS6 in
   exit
   exit
   ```
2. Retest whatever wasn't working (Vivint app, Control4 driver, adding a device).
3. **Put it back**:
   ```
   configure
   interface 1/0/17
   ipv6 traffic-filter VIVINT_NO_MDNS6 in 1
   ip access-group VIVINT_NO_MDNS in 2
   exit
   exit
   ```
   Keep the order and the numbers. On this switch, IPv4 and IPv6 lists on one port share sequence numbers. Attaching the second list at an in-use number **silently replaces** the first list (this happened on 2026-09-30).
4. Only if the block turns out to be the cause and you want it gone permanently: do step 1 and then `write memory`. To also delete the lists: `configure`, `no ip access-list VIVINT_NO_MDNS`, `no ipv6 access-list VIVINT_NO_MDNS6`, `exit`, then `write memory`.

## 6. Symptoms that *could* be related

- **The Vivint app can't reach the panel on the local network** (cloud control should still work).
- **The Control4 Vivint driver can't find the panel.** Set the driver to the reserved IP `192.168.10.108`, not automatic discovery.
- **Adding a new Vivint device or integration fails** during a discovery step. Remove the block (§5), pair, then put it back.
- **Google, Nest, Spotify, Hue or HomeKit integrations with Vivint** don't work. This is **expected**.

Unrelated, even though they look similar:
- **Camera offline:** cameras connect via the Vivint/LG PoE Wi-Fi bridge to the **panel's own AP**. Check that bridge's LEDs.
- **Panel shows offline in the app:** check its internet access (DNS to AdGuard, WAN).

## 7. Verify from the capture side

Run on luna-server (`meek2100`). It counts the panel's mDNS seen on the SPAN over 30 s: about 0 means the block is working, and the count was about 290 before.

```bash
sudo timeout 30 tcpdump -ni ens19 'vlan and ether src 88:6a:e3:d8:eb:1c and udp port 5353' 2>/dev/null | wc -l
```

## 8. Related facts

| Item | Value |
|---|---|
| Vivint panel | `192.168.10.108` (DHCP reservation), `88:6a:e3:d8:eb:1c`, SW920 `1/0/17`, access VLAN 10 |
| Control4 Director (CA-10) | `192.168.10.200` (DHCP reservation), `00:0f:ff:20:74:d0`, SW920 `1/0/11`, access VLAN 10 |
| Integration port | Panel listens on **8765**, and the Director connects to it |
| Vivint cameras | On the panel's own Wi-Fi via the Vivint/LG PoE bridge since 2026-09-30, no longer on the home LAN (the old camera address `192.168.1.112` is retired) |
| Plan reference | [`network-implementation-plan.md`](../roadmaps/network-implementation-plan.md), Part 7 |
