# 6. Seven dead ends, and what each one proved

Failed attempts are evidence. Each entry states what was done, what came back, and what
that rules out.

## 1. Decode the pairing capture and look for the key

**Done.** Recorded a full pairing between an iPhone and the tracker, 16.7 minutes, 4.7 MB.
Reassembled GattLink, extracted the IPv4 and UDP layers, and listed every DTLS record.

**Result.** Three DTLS sessions on the busiest connection. Every session: one ClientHello
of 101 bytes, one ServerHello of 131 bytes picking `0xC0A4`, one ClientKeyExchange of 122
bytes with the 20 byte identity, one change cipher spec, then application data. The
identity `MD-<keyid>-<expiry>` appears in clear. The key does not appear anywhere, in any
session, in either direction.

**Proved.** The transport is fully visible. The plaintext is not.

## 2. Try every 16 byte slice of the bootstrap session

**Done.** The bootstrap session uses a public key, so it decrypts. A 16 byte window slid
across all of it, 2,861 candidates, and each candidate was tried as the data session key.

**Result.** Zero matches.

**Proved.** The key is not a copy, a shift, or a reordering of anything in the handshake.
It arrives from outside the radio link.

## 3. Rooted Android emulator running the real app

**Done.** Installed Google Health 5.12.1 on an API 35 emulator, rooted with `adb root`,
signed in, opened the device list.

**Result.** The app worked. The account synced. The tracker appeared with its battery
level, its wire id, and `supportsMobileData = 1`. The keystore file never appeared, and the
log stopped at `BluetoothAdapter: isLeEnabled(): ON`. The emulated radio reported itself
as `XX:XX:XX:XX:BB:BB` and had no peer to connect to.

**Proved.** Root is necessary but not sufficient. The app only provisions the key store
after a real Bluetooth session with a real tracker.

## 4. Bridge a real radio into the emulator

**Done.** Read the source of a community project that adds Bluetooth to the Android
emulator.

**Result.** It is not a transparent radio bridge. It gives the target app a library to
call, and the app must be rebuilt against it. The Google Health app is closed source.

**Proved.** There is no emulator path for a closed source app on macOS. Rule this out fast
in future.

## 5. Full GATT probe from a Mac

**Done.** Phone Bluetooth off, tracker advertising, Mac connected with CoreBluetooth, read
every readable characteristic, subscribed to the notify end of the pipe, wrote the GattLink
reset request.

**Result.** Every identity read returned a value. Two status reads returned values. The
subscribe was accepted. The reset write was accepted with no error. Then: zero
notifications, no reset complete, no DTLS record.

**Proved.** The tracker is bonded to one phone and ignores everyone else at the data
layer, without even an error. Also proved the tracker's ATT MTU is 247 while the phone asks
for 527.

## 6. Ask the public API for the key

**Done.** Read both discovery documents for Google Health API v4.

**Result.** 27 methods. Two device methods. Both return metadata.

**Proved.** There is no endpoint to request, and no scope that would unlock one. Stop
suggesting it.

## 7. Use the old unauthenticated live data characteristic

**Done.** Checked the tracker for service `558dfa00` and the old live data
characteristic.

**Result.** Neither exists. The device has five services, listed in
[3-gatt-map.md](3-gatt-map.md).

**Proved.** Guides that describe a 16 byte live data frame apply to older Fitbits only.

## Summary

| Attempt | Time cost | Ceiling reached |
|---|---|---|
| Capture and decode | hours | plaintext is encrypted |
| Slice brute force | hours | key is not present |
| Rooted emulator | half a day | no radio, no peer |
| Radio bridge | an hour of reading | app must be rebuilt |
| Mac central | an hour | bond required, and cannot be forced |
| Public API | minutes | no endpoint |
| Old stack path | minutes | not on this device |
| Rooted phone that pairs | a device | the only path with a working key |

## Two firmware notes worth keeping

**Firmware string.** `63.20001.220.31`, with `63` as the model prefix.

**Rotating serial.** Characteristic `2A25` changed value between connections. Anything
that depends on it as a stable id will break.
