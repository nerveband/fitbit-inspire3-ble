#!/usr/bin/env python3
"""Test candidate keys and modes against a Fitbit mobile data dump.

The dump format, measured: a 21 byte plaintext header, then a body whose length
is always a multiple of 16. This tool tries a candidate 16 byte key in several
modes and reports whether the plaintext looks structured. A real hit has to look
structured in every dump given, because a wrong key produces noise.

Usage:
  python3 try_dump_key.py dump1.bin [dump2.bin ...]
  python3 try_dump_key.py --key-file psk.bin dump1.bin
  python3 try_dump_key.py --key-hex 810654e336adcab0a03c60f74aa0b6fb dump1.bin
  python3 try_dump_key.py --null 500 dump1.bin      # false positive rate
"""
import argparse
import math
import os
import re
import struct
import sys

HEADER = 21

# Keys that are public, plus trivially derived values that people try.
def builtin_candidates():
    out = {}
    out["BOOTSTRAP"] = bytes.fromhex("810654e336adcab0a03c60f74aa0b6fb")
    out["hello"] = bytes(range(16))
    out["zeros"] = b"\x00" * 16
    out["ones"] = b"\xff" * 16
    for name, text in {
        "ascii-fitbit": b"fitbit",
        "ascii-mobiledata": b"MobileDataKey",
        "ascii-md-identity": b"MD-",
        "ascii-pairing": b"pairing",
    }.items():
        out[name] = (text * 16)[:16]
    return out


def entropy(data):
    if not data:
        return 0.0
    counts = {}
    for byte in data:
        counts[byte] = counts.get(byte, 0) + 1
    n = len(data)
    return -sum((v / n) * math.log2(v / n) for v in counts.values())


def looks_structured(data):
    """A cheap plausibility test for a decrypted block stream.

    Returns a score from 0 to 4. Real plaintext from a protobuf or TLV format
    scores high: a small set of distinct leading bytes, low entropy, a healthy
    share of printable or zero bytes, and repeated structure near the start.
    """
    if len(data) < 64:
        return 0, "short"
    head = data[:256]
    score = 0
    notes = []
    h = entropy(head)
    if h < 6.0:
        score += 1
        notes.append(f"head entropy {h:.1f}")
    printable = sum(1 for b in head if 0x20 <= b < 0x7F)
    zeros = head.count(0)
    if printable + zeros > len(head) * 0.6:
        score += 1
        notes.append(f"printable+zero {100 * (printable + zeros) // len(head)}%")
    # protobuf-like: first byte of many 16 byte blocks is a small tag
    starts = [data[i] for i in range(0, min(len(data), 4096) - 1, 16)]
    small = sum(1 for b in starts if b < 0x30)
    if small > len(starts) * 0.75:
        score += 1
        notes.append(f"{small}/{len(starts)} block starts under 0x30")
    # repeated byte pairs, which ciphertext never has
    pairs = {}
    for i in range(0, min(len(data), 8192) - 1, 2):
        key = data[i:i + 2]
        pairs[key] = pairs.get(key, 0) + 1
    repeats = sum(1 for v in pairs.values() if v > 2)
    if repeats > 5:
        score += 1
        notes.append(f"{repeats} repeated pairs")
    return score, ", ".join(notes) or "noise"


def decrypt(key, body, mode):
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    except ImportError:
        sys.exit("needs the cryptography package: pip install cryptography")
    if len(body) < 32 or len(body) % 16:
        return None
    if mode == "cbc-iv-first":
        iv, ct = body[:16], body[16:]
        dec = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
        return dec.update(ct) + dec.finalize()
    if mode == "ecb":
        dec = Cipher(algorithms.AES(key), modes.ECB()).decryptor()
        return dec.update(body) + dec.finalize()
    if mode == "cbc-zero-iv":
        dec = Cipher(algorithms.AES(key), modes.CBC(b"\x00" * 16)).decryptor()
        return dec.update(body) + dec.finalize()
    if mode == "ctr-zero":
        dec = Cipher(algorithms.AES(key), modes.CTR(b"\x00" * 16)).decryptor()
        return dec.update(body) + dec.finalize()
    raise SystemExit("unknown mode " + mode)


MODES = ("cbc-iv-first", "ecb", "cbc-zero-iv", "ctr-zero")


def split_bodies(path):
    data = open(path, "rb").read()
    if len(data) < HEADER + 16:
        return []
    return [data[HEADER:]]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("dumps", nargs="+")
    parser.add_argument("--key-file")
    parser.add_argument("--key-hex")
    parser.add_argument("--null", type=int, default=0, help="try N random keys to measure false positives")
    args = parser.parse_args()

    bodies = []
    for path in args.dumps:
        bodies.extend(split_bodies(path))
    if not bodies:
        sys.exit("no usable bodies")

    candidates = {}
    if args.key_hex:
        candidates["given"] = bytes.fromhex(args.key_hex)
    if args.key_file:
        candidates[os.path.basename(args.key_file)] = open(args.key_file, "rb").read()
    if not candidates and not args.null:
        candidates = builtin_candidates()

    if args.null:
        candidates = {f"random-{i}": os.urandom(16) for i in range(args.null)}

    best = None
    hits = []
    for name, key in candidates.items():
        if len(key) != 16:
            print(f"skip {name}: {len(key)} bytes")
            continue
        for mode in MODES:
            scores = []
            notes = []
            for body in bodies:
                plain = decrypt(key, body, mode)
                if plain is None:
                    continue
                score, note = looks_structured(plain)
                scores.append(score)
                notes.append(note)
            if not scores:
                continue
            worst = min(scores)
            if worst >= 3:
                hits.append((name, mode, scores, notes[0]))
            if best is None or worst > best[2]:
                best = (name, mode, worst, notes[0])

    print(f"bodies: {len(bodies)}  candidates: {len(candidates)}  modes: {len(MODES)}")
    if best:
        print(f"best: {best[0]} / {best[1]} worst-score {best[2]}  ({best[3]})")
    if hits:
        print("HITS:")
        for hit in hits:
            print("  ", hit)
    else:
        print("no candidate scored 3 or more on every body")

    if args.null:
        rate = len(hits) / max(1, len(candidates) * len(MODES))
        print(f"false positive rate at this size: {100 * rate:.2f}% of trials")


if __name__ == "__main__":
    main()
