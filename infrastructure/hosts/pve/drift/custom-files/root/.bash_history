bridge vlan show dev vmbr0
bridge vlan show
bridge vlan show dev vmbr0
bridge vlan show
ifreload -a
cat /etc/network/interfaces
bridge vlan show
cat /etc/network/interfaces
# Show only vmbr0’s VLAN memberships:
bridge vlan show dev vmbr0
bridge vlan add dev vmbr0 vid 40
ip link set dev vmbr0 type bridge vlan_filtering 1
bridge vlan add dev vmbr0 vid 40
bridge vlan show dev vmbr0
bridge vlan show dev lan0
ip a
brctl show
bridge vlan add dev vmbr0 vid 40
# Tell the bridge “I want VLAN 40 on vmbr0 (the bridge device) itself.”
bridge vlan add dev vmbr0 vid 40 self
bridge vlan show dev vmbr0
bridge vlan show dev lan0
ip link del macvlan1   2>/dev/null || true
nano /etc/network/interfaces
ifdown --ignore-errors vmbr0
sudo ifup vmbr0
ip link set dev vmbr0 type bridge vlan_filtering 1
bridge vlan add dev vmbr0 vid 40 self
bridge vlan show dev vmbr0
bridge vlan add dev lan0 vid 1 pvid untagged
bridge vlan add dev lan0 vid 40 tagged
sudo ip link set dev vmbr0 type bridge vlan_filtering 1
ip link set dev vmbr0 type bridge vlan_filtering 1
bridge vlan add dev vmbr0 vid 40 self
bridge vlan add dev lan0 vid 1 pvid untagged
bridge vlan add dev lan0 vid 40 tagged
cat /etc/network/interfaces
ip link show vmbr0
bridge vlan show dev vmbr0
bridge vlan show dev lan0
nano nano /etc/pve/qemu-server/100.conf
cat /etc/pve/qemu-server/100.conf
cat /etc/pve/qemu-server/100.conf
nano /etc/pve/qemu-server/100.conf
ip link show vmbr0
bridge vlan show dev vmbr0
nano /etc/pve/qemu-server/100.conf
nano /etc/pve/qemu-server/100.conf
sudo
nginx -t
cd /etc/nginx/conf.d
ls -l
ls | cat
dig luna.theurer.secure.dev
cd /etc/nginx/conf.d
ls | cat
apt update
apt upgrade
apt update
apt upgrade
-s --app nginx-proxy-manager
python -v
python -v
cat apt/history.log
cat /var/log/apt/history.log
apt update
apt update
apt upgrade
apt update
apt autoremove
apt update
apt upgrade
apt autoremove
ls
cd /
ls
cd /etc
ls
cd cron.daily
ls
cat pvehost-backup
nano pvehost-backup
cd /usr/local/bin/
ls
nano sysprep.sh
chmod +x sysprep.sh
ls
ls -l
ls
cd /etc/cron.daily
ls
ls -l
./pvehost-backup
sudo apt update
apt update
ls
nano Proxmox-Enhanced-Configuration-Utility
cd Proxmox-Enhanced-Configuration-Utility
ls
cat README.md
ping 8.8.8.8
ping 8.8.8.8
ping 8.8.8.8
traceroute google.com
exit
cd /etc/lvm
ls
nano lvm.conf
cd profile
ls
cd ..
ls
cd ..
ls
cd pve
ls
cd nodes
ls
cd pve
ls
cd config
ls
nano config
cd openvz
ls
cd ..
ls
cd priv
ls
cd ..
cd ..
ls
cd ..
ls
cd ..
ls
cd ..
cd var
cd lib
cd vz
ls
cd dump
ls
cd ..
ls
cd images
ls
cd ..
ls
cd ..
ls
cd pve
ls
cd ..
ls
cd qemu-server
ls
cd ..
ls
cd ..
ls
cd ..
ls
cd /etc/lvm.conf
ls
nano /etc/lvm.conf
cd /etc
ls
lvm.conf
nano lvm.conf
cd lvm
ls
nano lvm.conf
cd /dev
ls
cd pve
ls
cd vm-100-disk-0
cd /dev
cd vm-100-disk-0
cd pve
ls
exit
cd /etc/pve/qemu-server/
ls
nano 101.conf
cd /dev/pve
ls
nano vm-101-disk-0
cd vm-101-disk-0
cat vm-101-disk-0
apt update
ip a
apt update
apt upgrade
pve8to9 --full
cd /etc/lvm
ls
cd ..
cd pve
ls
nano storage.cfg
exit
apt autoremove
apt update
apt upgrade
pve8to9 --full
pve8to9 --full
apt update
apt upgrade
apt autoremove
apt remove systemd-boot
pve8to9 --full
/usr/share/pve-manager/migrations/pve-lvm-disable-autoactivation
/usr/share/pve-manager/migrations/pve-lvm-disable-autoactivation
/usr/share/pve-manager/migrations/pve-lvm-disable-autoactivation
pve8to9 --full
apt update
apt upgrade
apt modernize-sources
apt update
apt upgrade
apt policy intel-microcode
apt install intel-microcode=3.20250812.1~deb12u1
apt update
apt upgrade
apt autoremove
pve8to9 --full
apt dist-upgrade
sed -i 's/bookworm/trixie/g' /etc/apt/sources.list
sed -i 's/bookworm/trixie/g' /etc/apt/sources.list.d/pve-enterprise.list
apt update
apt dist-upgrade
apt update
apt update
apt upgrade
apt autoremove
apt modernize-sources
apt update
apt upgrade
apt autoremove
reboot now
reboot now
pve8to9 --full
apt update
apt upgrade
apt autoremove
exit
apt update
apt upgrade
apt update
apt upgrade
apt autoremove
exit
apt update
apt upgrade
apt autoremove
exit
apt update
apt upgrade
apt update
apt upgrade
apt upgrade
apt autoremove
apt update
apt upgrade
apt autoremove
lsmod | grep 8021q
ip link show
bridge vlan show
cat /etc/network/interfaces
ip a
exit
sudo apt update
apt update
apt upgrade
sudo apt update
apt update
apt upgrade
apt autoremove
exit
sudo apt update
apt update
sudo apt upgrade
apt upgrade
apt auto-remove
exit
apt update
apt upgrade
apt autoremove
apt update
apt upgrade
apt autoremove
apt update
apt autoremove
exit
lsblk
sudo mkdir -p /mnt/pi
mkdir -p /mnt/pi
mount /dev/sdc1 /mnt/pi
lsblk
cd /mnt
ls
cd pi
ls
cd backup
ls
ls
cd dump
ls
cd ..
cd images
ls
cd ..
ls
cd ..
ls
rm /mnt/pi
rm -rf /mnt/pi
umount /mnt/pi
reboot now
lsblk
fsidk -l
fdisk -l
lsblk
fdisk -l
lsblk
cd /mnt/pve/backup2
ls
cd dump
ls
cd ..
ls
cd /
lsblk
sudo reboot now
shutdown
exit
lsblk
mkdir -p /mnt/pi
mount /mmcblk0/mmcblk0p2 /mnt/pi
mkdir -p /mnt/pi_root
mount /dev/mmcblk0p2 /mnt/pi_root
ls /mnt/pi_root
cd /mnt/pi_root
ls
cd etc
ls
nano /mnt/pi_root/etc/wpa_supplicant/wpa_supplicant.conf
cd /mnt/pi_root/etc/network/interfaces.d
ls
cd ..
ls
cd interfaces
ls
cd interfaces
nano interfaces
nano interfaces
nano /mnt/pi_root/etc/wpa_supplicant/wpa_supplicant.conf
sync
umount /mnt/pi_root
cd /root
fuser -kv /mnt/pi_root
umount /mnt/pi_root
umount /mnt/pi_boot
lsblk
mkdir -p /mnt/pi_boot
mount /dev/mmcblk0p1 /mnt/pi_boot
ls
cd /mnt/pi_boot
ls
cat Automation_Custom_PreScript.sh
nano cmdline.txt
echo "root=PARTUUID=7dcddcf2-02 rootfstype=ext4 rootwait fsck.repair=yes net.ifnames=0 logo.nologo console=tty1 isolcpus=3 irqaffinity=0-2" > /mnt/pi_boot/cmdline.txt
nano cmdline.txt
cat cmdline.txt
nano /mnt/pi_boot/config.txt
sync
umount /mnt/pi_root
umount /mnt/pi_boot
cd /root
umount /mnt/pi_boot
cd mnt
ls
cd /mnt
ls
cd pi_boot
ls
cd ..
cd pi_root
ls
cd ..
rm -rf pi_boot
rm -rf pi_root
rm -rf pi
ls
shutdown
lsblk
mkdir -p /mnt/pi_root
mount /dev/mmcblk0p2 /mnt/pi_root

