# 6. Dead ends, and what each one proved

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

## 5. Full GATT probe from a Mac, first attempt

**Done.** Phone Bluetooth off, tracker advertising, Mac connected with CoreBluetooth, read
every readable characteristic, subscribed to the notify end of the pipe, wrote the GattLink
reset request `0x80`.

**Result.** Every identity read returned a value. Two status reads returned values. The
subscribe was accepted. The reset write was accepted with no error. Then: zero
notifications, no reset complete, no DTLS record.

**Proved at the time.** Read as a refusal. That reading was wrong, and the correction is
below. What it did prove is that the tracker's ATT MTU is 247 while the phone asks for 527.

## 5b. The same probe with the real stack, corrected

**Done.** Built the archived Golden Gate stack with the CoreBluetooth patch from
[Hasaber8/airLocal](https://github.com/Hasaber8/airLocal), then connected a Mac to the same
Inspire 3 with a deliberately wrong 16 byte key.

**Result, measured.** The connection came up, MTU 244 of payload, connection interval
30 ms. GattLink then ran both ways: the Mac sent a reset request, the tracker sent its own
reset request, the Mac sent a reset complete, and the tracker began sending IP packets
starting with `45` inside GattLink packet number 0, 129 bytes long. In order:

| Event | Measurement |
|---|---|
| ClientHello | 101 bytes, arrives as the first IP packet |
| Suite list | 8 bytes, 4 suites |
| Suite selection | the stack tries `0xc0a4` first and selects it |
| PSK identity | 20 bytes resolved from the ClientKeyExchange |
| Result with a wrong key | `mbedtls_cipher_auth_decrypt() returned -25344 (-0x6300)` |
| Error code meaning | `MBEDTLS_ERR_SSL_INVALID_MAC` |

**Proved.** The tracker is not closed to a laptop at all. It opens DTLS toward any central
that completes the GattLink handshake. The only thing missing is the 16 byte key, and the
failure with the wrong key is a MAC check, not a policy refusal.

The identity the tracker offered was the same key id and expiry as in the iOS capture, so
the credential is stable across phones, Macs and days.

## 6. A Flipper Zero as the radio

**Done.** Checked whether a Flipper Zero can stand in for a Bluetooth adapter, as a
central or as a USB HCI dongle.

**Result.** No on both counts. Stock firmware runs a peripheral only BLE stack on the
STM32WB55, so it advertises and can act as a keyboard, and cannot initiate connections.
Official firmware does not expose a USB to HCI transport, so a host computer cannot use it
as a dongle. It also cannot follow an established connection, so it is not a sniffer.

**Proved.** A Flipper is not useful for this work. It is also not needed: the Mac's own
radio drives the link fine, as 5b shows. The dongle recommendation was only ever for the
Android emulator route.

## 7. Ask the public API for the key

**Done.** Read both discovery documents for Google Health API v4.

**Result.** 27 methods. Two device methods. Both return metadata.

**Proved.** There is no endpoint to request, and no scope that would unlock one. Stop
suggesting it.

## 8. Use the old unauthenticated live data characteristic

**Done.** Checked the tracker for service `558dfa00` and the old live data
characteristic.

**Result.** Neither exists. The device has five services, listed in
[3-gatt-map.md](3-gatt-map.md).

**Proved.** Guides that describe a 16 byte live data frame apply to older Fitbits only.

## 9. Bootstrap credential against the Inspire 3

**Done.** Patched airLocal's key resolver so it answers the `BOOTSTRAP` identity with the
public key from the open source bindings, then connected a Mac to the Inspire 3.

**Result.** DTLS completed, and every data resource refused:

| Request | Response |
|---|---|
| `GET /liveactivity` | `4.01` |
| `GET /sync/status` | `4.01` |
| `GET /app/outbox` | `4.01` |
| `PUT /bond/control` | `4.01` |
| `GET /.well-known/core` | `4.04` |

**Proved.** The bootstrap credential is a real session, not a rejected one, and it authorizes
nothing that carries health data. This closes the last hope of skipping the per device key.

**New question it opens.** The tracker offered `BOOTSTRAP` in these runs and
`MD-<key id>-<expiry>` in earlier ones, on the same Mac. What decides that? A candidate is the
tracker's view of the peer, and a peer that fails a MAC check may be demoted to bootstrap. A
test would be: connect with the correct key once, then with a wrong key, and watch which
identity comes back each time.

## Summary

| Attempt | Time cost | Ceiling reached |
|---|---|---|
| Capture and decode | hours | plaintext is encrypted |
| Slice brute force | hours | key is not present |
| Rooted emulator | half a day | no radio, no peer |
| Radio bridge | an hour of reading | app must be rebuilt |
| Bare GATT probe | an hour | incomplete handshake, not a refusal |
| Full stack, wrong key | an hour | invalid MAC, key required |
| Full stack, public bootstrap key | an hour | session opens, every data resource returns `4.01` |
| Public API | minutes | no endpoint |
| Old stack path | minutes | not on this device |
| Flipper Zero as radio | minutes | peripheral only, no HCI |
| Rooted phone that pairs | a device | the only path with a working key |

## Two firmware notes worth keeping

**Firmware string.** `63.20001.220.31`, with `63` as the model prefix.

**Rotating serial.** Characteristic `2A25` changed value between connections. Anything
that depends on it as a stable id will break.
