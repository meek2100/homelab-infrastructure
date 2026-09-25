# **Headless Management and Automated Provisioning Architecture for the Netgear GS108Ev2 via NSDP**

## **Netgear Switch Discovery Protocol Internals and Framing Specification**

The Netgear GS108Ev2 hardware running firmware version 1.00.12 occupies a distinct niche in desktop switching infrastructure1. Marketed as an "Easy Smart" ProSAFE Plus device, it provides Layer 2 switching capabilities alongside managed features such as IEEE 802.1Q VLAN tagging, Port VLAN ID (PVID) assignment, port-based rate limiting, and link health telemetry3.

Unlike modern enterprise managed switches or subsequent hardware iterations such as the GS108Ev3 that incorporate lightweight embedded web daemons, the GS108Ev2 hardware platform operates completely headless5. The physical controller lacks an HTTP/HTTPS daemon, an SSH server, a Telnet listener, and an SNMP management agent.

Direct programmatic interaction with the switch requires interfacing with the Netgear Switch Discovery Protocol (NSDP), a proprietary binary protocol developed to facilitate discovery and remote configuration across unmanaged broadcast segments1.

### **Transport Layer Dynamics and Packet Anatomy**

NSDP operates strictly over UDP, encapsulated within Layer 2 Ethernet broadcast or unicast frames1. The operational specification reserves fixed UDP ports for client-switch exchanges:

* The management workstation or runner dispatches requests from UDP source port 63321 (with secondary tooling occasionally utilizing 63323\)1.  
* The switch agent listens on UDP port 63322 (and on certain hardware variants, port 63324\)1.

Initial discovery procedures use broadcast transmission directed to destination IP 255.255.255.255, allowing unconfigured nodes on the local broadcast domain to announce their physical and logical addresses1.

For targeted configuration queries and state mutations, NSDP supports directed unicast delivery to the switch management IPv4 address (192.168.1.220)1.

Every NSDP transmission conforms to a rigid 32-byte header encoded in network byte order (big-endian), succeeded by a sequence of variable Type-Length-Value (TLV) records and a terminal delimiter1.

&nbsp;

| Byte Offset | Field Length | Data Type | Field Identifier | Protocol Definition and Operational Function |
| :---- | :---- | :---- | :---- | :---- |
| 0x0000 | 1 byte | uint8 | Protocol Version | Protocol revision identifier; statically assigned to 0x01 across standard ProSAFE Plus switches4. |
| 0x0001 | 1 byte | uint8 | Operation Code | Defines the operational transaction: 0x01 (Read Request), 0x02 (Read Response), 0x03 (Write Request), and 0x04 (Write Response)4. |
| 0x0002 | 2 bytes | uint16 | Result Status | Status code returned by the switch; 0x0000 signifies successful processing, whereas non-zero values denote syntax, range, or authentication rejections1. |
| 0x0004 | 4 bytes | byte\[4\] | Failure TLV | Error diagnostic field indicating the specific TLV tag that triggered an execution fault7. |
| 0x0008 | 6 bytes | byte\[6\] | Host MAC (Manager ID) | Physical MAC address of the issuing runner or management station interface4. |
| 0x000E | 6 bytes | byte\[6\] | Device MAC (Agent ID) | Hardware MAC address of the target switch; 00:00:00:00:00:00 denotes an all-switch broadcast1. |
| 0x0014 | 2 bytes | uint16 | Alignment / Reserved | Big-endian padding field; standard implementations zero this field4. |
| 0x0016 | 2 bytes | uint16 | Sequence Number | Monotonically incrementing transaction identifier used to map asynchronous switch responses to issued queries1. |
| 0x0018 | 4 bytes | char\[4\] | Protocol Signature | Fixed magic ASCII bytes "NSDP" (0x4E534450) designating authentic NSDP frame encapsulation1. |
| 0x001C | 4 bytes | byte\[4\] | Reserved Padding | Null-byte boundary padding preceding the message payload4. |

The message body begins immediately at byte offset 0x00204. Each TLV entry is framed by a 16-bit Tag (uint16) identifying the target parameter, a 16-bit Length field (uint16) indicating value length in bytes, and an ![][image1]\-byte payload6.

When formulating a Read Request (0x01), the client specifies the desired Tag with a Length of 0x0000 and no trailing data4. In the corresponding Read Response (0x02), the switch echoes the Tag, populates the actual Length, and appends the raw byte value4.

Conversely, Write Requests (0x03) populate both the explicit length and the payload bytes to be committed into internal memory4.

Every message payload concludes with a mandatory 4-byte End-of-Message (EOM) marker consisting of the tag 0xFFFF with zero length (0xFFFF0000)1. Frames lacking this exact byte signature are discarded by the switch microcode1.

### **Core Data Structure Implementations**

In programmatic implementations, the 32-byte header and TLV records map cleanly to low-level data structures.

#### **C Implementation (libnsdp Architecture)**

The following structure definitions correspond to the POSIX-compliant C memory layout used in AlbanBedel/libnsdp1:

&nbsp;

&nbsp;

&nbsp;

C

\#**include** \<stdint.h\>

/\* NSDP Fixed 32-byte Protocol Header \*/  
struct \_\_attribute\_\_((packed)) nsdp\_header {  
&nbsp;&nbsp;&nbsp;&nbsp;uint8\_t  version;        /\* 0x00: Protocol version (always 0x01) \*/  
&nbsp;&nbsp;&nbsp;&nbsp;uint8\_t  op\_code;        /\* 0x01: Opcode (0x01=Read, 0x02=ReadResp, 0x03=Write, 0x04=WriteResp) \*/  
&nbsp;&nbsp;&nbsp;&nbsp;uint16\_t result\_code;    /\* 0x02: Return status (0x0000 \= OK) \*/  
&nbsp;&nbsp;&nbsp;&nbsp;uint32\_t failure\_tlv;    /\* 0x04: TLV identifier triggering failure \*/  
&nbsp;&nbsp;&nbsp;&nbsp;uint8\_t  host\_mac\[6\];    /\* 0x08: Management host physical MAC \*/  
&nbsp;&nbsp;&nbsp;&nbsp;uint8\_t  device\_mac\[6\];  /\* 0x0E: Switch target physical MAC \*/  
&nbsp;&nbsp;&nbsp;&nbsp;uint16\_t reserved1;      /\* 0x14: Alignment padding \*/  
&nbsp;&nbsp;&nbsp;&nbsp;uint16\_t seq\_num;        /\* 0x16: Transaction sequence counter \*/  
&nbsp;&nbsp;&nbsp;&nbsp;uint32\_t signature;      /\* 0x18: Magic 0x4E534450 ("NSDP") \*/  
&nbsp;&nbsp;&nbsp;&nbsp;uint32\_t reserved2;      /\* 0x1C: Boundary padding \*/  
};

/\* NSDP Type-Length-Value Record Entry \*/  
struct \_\_attribute\_\_((packed)) nsdp\_tlv\_record {  
&nbsp;&nbsp;&nbsp;&nbsp;uint16\_t tag;            /\* TLV register identifier \*/  
&nbsp;&nbsp;&nbsp;&nbsp;uint16\_t length;         /\* Payload byte length \*/  
&nbsp;&nbsp;&nbsp;&nbsp;uint8\_t  value\[\];        /\* Flexible array payload \*/  
};

#### **Go Implementation (go-nsdp Architecture)**

The Go data representation reflects the memory serialization layout implemented in yaamai/go-nsdp7:

&nbsp;

&nbsp;

&nbsp;

Go

package nsdp

import (  
&nbsp;&nbsp;&nbsp;&nbsp;"bytes"  
&nbsp;&nbsp;&nbsp;&nbsp;"encoding/binary"  
&nbsp;&nbsp;&nbsp;&nbsp;"io"  
&nbsp;&nbsp;&nbsp;&nbsp;"sort"  
)

// Header defines the fixed 32-byte NSDP transport framing  
type Header struct {  
&nbsp;&nbsp;&nbsp;&nbsp;Version    byte     // 0x00: Protocol version (0x01)  
&nbsp;&nbsp;&nbsp;&nbsp;Command    byte     // 0x01: Opcode (0x01=Read, 0x03=Write, 0x17=Token, 0x1A=AuthWrite)  
&nbsp;&nbsp;&nbsp;&nbsp;Status     uint16   // 0x02: Status code  
&nbsp;&nbsp;&nbsp;&nbsp;FailureTLV \[4\]byte  // 0x04: Offending TLV register on error  
&nbsp;&nbsp;&nbsp;&nbsp;ManagerID  \[6\]byte  // 0x08: Runner host MAC address  
&nbsp;&nbsp;&nbsp;&nbsp;AgentID    \[6\]byte  // 0x0E: Target switch MAC address  
&nbsp;&nbsp;&nbsp;&nbsp;Reserved   uint16   // 0x14: Reserved alignment  
&nbsp;&nbsp;&nbsp;&nbsp;Sequence   uint16   // 0x16: Monotonic transaction sequence ID  
&nbsp;&nbsp;&nbsp;&nbsp;Signature  \[4\]byte  // 0x18: Magic bytes "NSDP" (0x4E, 0x53, 0x44, 0x50)  
&nbsp;&nbsp;&nbsp;&nbsp;Padding    \[4\]byte  // 0x1C: Trailing header padding  
}

