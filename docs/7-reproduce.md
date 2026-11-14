# 7. Reproduce every measurement

Run this only on hardware you own. Every step was run on the author's own tracker, phone
and Mac.

## Tools you need

| Tool | For |
|---|---|
| Xcode command line tools | compiling the Swift probes on macOS |
| Python 3 | the capture parsers |
| `adb` | Android capture |
| PacketLogger from Additional Tools for Xcode | iOS capture |
| jadx | reading the app code |

## Step 1: capture the traffic

### Android, no root

```
adb shell settings put secure bluetooth_btsnoop_default_mode full
adb shell svc bluetooth disable && adb shell svc bluetooth enable
# open the app, pull to refresh, sync, run a workout for two minutes, sync again
adb bugreport bugreport.zip
unzip -l bugreport.zip | grep -i btsnoop
```

The log is at `FS/data/misc/bluetooth/logs/` inside the zip. The first two commands write
the snoop setting and restart the radio so logging begins.

### iPhone

Install Apple's Bluetooth logging profile, then use PacketLogger from Additional Tools for
Xcode. Save as `.pklg`.

## Step 2: decode it

```
python3 tools/decode_sessions.py capture.pklg
python3 tools/analyze_capture.py capture.pklg
```

`decode_sessions.py` needs `parse_pklg.py` in the same directory. It prints, per connection:
MTU negotiation, UDP endpoints, a DTLS record census, the clear text key identity, and a
five second histogram of application records.

Expected output shape:

```
handle 0x0058 udp=596 up=293 down=293 sizes=[(215, 190), (58, 95), ...]
MTU: request 527 from phone, response 247 from tracker
DTLS: ClientHello suites=0xc0a4 0x00a8 0xc037 0x00ff, ServerHello picked 0xc0a4
identity: MD-<keyid>-<expiry>
```

If your tool prints handles instead of UUIDs, fix that first. Handles change per
connection.

## Step 3: probe the tracker from a Mac

Turn the phone's Bluetooth off first, or the tracker will not advertise.

```
swiftc -O tools/blescan.swift -o blescan && ./blescan 15
swiftc -O tools/bleenum.swift -o bleenum && ./bleenum Inspire 20
swiftc -O tools/blegatt.swift -o blegatt && ./blegatt Inspire 20 15
```

| Tool | What it does |
|---|---|
| `blescan` | lists advertisers, names, RSSI, advertised services |
| `bleenum` | connects, lists services and characteristics, reads every readable value |
| `blegatt` | same, then subscribes to `ABBAFF02` and writes the GattLink reset |

Expected with an unbonded Mac: identity values returned, reset write accepted, nothing
sent back. If a notification ever arrives, something new has been found.

## Step 4: read the key, own device only

Needs a rooted Android phone with the app signed in and the tracker paired at least once.

```
python3 tools/extract_mobile_data_key.py
```

The script reads `MobileDataKeyManagerKeyStore.keystore` from the app's private directory
through `adb`, builds the password from `android_id`, the mobile data instance id and the
uid, opens the BKS store, and prints each entry alias with its key length.

Needs `pyjks`. Without root the file cannot be read at all, so the script fails at the
first step, which is the intended behaviour.

## Step 5: check a claim against the app code

```
jadx -d jadx_out app.apk
grep -rn "liveactivity" jadx_out/sources
grep -rn "MobileDataKeyManagerKeyStore" jadx_out/sources
grep -rn "interval(1000L" jadx_out/sources
```

| Claim | Find it at |
|---|---|
| poll interval is 1000 ms | `LiveDataCommandsHandler.java:169` |
| poll resource is `liveactivity`, GET, no resend | `LiveDataCommandsHandler.java:109` |
| key store is BKS, file name and password recipe | `xjl.java:93` |
| entry alias is the decimal key id | `pbz.java:54` |
| cipher suites default list | `DtlsOptions.swift` in the GoldenGate repo |

## Step 6: check the public API claim

```
curl -s "https://health.googleapis.com/\$discovery/rest?version=v4" | python3 -m json.tool | less
```

Look at `resources.users.resources.pairedDevices`. Two methods, both metadata. No key. Do
this once and the question is closed.

## Step 7: test a candidate envelope key

Once you hold a key that might open the stored dump:

```
python3 tools/try_dump_key.py capture1.bin capture2.bin --key-hex <32 hex chars>
python3 tools/try_dump_key.py capture1.bin capture2.bin --key-file psk.bin
python3 tools/try_dump_key.py --null 300 capture1.bin     # false positive rate
```

It needs the `cryptography` package. It reports the best scoring candidate and mode, and it
requires a hit to look structured in every capture, which is what stops a lucky first block from
being read as a success. With no key given it tries the public keys as a control.

## House rules

Test on your own hardware. Do not run the extractor against a phone or an account that is
not yours. Do not publish device identifiers, key ids, or captures. If you find something
new, open an issue with the bytes redacted.
