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
