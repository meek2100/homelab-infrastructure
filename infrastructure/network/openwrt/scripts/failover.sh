#!/bin/sh
# failover.sh - Unified 3-Priority Failover Controller for OpenWrt
# Handles Monitoring, State Transitions, Status Reporting, and Testing Wrapper.

LOGFILE="/var/log/failover.log"
TRACK_IP="192.168.1.1"
VXLAN_SERVER_IP="192.168.1.150"
BR_IF="br-lan"
P1_IF="wan"
VXLAN_IF="vxlan150"
FAIL_COUNT_FILE="/tmp/failover_p1_fails"
P1_DOWN_SINCE_FILE="/tmp/failover_p1_down_since"
P2_DOWN_SINCE_FILE="/tmp/failover_p2_down_since"
FAIL_THRESHOLD=3

log_msg() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$LOGFILE"
    logger -t failover -- "$1"
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

    # P1: wan
    P1_STATE=$(get_stp_status "$P1_IF")
    P1_CARRIER=$(get_carrier "$P1_IF")
    P1_MTU=$(get_mtu "$P1_IF")
    if [ "$P1_STATE" = "forwarding" ]; then
        echo "Priority 1 (Wifi 7 Bridge): [ ACTIVE / FORWARDING ] (MTU: $P1_MTU)"
    elif [ "$P1_CARRIER" = "1" ]; then
        echo "Priority 1 (Wifi 7 Bridge): [ STANDBY / $P1_STATE ] (MTU: $P1_MTU)"
    else
        echo "Priority 1 (Wifi 7 Bridge): [ OFFLINE / NO CARRIER ] (MTU: $P1_MTU)"
    fi

    # P2: vxlan150
    P2_MTU=$(get_mtu "$VXLAN_IF")
    if [ -f /tmp/failover_p2_active ]; then
        echo "Priority 2 (VXLAN Tunnel) : [ FAILOVER ACTIVE (VLAN 1 Forwarding) ] (MTU: $P2_MTU)"
    elif bridge link 2>/dev/null | grep -q "$VXLAN_IF"; then
        echo "Priority 2 (VXLAN Tunnel) : [ ACTIVE / TRUNKED (Tagged VLANs Active, VLAN 1 Isolated) ] (MTU: $P2_MTU)"
    elif ip link show "$VXLAN_IF" 2>/dev/null | grep -q "UP"; then
        echo "Priority 2 (VXLAN Tunnel) : [ STANDBY / ADMIN ] (MTU: $P2_MTU)"
    else
        echo "Priority 2 (VXLAN Tunnel) : [ OFFLINE ]"
    fi

    # P3: Relayd (uses br-lan MTU)
    BR_MTU=$(get_mtu "$BR_IF")
    if /etc/init.d/relayd status 2>/dev/null | grep -q "running"; then
        echo "Priority 3 (Relayd)       : [ READY / RUNNING ] (MTU: $BR_MTU)"
    else
        echo "Priority 3 (Relayd)       : [ INACTIVE (Service Stopped) ] (MTU: $BR_MTU)"
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

check_p1() {
    # wan always stays in bridge (managed by netifd)
    # Check if wan is UP and forwarding
    WAN_LINK=$(ip link show "$P1_IF" 2>/dev/null | head -1)
    if echo "$WAN_LINK" | grep -q "state UP"; then
        # wan is UP - check STP convergence
        STP_STATE=$(brctl showstp "$BR_IF" 2>/dev/null | grep -A3 "$P1_IF" | grep "state" | awk '{print $NF}')
        if [ "$STP_STATE" != "forwarding" ]; then
            log_msg "P1 STP state: $STP_STATE (waiting for convergence)"
            return 0
        fi
        ping -c 5 -W 3 -I 192.168.1.226 "$TRACK_IP" >/dev/null 2>&1
        return $?
    fi

    # wan is DOWN - check if physical link is present (carrier)
    # Cannot arping here: STP puts the bridge port in listening state for ~30s,
    # which blocks L2 data frames. Carrier check is sufficient to trigger recovery;
    # the normal UP-path ping validates end-to-end after STP converges.
    ip link set "$P1_IF" up
    for i in $(seq 1 5); do
        if ip link show "$P1_IF" | grep -q "LOWER_UP"; then
            break
        fi
        sleep 1
    done

    CARRIER=$(cat /sys/class/net/$P1_IF/carrier 2>/dev/null || echo 0)

    # Bring wan back DOWN if P2/P3 is currently active
    if [ -f /tmp/failover_p2_active ] || /etc/init.d/relayd status 2>/dev/null | grep -q "running"; then
        ip link set "$P1_IF" down
    fi
    [ "$CARRIER" = "1" ] && return 0 || return 1
}

