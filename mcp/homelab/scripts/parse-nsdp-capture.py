#!/usr/bin/env python3
"""
Inspect and parse Netgear NSDP frames from Wireshark pcapng capture files.
"""

import glob
import os
import struct
import sys

def main():
    capture_dir = sys.argv[1] if len(sys.argv) > 1 else "/captures"
    files = sorted(glob.glob(os.path.join(capture_dir, "router_baseline*.pcapng")), key=os.path.getmtime, reverse=True)
    if not files:
        files = sorted(glob.glob("/nas-storage/router_baseline*.pcapng"), key=os.path.getmtime, reverse=True)

    if not files:
        print("No capture files found in", capture_dir)
        sys.exit(0)

    target = files[0]
    size = os.path.getsize(target)
    print(f"Analyzing {target} ({size} bytes)...")

    with open(target, "rb") as f:
        data = f.read()

    sig = b"NSDP"
    pos = 0
    found = 0
    opcodes = {
        1: "ReadReq",
        2: "ReadResp",
        3: "WriteReq",
        4: "WriteResp",
        0x18: "ChallengeReq",
        0x19: "ChallengeResp",
    }
    delimiter = bytes.fromhex("ffff0000")

    while pos < len(data) and found < 30:
        idx = data.find(sig, pos)
        if idx == -1:
            break

        start = idx - 24
        if start >= 0 and start + 32 <= len(data):
            ver = data[start]
            opcode = data[start + 1]
            res_code = struct.unpack_from(">H", data, start + 2)[0]
            mgr_mac = ":".join(f"{b:02x}" for b in data[start + 8 : start + 14])
            sw_mac = ":".join(f"{b:02x}" for b in data[start + 14 : start + 20])
            seq = struct.unpack_from(">H", data, start + 22)[0]

            end_idx = data.find(delimiter, idx)
            if end_idx != -1 and end_idx - start < 1500:
                payload_len = (end_idx + 4) - start
                packet_bytes = data[start : start + payload_len]
                op_name = opcodes.get(opcode, f"Opcode({opcode})")
                print(f"\n[Frame #{found + 1}] {op_name} | Seq: {seq} | Mgr MAC: {mgr_mac} | Sw MAC: {sw_mac}")
                print("Hex Payload:", packet_bytes.hex())

                offset = start + 32
                tlvs = []
                while offset + 4 <= end_idx:
                    tag, tlen = struct.unpack_from(">HH", data, offset)
                    offset += 4
                    if tag == 0xFFFF:
                        break
                    val = data[offset : offset + tlen]
                    tlvs.append(f"0x{tag:04X}({tlen}B):{val.hex()}")
                    offset += tlen
                print("TLVs:", tlvs)
                found += 1
                pos = end_idx + 4
            else:
                pos = idx + 4
        else:
            pos = idx + 4

    print(f"\nFinished scan: found {found} NSDP frames.")

if __name__ == "__main__":
    main()
