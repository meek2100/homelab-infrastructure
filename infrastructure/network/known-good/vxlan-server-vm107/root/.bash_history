apt install tmux
apt install tmux
apt update
apt upgrade
apt install nano
apt install sudo
adduser meek2100 sudo
exit
apt update
exit
apt update
ls /etc/netplan
nano /etc/network/interfaces
/etc/network/interfaces
nano /etc/network/interfaces
cd /etc/netplan/
sudo ifdown ens18 && sudo ifup br0
ip link set ens18 down
ip link set ens18 up
ip add 192.168.1.150/24 dev br0
ip addr add 192.168.1.150/24 dev br0
brctl show
ip a
exit
which btctl
ls -l /usr/sbin/brctl
ls -l /usr/share/bash-completion/completions/brctl
echo $PATH
hash -r
hash brctl
which btctl
which brctl
brctl --version
which brctl
brctl --version
sudo brctl addbr br0
sudo ip link set br0 up
sudo brctl addif br0 ens18
nano /etc/network/interfaces.d/
nano /etc/network/interfaces
nano /etc/network/interfaces
sudo systemctl restart networking
brctl show
ip a
brctl show
ip a
ip r
ping -c 4 google.com
ping -c 4 192.168.2.10
sudo ip link set up dev vxlan0
sudo modprobe vxlan
ip a
brctl show
sudo modprobe vxlan
sudo ip link add vxlan0 type vxlan id 42 local 192.168.1.150 remote 192.168.1.225 dstport 4789
sudo ip link set up dev vxlan0
sudo brctl addif br0 vxlan0
sudo brctl show
sudo reboot now
lsmod | grep vxlan
sudo modprobe vxlan
sudo ip link add vxlan0 type vxlan id 42 local 192.168.1.150 remote 192.168.1.225 dstport 4789
sudo ip link set up dev vxlan0
sudo brctl addif br0 vxlan0
sudo brctl show
sudo modprobe vxlan
sudo ip link add vxlan0 type vxlan id 42 local 192.168.1.150 remote 192.168.1.225 dstport 4789
sudo ip link set up dev vxlan0
sudo brctl addif br0 vxlan0
sudo brctl show
brctl show
brctl show
ufw
iptables
nftables
sudo ufw status
sudo iptables -L -n -v
sudo nft list ruleset
cat /etc/config/firewall
/etc/init.d/firewall stop
ip link show vxlan42
ip link show vxlan
ip link show vxlan0
ip link show vxlan0
ping 192.168.1.226
ping -c 4 192.168.1.1
ping -c 4 192.168.1.150
sudo ufw disable
sudo nft list ruleset
sudo nft flush ruleset
iw dev
ip a
ping 192.168.1.225
sudo ip link del vxlan0
sudo ip link add vxlan42 type vxlan id 42 local 192.168.1.150 remote 192.168.1.225 dstport 4789
sudo ip link set up dev vxlan42
sudo brctl addif br0 vxlan42
sudo brctl show br0
ping 192.168.1.225
ping -c 4 192.168.1.150
ip route show
ping -c 4 192.168.1.225
ip a show vxlan42
bridge fdb show dev vxlan42
netstat -upan | grep 4789
sudo ip link add vxlan42 type vxlan id 42 local 192.168.1.150 remote 192.168.1.225 dstport 4789
sudo ip link set vxlan42 up
sudo apt update
sudo apt install net-tools
ip a show vxlan42
bridge fdb show dev vxlan42
netstat -upan | grep 4789
sudo ip link add br0 type bridge
ip a
brctl show br0
ip a show br0
ip a show ens18
ip a show vxlan42
sudo bridge fdb show br0
exit
sudo tcpdump -i br0 -n -vv dst 224.0.0.1
sudo tcpdump -i vxlan42 -n -vv dst 224.0.0.1
sudo apt install iperf

