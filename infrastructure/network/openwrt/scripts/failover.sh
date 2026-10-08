#!/bin/sh
# failover.sh - Unified 3-Priority Failover Controller for OpenWrt
# Handles Monitoring, State Transitions, Status Reporting, and Testing Wrapper.

LOGFILE="/var/log/failover.log"
TRACK_IP="192.168.1.1"
VXLAN_SERVER_IP="192.168.1.150"
BR_IF="br-lan"
P1_IF="wan"
VXLAN_IF="vxlan150"
# Physical br-lan ports facing the Netgear switch (Port 8 → lan4) and spare wired drops.
# These must carry the same tagged VLANs as vxlan150 so the bridge can forward between them.
# lan1 is on br-mgmt (out-of-band management), never add trunk VLANs there.
LAN_TRUNK_PORTS="lan2 lan3 lan4"
# Tagged VLANs carried over vxlan150 and the LAN trunk ports. Must match TAGGED_VLANS in
# vxlan-server's /usr/local/bin/vxlan-nm. VLAN 100 (Wireshark SPAN isolation) is deliberately
# excluded: it must exist only on SW920 1/0/24.
TAGGED_VLANS="10 20"  # office devices: 10 (Control4, printers) and 30 (Apple TV) per Netgear VLAN table
FAIL_COUNT_FILE="/tmp/failover_p1_fails"
P1_DOWN_SINCE_FILE="/tmp/failover_p1_down_since"
P2_DOWN_SINCE_FILE="/tmp/failover_p2_down_since"
FAIL_THRESHOLD=3
# Integrity-triggered rebuilds tear down vxlan150 for every office device on a tagged VLAN.
# Allow at most one per REBUILD_MIN_INTERVAL; a repeat inside the window means the check itself is wrong.
REBUILD_STAMP_FILE="/tmp/failover_last_integrity_rebuild"
REBUILD_MIN_INTERVAL=300
# P1 recovery probe (P2/P3 only). With no VLAN membership the DSA switch drops every frame on wan,
# and a packet socket on a bridge port never sees replies anyway, so `arping -I wan` could never
# detect a recovered bridge (2026-10-01 outage: stuck in P2, wan rx_packets delta 0).
# Instead wan is parked untagged in PROBE_VID, whose only other member is the bridge CPU port
# (no loop possible), and PROBE_IF sends RFC 5227 ARP probes (sender IP 0.0.0.0) from its own
# locally administered MAC, so SW920 learns that MAC only behind the Wi-Fi bridge.
PROBE_VID=4094
PROBE_IF="p1probe"
PROBE_MAC="02:9f:80:50:58:2f"

# Ensure log file exists — /var is tmpfs on OpenWrt; dir survives reboot but files do not.
mkdir -p "$(dirname "$LOGFILE")"
touch "$LOGFILE" 2>/dev/null

log_msg() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$LOGFILE"
    logger -t failover -- "$1"
}

ensure_policy_routing() {
    ip rule show 2>/dev/null | grep -q "from 192.168.1.225" || ip rule add from 192.168.1.225 table 100 2>/dev/null
    ip route show table 100 2>/dev/null | grep -q "dev wl1-sta0" || {
        ip route add 192.168.1.0/24 dev wl1-sta0 table 100 2>/dev/null
        ip route add default via 192.168.1.1 dev wl1-sta0 table 100 2>/dev/null
    }
}

# --- Status Functions (from CLI) ---

get_stp_status() {
    iface=$1
    if ! brctl show "$BR_IF" 2>/dev/null | grep -q "$iface"; then
        echo "MISSING FROM BRIDGE"
        return
    fi
    stp=$(brctl showstp "$BR_IF" 2>/dev/null | grep -A5 "$iface" | grep "state" | awk '{print $NF}')
    if [ -z "$stp" ]; then
        echo "LINK DOWN"
    else
        echo "$stp"
    fi
}

get_carrier() {
    [ -f "/sys/class/net/$1/carrier" ] && cat "/sys/class/net/$1/carrier" 2>/dev/null || echo "0"
}

get_mtu() {
    [ -d "/sys/class/net/$1" ] && cat "/sys/class/net/$1/mtu" 2>/dev/null || echo "N/A"
}