// Tag represents the 16-bit big-endian TLV identifier  
type Tag uint16

// Tags stores the associative map of TLVs to raw payload byte slices  
type Tags map\[Tag\]\[\]byte

// Message bundles the fixed header and dynamic TLV payload dictionary  
type Message struct {  
&nbsp;&nbsp;&nbsp;&nbsp;Header Header  
&nbsp;&nbsp;&nbsp;&nbsp;Tags   Tags  
}

// Serialize marshals the Message struct into raw big-endian UDP bytes  
func (m \*Message) WriteTo(w io.Writer) (int64, error) {  
&nbsp;&nbsp;&nbsp;&nbsp;var buf bytes.Buffer  
&nbsp;&nbsp;&nbsp;&nbsp;if err := binary.Write(\&buf, binary.BigEndian, \&m.Header); err \!= nil {  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return 0, err  
&nbsp;&nbsp;&nbsp;&nbsp;}  
&nbsp;&nbsp;&nbsp;&nbsp;  
&nbsp;&nbsp;&nbsp;&nbsp;// Sort keys to guarantee deterministic TLV packet ordering  
&nbsp;&nbsp;&nbsp;&nbsp;keys := make(\[\]int, 0, len(m.Tags))  
&nbsp;&nbsp;&nbsp;&nbsp;for k := range m.Tags {  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;keys \= append(keys, int(k))  
&nbsp;&nbsp;&nbsp;&nbsp;}  
&nbsp;&nbsp;&nbsp;&nbsp;sort.Ints(keys)  
&nbsp;&nbsp;&nbsp;&nbsp;  
&nbsp;&nbsp;&nbsp;&nbsp;for \_, k := range keys {  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;tag := Tag(k)  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;val := m.Tags\[tag\]  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;\_ \= binary.Write(\&buf, binary.BigEndian, tag)  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;\_ \= binary.Write(\&buf, binary.BigEndian, uint16(len(val)))  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;buf.Write(val)  
&nbsp;&nbsp;&nbsp;&nbsp;}  
&nbsp;&nbsp;&nbsp;&nbsp;  
&nbsp;&nbsp;&nbsp;&nbsp;// Write mandatory 4-byte End-of-Message delimiter (0xFFFF0000)  
&nbsp;&nbsp;&nbsp;&nbsp;\_ \= binary.Write(\&buf, binary.BigEndian, uint16(0xFFFF))  
&nbsp;&nbsp;&nbsp;&nbsp;\_ \= binary.Write(\&buf, binary.BigEndian, uint16(0x0000))  
&nbsp;&nbsp;&nbsp;&nbsp;  
&nbsp;&nbsp;&nbsp;&nbsp;return buf.WriteTo(w)  
}

### **Type-Length-Value Register Schema and Payload Layouts**

NSDP structures switch operational state through a designated register space spanning identity records, management network addressing, port telemetry counters, and switching tables1.

The primary TLVs governing the GS108Ev2 switch are detailed below:

&nbsp;

| TLV Tag | Register Definition | Length | R/W Mode | Schema and Operational Semantics |
| :---- | :---- | :---- | :---- | :---- |
| 0x0001 | Product Model Name | Variable | Read-Only | Printable ASCII string declaring the hardware revision (e.g., "GS108Ev2")4. |
| 0x0003 | Host / Device Name | ![][image2] B | Read / Write | Configurable administrative system label4. |
| 0x0004 | Switch MAC Address | 6 bytes | Read-Only | Hardware physical Ethernet address of the switch agent4. |
| 0x0005 | Physical Location | ![][image2] B | Read / Write | Administrative location string4. |
| 0x0006 | IPv4 Management Address | 4 bytes | Read / Write | Current IPv4 interface address (192.168.1.220)4. |
| 0x0007 | Subnet Netmask | 4 bytes | Read / Write | Subnet mask boundary (e.g., 255.255.255.0)4. |
| 0x0008 | Default IPv4 Gateway | 4 bytes | Read / Write | Upstream default gateway address4. |
| 0x000A | Administrative Password | Variable | Write-Only | Plaintext or hashed password applied for authentication validation4. |
| 0x000B | Addressing Mode | 1 byte | Read / Write | 0x00 \= Static addressing, 0x01 \= DHCP client, 0x02 \= Force DHCP refresh4. |
| 0x000D | Primary Firmware Image | Variable | Read-Only | ASCII firmware version stored in Bank 1 ("1.00.12")4. |
| 0x000E | Secondary Firmware Image | Variable | Read-Only | ASCII firmware version stored in Bank 24. |
| 0x000F | Next Active Boot Slot | 1 byte | Read / Write | 0x01 \= Bank 1, 0x02 \= Bank 2; designates the boot partition for the subsequent restart4. |
| 0x0C00 | Port Physical Link Matrix | Variable | Read / Write | Multi-byte array defining physical link state, link speed (10M/100M/1000M), duplex mode, and administrative shutdown state across ports 1–81. |
| 0x1000 | Port Performance Counters | 192 bytes | Read-Only | Contiguous array of counters per port detailing ingress/egress bytes, frame counts, broadcast/multicast distributions, and CRC error totals1. |
| 0x2800 | 802.1Q VLAN Membership | Variable | Read / Write | Multi-byte bitmask map registering active VLAN IDs alongside per-port egress tagging properties (Tagged, Untagged, or Excluded)4. |
| 0x3000 | Port PVID Assignment | 3 bytes per port | Read / Write | 3-byte TLV per port consisting of 1 byte port ID (1-8) and 16-bit big-endian integer PVID. |
| 0x2C00 | VLAN Deletion Directive | 2 bytes | Write-Only | Purges a specific 16-bit VLAN ID entry from active switch memory4. |

#### **Detailed Internal Payload Layouts**

Complex switch operations rely on binary layouts packed inside the TLV payload:

* **Port Link Matrix (0x0C00)**: Formatted as a repeated sequence of 4 bytes per physical port (32 bytes total for GS108Ev2):  
  * Byte 0: Physical Connection Status (0x00 \= Link Down, 0x01 \= Link Up).  
  * Byte 1: Negotiated Operational Speed (0x00 \= No Link, 0x01 \= 10 Mbps, 0x02 \= 100 Mbps, 0x03 \= 1000 Mbps).  
  * Byte 2: Duplex Setting (0x01 \= Half Duplex, 0x02 \= Full Duplex).  
  * Byte 3: Administrative State (0x01 \= Enabled / Unshut, 0x02 \= Administratively Disabled / Shutdown).  
* **Port Statistics Register (0x1000)**: Spans 192 bytes representing 8 ports ![][image3] 24 bytes per port. Each port segment contains six 32-bit big-endian cumulative telemetry counters:  
  * Bytes 0x00–0x03: Total Ingress Octets (Rx Bytes).  
  * Bytes 0x04–0x07: Total Egress Octets (Tx Bytes).  
  * Bytes 0x08–0x0B: Ingress Frame Count (Rx Packets).  
  * Bytes 0x0C–0x0F: Egress Frame Count (Tx Packets).  
  * Bytes 0x10–0x13: Ingress CRC / Checksum Frame Errors.  
  * Bytes 0x14–0x17: Collision and Ingress Frame Drop Count.  
* **Port PVID Assignment Register (0x3000)**: Repeated sequence of 3-byte TLVs per port (`0x3000`, length 3). Byte 0 is physical Port (1-8), Bytes 1-2 are uint16 big-endian PVID (e.g., `01 0001` for Port 1 PVID 1).  
* **802.1Q VLAN Membership Register (0x2800)**: On GS108Ev2 firmware 1.00.12, the switch returns a sequence of repeated 4-byte TLVs (one TLV per configured VLAN):
  * Bytes 0x00–0x01: 16-bit VLAN ID (`uint16` big-endian, e.g., `0x000A` for VLAN 10).
  * Byte 0x02: Port Membership Bitmask (`uint8`, bit 7 = Port 1, bit 6 = Port 2, ..., bit 0 = Port 8). 1 = Member, 0 = Excluded.
  * Byte 0x03: Port Tagged Bitmask (`uint8`, bit 7 = Port 1, bit 6 = Port 2, ..., bit 0 = Port 8). 1 = Tagged (T), 0 = Untagged (U).
  *(Note: Certain legacy/alternate firmware variants employ a 10-byte format with 1 byte per port; both formats are supported by `manage-netgear-switch.py`).*

