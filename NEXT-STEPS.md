# Next steps

State of the work, the open threads, and the exact commands to resume each one. Written so that a
future session, human or agent, can pick this up cold.

Last confirmed state, November 2026. Repo `nerveband/fitbit-inspire3-ble`, branch `main`.

## Where things stand

| Area | State |
|---|---|
| Protocol | mapped. Layers, parameters, packet layouts, `docs/2` to `docs/4` |
| GATT | fully enumerated, `docs/3` |
| Live data cadence | proven at 1 Hz by capture and by code, `docs/1` |
| Bootstrap session | measured, full namespace mapped, `docs/12` |
| Stored archive | pullable with no key, encrypted, `docs/12` and `docs/11` |
| Key extraction | blocked on one rooted Android, `docs/5`, `docs/14` |
| Apps, firmware | closed, `docs/13` |
| Health Connect | measured, not yet harvested, `docs/15` |

One sentence: everything is documented and reproducible except the 16 bytes that open the live
session.

## Thread 1: get the key (the one that unblocks everything)

**Prerequisite.** An Android phone whose bootloader unlocks, with the tracker paired once in the
Google Health app. The A15 is locked and cannot be used.

**Check a candidate device first.**

```
adb shell getprop ro.boot.flash.locked        # 0 is good, 1 is locked
adb shell getprop ro.oem_unlock_supported     # 1 means OEM unlocking can be enabled
adb shell getprop ro.boot.vbmeta.device_state # unlocked is good
```

Model note: `SM-G950F` and `SM-G950FD` unlock. `SM-G950U`, `G950U1` and `G950W` do not. A used
Pixel 6a is the known good path and costs about a hundred dollars.

**Then, in order.**

1. Install Google Health, sign in, pair the Inspire 3, let one sync finish.
2. Choose one of two routes to the 16 bytes.
   - Read the key through the app's own API with Frida. This is what airLocal documents, and it
     avoids the store password entirely. Hook names differ per version: 5.09 uses `qqh.b(long)`
     and `qaa`, 5.12.1 uses the resolver in `com.fitbit.goldengate.dtls` and `pbz`.
   - Or pull the store file and open it offline: `files/MobileDataKeyManagerKeyStore.keystore`,
     type BKS, alias is the decimal key id, password is `android_id` plus the mobile data instance
     id plus the uid. Script ready: `tools/extract_mobile_data_key.py`.
3. Verify, do not assume. On the Mac:

```
cd ~/fitbit-airlocal
./standalone/build/fitbit-air-reader.app/Contents/MacOS/fitbit-air-reader pair \
  --device <UUID from scan> --key-file <16 bytes> --key-id <8 hex> --output /tmp/binding.json
```

Success looks like `DTLS session established`, the bonding window accepted, and a saved binding.
Then:

```
./standalone/build/fitbit-air-reader.app/Contents/MacOS/fitbit-air-reader read \
  --device paired:<UUID> --key-file <key> --key-id <8 hex> --output /tmp/live.bin --type live
```

A `2.05` with a 24 byte protobuf is the end of this thread.

**Kill criterion.** If a candidate phone is locked, stop and pick another. Do not spend time on
kernel exploitation for a phone when a hundred dollar phone exists.

## Thread 2: the archive plaintext

**Prerequisite.** Thread 1, because a bonded session may open more resources, and because the
search space is the app's key store.

**Then.**

1. Dump **every** entry in the store, not just the id the tracker announces.
2. Test each against a captured archive:

```
python3 tools/try_dump_key.py local/dump.raw local/dump2.raw local/back.raw --key-file candidate.bin
```

3. If no entry works, take the other route: hook the app during a real sync and catch the decoded
backend reply that lands in `cache/sync-*.bin`.

**Kill criterion.** If the store holds one key, and no candidate scores a hit, the plaintext needs
the backend, and the value of continuing is low.

## Thread 3: firmware study

**Prerequisite.** Thread 1, because the image comes from an app-authenticated cloud call.

```
POST devices/client/tracker/data/<productId>/firmware?optimize=BLE
```

