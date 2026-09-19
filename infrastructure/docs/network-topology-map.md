# 🌐 Comprehensive Network Topology & Subnet Map

This document outlines all physical host bridges, VLANs, static IP assignments, and private storage networks across `pve`, `pve2`, `pve3`, and all virtual machines.

--- 


## 🛜 Subnet Breakdown


1. **Primary Management & Service LAN (`192.168.1.0/24`)**:

   - Primary home network subnet used for Proxmox GUI management, DNS (`AdGuard`), WireGuard, Cloudflare Tunnel, Web applications, and default VM egress.

2. **Private High-Speed NAS Storage LAN (`10.25.25.0/24`)**:

   - Isolated, dedicated storage network linking `pve3` (`nas-server` OpenMediaVault), `pve2` (`discovery-server`), and storage clients for direct NFS/SMB/iSCSI backup and download traffic without saturating the primary management LAN.

3. **VLAN 40 (`Smart Home / IoT`) & VLAN 50 (`Isolated Security`)**:

   - Virtual local area networks defined on `pve2` (`vmbr0.40` & `vmbr0.50`) and passed to `luna-server` via `macvlan`.


--- 


## 🖥️ Physical Proxmox Host Network Interfaces & Routing Table


### Proxmox Host: `pve` (`192.168.1.250`)


#### Network Interfaces & IPs
```text

1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN group default qlen 1000
    inet 127.0.0.1/8 scope host lo
       valid_lft forever preferred_lft forever
3: vmbr0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP group default qlen 1000
    inet 192.168.1.250/24 scope global vmbr0
       valid_lft forever preferred_lft forever
4: vmbr1: <NO-CARRIER,BROADCAST,MULTICAST,UP> mtu 1500 qdisc noqueue state DOWN group default qlen 1000
    inet 10.25.25.250/24 scope global vmbr1
       valid_lft forever preferred_lft forever
```


#### Routing Table
```text

default via 192.168.1.1 dev vmbr0 proto kernel onlink 
10.25.25.0/24 dev vmbr1 proto kernel scope link src 10.25.25.250 linkdown 
192.168.1.0/24 dev vmbr0 proto kernel scope link src 192.168.1.250
```


### Proxmox Host: `pve2` (`192.168.1.240`)


#### Network Interfaces & IPs
```text

1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN group default qlen 1000
    inet 127.0.0.1/8 scope host lo
       valid_lft forever preferred_lft forever
5: vmbr1: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP group default qlen 1000
    inet 10.25.25.240/24 scope global vmbr1
       valid_lft forever preferred_lft forever
6: vmbr0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP group default qlen 1000
    inet 192.168.1.240/24 scope global vmbr0
       valid_lft forever preferred_lft forever
7: vmbr0.40@vmbr0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP group default qlen 1000
    inet 192.168.40.240/24 scope global vmbr0.40
       valid_lft forever preferred_lft forever
8: vmbr0.50@vmbr0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP group default qlen 1000
    inet 192.168.50.240/24 scope global vmbr0.50
       valid_lft forever preferred_lft forever
```


#### Routing Table
```text

default via 192.168.1.1 dev vmbr0 proto kernel onlink 
10.25.25.0/24 dev vmbr1 proto kernel scope link src 10.25.25.240 
192.168.1.0/24 dev vmbr0 proto kernel scope link src 192.168.1.240 
192.168.40.0/24 dev vmbr0.40 proto kernel scope link src 192.168.40.240 
192.168.50.0/24 dev vmbr0.50 proto kernel scope link src 192.168.50.240
```


### Proxmox Host: `pve3` (`192.168.1.245`)


#### Network Interfaces & IPs
```text

1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN group default qlen 1000
    inet 127.0.0.1/8 scope host lo
       valid_lft forever preferred_lft forever
5: vmbr0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP group default qlen 1000
    inet 192.168.1.245/24 scope global vmbr0
       valid_lft forever preferred_lft forever
6: vmbr1: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP group default qlen 1000
    inet 10.25.25.245/24 scope global vmbr1
       valid_lft forever preferred_lft forever
```