show_status() {
    echo "--- 3-Priority Failover System Status ---"
    echo ""

    # Which path carries VLAN 1 is the real state (vxlan150 always carries the tagged VLANs, and
    # wan stays STP-forwarding while parked in the probe VLAN, so neither alone means "active").
    V1_ON_P1=no; V1_ON_P2=no; P3_UP=no
    bridge vlan show dev "$P1_IF" 2>/dev/null | grep -qE '[[:space:]]1 PVID' && V1_ON_P1=yes
    bridge vlan show dev "$VXLAN_IF" 2>/dev/null | grep -qE '[[:space:]]1 PVID' && V1_ON_P2=yes
    /etc/init.d/relayd status 2>/dev/null | grep -q "running" && P3_UP=yes

    # P1: wan
    P1_STATE=$(get_stp_status "$P1_IF")
    P1_CARRIER=$(get_carrier "$P1_IF")
    P1_MTU=$(get_mtu "$P1_IF")
    if [ "$V1_ON_P1" = "yes" ] && [ "$P1_STATE" = "forwarding" ]; then
        echo "Priority 1 (Wifi 7 Bridge): [ ACTIVE / carrying VLAN 1 ] (MTU: $P1_MTU)"
    elif bridge vlan show dev "$P1_IF" 2>/dev/null | grep -qE "[[:space:]]$PROBE_VID PVID"; then
        echo "Priority 1 (Wifi 7 Bridge): [ STANDBY / parked in probe VLAN $PROBE_VID, carrier $P1_CARRIER ] (MTU: $P1_MTU)"
    elif [ "$P1_CARRIER" = "1" ]; then
        echo "Priority 1 (Wifi 7 Bridge): [ STANDBY / $P1_STATE ] (MTU: $P1_MTU)"
    else
        echo "Priority 1 (Wifi 7 Bridge): [ OFFLINE / NO CARRIER ] (MTU: $P1_MTU)"
    fi

    # P2: vxlan150
    P2_MTU=$(get_mtu "$VXLAN_IF")
    if [ "$V1_ON_P2" = "yes" ]; then
        echo "Priority 2 (VXLAN Tunnel) : [ FAILOVER ACTIVE / carrying VLAN 1 + tagged $TAGGED_VLANS ] (MTU: $P2_MTU)"
    elif bridge link 2>/dev/null | grep -q "$VXLAN_IF"; then
        echo "Priority 2 (VXLAN Tunnel) : [ STANDBY / tagged VLANs $TAGGED_VLANS only (normal) ] (MTU: $P2_MTU)"
    elif ip link show "$VXLAN_IF" 2>/dev/null | grep -q "UP"; then
        echo "Priority 2 (VXLAN Tunnel) : [ STANDBY / ADMIN ] (MTU: $P2_MTU)"
    else
        echo "Priority 2 (VXLAN Tunnel) : [ OFFLINE ]"
    fi

    # P3: Relayd (uses br-lan MTU)
    BR_MTU=$(get_mtu "$BR_IF")
    if [ "$P3_UP" = "yes" ]; then
        echo "Priority 3 (Relayd)       : [ ACTIVE / RUNNING ] (MTU: $BR_MTU)"
    else
        echo "Priority 3 (Relayd)       : [ INACTIVE (Service Stopped) ] (MTU: $BR_MTU)"
    fi

    # One-line verdict: exactly one path should carry VLAN 1
    if [ "$V1_ON_P1" = "yes" ] && [ "$V1_ON_P2" = "yes" ]; then
        echo ">>> VLAN 1 path: P1 AND P2 — LOOP RISK (the monitor's loop guard fixes this within 30 s; to force it now: $0 -m)"
    elif [ "$V1_ON_P1" = "yes" ] && [ "$P3_UP" = "yes" ]; then
        echo ">>> VLAN 1 path: P1 AND P3 (relayd) — LOOP RISK (the monitor's loop guard fixes this within 30 s; to force it now: $0 -m)"
    elif [ "$V1_ON_P1" = "yes" ]; then
        echo ">>> VLAN 1 path: P1 (Wi-Fi bridge) — normal"
    elif [ "$V1_ON_P2" = "yes" ]; then
        echo ">>> VLAN 1 path: P2 (VXLAN tunnel) — failover"
    elif [ "$P3_UP" = "yes" ]; then
        echo ">>> VLAN 1 path: P3 (relayd) — failover"
    else
        echo ">>> VLAN 1 path: NONE — office VLAN 1 is down"
    fi

    # Monitor state
    echo ""
    echo "--- Monitor State ---"
    FAILS=$(get_fail_count)

    # Helper: format seconds as Xm Ys or Xs
    fmt_dur() {
        _m=$(( $1 / 60 )); _s=$(( $1 % 60 ))
        [ $_m -gt 0 ] && echo "${_m}m ${_s}s" || echo "${_s}s"
    }

    # Last check age
    if [ -f "$FAIL_COUNT_FILE" ]; then
        FAIL_AGE=$(( $(date +%s) - $(date -r "$FAIL_COUNT_FILE" +%s 2>/dev/null || echo "0") ))
        LAST_CHECK="$(fmt_dur $FAIL_AGE) ago"
    else
        LAST_CHECK="never"
    fi

    # P1 status
    if [ "$FAILS" -ge "$FAIL_THRESHOLD" ]; then
        if [ -f "$P1_DOWN_SINCE_FILE" ]; then
            DOWN_EPOCH=$(cat "$P1_DOWN_SINCE_FILE" 2>/dev/null)
            if [ -n "$DOWN_EPOCH" ]; then
                echo "P1: DOWN ($(fmt_dur $(( $(date +%s) - DOWN_EPOCH ))))"
            else
                echo "P1: DOWN"
            fi
        else
            echo "P1: DOWN"
        fi
    elif [ "$FAILS" -gt 0 ]; then
        echo "P1: DEGRADED ($FAILS/$FAIL_THRESHOLD checks failed)"
    else
        echo "P1: HEALTHY"
    fi

    # P2 status
    if [ -f "$P2_DOWN_SINCE_FILE" ]; then
        P2_EPOCH=$(cat "$P2_DOWN_SINCE_FILE" 2>/dev/null)
        if [ -n "$P2_EPOCH" ]; then
            echo "P2: DOWN ($(fmt_dur $(( $(date +%s) - P2_EPOCH ))))"
        else
            echo "P2: DOWN"
        fi
    elif [ "$FAILS" -ge "$FAIL_THRESHOLD" ]; then
        echo "P2: ACTIVE"
    fi

    echo "Last check: $LAST_CHECK"

    # Last 3 log entries
    if [ -f "$LOGFILE" ]; then
        echo ""
        echo "--- Recent Log ---"
        tail -3 "$LOGFILE"
    fi

    echo "--- Bridge VLAN Ports ---"
    bridge vlan show dev "$P1_IF" 2>/dev/null
    bridge vlan show dev "$VXLAN_IF" 2>/dev/null
    echo ""
}