### **Cryptographic and Challenge-Response Authentication Handshake**

The security model of NSDP evolved across switch hardware generations10.

Under Version 1 authentication, write requests transmitted the administrative password embedded directly in TLV 0x000A within the configuration datagram4. The embedded processor performed a comparison against the local configuration store, executing the write if matched, or returning a non-zero error status code if invalid1.

To mitigate local packet sniffing, later firmware revisions introduced Version 2 authentication, which enforces a two-step challenge-response transaction6:

> 1. **Token Request**: The automation runner dispatches an empty challenge request datagram using opcode 0x17 to UDP port 63322 on the switch10.  
> 2. **Challenge Emission**: The switch microcode responds with opcode 0x18, echoing an ephemeral, pseudo-random challenge nonce (token)10.  
> 3. **Cryptographic Hashing**: The runner computes the authentication hash using the received token and administrative password:  
>    ![][image4]  
> 4. **Authenticated Write**: The runner issues an authenticated write datagram using opcode 0x1A (or standard 0x03 with hash injection), embedding the computed hash alongside the target configuration TLVs10.  
> 5. **Transaction Status**: The switch microcode validates the hash and returns result status 0x0000 on success, or an error status code with the offending TLV tag on failure1.

Historically, security researchers identified structural vulnerabilities in this mechanism (cataloged under CVE-2020-35231), in which switches rebooted into an uninitialized state would accept an empty authentication hash if an attacker intentionally skipped the opcode 0x17 challenge request10.

For reliable automated administration, client tooling must explicitly implement full challenge-response tracking to prevent unexpected transaction rejections10.

## **Comparative Evaluation of Implementation Frameworks and Open-Source Codebases**

Programmatic orchestration requires selecting a reliable software toolchain capable of issuing raw NSDP datagrams. A thorough investigation of available open-source implementations reveals stark operational trade-offs, functional divergences, and runtime incompatibilities.

### **Codebase Breakdown and Capabilities**

#### **1\. nccgroup/nsdp-discover**

* **Repository**: https://github.com/nccgroup/nsdp-discover  
  \[cite: 8\]  
* **Author / Maintainer**: Manuel Ginés Rodríguez (NCC Group)8  
* **Implementation Language**: Lua (Nmap Scripting Engine module)8  
* **Mechanics**: Implements standard broadcast discovery frames directed to UDP ports 63322 and 633248. It captures asynchronous switch responses and decodes identity attributes including model name, MAC address, active firmware partition, and IP addressing8.  
* **Write Support**: Read-only8. It contains no write logic, cannot modify switch parameters, and does not implement challenge-response hashing8.

#### **2\. AlbanBedel/libnsdp**

* **Repository**: https://github.com/AlbanBedel/libnsdp  
  \[cite: 1, 9\]  
* **Author / Maintainer**: Alban Bedel1  
* **Implementation Language**: Pure C (POSIX compliant)1  
* **Key Files**: nsdp\_packet.c (packet serialization), nsdp\_property\_types.h (TLV register definitions), nsdp.c (CLI front-end)1.  
* **Mechanics**: Implements low-level BSD socket primitives directly over UDP. It reads and writes network interfaces, port link speed/duplex negotiation, 802.1Q VLAN entries, and PVID registers1.  
* **Cross-Compilation**: Native C structure layout allows direct compilation across OpenWrt toolchains (aarch64-openwrt-linux-musl-gcc), producing a lean binary footprint under 100 KB.

#### **3\. yaamai/go-nsdp**

* **Repository**: https://github.com/yaamai/go-nsdp  
  \[cite: 6\]  
* **Author / Maintainers**: yaamai, Ulrich Weber6  
* **Implementation Language**: Go (Golang)6  
* **Key Packages**: nsdp/ (protocol codec, types, framing), cmd/nsdp-cli/ (CLI runner)6.  
* **Mechanics**: Provides a pure Go implementation of NSDP framing and challenge-response authentication (v2auth)6. The CLI tool natively formats query output as structured JSON and supports configuration writes for VLAN memberships via declarative parameters6.  
* **Deployment Viability**: Compiles with CGO\_ENABLED=0 to create completely static, zero-dependency binaries suitable for ARM64 and x86\_64 target platforms.

#### **4\. s-t-e-f-a-n-o/netgear-tool & jfrancis42/netgear-tool**

* **Repositories**: https://github.com/s-t-e-f-a-n-o/netgear-tool, https://github.com/jfrancis42/netgear-tool  
  \[cite: 11\]  
* **Implementation Language**: Python 311  
* **Mechanics**: Implements NSDP packet framing directly using Python standard libraries (socket, struct) rather than relying on HTTP11. Features a Cisco-like CLI interactive shell (cli.py) supporting interface configuration, port disabling, duplex overrides, and VLAN provisioning11.  
* **Deployment Viability**: Functionally compatible with the GS108Ev2, but constrained by the storage footprint of Python virtual environments (![][image5]–![][image6] MB) on embedded hardware.

#### **5\. foxey/py-netgear-plus & ckarrie/ha-netgear-plus**

* **Repositories**: https://github.com/foxey/py-netgear-plus, https://github.com/ckarrie/ha-netgear-plus  
  \[cite: 12, 13\]  
* **Implementation Language**: Python 312  
* **Mechanics**: Employs HTTP screen scraping targeted at web-enabled Plus switches by requesting session cookies via http://\<IP\>/login.cgi and parsing http://\<IP\>/portStatistics.cgi12.  
* **GS108Ev2 Incompatibility**: Hardware platform GS108Ev2 with firmware 1.00.12 does not expose an embedded HTTP server5. All connection attempts to port 80/443 fail with connection timeouts or ECONNREFUSED15. This codebase cannot be used for GS108Ev2 management.

### **CLI Usage and Operational Patterns**

The command-line tools provide distinct execution interfaces:

* **Querying Status via go-nsdp**6:  
  Bash  
  \# Query switch model, hostname, IP, and MAC address in JSON format  
  ./nsdp-cli \-interface br-lan query model-name host-name ipaddr mac

* **Setting VLAN Membership via go-nsdp**6:  
  Bash  
  \# Provision VLAN 1000 tagged on ports 1 through 7 with password authentication  
  ./nsdp-cli \-interface br-lan \-password "secret123" set tag-vlan:1000:1,2,3,4,5,6,7:

* **Querying via libnsdp CLI**1:  
  Bash  
  \# Send discovery broadcast and display responsive devices  
  ./nsdp \-i br-lan discover

  \# Read port status register for target switch MAC  
  ./nsdp \-i br-lan \-m 00:a0:bc:xx:xx:xx get port-status

* **Interactive CLI via netgear-tool**11:  
  Bash  
  python3 cli.py \--ip 192.168.1.220 \--password "secret123"  
  GS108E\# configure terminal  
  GS108E(config)\# interface port 2  
  GS108E(config-if)\# shutdown

### **Structured Framework Feature and Dependency Matrix**

&nbsp;

| Evaluation Criteria | nccgroup/nsdp-discover\[cite: 8\] | AlbanBedel/libnsdp\[cite: 1, 9\] | yaamai/go-nsdp\[cite: 6\] | netgear-tool (Python) | py-netgear-plus\[cite: 12, 14\] |
| :---- | :---- | :---- | :---- | :---- | :---- |
| **Implementation Language** | Lua (NSE)8 | C (POSIX)1 | Go (Golang)6 | Python 311 | Python 312 |
| **Underlying Mechanism** | UDP Socket Probe8 | Raw UDP Sockets1 | UDP (net.PacketConn) | Raw UDP Sockets | HTTP Scraping (login.cgi)12 |
| **GS108Ev2 Compatibility** | Compatible (Audit only) | **Fully Compatible** | **Fully Compatible** | **Fully Compatible** | **Incompatible** (No HTTP) |
| **System Info Telemetry** | Model, MAC, IP, FW8 | Complete TLV Suite1 | Native JSON Export6 | Full Identity Query11 | Incompatible |
| **Port Link State & Duplex** | Unsupported8 | Supported (0x0C00)1 | Supported6 | Supported11 | Incompatible |
| **Port Error & CRC Telemetry** | Unsupported8 | Supported (0x1000)1 | Supported6 | Supported11 | Incompatible |
| **802.1Q VLAN Read / Write** | Unsupported8 | Supported (0x2800)1 | Supported (tag-vlan)6 | Supported11 | Unsupported |
| **PVID Read / Write** | Unsupported8 | Supported (0x2900)1 | Supported6 | Supported11 | Unsupported |
| **Administrative Port Disable** | Unsupported8 | Supported1 | Supported6 | Supported11 | Unsupported |
| **Password Modification** | Unsupported8 | Supported (0x000A)1 | Supported6 | Supported11 | Unsupported |
| **Runtime Footprint** | Heavy (![][image7] MB via Nmap) | **Minimal** (![][image8] KB ELF) | **Low** (![][image9]–![][image10] MB Static) | Heavy (![][image5]–![][image6] MB Venv) | Heavy (![][image5]–![][image6] MB Venv) |
| **Embedded Suitability** | Poor (Requires Nmap core) | **Optimal** (Native C) | **Optimal** (Static Binary) | Poor (Interpreter size) | Unusable (Protocol mismatch) |

