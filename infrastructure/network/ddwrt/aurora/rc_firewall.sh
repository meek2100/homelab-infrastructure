wan_if=$(nvram get wan_iface)

# Default to blocking all LAN to WAN traffic on boot
iptables -I FORWARD -i br0 -o "$wan_if" -j REJECT

# Block IPv6 leaks if the module is loaded
if command -v ip6tables &>/dev/null; then
    ip6tables -I FORWARD -i br0 -o "$wan_if" -j REJECT 2>/dev/null || true
fi

# Exempt upstream Luna router (10.20.20.1) management from killswitch
iptables -I FORWARD 1 -d 10.20.20.1 -j ACCEPT
iptables -I FORWARD 1 -s 10.20.20.1 -j ACCEPT

# NAT Masquerade so Luna router accepts packets from any homelab subnet
iptables -t nat -I POSTROUTING 1 -d 10.20.20.1 -j MASQUERADE