# --- Logic Functions (from Original failover.sh) ---

get_fail_count() {
    [ -f "$FAIL_COUNT_FILE" ] && cat "$FAIL_COUNT_FILE" 2>/dev/null || echo "0"
}

set_fail_count() {
    echo "$1" > "$FAIL_COUNT_FILE"
}

# True when vxlan150 exists and is administratively up.
# VXLAN devices have no carrier, so `ip link` reports "state UNKNOWN" even when healthy;
# matching "state UP" made every integrity check fail and rebuilt the tunnel every 30s.
vxlan_admin_up() {
    ip link show "$VXLAN_IF" 2>/dev/null | grep -qE "[<,]UP[,>]"
}

# Rebuild P1 for an integrity failure ($1 = reason), rate-limited to one per REBUILD_MIN_INTERVAL.
integrity_restore() {
    _now=$(date +%s)
    _last=$(cat "$REBUILD_STAMP_FILE" 2>/dev/null || echo 0)
    if [ $((_now - _last)) -lt "$REBUILD_MIN_INTERVAL" ]; then
        log_msg "WARNING: P1 integrity tripped again within ${REBUILD_MIN_INTERVAL}s of last rebuild ($1) — NOT rebuilding; check may be misfiring"
        return 0
    fi
    echo "$_now" > "$REBUILD_STAMP_FILE"
    log_msg "P1 integrity: $1 — restoring P1"
    activate_p1
}

park_p1_in_probe_vlan() {
    bridge vlan add dev "$BR_IF" vid "$PROBE_VID" self 2>/dev/null
    bridge vlan add dev "$P1_IF" vid "$PROBE_VID" pvid untagged master 2>/dev/null
    if ! ip link show "$PROBE_IF" >/dev/null 2>&1; then
        ip link add link "$BR_IF" name "$PROBE_IF" type vlan id "$PROBE_VID"
        ip link set "$PROBE_IF" address "$PROBE_MAC"
    fi
    ip link set "$PROBE_IF" up
}