activate_p1() {
    log_msg "Activating Priority 1 (Wifi 7 Bridge)..."
    /etc/init.d/relayd stop >/dev/null 2>&1
    # Remove VLAN 1 from VXLAN (Mutual Exclusion for VLAN 1, keep tagged VLANs active)
    bridge vlan del dev "$VXLAN_IF" vid 1 >/dev/null 2>&1
    rm -f /tmp/failover_p2_active
    # Repoint vxlan150 back to wired local 192.168.1.226 dev wan
    ip link set dev "$VXLAN_IF" type vxlan local 192.168.1.226 dev "$P1_IF" remote "$VXLAN_SERVER_IP" 2>/dev/null || {
        ip link del "$VXLAN_IF" 2>/dev/null
        ip link add "$VXLAN_IF" type vxlan id 150 dstport 4789 remote "$VXLAN_SERVER_IP" local 192.168.1.226
        ip link set "$VXLAN_IF" master "$BR_IF"
        for vid in 10 20 30 40 100 150 200; do
            bridge vlan add dev "$VXLAN_IF" vid "$vid" 2>/dev/null
        done
    }
    # wan stays in bridge (managed by netifd), just bring it UP
    ip link set "$P1_IF" up
    # DSA PVID Restoration
    bridge vlan add dev "$P1_IF" vid 1 pvid untagged master >/dev/null 2>&1
    bridge vlan del dev "$P1_IF" vid 40 master >/dev/null 2>&1
    ip link set "$BR_IF" mtu 1500
    # Ensure vxlan150 remains in br-lan for tagged traffic
    if ip link show "$VXLAN_IF" >/dev/null 2>&1; then
        bridge link | grep -q "$VXLAN_IF" || ip link set dev "$VXLAN_IF" master "$BR_IF"
    fi
    # Restore br-lan routes (removed during P3 for wl1-sta0 upstream)
    # Connected route first — kernel needs it to validate the gateway next-hop
    ip route add 192.168.1.0/24 dev "$BR_IF" proto static scope link src 192.168.1.226 metric 10 2>/dev/null
    ip route add default via 192.168.1.1 dev "$BR_IF" proto static metric 10 2>/dev/null
    # Inform VM 107
    ssh -y -i /root/.ssh/id_ed25519 meek2100@"$VXLAN_SERVER_IP" 'sudo /usr/local/bin/vxlan-nm -p1' >/dev/null 2>&1 &
    # ARP Storm Prevention: flush stale entries after topology change
    ip neigh flush all >/dev/null 2>&1
    set_fail_count 0
    rm -f "$P1_DOWN_SINCE_FILE" "$P2_DOWN_SINCE_FILE"
    log_msg "Priority 1 Active (Split-Trunking: Tagged on VXLAN, Native on wan)."
}

