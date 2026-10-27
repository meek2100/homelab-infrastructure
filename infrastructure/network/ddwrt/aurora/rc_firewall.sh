wan_if=$(nvram get wan_iface)
[ -z "$wan_if" ] && wan_if="vlan2"

# 1. Killswitch: Disallow general LAN forwarding to physical WAN
iptables -I FORWARD -i br0 -o "$wan_if" -j REJECT
if command -v ip6tables >/dev/null 2>&1; then
    ip6tables -I FORWARD -i br0 -o "$wan_if" -j REJECT 2>/dev/null || true
fi

# 2. Allow LAN management access (SSH, HTTP, HTTPS) to Luna router (10.20.20.1)
# Accessible from 192.168.1.0/24 (VLAN 1), 192.168.10.0/24 (VLAN 10), and local LAN (10.25.25.0/24)
iptables -I FORWARD 1 -s 10.20.20.1 -m state --state ESTABLISHED,RELATED -j ACCEPT
for src_net in 192.168.1.0/24 192.168.10.0/24 10.25.25.0/24; do
    for port in 22 80 443; do
        iptables -I FORWARD 2 -i br0 -s "$src_net" -d 10.20.20.1 -p tcp --dport "$port" -j ACCEPT
    done
done

for port in 22 80 443; do
    iptables -t nat -I POSTROUTING 1 -o "$wan_if" -d 10.20.20.1 -p tcp --dport "$port" -j MASQUERADE
done

# 3. Restrict local router egress on physical WAN (bare minimum when VPN is down)
iptables -N WAN_EGRESS_FILTER 2>/dev/null || true
iptables -F WAN_EGRESS_FILTER 2>/dev/null || true
for port in 22 80 443; do
    iptables -A WAN_EGRESS_FILTER -d 10.20.20.1 -p tcp --dport "$port" -j ACCEPT
done
iptables -A WAN_EGRESS_FILTER -p udp --dport 123 -j ACCEPT
iptables -A WAN_EGRESS_FILTER -p udp --dport 1337 -j ACCEPT
iptables -A WAN_EGRESS_FILTER -p udp --dport 51820 -j ACCEPT
iptables -A WAN_EGRESS_FILTER -d 10.25.25.0/24 -j ACCEPT
iptables -A WAN_EGRESS_FILTER -j REJECT
if ! iptables -C OUTPUT -o "$wan_if" -j WAN_EGRESS_FILTER 2>/dev/null; then
    iptables -I OUTPUT -o "$wan_if" -j WAN_EGRESS_FILTER
fi

# 4. Force all client DNS on LAN (br0) to router's dnsmasq (10.25.25.1) to prevent leaks
iptables -t nat -I PREROUTING -i br0 -p udp --dport 53 -j DNAT --to-destination 10.25.25.1:53
iptables -t nat -I PREROUTING -i br0 -p tcp --dport 53 -j DNAT --to-destination 10.25.25.1:53

# 5. Clamp TCP MSS on WireGuard tunnel (oet1) to prevent MTU packet drops
iptables -t mangle -I POSTROUTING -o oet1 -p tcp --tcp-flags SYN,RST SYN -j TCPMSS --clamp-mss-to-pmtu