unpark_p1_probe_vlan() {
    ip link del "$PROBE_IF" 2>/dev/null
    bridge vlan del dev "$P1_IF" vid "$PROBE_VID" master 2>/dev/null
    bridge vlan del dev "$BR_IF" vid "$PROBE_VID" self 2>/dev/null
}

# Success = TRACK_IP answered an ARP probe sent out the parked wan. Parse the reply count instead
# of the exit code: BusyBox and iputils disagree on what -D's exit status means.
probe_p1_parked() {
    command -v arping >/dev/null 2>&1 || return 0
    ip link show "$PROBE_IF" >/dev/null 2>&1 || park_p1_in_probe_vlan
    arping -D -c 3 -w 4 -I "$PROBE_IF" "$TRACK_IP" 2>&1 | grep -qE 'Received [1-9]'
}

check_p1() {
    # Check physical carrier first (0 = disconnected, 1 = link present)
    CARRIER=$(cat /sys/class/net/$P1_IF/carrier 2>/dev/null || echo 0)
    [ "$CARRIER" = "0" ] && return 1

    # In normal P1 mode (neither P2 nor P3 active), verify end-to-end ping to track IP
    if [ ! -f /tmp/failover_p2_active ] && ! /etc/init.d/relayd status 2>/dev/null | grep -q "running"; then
        # Check STP convergence if available
        STP_STATE=$(brctl showstp "$BR_IF" 2>/dev/null | grep -A3 "$P1_IF" | grep "state" | awk '{print $NF}')
        if [ -n "$STP_STATE" ] && [ "$STP_STATE" != "forwarding" ]; then
            log_msg "P1 STP state: $STP_STATE (waiting for convergence)"
            return 0
        fi
        ping -c 3 -W 2 -I 192.168.1.226 "$TRACK_IP" >/dev/null 2>&1
        return $?
    else
        # In P2 or P3 failover mode: wan has carrier=1. Probe through the isolated probe VLAN
        # (see PROBE_VID) to see whether the Wi-Fi bridge carries traffic end to end again.
        probe_p1_parked
        return $?
    fi
}

activate_p1() {
    log_msg "Activating Priority 1 (Wifi 7 Bridge)..."
    /etc/init.d/relayd stop >/dev/null 2>&1
    # 1. Remove VLAN 1 from VXLAN first to guarantee mutual exclusion
    bridge vlan del dev "$VXLAN_IF" vid 1 >/dev/null 2>&1
    rm -f /tmp/failover_p2_active

    # 2. Inform VM 107 to remove VLAN 1 from its end
    ensure_policy_routing
    ssh -y -i /root/.ssh/id_ed25519 -o ConnectTimeout=3 -b 192.168.1.225 meek2100@"$VXLAN_SERVER_IP" 'sudo /usr/local/bin/vxlan-nm -p1' >/dev/null 2>&1

    # 3. Recreate vxlan150 bound to wired local 192.168.1.226
    ip link del "$VXLAN_IF" 2>/dev/null
    ip link add "$VXLAN_IF" type vxlan id 150 dstport 4789 remote "$VXLAN_SERVER_IP" local 192.168.1.226
    ip link set "$VXLAN_IF" mtu 1450
    ip link set dev "$VXLAN_IF" master "$BR_IF"
    ip link set "$VXLAN_IF" up
    for vid in $TAGGED_VLANS; do
        bridge vlan add dev "$VXLAN_IF" vid "$vid" 2>/dev/null
    done
    bridge vlan del dev "$VXLAN_IF" vid 1 2>/dev/null || true

    # 3b. Add the same tagged VLANs to the physical LAN trunk ports.
    # The Netgear switch (Port 8 → lan4, PVID 1) sends tagged VLAN 10/30 frames
    # toward lan4. Without these entries the bridge VLAN filter drops them silently.
    for port in $LAN_TRUNK_PORTS; do
        for vid in $TAGGED_VLANS; do
            bridge vlan add dev "$port" vid "$vid" 2>/dev/null
        done
    done

    # 4. Restore VLAN 1 on wan without bouncing interface, then drop the P2/P3 probe VLAN
    bridge vlan add dev "$P1_IF" vid 1 pvid untagged master >/dev/null 2>&1
    bridge vlan del dev "$P1_IF" vid 40 master >/dev/null 2>&1
    unpark_p1_probe_vlan
    ip link set "$BR_IF" mtu 1500

    # 5. Restore br-lan routes
    ip route add 192.168.1.0/24 dev "$BR_IF" proto static scope link src 192.168.1.226 metric 10 2>/dev/null
    ip route add default via 192.168.1.1 dev "$BR_IF" proto static metric 10 2>/dev/null

    # 6. Flush ARP/MAC entries after topology change
    ip neigh flush all >/dev/null 2>&1
    set_fail_count 0
    rm -f "$P1_DOWN_SINCE_FILE" "$P2_DOWN_SINCE_FILE"
    log_msg "Priority 1 Active (Split-Trunking: Tagged on VXLAN, Native on wan)."
}