#### Routing Table
```text

default via 192.168.1.1 dev vmbr0 proto kernel onlink 
10.25.25.0/24 dev vmbr1 proto kernel scope link src 10.25.25.245 
192.168.1.0/24 dev vmbr0 proto kernel scope link src 192.168.1.245
```


--- 


## 📦 Virtual Machines Network Interfaces & Routing Table


### Virtual Machine: `nexus-server` (`pve` VM 100)


#### Interfaces & IPs
```text

1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN group default qlen 1000
    inet 127.0.0.1/8 scope host lo
       valid_lft forever preferred_lft forever
2: ens18: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc fq_codel state UP group default qlen 1000
    altname enp0s18
    inet 192.168.1.185/24 brd 192.168.1.255 scope global dynamic ens18
       valid_lft 137077sec preferred_lft 137077sec
3: br-92aff97ff438: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP group default 
    inet 172.20.0.1/16 brd 172.20.255.255 scope global br-92aff97ff438
       valid_lft forever preferred_lft forever
4: docker0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP group default 
    inet 172.17.0.1/16 brd 172.17.255.255 scope global docker0
       valid_lft forever preferred_lft forever
5: br-f0f703eb509d: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP group default 
    inet 172.19.0.1/16 brd 172.19.255.255 scope global br-f0f703eb509d
       valid_lft forever preferred_lft forever
6: br-23eea0c7c541: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP group default 
    inet 172.18.0.1/16 brd 172.18.255.255 scope global br-23eea0c7c541
       valid_lft forever preferred_lft forever
7: br-51c433bea17a: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP group default 
    inet 172.21.0.1/16 brd 172.21.255.255 scope global br-51c433bea17a
       valid_lft forever preferred_lft forever
8: br-566f4e16dd4c: <NO-CARRIER,BROADCAST,MULTICAST,UP> mtu 1500 qdisc noqueue state DOWN group default 
    inet 172.22.0.1/16 brd 172.22.255.255 scope global br-566f4e16dd4c
       valid_lft forever preferred_lft forever
41: br-047ac66b195f: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP group default 
    inet 172.23.0.1/16 brd 172.23.255.255 scope global br-047ac66b195f
       valid_lft forever preferred_lft forever

```


#### Routing Table
```text

default via 192.168.1.1 dev ens18 
172.17.0.0/16 dev docker0 proto kernel scope link src 172.17.0.1 
172.18.0.0/16 dev br-23eea0c7c541 proto kernel scope link src 172.18.0.1 
172.19.0.0/16 dev br-f0f703eb509d proto kernel scope link src 172.19.0.1 
172.20.0.0/16 dev br-92aff97ff438 proto kernel scope link src 172.20.0.1 
172.21.0.0/16 dev br-51c433bea17a proto kernel scope link src 172.21.0.1 
172.22.0.0/16 dev br-566f4e16dd4c proto kernel scope link src 172.22.0.1 linkdown 
172.23.0.0/16 dev br-047ac66b195f proto kernel scope link src 172.23.0.1 
192.168.1.0/24 dev ens18 proto kernel scope link src 192.168.1.185 

```


### Virtual Machine: `luna-server` (`pve` VM 102)


