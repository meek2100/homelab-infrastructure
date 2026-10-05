"""Minimal fast pcapng reader: yields (frame_no, ts, orig_len, data) for EPB/SPB blocks."""
import struct

def read(path):
    with open(path, "rb") as fh:
        buf = fh.read()
    n = len(buf); off = 0; endian = "<"; tsres = {}; ifidx = 0; frame = 0
    while off + 12 <= n:
        btype, blen = struct.unpack_from(endian + "II", buf, off)
        if btype == 0x0A0D0D0A:  # SHB: detect byte order
            bom = buf[off + 8:off + 12]
            endian = "<" if bom == b"\x4d\x3c\x2b\x1a" else ">"
            btype, blen = struct.unpack_from(endian + "II", buf, off)
            tsres = {}; ifidx = 0
        if blen < 12 or off + blen > n:
            break
        if btype == 1:  # IDB
            res = 1e-6
            o = off + 16
            end = off + blen - 4
            while o + 4 <= end:
                code, ln = struct.unpack_from(endian + "HH", buf, o)
                if code == 0:
                    break
                if code == 9 and ln >= 1:
                    v = buf[o + 4]
                    res = 2.0 ** -(v & 0x7f) if v & 0x80 else 10.0 ** -v
                o += 4 + ((ln + 3) & ~3)
            tsres[ifidx] = res; ifidx += 1
        elif btype == 6:  # EPB
            iid, th, tl, caplen, origlen = struct.unpack_from(endian + "IIIII", buf, off + 8)
            frame += 1
            ts = ((th << 32) | tl) * tsres.get(iid, 1e-6)
            yield frame, ts, origlen, buf[off + 28:off + 28 + caplen]
        elif btype == 3:  # SPB
            origlen = struct.unpack_from(endian + "I", buf, off + 8)[0]
            frame += 1
            yield frame, 0.0, origlen, buf[off + 12:off + blen - 4]
        off += blen