activate_p2() {
    log_msg "Activating Priority 2 (VXLAN Tunnel)..."
    /etc/init.d/relayd stop >/dev/null 2>&1

    # 1. Remove VLAN 1 from wan port FIRST (Do not bring interface down, just remove VID 1),
    #    and park wan in the isolated probe VLAN so check_p1 can see the bridge recover
    bridge vlan del dev "$P1_IF" vid 1 master >/dev/null 2>&1
    park_p1_in_probe_vlan

    # 2. Restore br-lan routes
    ip route add 192.168.1.0/24 dev "$BR_IF" proto static scope link src 192.168.1.226 metric 10 2>/dev/null
    ip route add default via 192.168.1.1 dev "$BR_IF" proto static metric 10 2>/dev/null

    # 3. Set bridge and tunnel MTU to 1450
    ip link set "$BR_IF" mtu 1450

    # 4. Ensure source-based policy routing for wl1-sta0 underlay
    ensure_policy_routing

    # 5. Dynamically recreate vxlan150 bound to wl1-sta0 (192.168.1.225)
    ip link del "$VXLAN_IF" 2>/dev/null
    ip link add "$VXLAN_IF" type vxlan id 150 dev wl1-sta0 dstport 4789 remote "$VXLAN_SERVER_IP" local 192.168.1.225
    ip link set "$VXLAN_IF" mtu 1450
    ip link set dev "$VXLAN_IF" master "$BR_IF"
    ip link set "$VXLAN_IF" up
    for vid in $TAGGED_VLANS; do
        bridge vlan add dev "$VXLAN_IF" vid "$vid" 2>/dev/null
    done

    # 5b. Add the same tagged VLANs to the physical LAN trunk ports (same reason as P1).
    # Netgear is still wired to lan4 during P2 failover; tagged VLANs must be allowed
    # on the ingress port for the bridge to forward them across to vxlan150.
    for port in $LAN_TRUNK_PORTS; do
        for vid in $TAGGED_VLANS; do
            bridge vlan add dev "$port" vid "$vid" 2>/dev/null
        done
    done

    # 6. Inform VM 107 via SSH to bridge VLAN 1
    ssh -y -i /root/.ssh/id_ed25519 -o ConnectTimeout=3 -b 192.168.1.225 meek2100@"$VXLAN_SERVER_IP" 'sudo /usr/local/bin/vxlan-nm -p2' >/dev/null 2>&1

    # 7. Add VLAN 1 to vxlan150 locally
    bridge vlan add dev "$VXLAN_IF" vid 1 pvid untagged
    touch /tmp/failover_p2_active

    # 8. Flush ARP/MAC entries
    ip neigh flush all >/dev/null 2>&1
    log_msg "Priority 2 Active (Failover: VLAN 1 added to VXLAN via wl1-sta0)."
}

activate_p3() {
    log_msg "Activating Priority 3 (Relayd)..."
    # Remove VLAN 1 from both P1 and P2; park wan in the probe VLAN (see PROBE_VID)
    bridge vlan del dev "$P1_IF" vid 1 master >/dev/null 2>&1
    park_p1_in_probe_vlan
    bridge vlan del dev "$VXLAN_IF" vid 1 >/dev/null 2>&1
    rm -f /tmp/failover_p2_active
    ip link set "$BR_IF" mtu 1500

    # Inform VM 107
    ensure_policy_routing
    ssh -y -i /root/.ssh/id_ed25519 -o ConnectTimeout=3 -b 192.168.1.225 meek2100@"$VXLAN_SERVER_IP" 'sudo /usr/local/bin/vxlan-nm -p3' >/dev/null 2>&1 &

    # Remove default route on br-lan so wl1-sta0 handles gateway
    ip route del default via 192.168.1.1 dev "$BR_IF" metric 10 2>/dev/null
    ip route add 192.168.1.0/24 dev "$BR_IF" proto static scope link src 192.168.1.226 metric 10 2>/dev/null

    ip neigh flush all >/dev/null 2>&1
    if ! /etc/init.d/relayd status 2>/dev/null | grep -q "running"; then
        /etc/init.d/relayd start >/dev/null 2>&1
    fi
    log_msg "Priority 3 Active (Relayd running for VLAN 1)."
}