## **Network Boundary Transversal and Homelab Execution Topologies**

The Netgear GS108Ev2 requires management datagrams to originate from a system that is directly Layer 2 adjacent1.

Because NSDP relies heavily on Layer 2 broadcast discovery framing, any command issued across a routed Layer 3 network boundary (such as from a remote management workstation or an MCP control runner located in a separate VLAN) will experience transport failure1.

Even when unicast UDP packets are addressed directly to 192.168.1.220, the simplified network stack of the switch embedded controller often fails to resolve off-subnet ARP routes correctly1.

To enable reliable automation, the orchestration pipeline must place an execution agent directly within the native Layer 2 management broadcast domain (VLAN 1\)16.

### **Analysis of Runner Candidate Environments**

Three distinct execution environments were evaluated to establish an adjacent execution proxy:

* **Approach A: Embedded Micro-Daemon on OpenWrt Router (192.168.1.226)**  
  The Belkin AX3200 (RT3200) router runs OpenWrt on a dual-core MediaTek MT7622 ARM64 platform with 512 MB of RAM. It sits directly adjacent to the GS108Ev2, hosting the primary br-lan bridge that defines the native VLAN 1 broadcast domain1. Running an embedded proxy daemon on this device guarantees sub-millisecond, unrouted Layer 2 visibility1. Because the router operates as a dedicated network appliance, its operational lifecycle is decoupled from virtualization clusters and compute nodes. It remains online continuously, ensuring that switch telemetry and control remain accessible even when hypervisor hosts are offline for scheduled maintenance.  
* **Approach B: SSH Execution on Proxmox VE Host (192.168.1.250)**  
  The Proxmox bare-metal host maintains a physical management bridge (vmbr0) assigned to the 192.168.1.0/24 subnet.  
  An automation controller can dispatch commands via SSH to the hypervisor, executing local binary queries.  
  While simple to configure initially, this approach presents significant operational trade-offs.  
  Granting an external automation agent continuous root SSH access to the virtualization host introduces unnecessary privilege escalation risks.  
  Furthermore, repeatedly spawning SSH subshells for high-frequency polling incurs significant fork-exec overhead, CPU context-switching penalties, and high transaction latency.  
* **Approach C: Containerized Runner on nexus-server (VM 100\)**  
  The nexus-server virtual machine can be configured with a secondary virtual network interface attached to Proxmox bridge vmbr0 without VLAN tagging, dropping the virtual interface directly into native VLAN 116. An automation agent deployed inside a lightweight Docker or LXC container can bind directly to this virtual interface, dispatching NSDP frames on UDP port 633211. This provides good workload isolation and fits cleanly into CI/CD pipelines. However, it introduces a circular dependency: if an automated configuration update misconfigures the switch trunk port feeding the Proxmox host, both the hypervisor and VM 100 instantly lose network connectivity, preventing any automated recovery.

### **Multi-Node Architectural Synthesis and Benchmark Matrix**

&nbsp;

| Evaluation Dimension | Approach A: OpenWrt Router (192.168.1.226) | Approach B: Proxmox Host (192.168.1.250) | Approach C: VM Container (nexus-server) |
| :---- | :---- | :---- | :---- |
| **Layer 2 Adjacency** | Direct physical attachment to br-lan1. | Direct physical attachment to vmbr0. | Virtualized attachment via bridged vNIC. |
| **Failure Isolation** | High; isolates network plane from compute plane. | Low; requires root shell access on core hypervisor. | Moderate; isolated inside an unprivileged container. |
| **Execution Latency** | **![][image11]** ms (Persistent in-memory resident daemon). | ![][image12]–![][image13] ms (SSH handshake \+ fork-exec cost). | ![][image14]–![][image15] ms (Resident container daemon). |
| **Maintenance Resilience** | Remains fully operational during VM/PVE maintenance. | Offline during Proxmox hypervisor kernel updates. | Offline during Proxmox reboots or VM 100 restarts. |
| **Binary Portability** | Static ARM64 Go binary (aarch64\_cortex-a53). | Native x86\_64 ELF binary. | Native x86\_64 container image. |
| **Circular Dependency Risk** | **Low**: Router uplink is independent of switch trunking. | **High**: Switch misconfiguration isolates hypervisor. | **Critical**: Switch misconfiguration isolates runner. |

The recommended architecture follows a decoupled, two-tier model:

> 1. **Local Execution Layer (OpenWrt 192.168.1.226)**: A statically compiled Go micro-daemon derived from yaamai/go-nsdp is installed on the Belkin AX32001. Managed by OpenWrt's native procd service manager, the daemon binds locally to br-lan and exposes an internal, token-authenticated HTTP API (192.168.1.226:8080)1. The daemon translates incoming JSON payloads into binary NSDP frames dispatched on port 63321, captures switch responses from port 63322, and returns structured JSON responses4.  
> 2. **Orchestration Layer (MCP Control Host)**: The existing control script (mcp/homelab/scripts/manage-netgear-switch.py) is refactored into a thin client. Instead of attempting to dispatch raw Layer 2 NSDP packets across routed network hops, it issues standard HTTP POST and GET requests to the OpenWrt daemon. This decouples the automation logic from physical Layer 2 networking constraints and ensures administrative access remains available even during compute cluster outages.

## **Embedded Daemon API Design and REST Interface Layout**

To decouple external automation runners from Layer 2 networking mechanics, the Go micro-daemon running on OpenWrt (nsdpd) exposes an HTTP REST API on port 8080\.

The daemon maintains a raw UDP socket bound to interface br-lan, handling big-endian TLV packing, MD5 authentication hashing, sequence tracking, and timeout recovery internally1.

### **REST Endpoints and HTTP Method Matrix**

&nbsp;

| Endpoint Route | HTTP Method | Auth Scope | NSDP Mapping | Function and Operational Description |
| :---- | :---- | :---- | :---- | :---- |
| /api/v1/switch/info | GET | Read Token | Opcode 0x01 (TLVs 0x0001–0x000F)4 | Returns switch hardware model, MAC address, current IP, subnet, gateway, and firmware partitions4. |
| /api/v1/switch/ports | GET | Read Token | Opcode 0x01 (TLV 0x0C00, 0x2900)4 | Retrieves operational link speed, duplex mode, administrative state, and PVID across all 8 ports4. |
| /api/v1/switch/vlans | GET | Read Token | Opcode 0x01 (TLV 0x2800, 0x2900)4 | Decodes the complete 802.1Q VLAN table, mapping tagged and untagged port arrays per VID4. |
| /api/v1/switch/metrics | GET | None / Public | Opcode 0x01 (TLV 0x1000)4 | Exports per-port octets, packets, and CRC error counters formatted for Prometheus ingestion1. |
| /api/v1/switch/vlans | POST | Write Token | Opcode 0x17 ![][image16] 0x1A (TLVs 0x2800, 0x2900)6 | Atomically provisions 802.1Q VLAN memberships and assigns Port VLAN IDs with pre-flight safety checks6. |
| /api/v1/switch/ports/{port} | PATCH | Write Token | Opcode 0x17 ![][image16] 0x1A (TLV 0x0C00)6 | Modifies port administrative state (enable/disable), speed negotiation, or duplex override6. |
| /api/v1/switch/rollback | POST | Write Token | Opcode 0x17 ![][image16] 0x1A (All cached TLVs)6 | Reverts active switch configuration to the last cached snapshot acquired prior to mutation6. |

### **Data Contracts and JSON Request/Response Schemas**

#### **1\. System Telemetry (GET /api/v1/switch/info)**