sudo apt uninstall iperf
sudo apt remove iperf
sudo apt install iperf
iperf3 -s -u -p 5201
exit
ping 192.168.1.225
brctl show br0
ip a show br0
ip a show ens18
ip a show vxlan42
sudo brctl addif br0 vxlan42
brctl show
sudo ifup vxlan0
exit
nano /etc/systemd/system/vxlan42.service
sudo systemctl enable vxlan42.service
sudo systemctl start vxlan42.service
journalctl -xeu vxlan42.service
nano /etc/systemd/system/vxlan42.service
sudo systemctl daemon-reload
sudo systemctl restart vxlan42.service
journalctl -xeu vxlan42.service
nano /etc/systemd/system/vxlan42.service
sudo systemctl daemon-reload
sudo systemctl restart vxlan42.service
systemctl status vxlan42.service
nano /etc/systemd/system/vxlan42.service
sudo systemctl daemon-reload
sudo systemctl restart vxlan42.service
systemctl status vxlan42.service
nano /etc/systemd/system/vxlan42.service
sudo systemctl daemon-reload
sudo systemctl restart vxlan42.service
systemctl status vxlan42.service
ip a show vxlan42
ip a show br0
nano /etc/network/interfaces
nano /etc/network/interfaces
sudo reboot now
./usr/local/bin/vxlan42-monitor.sh
/usr/local/bin/vxlan42-monitor.sh
cat /var/log/vxlan42-monitor.log
nano /var/log/vxlan42-monitor.log
cat /var/log/vxlan42-monitor.log
sudo systemctl status vxlan42.service
nano /etc/systemd/system/vxlan42.service
sudo systemctl start vxlan42.service
sudo systemctl status vxlan42.service
sudo tail -f /var/log/vxlan42-monitor.log
sudo systemctl daemon-reexec
sudo systemctl restart vxlan42.service
sudo systemctl status vxlan42.service
sudo tail -f /var/log/vxlan42-monitor.log
nano /etc/systemd/system/vxlan42.service
nano /etc/systemd/system/vxlan42.service
sudo systemctl daemon-reexec
sudo systemctl daemon
sudo systemctl daemon-reload
sudo reboot now
cat > /usr/local/bin/vxlan-network-manager.sh <<EOF
#!/bin/bash

SERVICE_NAME="vxlan-network-manager"

# Source the configuration file
if ! source /etc/network/vxlan42.conf; then
    logger -t "$SERVICE_NAME" "Error: Failed to source /etc/network/vxlan42.conf"
    echo "Error: Failed to source /etc/network/vxlan42.conf"
    exit 1
fi

# Ensure required variables are set
if [ -z "$PHYSICAL_IF" ] || [ -z "$BRIDGE_IF" ] || [ -z "$VXLAN_IF" ] || [ -z "$VXLAN_VNI" ] || [ -z "$REMOTE_IP" ] || [ -z "$LOCAL_IP" ]; then
    logger -t "$SERVICE_NAME" "Error: Missing required configuration variables in /etc/network/vxlan42.conf"
    echo "Error: Missing required configuration variables in /etc/network/vxlan42.conf"
    exit 1
fi

# Load VLAN IDs as an array if it's not already
if [[ ! -v VLAN_IDS[@] ]]; then
    if [[ -n "$VLAN_IDS" ]]; then
        # Handle cases where VLAN_IDS might be a space-separated string
        IFS=' ' read -r -a VLAN_IDS <<< "$VLAN_IDS"
    else
        VLAN_IDS=()
    fi
fi

# Set default MTU values if not defined
PHYSICAL_MTU=\${PHYSICAL_MTU:-1500}
BRIDGE_MTU=\${BRIDGE_MTU:-1446}
VXLAN_MTU=\${VXLAN_MTU:-1446}
VXLAN_DST_PORT=\${VXLAN_DST_PORT:-4789}

# Create the bridge interface if it doesn't exist
if ! ip link show "\$BRIDGE_IF" >/dev/null 2>&1; then
    sudo ip link add name "\$BRIDGE_IF" type bridge
    logger -t "\$SERVICE_NAME" "Created bridge interface: \$BRIDGE_IF"
