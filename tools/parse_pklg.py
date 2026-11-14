#!/usr/bin/env python3
"""Parse an Apple PacketLogger (.pklg) capture down to ATT/GATT.

Usage: python3 parse_pklg.py fitbit-ios.pklg

Format, per wiretap/packetlogger.c in Wireshark:
  u32 LE len | u32 LE ts_secs | u32 LE ts_usecs | u8 type | len bytes payload
Types: 0x00 cmd, 0x01 event, 0x02 sent ACL, 0x03 recv ACL, 0xF7 syslog, ...
"""
import struct
import sys
from collections import defaultdict

KNOWN = {0x00, 0x01, 0x02, 0x03, 0x08, 0x09, 0x0A, 0x0B,
         0x07, 0x0C, 0x0D, 0x0E, 0x0F, 0xF7, 0xF8, 0xF9, 0xFA,
         0xFB, 0xFC, 0xFD, 0xFE, 0xFF}


def records(path):
    data = open(path, "rb").read()
    off = 0
    n = len(data)
    bad = 0
    while off + 13 <= n:
        ln, secs, usecs, typ = struct.unpack_from("<IIIB", data, off)
        # len covers ts_secs + ts_usecs + type + payload, i.e. 9 header bytes
        plen = ln - 9
        if plen < 0:
            break
        payload = data[off + 13: off + 13 + plen]
        if len(payload) != plen:
            break
        if typ not in KNOWN:
            bad += 1
            if bad > 5:
                break
        yield secs + usecs / 1e6, typ, payload
        off += 4 + ln


def events(path):
    """Return (le_conns, acl_by_handle, att_stream)."""
    le_conns = {}
    acl = defaultdict(list)
    for ts, typ, p in records(path):
        if typ == 0x01 and len(p) >= 3 and p[0] == 0x3E:
            # LE Meta Event
            sub = p[1]
            if sub == 0x01 and len(p) >= 14:
                status, handle = p[2], struct.unpack_from("<H", p, 3)[0]
                role = p[5]
                peer = ":".join("%02X" % b for b in reversed(p[8:14]))
                if status == 0:
                    le_conns[handle & 0x0FFF] = (peer, role, ts)
        elif typ in (0x02, 0x03) and len(p) >= 4:
            h = struct.unpack_from("<H", p, 0)[0]
            handle = h & 0x0FFF
            pb = (h >> 12) & 0x3
            ln = struct.unpack_from("<H", p, 2)[0]
            acl[handle].append((ts, typ == 0x02, pb, p[4:4 + ln]))
    return le_conns, acl


def att_pdus(chunks):
    """Reassemble L2CAP and yield (ts, outbound, cid, body)."""
    buf = bytearray()
    meta = []
    for ts, sent, pb, frag in chunks:
        buf += frag
        meta.append((ts, sent, pb))
    out = []
    i = 0
    while i + 4 <= len(buf):
        ln, cid = struct.unpack_from("<HH", buf, i)
        if i + 4 + ln > len(buf):
            break
        body = bytes(buf[i + 4: i + 4 + ln])
        out.append((cid, body))
        i += 4 + ln
    return out


ATT_NAMES = {
    0x01: "ERROR", 0x02: "MTU_REQ", 0x03: "MTU_RSP",
    0x04: "FIND_INFO_REQ", 0x05: "FIND_INFO_RSP",
    0x06: "FIND_BY_TYPE_REQ", 0x07: "FIND_BY_TYPE_RSP",
    0x08: "READ_BY_TYPE_REQ", 0x09: "READ_BY_TYPE_RSP",
    0x0A: "READ_REQ", 0x0B: "READ_RSP",
    0x0C: "READ_BY_GROUP_REQ", 0x0D: "READ_BY_GROUP_RSP",
    0x10: "WRITE_REQ", 0x11: "WRITE_RSP",
    0x12: "WRITE_CMD", 0x13: "PREPARE_WRITE_REQ",
    0x16: "PREPARE_WRITE_RSP", 0x17: "EXEC_WRITE_REQ",
    0x18: "EXEC_WRITE_RSP", 0x1B: "NOTIFY", 0x1D: "INDICATE",
    0x1E: "CONFIRM", 0x52: "MULTI_NOTIFY",
}


def u16(b, o):
    return struct.unpack_from("<H", b, o)[0]


def uuid_str(b):
    if len(b) == 2:
        return "0x%04X" % u16(b, 0)
    if len(b) == 16:
        # little endian on the wire
        h = b[::-1].hex()
        return "%s-%s-%s-%s-%s" % (h[0:8], h[8:12], h[12:16], h[16:20], h[20:32])
    return b.hex()


def main(path):
    le, acl = events(path)
    print("connections seen: %d, acl-link handles: %d" % (len(le), len(acl)))
    for h, (peer, role, ts) in sorted(le.items()):
        print("  handle 0x%03X peer %s role=%s t=%.3f" % (h, peer, "central" if role == 0 else "peripheral", ts))

    for handle in sorted(acl):
        pdus = att_pdus(acl[handle])
        att = [(c, b) for c, b in pdus if c == 0x0004]
        if not att:
            continue
        peer = le.get(handle, ("?",))[0]
        ops = defaultdict(int)
        for _, b in att:
            if b:
                ops[ATT_NAMES.get(b[0], hex(b[0]))] += 1
        print("\n=== handle 0x%03X peer %s: %d ATT PDUs, %d L2CAP ===" % (handle, peer, len(att), len(pdus)))
        print("   ops: " + ", ".join("%s=%d" % kv for kv in sorted(ops.items(), key=lambda kv: -kv[1])[:12]))

        svcs, chars, notif = [], [], []
        for _, b in att:
            if not b:
                continue
            op = b[0]
            if op == 0x0D and len(b) >= 5:      # read by group type response
                l = b[1]
                for off in range(2, len(b) - l + 1, l):
                    if l >= 4:
                        s, e = u16(b, off), u16(b, off + 2)
                        svcs.append((s, e, uuid_str(b[off + 4: off + l])))
            elif op == 0x09 and len(b) >= 5:    # read by type response
                l = b[1]
                for off in range(2, len(b) - l + 1, l):
                    if l >= 3:
                        h = u16(b, off)
                        chars.append((h, b[off + 2], uuid_str(b[off + 3: off + l])))
            elif op in (0x1B, 0x52) and len(b) >= 3:
                notif.append((u16(b, 1), b[3:]))
        print("   services (%d):" % len(svcs))
        for s, e, u in svcs:
            print("     0x%04X-0x%04X %s" % (s, e, u))
        print("   characteristics (%d):" % len(chars))
        for h, props, u in chars:
            print("     handle 0x%04X props=0x%02X %s" % (h, props, u))

        if notif:
            print("   notifications: %d, sample payloads:" % len(notif))
            seen = set()
            for h, pl in notif[:400]:
                key = (h, pl[:2].hex())
                if key in seen:
                    continue
                seen.add(key)
                print("     handle 0x%04X len=%d %s" % (h, len(pl), pl[:24].hex()))
                if len(seen) >= 12:
                    break


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "fitbit-ios.pklg")