**Response Schema (200 OK)**:

&nbsp;

&nbsp;

&nbsp;

JSON

{  
&nbsp;&nbsp;"model": "GS108Ev2",  
&nbsp;&nbsp;"device\_name": "Core-GS108E",  
&nbsp;&nbsp;"mac\_address": "00:a0:bc:12:34:56",  
&nbsp;&nbsp;"location": "Rack-Alpha",  
&nbsp;&nbsp;"ipv4\_address": "192.168.1.220",  
&nbsp;&nbsp;"subnet\_mask": "255.255.255.0",  
&nbsp;&nbsp;"gateway": "192.168.1.1",  
&nbsp;&nbsp;"dhcp\_mode": "static",  
&nbsp;&nbsp;"firmware": {  
&nbsp;&nbsp;&nbsp;&nbsp;"bank\_1": "1.00.12",  
&nbsp;&nbsp;&nbsp;&nbsp;"bank\_2": "1.00.08",  
&nbsp;&nbsp;&nbsp;&nbsp;"active\_slot": 1  
&nbsp;&nbsp;}  
}

#### **2\. Port Status and Telemetry (GET /api/v1/switch/ports)**

**Response Schema (200 OK)**:

&nbsp;

&nbsp;

&nbsp;

JSON

{  
&nbsp;&nbsp;"ports": \[  
&nbsp;&nbsp;&nbsp;&nbsp;{  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"port\_id": 1,  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"link\_status": "up",  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"speed\_mbps": 1000,  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"duplex": "full",  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"admin\_enabled": true,  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"pvid": 1  
&nbsp;&nbsp;&nbsp;&nbsp;},  
&nbsp;&nbsp;&nbsp;&nbsp;{  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"port\_id": 2,  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"link\_status": "down",  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"speed\_mbps": 0,  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"duplex": "unknown",  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"admin\_enabled": false,  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"pvid": 10  
&nbsp;&nbsp;&nbsp;&nbsp;}  
&nbsp;&nbsp;\]  
}

#### **3\. VLAN Mutation Request (POST /api/v1/switch/vlans)**

**Request Payload**:

&nbsp;

&nbsp;

&nbsp;

JSON

{  
&nbsp;&nbsp;"commit\_confirm": true,  
&nbsp;&nbsp;"timeout\_seconds": 5,  
&nbsp;&nbsp;"vlans": \[  
&nbsp;&nbsp;&nbsp;&nbsp;{  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"vid": 1,  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"name": "Management",  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"untagged\_ports": \[1, 2, 3, 4\],  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"tagged\_ports": \[\]  
&nbsp;&nbsp;&nbsp;&nbsp;},  
&nbsp;&nbsp;&nbsp;&nbsp;{  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"vid": 10,  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"name": "Servers",  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"untagged\_ports": \[5, 6\],  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"tagged\_ports": \[1\]  
&nbsp;&nbsp;&nbsp;&nbsp;},  
&nbsp;&nbsp;&nbsp;&nbsp;{  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"vid": 20,  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"name": "IoT",  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"untagged\_ports": \[7, 8\],  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"tagged\_ports": \[1\]  
&nbsp;&nbsp;&nbsp;&nbsp;}  
&nbsp;&nbsp;\],  
&nbsp;&nbsp;"pvids": {  
&nbsp;&nbsp;&nbsp;&nbsp;"1": 1,  
&nbsp;&nbsp;&nbsp;&nbsp;"2": 1,  
&nbsp;&nbsp;&nbsp;&nbsp;"3": 1,  
&nbsp;&nbsp;&nbsp;&nbsp;"4": 1,  
&nbsp;&nbsp;&nbsp;&nbsp;"5": 10,  
&nbsp;&nbsp;&nbsp;&nbsp;"6": 10,  
&nbsp;&nbsp;&nbsp;&nbsp;"7": 20,  
&nbsp;&nbsp;&nbsp;&nbsp;"8": 20  
&nbsp;&nbsp;}  
}

**Response Schema (200 OK)**:

&nbsp;

&nbsp;

&nbsp;

JSON

{  
&nbsp;&nbsp;"status": "success",  
&nbsp;&nbsp;"transaction\_id": "tx-88319-vlan",  
&nbsp;&nbsp;"applied\_tlvs": \["0x2800", "0x2900"\],  
&nbsp;&nbsp;"health\_check\_passed": true,  
&nbsp;&nbsp;"committed\_to\_flash": true  
}

#### **4\. Prometheus Metrics Exporter Schema (GET /api/v1/switch/metrics)**

The endpoint decodes TLV 0x1000 into standard Prometheus exposition format1:

# **HELP netgear\_port\_receive\_bytes\_total Total inbound octets received on port**

# **TYPE netgear\_port\_receive\_bytes\_total counter**

netgear\_port\_receive\_bytes\_total{port="1",device="GS108Ev2"} 4829104820

netgear\_port\_receive\_bytes\_total{port="2",device="GS108Ev2"} 12049182

# **HELP netgear\_port\_transmit\_bytes\_total Total outbound octets transmitted on port**

# **TYPE netgear\_port\_transmit\_bytes\_total counter**

netgear\_port\_transmit\_bytes\_total{port="1",device="GS108Ev2"} 9812401829

netgear\_port\_transmit\_bytes\_total{port="2",device="GS108Ev2"} 8492019

# **HELP netgear\_port\_crc\_errors\_total Inbound frame CRC errors detected**

# **TYPE netgear\_port\_crc\_errors\_total counter**

netgear\_port\_crc\_errors\_total{port="1",device="GS108Ev2"} 0

netgear\_port\_crc\_errors\_total{port="2",device="GS108Ev2"} 4

## **Configuration Persistence, Mutation Safety, and Fault Mitigation**

Automating configuration updates on consumer-grade Easy Smart hardware requires careful operational safeguards.

Unlike enterprise platforms, the GS108Ev2 lacks redundant management processors, dedicated out-of-band serial consoles, and transactional rollback engines4.

Understanding its internal memory architecture is essential for preventing permanent lockout conditions.

### **Memory Hierarchy, NOR Flash Endurance, and Commit Dynamics**

In enterprise switching platforms, configuration modifications alter an active running-config held within volatile RAM17.

The administrator must issue an explicit commit instruction (such as copy running-config startup-config or write memory) to serialize changes to persistent non-volatile storage.

If an administrative error isolates the management plane, power-cycling the appliance discards the volatile state and restores the last operational configuration from flash.

The Netgear GS108Ev2 operates on a fundamentally different memory model6.

The switch incorporates an embedded microcontroller directly coupled to an SPI NOR flash memory chip6.

When the switch processes an authenticated NSDP Write Request (0x03 or 0x1A), the microcode immediately writes the updated configuration properties into the NOR flash sectors4.

There is no intermediate staging area and no uncommitted volatile state6.

This architectural behavior imposes two critical engineering constraints:

* **Flash Sector Wear and Write Exhaustion**: SPI NOR flash blocks typically support between 10,000 and 100,000 program-erase (P/E) cycles before sector degradation occurs. Automated workflows must never execute high-frequency write operations, such as dynamic port power-cycling or automated flapping scripts. Configuration mutations must be restricted to deliberate, batch-processed provisioning routines. Conversely, Read Requests (0x01) query hardware operational registers and RAM buffers directly without touching flash memory, permitting high-frequency polling for telemetry and monitoring6.  
* **Immediate Persistence of Faulty Configurations**: Because writes commit to non-volatile flash immediately, power-cycling a switch following an administrative misconfiguration will not recover the device6. The reboot sequence reloads the newly corrupted configuration directly from flash memory6.

### **Root Causes of Network Partitioning and Administrative Lockout**

Because the GS108Ev2 lacks an independent physical management port, management traffic shares the internal switching fabric6.

The internal management interface is permanently bound to **VLAN 1**16.

Three distinct misconfigurations can trigger administrative lockout:

* **PVID Inconsistency on Management Uplinks**: The Port VLAN ID (PVID) governs the VLAN assignment applied to incoming untagged Ethernet frames19. If an automated script assigns an alternative PVID (such as VLAN 10\) to the switch port connected to the OpenWrt router without establishing an untagged egress path on VLAN 1, incoming management frames are classified into VLAN 1016. The internal switch controller, listening strictly on VLAN 1, drops these packets immediately, severing all NSDP connectivity.  
* **Asymmetric Egress Tagging Discrepancies**: In the Netgear 802.1Q implementation, VLAN membership (defining which ports emit frames for a given VID) and PVID (defining ingress tagging) are managed in separate tables20. If an automation tool assigns a port to VLAN 20 as "Untagged" but fails to update its PVID from 1 to 20, an asymmetric state is created: outbound traffic from the switch is stripped of tags, but inbound traffic from the host is classified into VLAN 1, breaking bidirectional communication.  
* **Trunk Port Membership Omission**: When provisioning multi-VLAN networks, the trunk uplink port interconnecting the switch to the upstream router must be configured as a Tagged (T) member across all secondary VLANs while retaining Untagged (U) or Tagged membership on VLAN 116. Automated scripts that issue full VLAN table replacements often overwrite previous states; omitting the uplink port from the replacement bitmask disconnects the switch from the upstream network entirely.