#### Interfaces & IPs
```text

1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN group default qlen 1000
    inet 127.0.0.1/8 scope host lo
       valid_lft forever preferred_lft forever
2: ens18: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc fq_codel state UP group default qlen 1000
    altname enp0s18
    inet 192.168.1.249/24 brd 192.168.1.255 scope global dynamic ens18
       valid_lft 172250sec preferred_lft 172250sec
4: host-shim@ens18: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP group default qlen 1000
    inet 192.168.1.183/32 scope global host-shim
       valid_lft forever preferred_lft forever
5: br-eb2e05bce652: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP group default 
    inet 172.18.0.1/16 brd 172.18.255.255 scope global br-eb2e05bce652
       valid_lft forever preferred_lft forever
6: br-f5632c6879ab: <NO-CARRIER,BROADCAST,MULTICAST,UP> mtu 1500 qdisc noqueue state DOWN group default 
    inet 172.21.0.1/16 brd 172.21.255.255 scope global br-f5632c6879ab
       valid_lft forever preferred_lft forever
7: br-176e8f43917f: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP group default 
    inet 172.25.0.1/16 brd 172.25.255.255 scope global br-176e8f43917f
       valid_lft forever preferred_lft forever
8: br-24d9c14041c2: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP group default 
    inet 172.19.0.1/16 brd 172.19.255.255 scope global br-24d9c14041c2
       valid_lft forever preferred_lft forever
9: docker0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP group default 
    inet 172.17.0.1/16 brd 172.17.255.255 scope global docker0
       valid_lft forever preferred_lft forever
10: br-b8e04a2d7a06: <NO-CARRIER,BROADCAST,MULTICAST,UP> mtu 1500 qdisc noqueue state DOWN group default 
    inet 172.26.0.1/16 brd 172.26.255.255 scope global br-b8e04a2d7a06
       valid_lft forever preferred_lft forever
11: br-ba9df36c0fee: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP group default 
    inet 172.24.0.1/16 brd 172.24.255.255 scope global br-ba9df36c0fee
       valid_lft forever preferred_lft forever
12: br-1678e23d4ada: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP group default 
    inet 172.20.0.1/16 brd 172.20.255.255 scope global br-1678e23d4ada
       valid_lft forever preferred_lft forever
13: br-19a4d8e1d69f: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP group default 
    inet 172.23.0.1/16 brd 172.23.255.255 scope global br-19a4d8e1d69f
       valid_lft forever preferred_lft forever
14: br-a69769cc1503: <NO-CARRIER,BROADCAST,MULTICAST,UP> mtu 1500 qdisc noqueue state DOWN group default 
    inet 172.22.0.1/16 brd 172.22.255.255 scope global br-a69769cc1503
       valid_lft forever preferred_lft forever

```


#### Routing Table
```text

default via 192.168.1.1 dev ens18 
172.17.0.0/16 dev docker0 proto kernel scope link src 172.17.0.1 
172.18.0.0/16 dev br-eb2e05bce652 proto kernel scope link src 172.18.0.1 
172.19.0.0/16 dev br-24d9c14041c2 proto kernel scope link src 172.19.0.1 
172.20.0.0/16 dev br-1678e23d4ada proto kernel scope link src 172.20.0.1 
172.21.0.0/16 dev br-f5632c6879ab proto kernel scope link src 172.21.0.1 linkdown 
172.22.0.0/16 dev br-a69769cc1503 proto kernel scope link src 172.22.0.1 linkdown 
172.23.0.0/16 dev br-19a4d8e1d69f proto kernel scope link src 172.23.0.1 
172.24.0.0/16 dev br-ba9df36c0fee proto kernel scope link src 172.24.0.1 
172.25.0.0/16 dev br-176e8f43917f proto kernel scope link src 172.25.0.1 
172.26.0.0/16 dev br-b8e04a2d7a06 proto kernel scope link src 172.26.0.1 linkdown 
192.168.1.0/24 dev ens18 proto kernel scope link src 192.168.1.249 
192.168.1.185 dev host-shim scope link 

```


### Virtual Machine: `media-server` (`pve` VM 103)


#### Interfaces & IPs
```text

1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN group default qlen 1000
    inet 127.0.0.1/8 scope host lo
       valid_lft forever preferred_lft forever
2: ens18: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc fq_codel state UP group default qlen 1000
    altname enp0s18
    inet 192.168.40.247/24 metric 100 brd 192.168.40.255 scope global dynamic ens18
       valid_lft 96217sec preferred_lft 96217sec
3: br-19349278de52: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP group default 
    inet 172.19.0.1/16 brd 172.19.255.255 scope global br-19349278de52
       valid_lft forever preferred_lft forever
4: br-6d2892c642fb: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP group default 
    inet 172.20.0.1/16 brd 172.20.255.255 scope global br-6d2892c642fb
       valid_lft forever preferred_lft forever
5: br-a9eac0fa2e1a: <NO-CARRIER,BROADCAST,MULTICAST,UP> mtu 1500 qdisc noqueue state DOWN group default 
    inet 172.21.0.1/16 brd 172.21.255.255 scope global br-a9eac0fa2e1a
       valid_lft forever preferred_lft forever
6: br-abbb2928b736: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP group default 
    inet 172.18.0.1/16 brd 172.18.255.255 scope global br-abbb2928b736
       valid_lft forever preferred_lft forever
7: docker0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP group default 
    inet 172.17.0.1/16 brd 172.17.255.255 scope global docker0
       valid_lft forever preferred_lft forever
8: br-e5b06d22e81b: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP group default 
    inet 172.22.0.1/16 brd 172.22.255.255 scope global br-e5b06d22e81b
       valid_lft forever preferred_lft forever

```


