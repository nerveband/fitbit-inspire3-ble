# 10. Prior art: what other people already solved

Checked in November 2026. This page lists public work that bears on the questions in this
repo, and what each one settles. Licence and quality vary. Read the code before trusting it.

## The one that matters: airLocal

[Hasaber8/airLocal](https://github.com/Hasaber8/airLocal), Python plus C, last push
2026-10-05.

A macOS CoreBluetooth reader for a Fitbit Air that needs no phone, no Frida and no Android
at runtime. It builds the archived Golden Gate stack at commit `b8a6f255`, applies a
CoreBluetooth patch, and compiles a native client plus a local dashboard.

What it settles, all matching what this repo measured independently:

| Claim | Their result | Ours |
|---|---|---|
| Mac can be a Golden Gate hub | yes, verified | yes, measured 2026-11 |
| ATT MTU | 247, so 244 bytes of payload | 247 and 244 |
| Identity format | `MD-<8 hex key id>-<8 hex expiry>` | same |
| Key resolution | by key id only, expiry suffix ignored | same code path |
| Cipher | `TLS_PSK_WITH_AES_128_CCM` | same |
| Stack descriptor | `DSNG`: DTLS, UDP socket, network interface, Gattlink | implied by the capture |
| Data resources | `GET /liveactivity`, megadump, `/sync/status` | same |

It also documents the laptop bonding order that this repo did not have:

1. Authenticate DTLS with the provisioned key
2. `PUT /bond/control` with body `08 78`, opening a 120 second bonding window
3. Read the secure characteristic, and let macOS ask the user to confirm
4. Verify link encryption through the Link Status value, flag bit 1
5. Save the binding only after both checks pass

Doing step 3 before step 2 gave them an SMP timeout and `CBATTErrorDomain` code 5. That is a
cheap mistake to avoid.

Small discrepancy: their docs call `ABBAFD03` a secure status characteristic and also cite
`ABBAFD02` as Link Status with flag bit 1. On our device all three values read with no bond,
so treat the exact role as unconfirmed.

How they get the key: a rooted Android phone with root `adbd`, the Fitbit app paired and
synced once, and Frida reading the app's key store **through the app's own provider** instead
of decrypting the file. Their hook names are from Fitbit 5.09. In 5.12.1 the same cells are
`pbz` and `xjl`, as recorded in [5-keys.md](5-keys.md) and [8-app-internals.md](8-app-internals.md).

What they still cannot do, which is the same list as ours: provision a key without Google's
backend, and decode the historical dump envelope.

## The bootstrap session, and its limit

Two projects talk to a production Fitbit Air using the **public bootstrap key** from the open
source repo, with no root and no OAuth:

| Repo | What it does |
|---|---|
| [paceaitian/fitbit-air-notification-bridge](https://github.com/paceaitian/fitbit-air-notification-bridge) | `PUT /settings` and `POST /settings` to toggle haptic intensity |
| [ThoreKoritzius/fitbit-air](https://github.com/ThoreKoritzius/fitbit-air) | Flutter plugin, ships prebuilt `libgg.so` and `libxp.so`, haptics verified on a Pixel 7 Pro |

And the limit, from the second project's README:

> the Air rejects it with CoAP `4.01` in the bootstrap session available to this plugin

where "it" is `GET liveactivity`. So bootstrap access is real, and it does not reach health
data. Anyone hoping to skip the per device key with the bootstrap credential now has an
answer with evidence.

One more useful line from the same project: the tracker accepts **only one** Golden Gate
owner at a time. A second connection starves the app, and vice versa.

## Heart rate, settled

The Fitbit Air exposes the standard Bluetooth Heart Rate Service `180D`, switched on in the
Google Health app under Connections, "Share heart rate", with an optional "Always visible".
Several projects read it at 1 Hz:

- `brainstormity/Fitbit-Air-OBS-Overlay`
- `taku0193/fitbit-air-heart-rate`
- `AyushSagar16/fitbit-air`

The Inspire 3 does not have this feature, which matches the GATT map in this repo: no
`180D` service, no standard heart rate characteristic.

Gadgetbridge supports **no** Fitbit model, old or new.

## The emulator route, technically possible

Google's own Bumble stack can pipe the Android emulator's Bluetooth through a real radio:

```
emulator ... -packet-streamer-endpoint   (controller mode, emulator 33.1.4.0+, API 34+)
bumble-hci-bridge usb:0
```

Needs a USB Bluetooth dongle on macOS, because the host OS locks the internal radio. Not
worth it now that the Mac radio drives the link directly.

A Flipper Zero is not a substitute: stock firmware is peripheral only, there is no USB to HCI
transport, and it cannot follow an established connection.

## The upstream is archived

`Google-Health-API/golden-gate` is archived, last push April 2024, 32 forks, 14 open issues.
Open issue #77 from 2023 asks how to sync a Fitbit from a Windows PC and never got an answer.
Pin a commit if you build it.

## Two useful data points from their work

| Item | Value |
|---|---|
| LiveActivity field 3 | distance in millimetres |
| Heart rate confidence | `0` invalid, `1` tentative, `2` good, `3` microstill |

## Summary table

| Question | Public status |
|---|---|
| macOS client reading live data | solved, airLocal |
| Bonding a second central | solved, airLocal |
| Key export from a rooted phone | solved, Frida on the app's own provider |
| Skip the key with bootstrap credentials | answered no, `4.01` on `liveactivity` |
| Live heart rate without the app | solved on the Air, impossible on the Inspire 3 |
| Provision a key without the backend | unsolved, in public and here |
| Decode the historical dump envelope | unsolved, in public and here |
| Inspire 3 specific work | none public, all of it is Air |
