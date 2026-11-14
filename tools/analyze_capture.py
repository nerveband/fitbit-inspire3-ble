#!/usr/bin/env python3
"""Segment a .pklg by BLE connection, then decode ATT/GATT per connection.

Fixes over parse_pklg.py: iOS emits LE Enhanced Connection Complete (subevent 0x0A),
and handles are reused after a disconnect, so PDUs must be bucketed per epoch.
"""
import struct
import sys
from collections import defaultdict, OrderedDict

ATT = {
    0x01: "ERROR", 0x02: "MTU_REQ", 0x03: "MTU_RSP", 0x04: "FIND_INFO_REQ",
    0x05: "FIND_INFO_RSP", 0x06: "FIND_BY_TYPE_REQ", 0x07: "FIND_BY_TYPE_RSP",
    0x08: "READ_BY_TYPE_REQ", 0x09: "READ_BY_TYPE_RSP", 0x0A: "READ_REQ",
    0x0B: "READ_RSP", 0x0C: "READ_BY_GROUP_REQ", 0x0D: "READ_BY_GROUP_RSP",
    0x10: "WRITE_REQ", 0x11: "WRITE_RSP", 0x12: "WRITE_CMD",
    0x13: "PREP_WRITE_REQ", 0x16: "PREP_WRITE_RSP", 0x17: "EXEC_WRITE_REQ",
    0x18: "EXEC_WRITE_RSP", 0x1B: "NOTIFY", 0x1D: "INDICATE", 0x1E: "CONFIRM",
    0x52: "MULTI_NOTIFY",
}


def records(path):
    data = open(path, "rb").read()
    off, n = 0, len(data)
    while off + 13 <= n:
        ln, secs, usecs, typ = struct.unpack_from("<IIIB", data, off)
        plen = ln - 9
        if plen < 0:
            break
        payload = data[off + 13: off + 13 + plen]
        if len(payload) != plen:
            break
        yield secs + usecs / 1e6, typ, payload
        off += 4 + ln


def epochs(path):
    """Return ordered list of connection epochs with their ACL chunks."""
    conns = OrderedDict()      # handle -> list of epoch dicts
    cur = {}                   # handle -> epoch dict
    for ts, typ, p in records(path):
        if typ == 0x01 and p:
            if p[0] == 0x3E and len(p) > 1 and p[1] == 0x0A and len(p) >= 22:
                status = p[2]
                handle = struct.unpack_from("<H", p, 3)[0] & 0x0FFF
                role = p[5]
                addr_type = p[6]
                peer = ":".join("%02X" % b for b in reversed(p[7:13]))
                if status == 0:
                    e = {"handle": handle, "peer": peer, "role": role,
                         "addr_type": addr_type, "start": ts, "end": None,
                         "acl": []}
                    conns.setdefault(handle, []).append(e)
                    cur[handle] = e
            elif p[0] == 0x05 and len(p) >= 4:
                status = p[0:1]
                handle = struct.unpack_from("<H", p, 1)[0] & 0x0FFF
                if handle in cur and cur[handle] is not None:
                    cur[handle]["end"] = ts
                    cur[handle] = None
        elif typ in (0x02, 0x03) and len(p) >= 4:
            h = struct.unpack_from("<H", p, 0)[0]
            handle = h & 0x0FFF
            pb = (h >> 12) & 0x3
            ln = struct.unpack_from("<H", p, 2)[0]
            e = cur.get(handle)
            if e is not None:
                e["acl"].append((ts, typ == 0x02, pb, p[4:4 + ln]))
    return conns


def l2cap_pdus(chunks):
    buf = bytearray()
    for _, _, _, frag in chunks:
        buf += frag
    out, i = [], 0
    while i + 4 <= len(buf):
        ln, cid = struct.unpack_from("<HH", buf, i)
        if i + 4 + ln > len(buf):
            break
        out.append((cid, bytes(buf[i + 4:i + 4 + ln])))
        i += 4 + ln
    return out


def squuid(b):
    """16-byte little-endian UUID as canonical string."""
    h = bytes(reversed(b)).hex()
    return "%s-%s-%s-%s-%s" % (h[0:8], h[8:12], h[12:16], h[16:20], h[20:32])


def uu(b):
    return "0x%04X" % struct.unpack_from("<H", b, 0)[0] if len(b) == 2 else squuid(b)


def main(path):
    conns = epochs(path)
    print("%-6s %-18s %-5s %-9s %s" % ("handle", "peer", "role", "acl-pkts", "window"))
    flat = []
    for handle, eps in conns.items():
        for e in eps:
            flat.append(e)
    for e in flat:
        role = "central" if e["role"] == 0 else "peripheral" if e["role"] == 1 else str(e["role"])
        print("%-6s %-18s %-5s %-9d %.2f..%.2f" % ("0x%03X" % e["handle"], e["peer"], role,
              len(e["acl"]), e["start"] - flat[0]["start"],
              (e["end"] or e["acl"][-1][0] if e["acl"] else e["start"]) - flat[0]["start"]))

    for e in flat:
        pdus = l2cap_pdus(e["acl"])
        att = [(c, b) for c, b in pdus if c == 0x0004 and b]
        if not att:
            continue
        svcs, chars, reads, notifs = [], [], {}, defaultdict(list)
        for _, b in att:
            op = b[0]
            if op == 0x0D and len(b) >= 5:
                l = b[1]
                for off in range(2, len(b) - l + 1, l):
                    if l >= 4:
                        svcs.append((struct.unpack_from("<H", b, off)[0],
                                     struct.unpack_from("<H", b, off + 2)[0],
                                     uu(b[off + 4:off + l])))
            elif op == 0x09 and len(b) >= 5:
                l = b[1]
                for off in range(2, len(b) - l + 1, l):
                    if l == 21:
                        h = struct.unpack_from("<H", b, off)[0]
                        props = b[off + 2]
                        vh = struct.unpack_from("<H", b, off + 3)[0]
                        chars.append((h, props, vh, squuid(b[off + 5:off + 21])))
                    elif l >= 7:
                        h = struct.unpack_from("<H", b, off)[0]
                        chars.append((h, 0, None, uu(b[off + 2:off + l])))
            elif op == 0x0B and len(b) >= 3:
                pass
            elif op in (0x1B, 0x52) and len(b) >= 4:
                notifs[struct.unpack_from("<H", b, 1)[0]].append((len(b) - 3, b[3:]))
            elif op == 0x05 and len(b) >= 6:
                for off in range(2, len(b) - 3, 4):
                    h = struct.unpack_from("<H", b, off)[0]
                    reads.setdefault("handles", set()).add(h)

        if not svcs and not chars and not notifs:
            continue
        peers = e["peer"]
        print("\n=== handle 0x%03X peer %s (%d ATT PDUs) ===" % (e["handle"], peers, len(att)))
        if svcs:
            print("  services:")
            for s, en, u in svcs:
                print("    0x%04X-0x%04X  %s" % (s, en, u))
        if chars:
            print("  characteristics:")
            for h, props, vh, u in sorted(chars):
                print("    decl 0x%04X props=0x%02X value=0x%04X  %s" % (h, props, vh or 0, u))
        for h, lst in sorted(notifs.items()):
            print("  notify handle 0x%04X: %d pdus, first %d bytes: %s" %
                  (h, len(lst), lst[0][0], lst[0][1][:24].hex()))
            # look for ASCII strings
            for ln, pl in lst:
                for tok in (b"MD-", b"BOOTSTRAP", b"hello"):
                    if tok in pl:
                        print("      ascii %s in len=%d: %r" % (tok, ln, pl[:64]))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "fitbit-ios.pklg")