fi

# Set the bridge interface MTU
sudo ip link set dev "\$BRIDGE_IF" mtu "\$BRIDGE_MTU" up
logger -t "\$SERVICE_NAME" "Set bridge interface \$BRIDGE_IF MTU to \$BRIDGE_MTU"

# Create the VXLAN interface if it doesn't exist
if ! ip link show "\$VXLAN_IF" >/dev/null 2>&1; then
    sudo ip link add name "\$VXLAN_IF" type vxlan id "\$VXLAN_VNI" local "\$LOCAL_IP" remote "\$REMOTE_IP" dstport "\$VXLAN_DST_PORT" dev "\$PHYSICAL_IF"
    logger -t "\$SERVICE_NAME" "Created VXLAN interface: \$VXLAN_IF (VNI: \$VXLAN_VNI, Local: \$LOCAL_IP, Remote: \$REMOTE_IP)"
fi

# Set the VXLAN interface MTU
sudo ip link set dev "\$VXLAN_IF" mtu "\$VXLAN_MTU" up
logger -t "\$SERVICE_NAME" "Set VXLAN interface \$VXLAN_IF MTU to \$VXLAN_MTU"

# Add the VXLAN interface to the bridge
sudo brctl addif "\$BRIDGE_IF" "\$VXLAN_IF"
logger -t "\$SERVICE_NAME" "Added VXLAN interface \$VXLAN_IF to bridge \$BRIDGE_IF"

# Add physical interface to the bridge
sudo brctl addif "\$BRIDGE_IF" "\$PHYSICAL_IF"
logger -t "\$SERVICE_NAME" "Added physical interface \$PHYSICAL_IF to bridge \$BRIDGE_IF"

# Bring up the physical interface (if not already up and not a loopback)
if ! ip link show "\$PHYSICAL_IF" | grep -q UP && ! ip link show "\$PHYSICAL_IF" | grep -q LOOPBACK; then
    sudo ip link set dev "\$PHYSICAL_IF" up
    logger -t "\$SERVICE_NAME" "Brought up physical interface: \$PHYSICAL_IF"
fi

# Configure VLAN interfaces and add them to the bridge
if [[ -n "\${\VLAN_IDS[@]}" ]]; then
    for vlan_id in "\${\VLAN_IDS[@]}"; do
        VLAN_IF="vlan\${vlan_id}"
        if ! ip link show "\$VLAN_IF" >/dev/null 2>&1; then
            sudo ip link add link "\$PHYSICAL_IF" name "\$VLAN_IF" type vlan id "\$vlan_id"
            logger -t "\$SERVICE_NAME" "Created VLAN interface: \$VLAN_IF (ID: \$vlan_id)"
        fi
        sudo ip link set dev "\$VLAN_IF" up
        logger -t "\$SERVICE_NAME" "Brought up VLAN interface: \$VLAN_IF"
        sudo brctl addif "\$BRIDGE_IF" "\$VLAN_IF"
        logger -t "\$SERVICE_NAME" "Added VLAN interface \$VLAN_IF to bridge \$BRIDGE_IF"
    done
fi

logger -t "\$SERVICE_NAME" "VXLAN network managed successfully."
echo "VXLAN network managed."

exit 0
EOF

sudo chmod +x /usr/local/bin/vxlan-network-manager.sh
cat > /etc/systemd/system/vxlan-network-manager.service <<EOF
[Unit]
Description=Manage VXLAN network interfaces
After=network.target
Requires=network-online.service
After=network-online.service

