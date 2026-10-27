wan_if=$(nvram get wan_iface)
[ -z "$wan_if" ] && wan_if="vlan2"

# 1. Killswitch: Disallow LAN forwarding to physical WAN
iptables -I FORWARD -i br0 -o "$wan_if" -j REJECT
if command -v ip6tables >/dev/null 2>&1; then
    ip6tables -I FORWARD -i br0 -o "$wan_if" -j REJECT 2>/dev/null || true
fi

# 2. Allow LAN strictly SSH access to Luna router (10.20.20.1:22) only
iptables -I FORWARD 1 -p tcp -s 10.20.20.1 --sport 22 -m state --state ESTABLISHED -j ACCEPT
iptables -I FORWARD 1 -p tcp -d 10.20.20.1 --dport 22 -j ACCEPT
iptables -t nat -I POSTROUTING 1 -p tcp -d 10.20.20.1 --dport 22 -j MASQUERADE

# 3. Restrict local router egress on physical WAN (no leaks without VPN)
iptables -N WAN_EGRESS_FILTER 2>/dev/null || true
iptables -F WAN_EGRESS_FILTER 2>/dev/null || true
iptables -A WAN_EGRESS_FILTER -p tcp -d 10.20.20.1 --dport 22 -j ACCEPT
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
