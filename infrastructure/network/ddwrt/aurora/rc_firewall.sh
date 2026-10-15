wan_if=$(nvram get wan_iface)
iptables -I FORWARD -i br0 -o "$wan_if" -j REJECT
if command -v ip6tables >/dev/null 2>&1; then
    ip6tables -I FORWARD -i br0 -o "$wan_if" -j REJECT 2>/dev/null || true
fi
iptables -I FORWARD 1 -d 10.20.20.1 -j ACCEPT
iptables -I FORWARD 1 -s 10.20.20.1 -j ACCEPT
iptables -t nat -I POSTROUTING 1 -d 10.20.20.1 -j MASQUERADE

# Force all client DNS on LAN (br0) to router's dnsmasq (10.25.25.1) to prevent leaks
iptables -t nat -I PREROUTING -i br0 -p udp --dport 53 -j DNAT --to-destination 10.25.25.1:53
iptables -t nat -I PREROUTING -i br0 -p tcp --dport 53 -j DNAT --to-destination 10.25.25.1:53

# Clamp TCP MSS on WireGuard tunnel (oet1) to prevent MTU packet drops
iptables -t mangle -I POSTROUTING -o oet1 -p tcp --tcp-flags SYN,RST SYN -j TCPMSS --clamp-mss-to-pmtu
