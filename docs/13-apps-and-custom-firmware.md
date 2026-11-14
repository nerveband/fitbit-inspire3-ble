# 13. Apps, clock faces, and custom firmware

Short answer: no. Not on an Inspire 3, and not on any Fitbit after November 2026, because Google
is closing the app platform itself.

## The device

The Inspire 3 is a tracker with fixed firmware. It has no app store, no app runtime, and no
support for third-party clock faces. The face you see is one of the ones Fitbit ships, and the
Google Health app can switch between them.

Compare the two families:

| Family | Apps | Clock faces | Notes |
|---|---|---|---|
| Inspire 3, Charge, Luxe, Ace | no | official only | fixed firmware |
| Versa, Versa Lite, Versa 2, Versa 3, Ionic, Sense | yes, until late 2026 | yes, until late 2026 | Fitbit OS, JavaScript apps |
| Versa 4, Sense 2 | never | until late 2026 | removed third-party apps at launch in 2022 |
| Fitbit Air | no | no | screenless, data over the Google Health API |

## The platform is being switched off anyway

| Date | Change |
|---|---|
| November 28, 2026 | the App Gallery keeps only apps and clock faces made by Fitbit and Google |
| November 28, 2026 | Gallery Admin tools retired, so no new uploads and no updates to existing items |
| already closed | the Fitbit SDK developer forum is locked |

Apps already installed keep running, but anything removed or wiped by a factory reset cannot be
downloaded again. So even someone holding a Versa or Sense has weeks, not years, to develop for
it.

## Sideloading

There is one community path, and it needs a device that already runs the app engine:

- `cmengler/fitbit-app-versa4` describes an unofficial way to push an app onto a Versa 4 or
  Sense 2, using debug flags such as `FITBIT_QA_COMMANDS`.

That is not a way in for an Inspire 3. The tracker has no JavaScript runtime to run an app, so
there is nothing to sideload into.

## Custom firmware

None exists for modern Fitbit hardware. Images are signed and the boot chain verifies them, so a
modified image is rejected before it runs.

The only public custom firmware work is from 2018, on hardware made before October 2017. The
Seemoo lab and the Nexmon project reverse engineered the Fitbit Flex and Charge HR and flashed
their own firmware over the air, using a fault injection trick to get in. Every device since then
closes that door.

## The update path, as it exists in the app

Studied in the decompiled 5.12.1 app. Firmware is not a special channel. It is a file, and files
travel over the same mobile data plumbing as everything else.

| Piece | Evidence |
|---|---|
| check call | `POST devices/client/tracker/data/<productId>/firmware` with `?optimize=BLE`, body encoded `base64` or `hex` |
| response | `targetVersions` and `images`, each image carrying a `deviceMode` and image data |
| file objects | `com.fitbit.fbcomms.fwup.FirmwareImageFileInfo`, with total bytes and progress |
| transfer | `FileTransferReadFilePayload` over the mobile data file transfer, which is the `app/inbox` resource |
| inbox resources | `CoapFileInboxResource` and `CoapFileOutboxResource`, with metadata: action, version, checksum, file-metadata |
| app-side verification | none found. The only `SHA256withRSA` in the app is `nct`, a JWT check for something else |

So the app is a courier. It asks the cloud which image belongs on this tracker, receives it, and
pushes it into the tracker's file inbox with a version and a checksum. It never checks a
signature itself, which means the trust decision happens on the tracker.

## The two gates, precisely

These are the different mechanisms, and they are unrelated:

| Gate | What it proves | Key | Who holds it | Can a session key change it |
|---|---|---|---|---|
| DTLS with the mobile data PSK | this hub may talk to this tracker | 16 byte symmetric key, per device | the phone, in a plain file | no |
| Firmware acceptance | this image came from Google | asymmetric signature over the image | Google signs, the tracker verifies | no |

The first is authentication of a session. The second is integrity of code. A session key says
nothing about code signing, and the signing key never touches the phone. Even a perfect DTLS
client can push a file into `app/inbox` and have it rejected as an image.

## What it would take, honestly

Five tiers, cheapest first. Only the first is achievable in an evening.

**Tier 0, drive the device from a computer.** Needs the mobile data key. Effort: days. Payoff:
live data, notifications, sensor blobs, bonding. No code on the tracker.

