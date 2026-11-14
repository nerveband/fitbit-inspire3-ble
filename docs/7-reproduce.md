# 7. Reproduce it yourself

Only on hardware you own. Every step below was run on a tracker and a phone belonging to
the author.

## What you need

| Item | Notes |
|---|---|
| The tracker | tested on an Inspire 3, firmware `63.<version>` |
| A phone with the Google Health app | Android is easier to capture from |
| A Mac | for the Mac side steps, macOS with Xcode command line tools |
| Optional: rooted Android phone | only for the key step, and only your own phone |

## Step 1: capture the phone side

Android, no root needed:

1. Turn on Developer options, then turn on "Enable Bluetooth HCI snoop log".
2. Toggle Bluetooth off and on so logging starts.
3. Open the app, pull to refresh, wait for a sync.
4. Start a workout that records heart rate, run it two minutes, stop, sync again.
5. Run `adb bugreport bugreport.zip` and send the file to your computer.

The log is inside the zip under `FS/data/misc/bluetooth/logs/`.

iPhone: install Apple's Bluetooth logging profile, then use PacketLogger from
Additional Tools for Xcode. Save as `.pklg`.

## Step 2: decode it

```
python3 tools/decode_sessions.py capture.pklg
```

You get a per connection report: peer name, MTU, the number of DTLS records, the identity
string in cleartext, and a five second histogram of application records. The steady 5 per
5 seconds is the once per second poll.

If you also want the GATT table from the phone's point of view:

```
python3 tools/analyze_capture.py capture.pklg
```

## Step 3: talk to the tracker from a Mac

Switch the phone's Bluetooth off first. The tracker only advertises when nothing holds
it.

```
swiftc -O tools/blescan.swift -o blescan && ./blescan 15      # just look around
swiftc -O tools/bleenum.swift -o bleenum && ./bleenum inspire 20   # services and reads
swiftc -O tools/blegatt.swift -o blegatt && ./blegatt inspire 20 15 # reset poke
```

Expect: identity reads succeed, the GattLink reset is accepted, and nothing comes back.
If you see notifications, you have found something new, and it would be very interesting.

## Step 4: the key, only on your own device

Needs a rooted Android phone with the app signed in and the tracker paired.

```
python3 tools/extract_mobile_data_key.py
```

It reads the app's key store file, builds the password from the phone id, the app
instance id and the user number, opens the store, and prints the key for each entry.

Then you have what you need to build a client that decrypts the link. This repo does not
include that client.

## Step 5: confirm the stack from the app code

Decompile the app and look for these strings. They are what the notes in this repo are
based on.

| Look for | Where |
|---|---|
| `MobileDataTlsKeyResolver` | shows the identity format and the key provider |
| `LiveDataCommandsHandler` | shows the 1000 millisecond poll and the resource name |
| `/sync/dump`, `/sync/response` | shows the megadump resources |
| `pbz`, `xjl` | shows the key store file and its password recipe |

## Reading order if you are new

1. `docs/1-the-short-version.md`
2. `docs/2-how-the-link-works.md`
3. `docs/3-gatt-map.md`
4. Then whatever you need.

## House rules

Test on your own hardware. Do not run the key extraction against a phone or account that
is not yours. Do not publish other people's device identifiers. If you find something
new, open an issue with the bytes redacted.