#### Routing Table
```text

default via 192.168.40.1 dev ens18 proto dhcp src 192.168.40.247 metric 100 
172.17.0.0/16 dev docker0 proto kernel scope link src 172.17.0.1 
172.18.0.0/16 dev br-abbb2928b736 proto kernel scope link src 172.18.0.1 
172.19.0.0/16 dev br-19349278de52 proto kernel scope link src 172.19.0.1 
172.20.0.0/16 dev br-6d2892c642fb proto kernel scope link src 172.20.0.1 
172.21.0.0/16 dev br-a9eac0fa2e1a proto kernel scope link src 172.21.0.1 linkdown 
172.22.0.0/16 dev br-e5b06d22e81b proto kernel scope link src 172.22.0.1 
192.168.1.185 via 192.168.40.1 dev ens18 proto dhcp src 192.168.40.247 metric 100 
192.168.1.186 via 192.168.40.1 dev ens18 proto dhcp src 192.168.40.247 metric 100 
192.168.40.0/24 dev ens18 proto kernel scope link src 192.168.40.247 metric 100 
192.168.40.1 dev ens18 proto dhcp scope link src 192.168.40.247 metric 100 

```


### Virtual Machine: `vxlan-server` (`pve` VM 107)


#### Interfaces & IPs
```text

1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN group default qlen 1000
    inet 127.0.0.1/8 scope host lo
       valid_lft forever preferred_lft forever
3: br0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP group default qlen 1000
    inet 192.168.1.150/24 brd 192.168.1.255 scope global br0
       valid_lft forever preferred_lft forever

```


#### Routing Table
```text

default via 192.168.1.1 dev br0 onlink 
192.168.1.0/24 dev br0 proto kernel scope link src 192.168.1.150 
192.168.1.225 dev ens18 scope link 

```


### Virtual Machine: `minecraft-docker` (`pve` VM 109)


#### Interfaces & IPs
```text

1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN group default qlen 1000
    inet 127.0.0.1/8 scope host lo
       valid_lft forever preferred_lft forever
2: ens18: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc fq_codel state UP group default qlen 1000
    altname enp0s18
    inet 192.168.1.175/24 brd 192.168.1.255 scope global dynamic ens18
       valid_lft 120837sec preferred_lft 120837sec
3: docker0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP group default 
    inet 172.17.0.1/16 brd 172.17.255.255 scope global docker0
       valid_lft forever preferred_lft forever
4: br-7f2283d1cdc1: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP group default 
    inet 172.18.0.1/16 brd 172.18.255.255 scope global br-7f2283d1cdc1
       valid_lft forever preferred_lft forever
5: br-2548aa4c7abf: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP group default 
    inet 172.19.0.1/16 brd 172.19.255.255 scope global br-2548aa4c7abf
       valid_lft forever preferred_lft forever

```


#### Routing Table
```text

default via 192.168.1.1 dev ens18 
172.17.0.0/16 dev docker0 proto kernel scope link src 172.17.0.1 
172.18.0.0/16 dev br-7f2283d1cdc1 proto kernel scope link src 172.18.0.1 
172.19.0.0/16 dev br-2548aa4c7abf proto kernel scope link src 172.19.0.1 
192.168.1.0/24 dev ens18 proto kernel scope link src 192.168.1.175 

```


### Virtual Machine: `discovery-server` (`pve2` VM 100)