with the tracker's firmware report encoded `base64` or `hex`. The reply carries `targetVersions`
and `images`, each with `deviceMode` and image data. See `docs/13`.

**Then.** Read the container: header, chunk sizes, checksum and version fields, and whether the
image is signed, encrypted, or both. That single artefact converts `docs/13` from estimate to plan.

**Do not** flash anything to your only tracker.

## Thread 4: Health Connect reader

**Prerequisite.** None. This is the rootless, keyless, data-only path, measured in `docs/15`.

1. On the phone, open Health Connect, Data and access, and note whether **Health** appears and for
   which record types.
2. Run Health Connect's export and inspect the zip. If the granularity is useful, build a reader
   app with `androidx.health.connect:connect-client`, `health.READ_*` permissions, and a rationale
   activity, and poll `getChanges` into JSONL.
3. Compare a day of that against the same day in the Google Health app, to confirm it is the same
   underlying data and to measure the lag.

**Payoff.** Steps and heart rate at the writing app's cadence, with no root and no key. Not 1 Hz.

## What to build once the key lands

A local hub on the Mac, one program:

| Piece | Detail |
|---|---|
| bond and reconnect | CoreBluetooth plus Golden Gate, using the airLocal reader as the transport |
| poll | `GET /liveactivity` at 1 Hz, the app's own rate |
| store | SQLite plus a JSONL append log |
| serve | localhost HTTP and WebSocket for an overlay |
| extras | `POST /app/inbox` for notification payloads, `GET /sb/records` for sensor blobs |

The CoAP surface to drive it is listed in `docs/12`.

## Environment, so you can resume

| Thing | Where |
|---|---|
| this repo | `~/fitbit-inspire3-re`, published as `nerveband/fitbit-inspire3-ble` |
| reader with our local patches | `~/fitbit-airlocal`, built at `standalone/build/fitbit-air-reader.app` |
| our reader diff | `local/airlocal-bootstrap-sweep.patch`, unversioned and not published, because airLocal ships no licence |
| captured dumps and logs | `local/`, unversioned |
| golden gate checkout | `~/fitbit-airlocal/golden-gate` at pinned commit `b8a6f255` |
| decompiled apps | `~/Desktop/apks/v4.44.2` and `~/Desktop/apks/v5.12.1` |
| iOS capture | `~/fitbit-inspire3-re/fitbit-ios.pklg`, unversioned |
| test phone | Galaxy A15, `R5CX617QAJL`, Android 17, locked bootloader |

Rebuild after editing the reader:

```
cd ~/fitbit-airlocal
uv tool run --from cmake==3.31.6 cmake --build standalone/build --target fitbit-air-reader --parallel 6
```

## Gotchas that cost time

1. The tracker **stops advertising** after roughly fifteen to twenty connect and abort cycles. A tap
   or a movement brings it back. Batch work into one session, which is why the sweep mode exists.
2. The macOS UUID **rotates**. Re-scan before every session, never cache the old id.
3. The advertised marker rotates too, and the advertised name is not an identity.
4. The tracker chooses its **PSK identity** per peer state, and both `BOOTSTRAP` and
   `MD-<id>-<expiry>` were seen in the same hour. A `BOOTSTRAP` session authorizes almost nothing.
5. The reader **segfaults on exit**. Harmless, output is complete, exit code 139.
6. Pushing to GitHub needs the credential helper, because the SSH agent is unavailable:

```
git -c credential.helper='!gh auth git-credential' push https://github.com/nerveband/fitbit-inspire3-ble.git main
```

7. Only one Golden Gate owner at a time. The app and a Mac cannot both hold the tracker.

## Definition of done

| Goal | Done when |
|---|---|
| live local data | Mac bonds, `read --type live` returns `2.05`, `watch` records twelve samples |
| archive plaintext | a key candidate scores a hit in `try_dump_key.py`, or the backend hook yields records |
| firmware study | one image on disk, container documented in `docs/13` |
| Health Connect | a day of records exported and compared |
