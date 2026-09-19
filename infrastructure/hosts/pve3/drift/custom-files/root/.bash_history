apt update
apt upgrade
apt upgrade
apt update
apt upgrade
apt autoremove
shutdown now
apt install tmux
apt upgrade
apt autoremove
ip a
exit
ip a
lsblk
cd /etc
ls
cd pve
ls
cd storage.cfg
nano storage.cfg
lsblk
lsblk
sudo mkdir /media/sdcard_data
mkdir /media/sdcard_data
mount /dev/sdc1 /media/sdcard_data
ls /media/sdcard_data
umount /media/sdcard_data
rm -rf /media/sdcard_data
exit
lsblk
fdisk /dev/sdd
ping 8.8.8.8
traceroute google.com
fast
cd /etc/pve/qemu-server/
ls
nano 101.conf
cd /dev/pve
ls
ip a
apt update
apt upgrade
apt update
apt upgrade
apt autoremove
exit
ip a
apt update
apt upgrade
pve8to9 --full
pve8to9 --full
pve8to9 --full
apt update
apt upgrade
apt autoremove
apt update
apt upgrade
apt autoremove
apt modernize-sources
apt autoremove
apt dist-upgrade
apt update
apt modernize-sources
apt update
apt upgrade
apt upgrade
apt update
apt upgrade
apt update
apt autoremove
apt dist-upgrade
pveversion
apt full-upgrade
reboot now
pve8to9 --full
/usr/share/pve-manager/migrations/pve-lvm-disable-autoactivation
pve8to9 --full
reboot now
pve8to9 --full
apt update
apt upgrade
apt autoremove
exit
apt update
apt upgrade
apt upgrade
apt autoremove
exit
ip a
apt update
apt upgrade
apt autoremove
exit
apt update
apt upgrade
apt update
apt upgrade
apt autoremove
apt update
apt upgrade
apt autoremove
sudo apt update
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
apt autoremove
exit
sudo dmidecode -t memory | grep -E "Size:|Locator:|Speed:|Type:"
dmidecode -t memory | grep -E "Size:|Locator:|Speed:|Type:"
sudo dmidecode -t memory | grep -E "Size|Locator"
dmidecode -t memory | grep -E "Size|Locator"
apt update
apt upgrade
apt upgrade
reboot now
sudo apt update
apt update
apt upgrade
apt autoremove
sudo reboot now
reboot now
ip a
exit
lspci | grep -i -E "wireless|network|bluetooth"
lspci -nnk | grep -iA 3 "network"
dmesg | grep -iE "iwlwifi|btusb|firmware"
lsusb
dmesg | grep -iE "usb|bluetooth|btusb"
modprobe -r btusb
modprobe btusb
apt update
apt upgrade
apt update
apt autoremove
sudo reboot now
reboot now
apt update
apt upgrade
apt autoremove
exit
echo -e "\n=== 🖥️  SYSTEM & MOTHERBOARD ===" && dmidecode -s system-product-name 2>/dev/null || hostnamectl | grep "Hardware Model" && echo -e "\n=== 🧠 CPU INFO ===" && lscpu | grep -E "Model name|Core\(s\) per socket|Socket\(s\)|Thread\(s\) per core" && echo -e "\n=== 🗲 RAM TOTAL ===" && free -h | grep Mem | awk '{print "Total Memory: " $2}' && echo -e "\n=== 💾 STORAGE CONTROLLERS & DRIVES ===" && lsblk -o NAME,SIZE,TYPE,MODEL | grep -v "loop" && echo -e "\n=== 🎨 GRAPHICS / GPU ===" && lspci -nn | grep -E -i "vga|3d|display|nvidia|amd|intel"