[Service]
Type=oneshot
ExecStart=/usr/local/bin/vxlan-network-manager.sh
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable vxlan-network-manager.service
sudo systemctl restart vxlan-network-manager.service
sudo systemctl status vxlan-network-manager.service
sudo systemctl restart vxlan-network-manager.serviceex
exit
/usr/local/bin/configure_network.sh
cd /usr/local/bin
ls
cd ../
ls
cd sbin
ls
cd ..
ls
cd bin
ls
nano vxlan42-monitor.sh
cd /etc/systemd/system/
ls
nano vxlan42-setup.service
nano vxlan42.service
nano vxlan42-setup.service
nano vxlan42.service
nano /usr/local/bin/vxlan42-monitor.sh
nano /usr/local/bin/configure_network.sh
cat <<EOF | sudo tee /etc/network/vxlan42.conf
# VXLAN Tunnel Configuration for vxlan42

VXLAN_IF="vxlan42"
VXLAN_VNI="42"
REMOTE_IP="YOUR_OPENWRT_IP"
LOCAL_IP="YOUR_DEBIAN_IP"
VXLAN_DST_PORT="4789"
EOF

nano /etc/network/vxlan42.conf
ls
cd etc/network
ls
cd /etc/network
ls
nano /etc/network/vxlan42.conf
rm /etc/network/vxlan42.conf
cat <<EOF | sudo tee /etc/network/vxlan42.conf
# VXLAN Connection Configuration

PHYSICAL_IF="ens18"
BRIDGE_IF="br0"
VXLAN_IF="vxlan42"
VXLAN_VNI="42"
REMOTE_IP="192.168.1.225"
LOCAL_IP="192.168.1.150"
VLAN_IDS=("10" "20" "30" "40" "50" "60" "70" "80")
PHYSICAL_MTU="1500"
BRIDGE_MTU="1446"
VXLAN_MTU="1446"
VXLAN_DST_PORT="4789"
EOF

nano /usr/local/bin/vxlan-network-manager.sh
nano /usr/local/bin/vxlan-network-manager.sh
nano /etc/systemd/system/vxlan-network-manager.service
sudo systemctl disable vxlan42-setup.service
sudo systemctl stop vxlan42-setup.service
sudo systemctl disable vxlan42.service
sudo systemctl stop vxlan42.service
sudo systemctl enable vxlan-network-manager.service
sudo systemctl start vxlan-network-manager.service
sudo systemctl status vxlan-network-manager.service # Check for errors
ls -l /usr/local/bin/vxlan-network-manager.sh
sudo chmod +x /usr/local/bin/vxlan-network-manager.sh
head /usr/local/bin/vxlan-network-manager.sh
cat /etc/systemd/system/vxlan-network-manager.service
ExecStart=/usr/local/bin/vxlan-network-manager.sh
sudo systemctl daemon-reload
sudo systemctl restart vxlan-network-manager.service
sudo systemctl status vxlan-network-manager.service
sudo /usr/local/bin/vxlan-network-manager.sh
ping 8.8.8.8
sudo systemctl restart networking.service
ip a show ens18
ping 192.168.1.1
ping 8.8.8.8
sudo reboot now
ip addr show br0
ip addr show vlan40
ip addr show vxlan42
brctl show
sudo systemctl status vxlan-network-manager.service
sudo journalctl -xeu vxlan-network-manager.service
brctl show
ip addr show vlan40
sudo shutdown
exit
ip addr show br0
ip addr show vlan40
ip addr show vxlan42
brctl show
ping 192.168.1.1
ping 8.8.8.8
ping 
xit
exit
ls
rm vxlan-network-manager.log
ls -l
rm vxlan-network-manager-stdout.log
rm vxlan-network-manager-stderr.log
rm vxlan42-stderr.log
rm vxlan42-monitor-stdout.log
ls -l
rm vxlan42-monitor.log
ls
ls
/usr/local/bin/vxlan-network-manager.sh
~/.ssh./known_hosts 
ssh-keygen -t ed25519 -C "debian-to-openwrt"
cd ~/.ssh 
ls
cat id_ed22519.pub
ls
sudo ls 
nano id_ed25519.pub
cd ~/.ssh
ls
nano id_ed25519.pub
exit
exit
exit
apt update
apt upgrade
apt update
apt upgrade
apt autoremove
exit
