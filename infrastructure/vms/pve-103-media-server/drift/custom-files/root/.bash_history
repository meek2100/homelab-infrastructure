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
apt update
apt upgrade
apt autoremove
exit
cd /
ls

ls
$HOST
exit
nano /etc/fstab
ls
cd ../
ls
cd /
ls
cd mnt
ls
cd media
ls
exit
cd /var/lib/docker
ls
cd image
ls
cd overlay2
ls
cd /var/lib/docker/volumes/portainer_data/_data/compose
ls
cd 74
ls
cd v1
ls
nano docker-compose.yml
cd ../
ls
cd ../
ls
cd ../
ls
cd ..
ls
cd ..
ls
cd ..
ls
cd contrainers
ls
exit
growpart /dev/sda 3
pvresize /dev/sda3
lvdisplay
pvdisplay
lvextend -l +100%FREE /dev/ubuntu-vg/ubuntu-lv
resize2fs /dev/ubuntu-vg/ubuntu-lv
sudo reboot now
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
reboot
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
61
apt update
apt upgrade
apt update
apt upgrade
apt autoremove
nano /etc/fstab
shutdown now
nano /etc/fstab
exit
apt update
apt upgrade
lsblk
cd /
ls
cd mnt
ls
cd media
ls
cd content
ls
61;4;6;7;14;21;22;23;24;
nano /etc/fstab
systemctl daemon-reload
mount | grep /mnt/media
ls -l /mnt/media
sudo umount -l /mnt/media
sudo mount /mnt/media
mount | grep /mnt/media
ls -l /mnt/media
cd /
cd mnt
ls
cd media
ls
cd content
ls
exit
apt update
apt upgrade
apt autoremove
apt update
apt upgrade
apt autoremove
apt upgrade
apt autoremove
exit
apt update
apt upgrade
apt autoremove
exit
apt update
apt upgrade
reboot now
61;4;6;7;14;21;22;
apt update
apt upgrade
apt autoremove
ls
cd docker
ls
cd homarr
ls
cd config
ls
ls -l
cd appdata
ls
cd db
ls
cd /
find db.sqlite
which db.sqlite
grep db.sqlite
find / -name "db.sqlite"
rsync
exit
ls
find / -name "db.sqlite"
rsync -a /homarr/config /home/meek2100/docker/homarr/config
rm -rf /homarr
find / -name "db.sqlite"
rsync -a /home/meek2100/docker/homarr/config/config /homarr/config
mkdir -p /homarr/config
rsync -a /home/meek2100/docker/homarr/config/config /homarr/config
find / -name "db.sqlite"
rsync -a /homarr/config/config /homarr
ls
find / -name "db.sqlite"
rm -rf /homarr/config/config
find / -name "db.sqlite"
rm -rf /home/meek2100/docker/homarr/config/config
find / -name "db.sqlite"
rsync -a /homarr/config /home/meek2100/docker/homarr
find / -name "db.sqlite"
rm -rf /homarr/config/db/db.sqlite
ls
sudo reboot now
