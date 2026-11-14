#!/usr/bin/env python3
"""Extract the per-device GoldenGate mobile-data key from a rooted Android install.

The Google Health app keeps the AES keys in a plain BKS keystore in its private data
directory. The store passphrase is derived in the app as:

    android_id + mobileDataInstanceId + uid

  defpackage/xjl.java:92-96 (BKS, MobileDataKeyManagerKeyStore.keystore, passphrase)
  defpackage/pbz.java:54    (entry name is the key id as a decimal string)

Usage:
  python3 extract_mobile_data_key.py [--serial emulator-5554]
Requires: adb, a rooted or userdebug device, and pyjks >= 20 for BKS support.
"""
import argparse
import os
import re
import subprocess
import sys

PKG = "com.fitbit.FitbitMobile"
STORE = "MobileDataKeyManagerKeyStore.keystore"


def adb(serial, *args, binary=False):
    cmd = ["adb"] + (["-s", serial] if serial else []) + list(args)
    out = subprocess.run(cmd, capture_output=True, check=False)
    if out.returncode != 0:
        raise RuntimeError("%s failed: %s" % (" ".join(cmd), out.stderr.decode()[:300]))
    return out.stdout if binary else out.stdout.decode("utf-8", "replace")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--serial", default=None)
    ap.add_argument("--workdir", default=os.path.expanduser("~/fitbit-inspire3-re/keys"))
    args = ap.parse_args()
    s = args.serial
    os.makedirs(args.workdir, exist_ok=True)

    who = adb(s, "shell", "id").strip()
    if "uid=0" not in who:
        sys.exit("not root on device: %s" % who)

    data = adb(s, "shell", "find", "/data/data/%s" % PKG, "-name", STORE, "-o", "-name", "*.keystore")
    path = None
    for line in data.splitlines():
        if STORE in line:
            path = line.strip()
    if not path:
        sys.exit("no %s under /data/data/%s yet; has the app signed in and paired?" % (STORE, PKG))
    print("keystore:", path)

    raw = adb(s, "exec-out", "cat", path, binary=True)
    store_path = os.path.join(args.workdir, STORE)
    open(store_path, "wb").write(raw)
    print("saved:", store_path, len(raw), "bytes")

    android_id = adb(s, "shell", "settings", "get", "secure", "android_id").strip()
    prefs = adb(s, "shell", "grep", "-rho", "mobileDataInstanceId[^<]*<[^<]*", "/data/data/%s/shared_prefs/" % PKG)
    instance = None
    m = re.search(r">([^<]+)<", prefs or "")
    if m:
        instance = m.group(1)
    if instance is None:
        instance = adb(s, "shell", "cat", "/data/data/%s/shared_prefs/" % PKG + "*", ).strip()
    uid = adb(s, "shell", "stat", "-c", "%u", "/data/data/%s" % PKG).strip()
    print("android_id:", android_id)
    print("mobileDataInstanceId:", instance)
    print("uid:", uid)
    if not android_id or not instance:
        sys.exit("missing passphrase inputs")

    passphrase = android_id + instance + uid
    print("passphrase length:", len(passphrase))

    try:
        import jks
    except ImportError:
        sys.exit("pip install pyjks (>=20) for BKS support")
    ks = jks.bks.BksKeyStore.load(store_path, passphrase)
    print("aliases:", [e.alias for e in ks.entries])
    for e in ks.entries:
        if isinstance(e, jks.bks.BksSecretKeyEntry):
            print("alias %s -> %s %d bytes" % (e.alias, type(e.key).__name__, len(e.key)))
            print("   hex:", e.key.hex())


if __name__ == "__main__":
    main()