activate_p2() {
    log_msg "Activating Priority 2 (VXLAN Tunnel)..."
    /etc/init.d/relayd stop >/dev/null 2>&1
    # Disable wan by bringing it DOWN (stays in bridge but STP disabled, no loops)
    ip link set "$P1_IF" down
    # Restore br-lan routes (removed during P3 for wl1-sta0 upstream)
    # Connected route first — kernel needs it to validate the gateway next-hop
    ip route add 192.168.1.0/24 dev "$BR_IF" proto static scope link src 192.168.1.226 metric 10 2>/dev/null
    ip route add default via 192.168.1.1 dev "$BR_IF" proto static metric 10 2>/dev/null
    # Set bridge and tunnel MTU to 1450 (1500 Physical - 50 VXLAN Overhead)
    ip link set "$BR_IF" mtu 1450
    # Dynamically repoint vxlan150 to wl1-sta0 (192.168.1.225)
    ip link set dev "$VXLAN_IF" type vxlan local 192.168.1.225 dev wl1-sta0 remote "$VXLAN_SERVER_IP" 2>/dev/null || {
        ip link del "$VXLAN_IF" 2>/dev/null
        ip link add "$VXLAN_IF" type vxlan id 150 dev wl1-sta0 dstport 4789 remote "$VXLAN_SERVER_IP" local 192.168.1.225
        ip link set dev "$VXLAN_IF" master "$BR_IF"
        for vid in 10 20 30 40 100 150 200; do
            bridge vlan add dev "$VXLAN_IF" vid "$vid" 2>/dev/null
        done
    }
    ip link set "$VXLAN_IF" mtu 1450
    ip link set "$VXLAN_IF" up
    if ! bridge link | grep -q "$VXLAN_IF"; then
        ip link set dev "$VXLAN_IF" master "$BR_IF"
    fi
    # Add VLAN 1 to vxlan150 for failover
    bridge vlan add dev "$VXLAN_IF" vid 1 pvid untagged
    touch /tmp/failover_p2_active
    # Inform VM 107
    ssh -y -i /root/.ssh/id_ed25519 meek2100@"$VXLAN_SERVER_IP" 'sudo /usr/local/bin/vxlan-nm -p2' >/dev/null 2>&1 &
    # ARP Storm Prevention: flush stale entries after topology change
    ip neigh flush all >/dev/null 2>&1
    log_msg "Priority 2 Active (Failover: VLAN 1 added to VXLAN via wl1-sta0)."
}

activate_p3() {
    log_msg "Activating Priority 3 (Relayd)..."
    # Disable both P1 and P2 paths for VLAN 1
    ip link set "$P1_IF" down
    bridge vlan del dev "$VXLAN_IF" vid 1 >/dev/null 2>&1
    rm -f /tmp/failover_p2_active
    ip link set "$BR_IF" mtu 1500
    # Inform VM 107
    ssh -y -i /root/.ssh/id_ed25519 meek2100@"$VXLAN_SERVER_IP" 'sudo /usr/local/bin/vxlan-nm -p3' >/dev/null 2>&1 &
    # Remove br-lan upstream routes — br-lan has no upstream in P3,
    # so wl1-sta0 (metric 100) must handle gateway/internet traffic
    ip route del default via 192.168.1.1 dev "$BR_IF" metric 10 2>/dev/null
    ip route del 192.168.1.0/24 dev "$BR_IF" metric 10 2>/dev/null
    # ARP Storm Prevention: flush stale entries after topology change
    ip neigh flush all >/dev/null 2>&1
    if ! /etc/init.d/relayd status | grep -q "running"; then
        /etc/init.d/relayd start >/dev/null 2>&1
    fi
    log_msg "Priority 3 Active."
}

run_monitor() {
    if check_p1; then
        FAILS=$(get_fail_count)
        if [ "$FAILS" -gt 0 ]; then
            log_msg "P1 recovered after $FAILS failure(s)"
        fi
        set_fail_count 0
        rm -f "$P1_DOWN_SINCE_FILE" "$P2_DOWN_SINCE_FILE"
        # Ensure wan is UP and vxlan does not have VLAN 1
        WAN_STATE=$(ip link show "$P1_IF" 2>/dev/null | head -1)
        if echo "$WAN_STATE" | grep -qv "state UP"; then
            activate_p1
        elif bridge vlan show dev "$VXLAN_IF" 2>/dev/null | grep -q " 1 "; then
            activate_p1
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
        if [ ! -f /tmp/failover_p2_active ]; then
            activate_p2
        fi
    else
        [ ! -f "$P2_DOWN_SINCE_FILE" ] && date +%s > "$P2_DOWN_SINCE_FILE"
        activate_p3
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