mount /dev/mmcblk0p2 /mnt/pi_root
sudo reboot now
lsblk
fdisk -l
ls /dev/mmcblk0p2
mount /dev/mmcblk0p2
mount /mnt/pi_root /dev/mmcblk0p2
mount /dev/mmcblk0p2
mount /mnt/pi_root /dev/mmcblk0p2
reboot now
lsblk
mkdir -p /mnt/pi_root
mount /mnt/pi_root /dev/mmcblk0p2
mount /mnt/pi_root /dev/mmcblk0p2
mount /dev/mmcblk0p2 /mnt/pi_root
mkdir -p /mnt/pi_boot
mount /dev/mmcblk0p1 /mnt/pi_boot
mount /dev/mmcblk0p1 /mnt/pi_boot
reboot now
mount /dev/mmcblk0p1 /mnt/pi_boot
umount /dev/mmcblk0p1 /mnt/pi_boot
mount /dev/mmcblk0p1 /mnt/pi_boot
mount /dev/mmcblk0p1 /mnt/pi_boot
mount /dev/mmcblk0p2 /mnt/pi_root
mount /dev/mmcblk0p2 /mnt/pi_root
shutdown -now
shutdown --now
shutdown -h
shutdown -c
shutdown --h
shutdown --help
shutdown -p now
shutdown now
mount /dev/mmcblk0p2 /mnt/pi_root
cd /mnt/pi_root
ls
nano /etc/wpa_supplicant/wpa_supplicant.conf
nano /etc/wpa_supplicant/wpa_supplicant.conf
nano /mnt/pi_root/etc/wpa_supplicant/wpa_supplicant.conf
cat /mnt/pi_root/home/meek2100/logs/hardware_errors.log
cat /mnt/pi_root/home/meek2100/logs/software_errors.log
nano /mnt/pi_root/etc/wpa_supplicant/wpa_supplicant.conf
shutdown now
apt update
apt upgrade
reboot now
exit
apt update
apt upgrade
apt autoremove
reboot now
lsusb
qm set 100 -usb0 host=8087:0026
qm set 100 -delete usb0
lsusb
qm set 102 -usb0 host=8087:0026
lsusb
dmesg | grep -i bluetooth
qm set 102 -delete usb0
lspci | grep -i -E "wireless|network|bluetooth"
lspci -nnk | grep -iA 3 "network"
dmesg | grep -iE "iwlwifi|btusb|firmware"
cat /proc/cpuinfo
cat /proc/cpuinfo
\
sudo lshw -short
sudo lshw -short
lshw -short
lshw
uname
uname -a
lscpu
free -hj
free -h
lsblk
lsusb
exit
ping 8.8.8.8
ping 8.8.8.8
exit
apt update
apt upgrade
apt update
apt autoremove
ls
nvidia-smi
nvidia-smi
lspci
ls
exit
apt update
apt upgrade
apt update
apt upgrade
apt autoremove
exit
nvidia-smi
cat /etc/default/grub
echo -e "\n=== 🖥️  SYSTEM & MOTHERBOARD ===" && dmidecode -s system-product-name 2>/dev/null || hostnamectl | grep "Hardware Model" && echo -e "\n=== 🧠 CPU INFO ===" && lscpu | grep -E "Model name|Core\(s\) per socket|Socket\(s\)|Thread\(s\) per core" && echo -e "\n=== 🗲 RAM TOTAL ===" && free -h | grep Mem | awk '{print "Total Memory: " $2}' && echo -e "\n=== 💾 STORAGE CONTROLLERS & DRIVES ===" && lsblk -o NAME,SIZE,TYPE,MODEL | grep -v "loop" && echo -e "\n=== 🎨 GRAPHICS / GPU ===" && lspci -nn | grep -E -i "vga|3d|display|nvidia|amd|intel"
