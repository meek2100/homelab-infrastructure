wan_if=$(nvram get wan_iface)
iptables -I FORWARD -i br0 -o "$wan_if" -j REJECT
if command -v ip6tables >/dev/null 2>&1; then
    ip6tables -I FORWARD -i br0 -o "$wan_if" -j REJECT 2>/dev/null || true
fi
iptables -I FORWARD 1 -d 10.20.20.1 -j ACCEPT
iptables -I FORWARD 1 -s 10.20.20.1 -j ACCEPT
iptables -t nat -I POSTROUTING 1 -d 10.20.20.1 -j MASQUERADE
