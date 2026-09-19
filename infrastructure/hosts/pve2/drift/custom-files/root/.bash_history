ping 8.8.8.8
traceroute google.com
traceroute google.com
ip -a 
ip a
ip a
bash -c "$(curl -fsSL https://raw.githubusercontent.com/community-scripts/ProxmoxVE/main/ct/alpine-adguard.sh)"
ip a
reboot now
apt update
reboot now
apt update
apt upgrade
apt install intel-microcode
echo "deb http://deb.debian.org/debian/ unstable non-free-firmware" > /etc/apt/sources.list.d/debian-unstable.list
apt update && apt list --upgradable
reboot now
reboot now
apt update
apt upgrade
apt update
apt upgrade
apt install intel-microcode
reboot now
tmux
apt install tmux
traceroute google.com
reboot now
lsblk
lsblk
lsblk
cd /dev/pve
ls
du -h /dev/pve/root
du -h /dev/pve/swap
du -sh /dev/pve/swap
sudo resize2fs /dev/pve/root 20G
resize2fs /dev/pve/root 20G
top
lsblk
sudo umount /dev/mmcblk1p*
umount /dev/mmcblk1p*
fdisk
sudo fdisk /dev/mmcblk1
fdisk /dev/mmcblk1
sudo mkfs.ext4 -L backup /dev/mmcblk1p1
mkfs.ext4 -L backup /dev/mmcblk1p1
sudo mkdir -p /mnt/backup-sd
mkdir -p /mnt/backup-sd
mount /dev/mmcblk1p1 /mnt/backup-sd
blkid /dev/mmcblk1p1
nano /etc/fstab
systemctl daemon-reload
umount /mnt/backup-sd
mount /mnt/backup-sd
exit
mkdir -p /mnt/pve/backup-sd
nano /etc/fstab
systemctl daemon-reload
umount /mnt/backup-sd
mount /dev/mmcblk1p1 /mnt/pve/backup-sd
cat /proc/swaps
swapon -s
free -g
free -k
swapon -s
mount /dev/mmcblk1 /mnt/pve/backup
blkid /dev/mmcblk1p1
reboot now
lsblk
lsblk
lsblk
wipefs -a /dev/sdb
parted /dev/sdb mklabel gpt
fdisk /dev/sdb
sudo mkfs.ext4 -L backup /dev/sdb1
mkfs.ext4 -L backup /dev/sdb1
blkid /dev/sdb1
nano /etc/fstab
systemctl daemon-reload
mount -a
lslbk
lsblk
umount /mnt/pve/backup
mount /mnt/pve/backup
df -h | grep /mnt/pve/backup
exit
reboot now
apt update
apt upgrade
apt upgrade
exit
tmux
exit
apt update 
apt upgrade 
apt autoremove
exot
exit
apt update
apt upgrade
apt autoremove
exit
exit
apt update
apt upgrade
echo 'grub-efi-amd64 grub2/force_efi_extra_removable boolean true' | debconf-set-selections -v -u
apt install --reinstall grub-efi-amd64
apt update
nano /etc/grub/grub.cgf
cd /etc
ls
cd grub.d
ls
exit
nano /etc/default/grub
apt update
apt upgrade
apt autoremove
exit
sudo
apt update
apt upgrade
apt update
apt upgrade
apt autoremove
exit
apt update
apt upgrade
apt autoremove
apt update
apt update
apt upgrade
apt update
apt autoremove
apt update
apt upgrade
apt autoremove
apt update
sudo reboot
reboot now
 pve8to9 --full
apt update
apt upgrade
apt autoremove
 pve8to9 --full
apt remove systemd-boot
apt remove systemd-boot
 pve8to9 --full
apt dist-upgrade
pveversion
sed -i 's/bookworm/trixie/g' /etc/apt/sources.list
sed -i 's/bookworm/trixie/g' /etc/apt/sources.list.d/pve-enterprise.list
sed -i 's/bookworm/trixie/g' /etc/apt/sources.list.d/ceph.list
sed -i 's/bookworm/trixie/g' /etc/apt/sources.list.d/ceph-no-subscription.list
sed -i 's/bookworm/trixie/g' /etc/apt/sources.list.d/pve-no-subscription.list
 pve8to9 --full
apt update
apt update
apt upgrade
apt dist-upgrade
apt modernize-sources
apt update
apt modernize-sources
apt update
apt upgrade
apt autoremove
reboot now
apt update
apt upgrade
apt autoremove
apt update
apt upgrade
pve8to9
apt update
apt upgrade
apt autoremove
apt dist-upgrade
apt modernize-sources
pveversion
apt full-upgrade
reboot now
 pve8to9 --full
/usr/share/pve-manager/migrations/pve-lvm-disable-autoactivation
 pve8to9 --full
systemctl start pvescheduler.service
/usr/share/pve-manager/migrations/pve-lvm-disable-autoactivation
 pve8to9 --full
reboot now
reboot now
reboot now
reboot now
exit
reboot now
pve8to9 --full
systemctl start pvescheduler.service
systemctl status pvescheduler.service
exit
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
apt update
apt upgrade
apt autoremove
apt update
apt upgrade
apt autoremove
apt update
apt upgrade
apt autoremove
apt update
apt upgrade
exit
exit
apt update
apt upgrade
apt autoremove
exit
apt update
apt upgrade
apt update
apt upgrade
apt autoremove
sudo apt update
apt update
apt autoremove
exit
apt update
apt update
apt upgrade
reboot now
apt update
apt upgrade
apt autoremove
reboot now
apt update
apt upgrade
apt update
apt autoremove
sudo apt update
apt update
apt upgrade
apt autoremove
exit
exit
echo -e "\n=== 🖥️  SYSTEM & MOTHERBOARD ===" && dmidecode -s system-product-name 2>/dev/null || hostnamectl | grep "Hardware Model" && echo -e "\n=== 🧠 CPU INFO ===" && lscpu | grep -E "Model name|Core\(s\) per socket|Socket\(s\)|Thread\(s\) per core" && echo -e "\n=== 🗲 RAM TOTAL ===" && free -h | grep Mem | awk '{print "Total Memory: " $2}' && echo -e "\n=== 💾 STORAGE CONTROLLERS & DRIVES ===" && lsblk -o NAME,SIZE,TYPE,MODEL | grep -v "loop" && echo -e "\n=== 🎨 GRAPHICS / GPU ===" && lspci -nn | grep -E -i "vga|3d|display|nvidia|amd|intel"
