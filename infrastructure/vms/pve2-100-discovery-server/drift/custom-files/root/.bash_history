apt update
apt upgrade
apt update
apt upgrade
apt autoremove
apt-get install qemu-guest-agent
# Add Docker's official GPG key:
sudo apt-get update
sudo apt-get install ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
# Add the repository to Apt sources:
echo   "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" |   sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo docker run hello-world
docker container list
docker image list
docker image remove d2c94e258dcb
docker container list -a
docker container remove hello-world
docker container remove 859fc2b35577
docker image remove d2c94e258dcb
docker image list
docker container list -a
exit
sudo install nfs-common
sudo apt install nfs-common
nano /etc/fstab
reboot now
nano /etc/fstab
reboot now
61;6;7;14;21;22;23;24;28;32;42c0;10;1c
apt update
apt upgrade
apt autoremove
docker -v
docker volume create portainer_data
docker run -d -p 8000:8000 -p 9443:9443 --name portainer --restart=always -v /var/run/docker.sock:/var/run/docker.sock -v portainer_data:/data portainer/portainer-ee:2.21.5
cd /var/lib/docker/volumes/portainer_data/data/
cd /var/lib/docker/volumes
ls
cd portainer_data
ls
cd _data
ls
cd compose
ls
cd 19
ls
cd v13
ls
cd ../
ls
cd -r v13 fd27b9f7f6ede5ffee7822273d3b51353cb56212
cp -r v13 fd27b9f7f6ede5ffee7822273d3b51353cb56212
ls
cd ../
ls
cd ../
ls
cd ../
cd compose
ls
cd _data
ls
cd compose
ls
exit
docker ps
docker stop portainer
docker rm portainer
docker run -d -p 8000:8000 -p 9443:9443 --name portainer --restart=always -v /var/run/docker.sock:/var/run/docker.sock -v portainer_data:/data portainer/portainer-ee:latest
reboot now
ls
cd /mnt/media
ls
mv docker2.zip /home/meek2100
ls
sudo mv docker2.zip /home/meek2100
cp docker2.zip /home/meek2100
ls
cd ../
ls
cd home
ls
cd meek2100
ls
unzip docker2.zip
apt install unzip
unzip docker2.zip
ls
mv docker docker1
ls
mv docker2 docker
ls
sudo chown -R meek2100: /home/meek2100/
ls
cd docker
ls
cd ../
ls
cd docker1
ls
cd ../
ls
rm docker
rm -rf docker
ls
rm docker2.zip
mv docker1 docker
ls
sudo chown -R meek2100: /home/meek2100/
ls -l
exit
rsync
apt install rsync
apt-mark auto rsync
ls
sudo hostnamectl set-hostname discovery-server
ls
docker stop portainer
docker rm portainer
docker volume rm portainer_data
docker volume create portainer_data
docker run -d -p 8000:8000 -p 9443:9443 --name portainer --restart=always -v /var/run/docker.sock:/var/run/docker.sock -v portainer_data:/data portainer/portainer-ee:latest
cd /var/lib/docker/volumes/portainer_data/data/
cd /var/lib/docker/volumes/portainer_data/
ls
cd _data
ls
cd compose
ls
cd 19
ls
cp -r v13 fd27b9f7f6ede5ffee7822273d3b51353cb56212
ls\
ls
cd ../
ls
cd ../
ls
cd mnt
ls
cd media
l
ls
cd share
ls
rm -rf lazylibrarian
ls
exit
growpart /dev/sda 3
pvresize /dev/sda3
lvextend -l +100%FREE /dev/ubuntu-vg/ubuntu-lv
resize2fs /dev/ubuntu-vg/ubuntu-lv
lsblk
sudo reboot now
cd 	/var/lib/docker/volumes/6a475cdfe8d6d1f647f64f42e2c12db1ed5928c434397ce90bfa574697f238d6/_data
ls
cp ngircd.conf /home/meek2100/docker/ngircd/config/ngircd.conf
ls
cd ../
ls
cd /
ls
cd home
ls
cd meek2100
ls
cd docker
ls
rm -rf ngircd2
ls
cd ngircd
ls
rm -rf config2
ls
cd config
ls
cp ngircd.conf /home/meek2100/docker/ngircd/
ls
cd /home/meek2100/docker/ngircd/
ls
cd config
ls
exit
shutdown now
apt update
apt upgrade
apt autoremove
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
exit
apt update
apt upgrade
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
apt update
apt upgrade
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
apt autoremove
exit
61;4;6;7;14;21;22;23;24;28;32;42c0;10;1c
apt update
apt upgrade
apt autoremove
docker stop portainer
docker rm portainer
docker pull portainer/portainer-ee:latest
docker run -d -p 8000:8000 -p 9443:9443 --name=portainer --restart=always -v /var/run/docker.sock:/var/run/docker.sock -v portainer_data:/data portainer/portainer-ee:latest
free -h
sudo fallocate -l 8G /swapfile.img
cd /
ls
cd root
ls
cd ../
ls
cd ../
ls
cd home
ls
cd meek2100
ls
sudo chmod 0600 /swapfile.img
sudo mkswap /swapfile.img
sudo swapon /swapfile.img
sudo swapon -s
sudo swapoff /swapfile
sudo swapoff /swapfile.img
sudo swapon -s
sudo swapoff /swapfile
sudo swapoff /swap.img
sudo dd if=/dev/zero of=/swap.img bs=1M count=1024 oflag=append conv=notrunc
sudo mkswap /swap.img
sudo swapoff /swap.img
sudo swapon -s
sudo fallocate -l 8G /swap.img
sudo chmod 0600 /swap.img
sudo mkswap /swap.img
sudo swapon /swap.img
sudo swapon -s
sudo cp /etc/fstab /etc/fstab.bak
sudo nano /etc/fstab
rm /etc/fstab.bak
ls
sudo swapon -s
sudo swapon -a
sudo free -h
cd /var/log/nginx/
ls
apt update
nano /etc/systemd/sleep.conf
apt upgrade
cd /var/log/nginx/
sudo tmux
apt update
apt upgrade
apt autoremove
mount | grep /mnt/media
ls -l /mnt/media
sudo umount -l /mnt/media
sudo mount /mnt/media
mount | grep /mnt/media
ls -l /mnt/media
exit
nano /etc/fstab
systemctl daemon-reload
nano /etc/fstab
apt update
apt upgrade
apt update
apt upgrade
apt autoremove
exit
apt update
apt upgrade
exit
apt update
apt upgrade
apt update
apt upgrade
apt autoremove
