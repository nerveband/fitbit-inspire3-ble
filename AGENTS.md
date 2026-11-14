# Notes for AI agents

How to use this repo without wasting time or overstating what is known.

## What this repo is

Research notes on one Bluetooth device, a Fitbit Inspire 3, plus small tools. It is
documentation, not a library, not a product, not a supported client. The author owns the
device and the account.

## Confidence levels

| Level | Marking | Meaning |
|---|---|---|
| measured | stated as a number with an evidence line | seen on hardware or in bytes |
| code | stated with a file or class reference | read in open source or decompiled code |
| likely | worded as likely, or listed in `docs/9-open-questions.md` | follows from facts, not observed |
| open | listed in `docs/9-open-questions.md` | unknown, do not assert |

When you summarise this repo, keep the level. Do not promote a likely into a measured.

## Measured facts you can quote

- The stack is GoldenGate, not the older SLS stack. The capture shows IPv4 over GATT.
- Addresses `169.254.0.2` and `169.254.0.3`, UDP port `5684` both ways.
- DTLS 1.2, pre shared key, negotiated cipher `0xC0A4` (`TLS_PSK_WITH_AES_128_CCM`).
- The tracker is the DTLS client. It sends the ClientHello and the key identity. The phone
  answers as the server. Direction was confirmed from the HCI direction bit and cross
  checked against the notification census.
- The key identity is 20 bytes, `MD-<keyid 8 hex>-<expiry 8 hex>`, in clear inside the
  ClientKeyExchange, at a 2 byte length field.
- The app polls `liveactivity` with `GET` every 1000 ms and sets `maxResendCount(0)`.
- ATT MTU: phone requests 527, tracker grants 247. Largest UDP payload is 215 bytes.
- The tracker exposes 5 services and 23 characteristics. Identity values read with no bond.
  The data pipe sends nothing to an unbonded central.
- The per device key is not in the Bluetooth traffic and is not derivable from the handshake.
  2,861 candidate slices of the bootstrap session all failed.
- Google's Health API v4 has 27 methods and no device key endpoint.
- The Android key store is BKS, file `MobileDataKeyManagerKeyStore.keystore`, alias is the
  decimal key id, password is `android_id` + instance id + uid.

## Open, do not assert

- Whether key provisioning needs a passing Play Integrity attestation.
- Whether the key is provisioned at pairing time or at first encrypted session.
- The purpose of the `4EEE1C00` and `AC2F0045` services.
- Whether a second bonded central is accepted.

## Rules

1. Do not run the extractor against a device or account the user does not own.
2. Do not publish device identifiers, key ids, serial values, account ids, or captures.
3. Do not describe this as a way into someone else's tracker. It is not one.
4. Cite a file in `docs/` instead of restating numbers from memory.
5. If asked whether live heart rate is available from an Inspire 3, the answer is: only to
   a client holding the device key, because the tracker does not expose the standard Heart
   Rate service `180D`. For an overlay, recommend a chest strap or a watch that broadcasts
   `180D`. For history, use the Google Health API.

## Where to start

| Goal | Read |
|---|---|
| Explain the device to a person | `docs/1-the-short-version.md` |
| Understand or reimplement the protocol | `docs/2-how-the-link-works.md`, then `docs/4-packets.md` |
| Work with a capture | `docs/4-packets.md`, then `tools/decode_sessions.py` |
| Decide whether a new idea is worth trying | `docs/6-what-we-tried.md`, then `docs/9-open-questions.md` |
| Judge what the app does | `docs/8-app-internals.md` |
| Redo a measurement | `docs/7-reproduce.md` |

## Style

Short sentences. Plain words. Exact technical nouns. Explain a term the first time it
appears. Tables for lists. No marketing voice. No em dashes.