### **Automated Safety Pipeline and Commit-Confirm Emulation**

To prevent configurations that require a manual physical factory reset using the chassis pinhole, the automation daemon executes all mutations through a multi-stage validation and commit pipeline.

The transition pipeline progresses through the following sequential stages:

> 1. **Pre-Flight Invariant Validation**: The daemon parses the proposed configuration against static safety rules. Any rule violation results in an immediate transaction abort before network traffic generation.  
> 2. **Snapshot Acquisition**: The daemon queries the switch over NSDP to capture its active operational state (0x0C00, 0x2800, 0x2900), serializing the configuration into a local recovery snapshot4.  
> 3. **Atomic Multi-TLV Packing and Dispatch**: The daemon packs all configuration modifications into a single NSDP Write Request datagram (0x1A), transmitting it to the switch on port 633226.  
> 4. **Post-Write Health Verification**: The daemon initiates a verification sequence, issuing read requests and ICMP pings to confirm administrative access6.  
> 5. **Rollback Execution or Finalization**: If health verification succeeds, the transaction is finalized. If the check times out, the daemon transmits the snapshot configuration captured in stage 2 to restore operational state.

The pre-flight validation rules and operational invariants are detailed in the following specification:

&nbsp;

| Validation Rule | Target TLVs | Verification Logic | Failure Consequence |
| :---- | :---- | :---- | :---- |
| **Uplink Port Protection** | 0x0C00, 0x2800, 0x2900 | The designated uplink port (Port 1\) must never have its administrative state set to disabled, nor can its PVID be altered from 1 unless the upstream router sub-interface has been pre-configured for tagged management. | Immediate execution abort before packet generation. |
| **VLAN 1 Forwarding Invariant** | 0x2800 (802.1Q Map)4 | The bitmask corresponding to VLAN 1 must retain the uplink port as an active forwarding member (Tagged or Untagged). | Execution abort with validation exception. |
| **PVID / Untagged Parity** | 0x2800, 0x2900 | For every access port, the PVID assigned in 0x2900 must match the unique VID for which that port is marked "Untagged" in 0x280016. | Automatic configuration correction or abort. |
| **Atomic Multi-TLV Serialization** | All write TLVs | All desired modifications (0x0C00, 0x2800, 0x2900) must be packed into a single NSDP write datagram rather than multiple distinct requests4. | Prevents the switch from operating in an inconsistent intermediate state. |

#### **Commit-Confirm Emulation Workflow**

Because the GS108Ev2 hardware commits directly to flash, the proxy daemon implements software-managed commit-confirm emulation:

* **Phase 1: In-Memory Rollback Staging**: Before dispatching any mutation payload, the proxy requests full copies of TLVs 0x0C00, 0x2800, and 0x2900 from the switch4. This pristine state is cached in memory on OpenWrt alongside a 5-second countdown timer.  
* **Phase 2: Atomic Transmission**: The proxy issues the authenticated write datagram (0x1A) over UDP port 63321 to switch port 633224.  
* **Phase 3: Automated Connectivity Verification**: The daemon immediately dispatches an NSDP Read Request (0x01) targeting TLV 0x0001 (Model Name) and transmits an ICMP echo request to 192.168.1.2204.  
* **Phase 4A: Successful Verification**: If the switch responds within the 3-second timeout window, connectivity is verified. The staged rollback snapshot is discarded, and an HTTP 200 OK is returned to the MCP orchestrator.  
* **Phase 4B: Rollback Execution**: If the verification request times out, the daemon immediately transmits an authenticated write datagram containing the cached pre-mutation snapshot6. Because the OpenWrt router remains physically connected on VLAN 1, the rollback datagram reaches the switch, restoring operational parameters and averting a permanent lockout condition.

## **Implementation Strategy and Deployment Blueprint**

Transitioning homelab switch management from manual configuration to headless automation requires executing a focused implementation plan:

> 1. **Discard Web-Scraping Tooling**: Remove all references to py-netgear-plus from the automation environment12. Because firmware 1.00.12 does not expose an HTTP daemon, retaining web-scraping wrappers introduces recurring connection timeouts.  
> 2. **Compile the OpenWrt Micro-Daemon**: Leverage yaamai/go-nsdp as the protocol foundation for the embedded management proxy6. Cross-compile the daemon for OpenWrt running on the Belkin AX3200 (ARM64 MediaTek MT7622):  
>    Bash  
>    git clone https://github.com/yaamai/go-nsdp.git  
>    cd go-nsdp  
>    GOOS=linux GOARCH=arm64 go build \-ldflags="-s \-w" \-o nsdpd ./cmd/nsdp-daemon

> 3. **Deploy the Daemon to OpenWrt**: Copy the compiled nsdpd binary to /usr/bin/nsdpd on 192.168.1.226 and establish an OpenWrt procd init service script at /etc/init.d/nsdpd:  
>    Bash  
>    \#\!/bin/sh /etc/rc.common  
>    USE\_PROCD=1  
>    START=95  
>    STOP=10

>    start\_service() {  
>    &nbsp;&nbsp;&nbsp;&nbsp;procd\_open\_instance  
>    &nbsp;&nbsp;&nbsp;&nbsp;procd\_set\_param command /usr/bin/nsdpd \-interface br-lan \-port 8080 \-switch-ip 192.168.1.220  
>    &nbsp;&nbsp;&nbsp;&nbsp;procd\_set\_param respawn 3600 5 0  
>    &nbsp;&nbsp;&nbsp;&nbsp;procd\_set\_param stdout 1  
>    &nbsp;&nbsp;&nbsp;&nbsp;procd\_set\_param stderr 1  
>    &nbsp;&nbsp;&nbsp;&nbsp;procd\_close\_instance  
>    }

>    Enable and start the service:  
>    Bash  
>    chmod \+x /etc/init.d/nsdpd  
>    /etc/init.d/nsdpd enable  
>    /etc/init.d/nsdpd start