# Loop guard: VLAN 1 must never be on wan and vxlan150 (or wan and relayd) at the same time. Runs first
# in every monitor cycle and is NOT rate-limited like integrity_restore, because two VLAN 1 paths are a
# live loop. It keeps the path the controller believes is active and only takes VLAN 1 off the other;
# the normal checks below then decide whether to fail over or back as usual.
loop_guard() {
    bridge vlan show dev "$P1_IF" 2>/dev/null | grep -qE '[[:space:]]1 PVID' || return 0
    _p2=no; _p3=no
    bridge vlan show dev "$VXLAN_IF" 2>/dev/null | grep -qE '[[:space:]]1 PVID' && _p2=yes
    /etc/init.d/relayd status 2>/dev/null | grep -q "running" && _p3=yes
    [ "$_p2" = "no" ] && [ "$_p3" = "no" ] && return 0
    if [ -f /tmp/failover_p2_active ] || [ "$_p3" = "yes" ]; then
        log_msg "LOOP GUARD: VLAN 1 on $P1_IF and on the failover path (P2=$_p2 P3=$_p3) — parking $P1_IF"
        bridge vlan del dev "$P1_IF" vid 1 master >/dev/null 2>&1
        park_p1_in_probe_vlan
    else
        log_msg "LOOP GUARD: VLAN 1 on both $P1_IF and $VXLAN_IF outside failover — removing it from $VXLAN_IF"
        bridge vlan del dev "$VXLAN_IF" vid 1 >/dev/null 2>&1
    fi
}

run_monitor() {
    loop_guard
    if check_p1; then
        FAILS=$(get_fail_count)
        if [ "$FAILS" -gt 0 ]; then
            log_msg "P1 recovered after $FAILS failure(s)"
        fi
        set_fail_count 0
        rm -f "$P1_DOWN_SINCE_FILE" "$P2_DOWN_SINCE_FILE"

        # Check if we need to restore P1 (if P2/P3 active or VID 1 missing from wan or VID 1 on vxlan)
        if [ -f /tmp/failover_p2_active ] || /etc/init.d/relayd status 2>/dev/null | grep -q "running"; then
            log_msg "P1 detected healthy while failover was active — restoring P1"
            activate_p1
        elif ! bridge vlan show dev "$P1_IF" 2>/dev/null | grep -q " 1 "; then
            integrity_restore "VLAN 1 missing from $P1_IF"
        elif bridge vlan show dev "$VXLAN_IF" 2>/dev/null | grep -q " 1 "; then
            integrity_restore "VLAN 1 incorrectly present on $VXLAN_IF"
        elif ! vxlan_admin_up; then
            # vxlan150 missing entirely (e.g. after reboot) — /tmp state was wiped so
            # none of the flags above fire. Recreate the tunnel and tagged VLANs.
            integrity_restore "$VXLAN_IF absent or down"
        else
            # vxlan150 is up — verify every VLAN in TAGGED_VLANS is present on the tunnel
            _VLAN_OUT=$(bridge vlan show dev "$VXLAN_IF" 2>/dev/null)
            _MISSING=""
            for _vid in $TAGGED_VLANS; do
                echo "$_VLAN_OUT" | grep -qw "$_vid" || _MISSING="$_MISSING $_vid"
            done
            if [ -n "$_MISSING" ]; then
                integrity_restore "$VXLAN_IF missing tagged VLANs:$_MISSING"
            else
                # Also verify LAN trunk ports (Netgear uplink → lan4) carry the same VLANs.
                # Without these, tagged frames from the Netgear are dropped at bridge ingress.
                for _port in $LAN_TRUNK_PORTS; do
                    # Only check ports that are actually in the bridge
                    ip link show "$_port" 2>/dev/null | grep -q "master $BR_IF" || continue
                    _PORT_VLAN=$(bridge vlan show dev "$_port" 2>/dev/null)
                    _PORT_MISSING=""
                    for _vid in $TAGGED_VLANS; do
                        echo "$_PORT_VLAN" | grep -qw "$_vid" || _PORT_MISSING="$_PORT_MISSING $_vid"
                    done
                    if [ -n "$_PORT_MISSING" ]; then
                        integrity_restore "$_port missing tagged VLANs:$_PORT_MISSING"
                        break
                    fi
                done
            fi
        fi
        exit 0
    fi


    # P1 check failed - increment and check threshold
    FAILS=$(get_fail_count)
    # Touch fail count file so "Last check" timestamp stays current
    touch "$FAIL_COUNT_FILE"
    if [ "$FAILS" -lt "$FAIL_THRESHOLD" ]; then
        FAILS=$((FAILS + 1))
        set_fail_count "$FAILS"
        log_msg "P1 check failed ($FAILS/$FAIL_THRESHOLD)"
        if [ "$FAILS" -lt "$FAIL_THRESHOLD" ]; then
            exit 0
        fi
        # Threshold just reached — record downtime start
        log_msg "P1 threshold reached — failing over"
        date +%s > "$P1_DOWN_SINCE_FILE"
    fi

    # Threshold reached - failover
    if ping -c 3 -W 2 -I wl1-sta0 "$VXLAN_SERVER_IP" >/dev/null 2>&1; then
        rm -f "$P2_DOWN_SINCE_FILE"
        if [ ! -f /tmp/failover_p2_active ] || ! vxlan_admin_up || ! bridge vlan show dev "$VXLAN_IF" 2>/dev/null | grep -q " 1 "; then
            activate_p2
        fi
    else
        [ ! -f "$P2_DOWN_SINCE_FILE" ] && date +%s > "$P2_DOWN_SINCE_FILE"
        if ! /etc/init.d/relayd status 2>/dev/null | grep -q "running"; then
            activate_p3
        fi
    fi
}