**Tier 1, get one firmware image and read the format.** Needs the app signed in on an
instrumented phone so the cloud will hand out the image, or a public mirror if one exists. Effort:
hours once a phone is available. Payoff: container layout, chunking, checksum and version fields,
and the first real answer on whether images are encrypted or only signed.

**Tier 2, push a modified image and read the rejection.** Needs tier 0 plus tier 1. Effort: a day.
Payoff: the tracker's own error message tells you which check failed. That is the cheapest way to
learn whether the verifier is strong or lazy. Real risk: a bad flash can brick the tracker, so this
wants a second device and a version that can be rolled back.

**Tier 3a, bypass the verifier in hardware.** This is what the 2018 Flex work did: a voltage or
clock glitch at the exact moment the check runs. Needs a glitcher and a scope, a way into the case,
and test pads on the board. Effort: weeks, and success is not guaranteed because modern parts add
glitch detectors and readout protection.

**Tier 3b, exploit the running stack.** The tracker runs the same C lineage as the open source
Golden Gate stack, parsing attacker supplied CoAP and GattLink data. A memory corruption bug there
gives code execution without touching the signature chain. Effort: research grade, months, and no
public CVE or exploit exists for this stack today. It also needs the mobile data key first, because
the interesting handlers are behind the session.

## Why the payoff is thin even if you win

| You would gain | You would still lack |
|---|---|
| a custom face on a small OLED | a speaker, a microphone, a real UI toolkit |
| custom sensor sampling logic | an app runtime, so every change is a firmware change |
| maybe a faster or richer live stream | any path to distribute what you built |

A tracker with 64 KB of RAM class of hardware is a poor target for an app platform, which is
exactly why Fitbit never shipped one for it. If the goal is to write code that runs on a wrist,
that work is far better spent on hardware that invites it.

## Why the transport key does not help here

The mobile data key from [5-keys.md](5-keys.md) is a credential for a CoAP session. It proves to
the tracker that you are its hub. It does not sign firmware, it does not unlock the boot chain,
and it cannot create an app runtime that the firmware does not contain.

Same for the bootstrap key, and same for any key you could extract. Two different gates:

| Gate | Opens with | Result |
|---|---|---|
| Talk to a running tracker | the transport key | data, settings, notifications |
| Change what the tracker runs | a signed image | nothing, unless Google ships it |

## What can be done instead, with the key

The Inspire 3 exposes a real feature surface over CoAP, so a local client can drive the device
the way the app does. Every path below returned a code proving it exists:

| Resource | Methods | What it is |
|---|---|---|
| `liveactivity` | GET | the 1 Hz record |
| `sync/dump` | GET | the stored archive, obfuscated |
| `sync/status`, `sync/config` | GET, PUT | sync state |
| `sync/response` | PUT, POST | the hub's reply to a dump |
| `app/inbox`, `app/inbox/status` | GET, POST | app and notification payloads |
| `app/outbox` | GET | app data from the tracker |
| `sb/records`, `sb/delete-records` | GET, POST | sensor blob records |
| `bond/control` | PUT | opens the Bluetooth bonding window |
| `pair/display` | PUT | shows the pairing prompt |
| `time` | GET, PUT | clock |

That is the honest definition of "customising" here: a program on a computer that uses these
paths. A screen, a dashboard, a logger, a notification bridge, a button that makes the tracker
buzz. Not code running on the wrist.

What is missing on this model, which the Air has: `settings` and `tiles/config` both answer
`4.04` here, so haptic intensity and tile configuration are not available on an Inspire 3.

## If the goal is a programmable wearable

Fitbit is the wrong platform. Devices built for this:

| Device | Why |
|---|---|
| PineTime | open firmware, community apps, cheap |
| Bangle.js | JavaScript apps on the watch |
| Watchy | ESP32, fully open |
| Any Gadgetbridge supported band | local protocol, no cloud |
| A Fitbit Air, if only heart rate matters | standard `180D` broadcast, no apps needed |

## Summary

| Question | Answer |
|---|---|
| Install an app on an Inspire 3 | no |
| Change its clock face | pick from the official ones |
| Sideload onto it | no runtime to load into |
| Custom firmware | no, and none public since 2017-era devices |
| Drive it from a computer with the key | yes, through the resources above |
| Does the key change any of this | no |