> 4. **Refactor Remote Control Scripts**: Update mcp/homelab/scripts/manage-netgear-switch.py to target the OpenWrt REST API (http://192.168.1.226:8080/api/v1/...) rather than attempting direct L2 packet dispatch. This eliminates Layer 3 routing barriers while maintaining centralized control from the MCP server.  
> 5. **Enforce Safe Mutation Pipelines**: Require all write operations to pass through pre-flight invariant validation and the automated commit-confirm rollback loop. Packing all VLAN and PVID mutations into single, atomic NSDP datagrams guarantees transactional consistency and protects the GS108Ev2 switch against unrecoverable network partitioning4.

#### **Works cited**

> 1. Netgear Switch Discovery Protocol \- Grokipedia, [https://grokipedia.com/page/netgear\_switch\_discovery\_protocol](https://grokipedia.com/page/netgear_switch_discovery_protocol)  
> 2. GS108Ev2 | 8-Port Gigabit Ethernet Plus Switch \- Netgear, [https://www.netgear.com/support/product/gs108ev2](https://www.netgear.com/support/product/gs108ev2)  
> 3. ntgrrc (Netgear Remote Control) a command line (CLI) tool ... \- GitHub, [https://github.com/nitram509/ntgrrc](https://github.com/nitram509/ntgrrc)  
> 4. Netgear Switch Discovery Protocol \- Wikipedia, [https://en.wikipedia.org/wiki/Netgear\_Switch\_Discovery\_Protocol](https://en.wikipedia.org/wiki/Netgear_Switch_Discovery_Protocol)  
> 5. GS108PEv2: No web GUI & IP Scanner can't see. Netgear config, [https://community.netgear.com/discussions/business-smart-plus-click-switches/gs108pev2-no-web-gui--ip-scanner-cant-see-netgear-config-utility-ok-is-this-norm/1063799](https://community.netgear.com/discussions/business-smart-plus-click-switches/gs108pev2-no-web-gui--ip-scanner-cant-see-netgear-config-utility-ok-is-this-norm/1063799)  
> 6. NSDP(Netgear Switch Discovery Protocol) client library for go · GitHub, [https://github.com/yaamai/go-nsdp](https://github.com/yaamai/go-nsdp)  
> 7. go-nsdp/types.go at master \- GitHub, [https://github.com/CursedHardware/go-nsdp/blob/master/types.go](https://github.com/CursedHardware/go-nsdp/blob/master/types.go)  
> 8. nccgroup/nsdp-discover \- GitHub, [https://github.com/nccgroup/nsdp-discover](https://github.com/nccgroup/nsdp-discover)  
> 9. libnsdp/nsdp\_property\_types.h at master · AlbanBedel/libnsdp, [https://github.com/AlbanBedel/libnsdp/blob/master/nsdp\_property\_types.h](https://github.com/AlbanBedel/libnsdp/blob/master/nsdp_property_types.h)  
> 10. Technical Advisory – Multiple Vulnerabilities in Netgear ProSAFE, [https://www.nccgroup.com/research/technical-advisory-multiple-vulnerabilities-in-netgear-prosafe-plus-jgs516pe-gs116ev2-switches/](https://www.nccgroup.com/research/technical-advisory-multiple-vulnerabilities-in-netgear-prosafe-plus-jgs516pe-gs116ev2-switches/)  
> 11. netgear-tool/docs/cli.md at main \- GitHub, [https://github.com/jfrancis42/netgear-tool/blob/main/docs/cli.md](https://github.com/jfrancis42/netgear-tool/blob/main/docs/cli.md)  
> 12. Python Library for NETGEAR Plus Switches \- GitHub, [https://github.com/foxey/py-netgear-plus](https://github.com/foxey/py-netgear-plus)  
> 13. ckarrie/ha-netgear-plus: HomeAssistant Netgear Switch Integration, [https://github.com/ckarrie/ha-netgear-plus](https://github.com/ckarrie/ha-netgear-plus)  
> 14. py-netgear-plus \- PyPI, [https://pypi.org/project/py-netgear-plus/](https://pypi.org/project/py-netgear-plus/)  
> 15. Devlog \- Maja Bojarska, [https://majabojarska.dev/devlog/](https://majabojarska.dev/devlog/)  
> 16. HPE ArubaOS switch \- "PVID mismatch" messages on the event log, [https://support.hpe.com/hpesc/public/docDisplay?docId=sf000046817en\_us\&docLocale=en\_US](https://support.hpe.com/hpesc/public/docDisplay?docId=sf000046817en_us&docLocale=en_US)  
> 17. Managed Switch Software Setup Manual \- Netgear, [https://www.downloads.netgear.com/files/GDC/M5300/M5300\_Software\_Setup\_Manual\_v10.pdf](https://www.downloads.netgear.com/files/GDC/M5300/M5300_Software_Setup_Manual_v10.pdf)  
> 18. VLAN Bandwidth Speed Issue | Netgate Forum, [https://forum.netgate.com/topic/197328/vlan-bandwidth-speed-issue](https://forum.netgate.com/topic/197328/vlan-bandwidth-speed-issue)  
> 19. What is the difference between native vlan and PVID?, [https://community.cisco.com/t5/switching/what-is-the-difference-between-native-vlan-and-pvid/m-p/4901711/highlight/true](https://community.cisco.com/t5/switching/what-is-the-difference-between-native-vlan-and-pvid/m-p/4901711/highlight/true)  
> 20. Confused by prosumer gear: What really is PVID and why is ... \- Reddit, [https://www.reddit.com/r/networking/comments/e1igrv/confused\_by\_prosumer\_gear\_what\_really\_is\_pvid\_and/](https://www.reddit.com/r/networking/comments/e1igrv/confused_by_prosumer_gear_what_really_is_pvid_and/)  
> 21. Why are untagged VLANs configured separately from the port PVID?, [https://serverfault.com/questions/1044237/why-are-untagged-vlans-configured-separately-from-the-port-pvid](https://serverfault.com/questions/1044237/why-are-untagged-vlans-configured-separately-from-the-port-pvid)

[image1]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABMAAAAaCAYAAABVX2cEAAABHElEQVR4XmNgGAWUAkcgfg3E/6F4BxBzIsnzAfEuJHkQXgfE3EhqUAAjEM8C4l9A/BOILVGlwSAIiNcwoFqEFQgC8UIgzmeA2DyFAWIBMigC4mg0MaxAH4j7gVgSiK8D8RMgVkSSZwHi2VB1BAHIxnQou4EB4rocuCwDgwgDxOUgHxAEfUBsDGXrAPF7ID4BxPxQMRsgngxl4wWw8ALZDgIgLy0H4n9A7AEVA7mapPBCDnCQISDDQIaCYo+s8IIBkPdA3gR514mByPACuQYUFqboEkAQwwCJiGtA3IkmhxWghxcyEGeAJBOQgUSFF8gLoKzBhS4BBQ1A/BaINdHEUYALEH9hQOQ1UBbyRlEBAaBkAsqrBMNrFIyCIQMA260zNBT6yKgAAAAASUVORK5CYII=>

[image2]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACUAAAAWCAYAAABHcFUAAAAAsklEQVR4XmNgGAWjYBSgAD4grgHiQ0CsjCZHdyAMxN1AfBiInYCYGVWavkARiOcyQELGHIgZUaXpC9SBeDUUazEMoGNAFoNCYzsDJHRAoTTgwB+IPwFxEMMAhgw2MKgSNDqAZf0TDJAQHFSO4wbifCA+B8RxQMyJKj2wgBWIIxggjgM5EuTYQQNA0QiKzh1ArIImNwoGFIDSjTgQSxKBxRjolCMNgHgWkbiXAeK4UTDgAACDZRlztwW9PwAAAABJRU5ErkJggg==>

[image3]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAZCAYAAAA4/K6pAAAAj0lEQVR4XmNgGAXDDHADsTi6IBJgBGIpIGZGl4ABUSBeBcQm6BIMEM0JQDwZiFlRpVCBDBDvAGIzJDGiNcMAsiEka4YBmCFTGMjQDAIgm4uA+DUQW6HJEQQgzTkMEJvlgHg9A2qY4AXImmHOlmAg0hCQ5iwgnsCA6WeiDNEC4iYGTM0wIATEXVB6FIwCFAAAf0YRLC1qw90AAAAASUVORK5CYII=>

[image4]: <data:image/png;base64,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>

[image5]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABIAAAAWCAYAAADNX8xBAAABNElEQVR4Xu3TvUoDURCG4bEQIgohCHaChWAlRPy7AbEUQQWJN5AijRaKVoJYKNhYaiEWXoKVFgHBQnsbC0EEwcJK7UTf2bO7mcweMFjng6fIt+zsmU0i0s1/U8YZxv0FMoZDnKCGvvbLrfRgG5+YdNeW8IAqBrCHKwkPLmQW71IcNIxHrJmugns0TJdEJ59KOLYfpAN8p6e/QNN0Sbkh4fhbUrzpONJpzvFqixkcoVfig/QG39k+ia6k64ykn/0gfbFN12XJB+lK61gxF/2gfly7Lks+aEJaK2XxgzR/rlbHs/OBH7zhBkPYT2+IDXpxXZ7YiRbwjTnTlXCZimYHX5g23SDusGu6UQmnWTVdEn2arqNrKT3BrYTVNFN4wiaWJfyqD6T9/XYc/QbnsSjhb9NNh/kFbmRK+WJXmWsAAAAASUVORK5CYII=>

[image6]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABIAAAAWCAYAAADNX8xBAAABcklEQVR4Xu2TsStFYRjGH0kRkWRQJFIiRbHYZbwpiiirxaaIScnAaLQZrEpSwnCjDAwyMKCUlL/AKJ7nPN8595xbJ9d+n/rV/d73/Z7zft/3XqCq/6iBzJN9sksGSU2mwuqH86pTvfYlaiFHZJF0kGFyRVaQNZsmT2SENJEtcgHvj7RMNuJF0BC5Jz1h3UVeyEJSAbSSO3h/pAOyg+zX1ZmM1J0kgy8ymlS4/pAU48A2+SF7pDHEZskpfARJuXIjSU18xotu8gybvcLG1yEeSxvyjBRPNEDeYTOhguaQU1dFVGDUCXewBL+cEjK7IW3wcS9DPNdIc3BC1lJJGR/DZvGL/Hk0vYruR0dLSx84gwsl3Vue0Yd+KKEh682kLc2WXksqkG8yUUqjHn5ZEV3kOVlHdo7a4QseD2vd1S3ZDGupD+5mLh14gA01eOrkEb74tPkYeSOrZAaeag1yXaoGtfAxVTCJ0mCWS3Hlp+C/TVUV6hcMyE8bnqodUAAAAABJRU5ErkJggg==>

[image7]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACUAAAAWCAYAAABHcFUAAAAAm0lEQVR4XmNgGAWjYBSMglEwvAAjEIcD8VMg/gvEK4FYBkUFAnADcSq6IC2AKxBvBWI1IBYD4mQgvg7ElsiKoEAciHPQBakNWIC4lQFiGTJQAeITQJwExMxQMRBdAsTuMEW0AiJAXIouCAVCQLwKiG8B8VwgPgfEU4GYFVkRLQDIAkl0QSQASm+gaA0BYmMGRKiNglEwCkYBPQAAsWUOPkwNLy0AAAAASUVORK5CYII=>

[image8]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAC4AAAAWCAYAAAC/kK73AAAAqUlEQVR4XmNgGAWjYBSMgoEG3EDMii44mIE6EK8G4mVALIomN+gAIxCbA/F+IJ4CxLKo0oMPMAOxExAfBuJuIBZGlR58AORgfyA+AcQ1QMyHKj34ACizRQDxOSDOZ4BkwCEBHIH4ARBnADEnqtTgB8ihXsYwBJIJOoCl89MMQyRjogP0olASVXrwA5AH9IB4OxDPBWJFVOmhAUCO7gJiFXSJUTAKRgF1AQCkpxFIZl0KMAAAAABJRU5ErkJggg==>

[image9]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAkAAAAWCAYAAAASEbZeAAAA3UlEQVR4Xs3RPY5BURjG8VeMQkhEyGjMAlQk7EDoJCLRWABLYEKrmHoyjU5lEwql0CiISjQ60Ui0+L9zznEJifY+yS+5H889X1fE/wmjgQH6SD++FslggW8xL+uY4dMV9GJpCwFEMMYJeVdq4yBmNJciOmKWIDFMMUfC0pGDrq3Rr3UULf6hi1+skHMlnVPnPqNmn+m6frAWu0NX0i+TtqSp4IKW3mRxxARRr3MrDfUmhY28KX1gJGZ38Rel/+k0JezFO7inhWtC6GGLppgj2KHgCvf5QhVlMb/Gt7kCDv8p9g6oXcIAAAAASUVORK5CYII=>

[image10]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABIAAAAWCAYAAADNX8xBAAABCElEQVR4Xu3TsWrCUBTG8eNQUFoo0slB6CCIQ6FQp87iKIIdRN9AnJ0LpUM7duzWwUfoVBFn3RxcHIpQ8AV0FP0fk5STaEKQjH7wW869fNHkXpFzTsktmsGhSRHv+EQLGbtYQgdDbPBlF00amOEeV3jBD669DVpUxyP+5HhRHnO0zSyLCbpmtk8OCzlepAVrPJhZCn2MzGyfqKIPOSzS6N5lYBZZpLOwIp37ElakL3YkCRRdYiAJFGkS+WuaVwkv0iPjS1RRTZzDWjGzNL5dvnhFejZSgbUbjPFsZgVxfs3/ldKn6ECfuHWtMMWdt4mU8YsensQ51W+4MHtiR79gVZwrpdfmnJjZAcCTQgXrRv/4AAAAAElFTkSuQmCC>

[image11]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABwAAAAWCAYAAADTlvzyAAAAn0lEQVR4XmNgGAWjYDgCbiBmRRekBVAH4tVAvAyIRdHkqAYYgdgciPcD8RQglkWVph5gBmInID4MxN1ALIwqTT0AssgfiE8AcQ0Q86FKUw+AEkEEEJ8D4nwGSMKgKXAE4gdAnAHEnKhStAPIvixjoGFwogNYPJ5moHGCQQfoWUISVZp2AGSxHhBvB+K5QKyIKk1bALKsC4hV0CVGwcgBAOc5EUgX07EAAAAAAElFTkSuQmCC>

[image12]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABsAAAAWCAYAAAAxSueLAAABmElEQVR4Xu2UPyiFURjGH6EokoUUhYEMikQxmKQkpRBhkUVWg8w2i0IpKRmksJoUNkoZ5M9kIGVioqT8eZ57vo/3O5dw3YXuU7/6znve9zznnnvOC6T0H1RK+vxgoB7SRHJIGikgg6TGJlHZpJ8skClSaSeryCjZJk9k2U4GyiBr5MVjneSZPH1vkUm4TWkjp6QrTJBZJ9yur/CxmbRIjskl2SDtJD2SAYyTA5JvYgPkzIxjKiIX+NxsltT5QSMZyMivryd3XuzXZjqhG8TXq+bei31pNkemySHcce+RWjMfLurXJ2S2RCbw/j/pJt6ShmDcAXdp/PqEzHIRvRDFcL9wFe62tiGJZr7C/HNSiCQe4xB5JiMmFuYLfZeTa8TX/9hM70dHZM3CY9yFe8BC35sk6y0LaCGPZhxTaLYC146sGuFuY6aJ9ZIHmO4Ad2n06MuCsdZRN9kPE+SsHapVhW1Ij/CIVAc5KhojO2SYzMC9KbU5uzFtZj7IU1eS0Qni++e3VAK3SCuiPdFK5hWkmzQjehop/SG9ArgOYnteAWEnAAAAAElFTkSuQmCC>

[image13]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABsAAAAWCAYAAAAxSueLAAAB1ElEQVR4Xu2UvSuFcRTHj6TIW2JkIHkphbDqDiIDKQZhMzAoSbGSDJTFokwk5R8wUW5ZxIwBKYlJIhYlvt97fufe3/Nwe0oG6n7rU79znvPy/F5FMvrPKgKTYB3MgxqQFYhQ1YJl0bghkBf8nBB9/MYYxjInqUYQBzFQAsbAG5iWYMN+cAaaQAFYAHug2IvhmD5+YwxjmcPchFbBO+h1NhuegAdQ73wV4AIMO5uyuAnPN+t8/GZizrkZK+ADjDq7EByCZ9FZU0x4BS3OpjjrbdFV4Sys+aYXQ7WBFzNyQBnIdnYDeJRUEYqzDzejWPgeVImuAlcj3Iw5zP0iHhT+7Y3oeptYIF0z81vRyGb5YEe0yRXoktRMObu4RDfrEd2OyGa+6sAd2BL9CbIv0c265QfNbOOZOO58v7KMPBxTDo5NPML+Xy5K+ma3oFz0kPCwpG1mg3AhJrAZTyHFO8i72JGMEMkFuw6ObW/NNjGHj0Tysm5I6iUoBceix7855JtzNlUtOqtBzzciesgqnc0t4WtyZAHc2EuwJJrIP3tyfl+t4BrMgAHRC8wcf/k5XgMHoE+00akEr1Fi2jHRIu0SLOCLJ7NTtBBX5TtxNnzIo2pl9Mf1CYMPdGpr2G1qAAAAAElFTkSuQmCC>

[image14]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAkAAAAWCAYAAAASEbZeAAAAU0lEQVR4XmNgGBpAAYgj0AVBQBOIs4B4HxD/BeKFqNIQAFIUAMRWQPyEAYciGJAE4ocMo4oYiFS0FIgZ0eQYXBggIQ2Kkv9Q/AWILwGxLpK6oQUAt74aLpIdjysAAAAASUVORK5CYII=>

[image15]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAkAAAAWCAYAAAASEbZeAAAAyklEQVR4XmNgGLxAAYijgFgGiJmBmAOI9YE4DcoGAysg/gnE/5HwVyD2hikAAWMgvgbEN4D4AhA3ArEksgIQACmajC6IDohWtB6IFwHxHSB+BMT1QMyJrugkEKtA+cJAfAqIZwExK0wRiMEN40BBFQPEx5Zo4iignAESFEUgDsjo00B8BYjFsCgC0eDweIhFEcg6kCI/EIcFiGcAsTmSAn4gPgTEe6BsMJAH4sNA3A3EyUB8HoiPMUDiEgWAfGgHxCFArMkAiehBCwDQuSOjpGHQNAAAAABJRU5ErkJggg==>

[image16]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABIAAAAWCAYAAADNX8xBAAAAhUlEQVR4XmNgGAWjgCTAAcRpQMyDLkEqYATiViA2RpcgB4AM6QViFnQJUgHIVQVAHAdlw4EAEEuSiOWAeD4QTwZiPiBm4AbiaiCeRQbeAcRfgbiZgQJgAsSrgVgGXYIUIAzEi4FYHl2CVJAFxBHogqQCUIKcCsTS6BKkAlB080LpUUACAABjSBNDIJEBIwAAAABJRU5ErkJggg==>