# --- CLI Core ---

show_help() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"

    echo "  -s, --status    Show health and VLAN status"
    echo "  -m, --monitor   Run the failover check logic"
    echo "  -t, --test      Run diagnostic tests"
    echo ""
    echo "  Test sub-options (use with --test):"
    echo "  --all, -a       Run all tests (default)"
    echo "  --icmp, -i      ICMP latency and packet loss"
    echo "  --arp, -r       ARP transparency verification"
    echo "  --mtu, -u       MTU path sweep (1500/1450/1446)"
    echo "  --iperf, -p     TCP bandwidth upload (iperf3)"
    echo "  --udp, -j       UDP jitter and packet loss"
    echo "  --multi, -x     Multi-stream TCP throughput (4P)"
    echo "  --mdns, -m      mDNS service discovery"
    echo "  --ssdp, -s      SSDP device discovery"
    echo "  --vlan, -v      L2 VLAN 40 transparency probe"
    echo "  --dhcp, -d      DHCP relay/offer verification"
    echo "  --gw, -g        Gateway + internet reachability"
    echo "  --local, -L     Run local tests only (skip remote)"
    echo "  --remote, -R    Run remote tests only (skip local)"
    echo ""
    echo "  -p1, --p1       Force Priority 1"
    echo "  -p2, --p2       Force Priority 2"
    echo "  -p3, --p3       Force Priority 3"
    echo "  -h, --help      Show this help"
    echo ""
    echo "Examples:"
    echo "  $0 --test --all           Run full suite"
    echo "  $0 --test --icmp --arp    Run only ping and ARP"
    echo "  $0 --test --iperf --udp   Run bandwidth tests only"
    echo ""
}

case "$1" in
    -s|--status)
        show_status
        ;;
    -m|--monitor)
        run_monitor
        ;;
    -t|--test)
        shift
        PYTHON_PATH=$(which python3 2>/dev/null || which python 2>/dev/null)
        if [ -f "/usr/bin/failover-tester.py" ]; then
            "$PYTHON_PATH" /usr/bin/failover-tester.py "$@"
        else
            echo "Error: failover-tester.py not found at /usr/bin/"
            exit 1
        fi
        ;;
    -p1|--p1)
        activate_p1
        ;;
    -p2|--p2)
        activate_p2
        ;;
    -p3|--p3)
        activate_p3
        ;;
    -h|--help|*)
        show_help
        ;;
esac
