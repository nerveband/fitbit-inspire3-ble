#!/usr/bin/env python3
"""Session-level decode of a PacketLogger iOS capture for the Fitbit link.

For every ATT connection carrying GattLink/IP traffic, report:
  - peer name if seen, MTU negotiated
  - UDP endpoints and DTLS record census
  - the DTLS pre-shared-key identity (cleartext, in the handshake)
  - app-data cadence per 5 s bucket, to see sync bursts vs 1 Hz polling
Usage: python3 decode_sessions.py fitbit-ios.pklg
"""
import struct
import sys
import collections
import importlib.util

spec = importlib.util.spec_from_file_location("pp", "parse_pklg.py")
pp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pp)

ATT_WRITE_START = {0x12, 0x52, 0x1B}
DTLS_NAMES = {20: "change_cipher_spec", 21: "alert", 22: "handshake", 23: "app_data"}


def sq(b):
    h = bytes(reversed(b)).hex()
    return "%s-%s-%s-%s-%s" % (h[0:8], h[8:12], h[12:16], h[16:20], h[20:32])


def build(path):
    recs = list(pp.records(path))
    t0 = recs[0][0]
    chunks = collections.defaultdict(list)
    for ts, typ, p in recs:
        if typ in (0x02, 0x03) and len(p) >= 4:
            h = struct.unpack_from("<H", p, 0)[0]
            ln = struct.unpack_from("<H", p, 2)[0]
            chunks[h & 0x0FFF].append((ts, typ, (h >> 12) & 3, p[4:4 + ln]))
    return t0, chunks


def att(path, handle, chunks):
    buf = bytearray()
    out = []
    for ts, typ, pb, frag in chunks:
        if (pb & 1) == 0:
            buf = bytearray(frag)
        else:
            buf += frag
        if len(buf) < 4:
            continue
        ln = struct.unpack_from("<H", buf, 0)[0]
        if len(buf) < 4 + ln:
            continue
        cid = struct.unpack_from("<H", buf, 2)[0]
        body = bytes(buf[4:4 + ln])
        buf = bytearray()
        if cid == 4 and body:
            out.append((ts, typ, body))
    return out


def analyze(path):
    t0, chunks = build(path)
    for handle in sorted(chunks):
        pdus = att(path, handle, chunks[handle])
        name, mtu, services, udp, ids = None, None, [], [], set()
        for ts, typ, b in pdus:
            op = b[0]
            if op == 0x03:
                mtu = struct.unpack_from("<H", b, 1)[0]
            if op == 0x09 and b[1] >= 7:
                h = struct.unpack_from("<H", b, 2)[0]
                if h == 0x0003:
                    name = b[4:].decode("utf-8", "replace")
            if op == 0x06 and len(b) >= 23:
                t = struct.unpack_from("<H", b, 5)[0]
                v = b[7:]
                if t == 0x2800 and len(v) == 16:
                    services.append(sq(v))
            if op in ATW:
                pl = b[3:]
                i = pl.find(b"\x45")
                if i >= 0 and len(pl) >= i + 28:
                    v = pl[i:]
                    ihl = (v[0] & 0xF) * 4
                    if v[9] == 17 and len(v) >= ihl + 8:
                        sp, dp = struct.unpack_from(">HH", v, ihl)
                        udp.append((ts, typ, v[12:16], v[16:20], sp, dp, v[ihl + 8:]))
                        body = v[ihl + 8:]
                        for tok in (b"MD-", b"BOOTSTRAP"):
                            if tok in body:
                                j = body.find(tok)
                                ids.add(body[j:j + 20].decode("latin1"))
        if not udp:
            continue
        span = udp[-1][0] - udp[0][0]
        print("=== handle 0x%03X  name=%r  mtu=%s  udp=%d pkts over %.0fs ===" %
              (handle, name, mtu, len(udp), span))
        if services:
            print("   services searched by the peer:", ", ".join(sorted(set(services))))
        types = collections.Counter(DTLS_NAMES.get(p[6][0], p[6][0]) for p in udp)
        print("   dtls records:", dict(types))
        if ids:
            print("   psk identities:", sorted(ids))
        for p in udp[:3]:
            print("   %s:%d -> %s:%d  %s" % (".".join(map(str, p[2])), p[4],
                                             ".".join(map(str, p[3])), p[5], p[6][:10].hex()))
        buck = collections.Counter()
        for ts, typ, *_ in udp:
            if _[-1][:1] == b"\x17":
                buck[(int(ts - t0) // 5 * 5, "ph" if typ == 0x02 else "trk")] += 1
        if buck:
            print("   app-data 5 s buckets: " + " ".join(
                "%ds/%s:%d" % (k[0], k[1], v) for k, v in sorted(buck.items())))
        print()


ATW = {0x1B, 0x52, 0x12}

if __name__ == "__main__":
    analyze(sys.argv[1] if len(sys.argv) > 1 else "fitbit-ios.pklg")
