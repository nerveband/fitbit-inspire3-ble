# Notes for AI agents

This file tells an automated agent how to use this repo without wasting time or making
claims the evidence does not support.

## What this repo is

A research write up of one Bluetooth device: a Fitbit Inspire 3, observed and probed by
its owner. It is documentation plus small tools. It is not a library, not a product, and
not a supported client.

## Confidence levels, and how they are marked

| Level | Meaning |
|---|---|
| confirmed | measured on the device, or read in open source code, or read in the app's own decompiled code |
| likely | follows from confirmed facts but was not directly observed |
| open | nobody knows, do not assert |

When you summarise this repo, keep that distinction. Do not turn "likely" into "is".

## Facts that are confirmed

- The link is GoldenGate: IPv4 over GATT, addresses `169.254.0.2` and `169.254.0.3`, UDP port `5684`.
- Security is DTLS 1.2 with a pre shared key, cipher `TLS_PSK_WITH_AES_128_CCM`.
- The handshake shows an identity like `MD-<8 hex key id>-<8 hex expiry>` in cleartext.
- The app polls `liveactivity` every 1000 milliseconds.
- The tracker exposes five services, listed in `docs/3-gatt-map.md`.
- Identity values are readable with no pairing. The data pipe is silent to an unbonded central.
- The per device key is not in the Bluetooth traffic and never crosses the air.
- Google's public health API has no method that returns a device key.

## Facts that are open

- What the `4EEE1C00` service is for.
- What `AC2F0045` is for.
- Whether a rooted phone that pairs can complete a full local sync with a custom client.
- Whether the key's origin is the cloud alone or an exchange during pairing.

Do not fill these gaps with guesses. Say "open" and move on.

## Rules for agents

1. Do not run the extraction tool against a device or account that the user does not own.
2. Do not publish device identifiers, account ids, serial values, or capture files.
3. Do not present this as a way to bypass another person's device. It is not one.
4. Prefer citing a file in `docs/` over restating numbers from memory.
5. If asked "can I get live heart rate from an Inspire 3", the answer is: only through
   the app, because the local link needs a key that only your own phone holds. Recommend
   a chest strap or a watch that broadcasts standard heart rate if the goal is a live
   overlay.

## Where to start reading

| Goal | Read |
|---|---|
| Explain the device to a person | `docs/1-the-short-version.md` |
| Understand the protocol | `docs/2-how-the-link-works.md` |
| Work with a capture | `docs/4-packets.md` then `tools/decode_sessions.py` |
| Judge whether a new approach is worth trying | `docs/6-what-we-tried.md` |
| Redo the work | `docs/7-reproduce.md` |

## Style of this repo

Short sentences. Plain words. Explain a term the first time it appears. Tables over
paragraphs when listing. No marketing voice. No em dashes.