#### Interfaces & IPs
```text

1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN group default qlen 1000
    inet 127.0.0.1/8 scope host lo
       valid_lft forever preferred_lft forever
2: ens18: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc fq_codel state UP group default qlen 1000
    altname enp0s18
    inet 10.25.25.246/24 metric 100 brd 10.25.25.255 scope global ens18
       valid_lft forever preferred_lft forever
3: br-5cc5a6255d13: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP group default 
    inet 172.19.0.1/16 brd 172.19.255.255 scope global br-5cc5a6255d13
       valid_lft forever preferred_lft forever
4: br-7c79d8b0a932: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP group default 
    inet 172.18.0.1/16 brd 172.18.255.255 scope global br-7c79d8b0a932
       valid_lft forever preferred_lft forever
5: docker0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP group default 
    inet 172.17.0.1/16 brd 172.17.255.255 scope global docker0
       valid_lft forever preferred_lft forever
6: br-55fcd3b418b5: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP group default 
    inet 172.20.0.1/16 brd 172.20.255.255 scope global br-55fcd3b418b5
       valid_lft forever preferred_lft forever

```


#### Routing Table
```text

default via 10.25.25.1 dev ens18 proto dhcp src 10.25.25.246 metric 100 
10.25.25.0/24 dev ens18 proto kernel scope link src 10.25.25.246 metric 100 
10.25.25.1 dev ens18 proto dhcp scope link src 10.25.25.246 metric 100 
172.17.0.0/16 dev docker0 proto kernel scope link src 172.17.0.1 
172.18.0.0/16 dev br-7c79d8b0a932 proto kernel scope link src 172.18.0.1 
172.19.0.0/16 dev br-5cc5a6255d13 proto kernel scope link src 172.19.0.1 
172.20.0.0/16 dev br-55fcd3b418b5 proto kernel scope link src 172.20.0.1 

```


### Virtual Machine: `nexus-server2` (`pve3` VM 100)


#### Interfaces & IPs
```text

1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN group default qlen 1000
    inet 127.0.0.1/8 scope host lo
       valid_lft forever preferred_lft forever
2: ens18: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc fq_codel state UP group default qlen 1000
    altname enp0s18
    inet 192.168.1.186/24 brd 192.168.1.255 scope global dynamic ens18
       valid_lft 167030sec preferred_lft 167030sec
3: docker0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP group default 
    inet 172.17.0.1/16 brd 172.17.255.255 scope global docker0
       valid_lft forever preferred_lft forever
4: br-23eea0c7c541: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP group default 
    inet 172.18.0.1/16 brd 172.18.255.255 scope global br-23eea0c7c541
       valid_lft forever preferred_lft forever
28: br-2012238a2c41: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP group default 
    inet 172.19.0.1/16 brd 172.19.255.255 scope global br-2012238a2c41
       valid_lft forever preferred_lft forever

```


#### Routing Table
```text

default via 192.168.1.1 dev ens18 
172.17.0.0/16 dev docker0 proto kernel scope link src 172.17.0.1 
172.18.0.0/16 dev br-23eea0c7c541 proto kernel scope link src 172.18.0.1 
172.19.0.0/16 dev br-2012238a2c41 proto kernel scope link src 172.19.0.1 
192.168.1.0/24 dev ens18 proto kernel scope link src 192.168.1.186 

```


### Virtual Machine: `nas-server` (`pve3` VM 101)


#### Interfaces & IPs
```text

1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN group default qlen 1000
    inet 127.0.0.1/8 scope host lo
       valid_lft forever preferred_lft forever
2: ens18: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc fq_codel state UP group default qlen 1000
    altname enp0s18
    inet 192.168.40.248/24 brd 192.168.40.255 scope global ens18
       valid_lft forever preferred_lft forever
3: ens19: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc fq_codel state UP group default qlen 1000
    altname enp0s19
    inet 10.25.25.248/24 brd 10.25.25.255 scope global ens19
       valid_lft forever preferred_lft forever

```


#### Routing Table
```text

default via 192.168.40.1 dev ens18 proto static 
default via 10.25.25.248 dev ens19 proto static metric 1 
10.25.25.0/24 dev ens19 proto kernel scope link src 10.25.25.248 
192.168.40.0/24 dev ens18 proto kernel scope link src 192.168.40.248 

```

