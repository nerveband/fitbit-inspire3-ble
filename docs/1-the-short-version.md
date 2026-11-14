# 1. The result, with numbers

The Inspire 3 speaks a Fitbit stack called GoldenGate. It carries a small IPv4 network
over Bluetooth, encrypts it with DTLS, and answers CoAP requests inside it. The app polls
live activity once per second. All of that is measurable. The only closed part is the 16
byte key that unwraps the DTLS session.

## The measurement that matters

One capture, 16.7 minutes, iPhone and tracker, three connections.

| Connection | ATT frames | UDP packets | App data each way | What was happening |
|---|---|---|---|---|
| handle `0x0058` | 2298 | 596 | 293 requests, 293 responses | steady polling, plus a sync burst |
| handle `0x0041` | 654 | 58 | 27 each way | short session after reconnect |
| handle `0x0052` | 526 | 38 | 17 each way | short session |

293 requests in 16.7 minutes is 1 every 3.4 seconds averaged, because the burst pushes
the rate up and idle time pulls it down. Look at the steady part and it is exactly 5
requests every 5 seconds. The app code says why: an interval of `1000L` milliseconds
(`LiveDataCommandsHandler.java:169`).

## The six facts that shape everything else

**One: the tracker runs an internet inside Bluetooth.** Source `169.254.0.2`, destination
`169.254.0.3`, UDP port `5684`. Real IPv4 headers with a real header checksum.

**Two: security is a shared secret, not certificates.** DTLS 1.2, one pre shared key,
cipher `TLS_PSK_WITH_AES_128_CCM` (`0xC0A4`). No public key exchange is needed to start.

**Three: the tracker opens the secure session.** It sends the ClientHello. The phone
answers with the ServerHello. The tracker then sends a key exchange holding its own key
identity in the clear: `MD-<key id>-<expiry>`, 20 bytes.

**Four: the key is provisioned, not derived.** The phone keeps a copy indexed by that key
id and looks it up when the tracker connects. Nothing in the handshake lets an outsider
compute it.

**Five: the data pipe ignores strangers.** Without a bond, the tracker accepts a write to
its GattLink characteristic, accepts the subscribe, and sends zero notifications. Silent.

**Six: the public API has no key endpoint.** 27 methods in Google's Health API v4, two
about devices, both metadata.

## What a stranger can and cannot see

| Can see | Cannot see |
|---|---|
| maker `Fitbit`, model `63`, firmware string | heart rate, steps, distance, calories |
| two small status values | the data key |
| that a tracker is nearby, and its advertised name | the phone's account, its tokens, its device ids |
| the key id and its expiry, from the handshake | the traffic content, at all |

## What the numbers say about the design

The MTU is 247 bytes. GattLink adds 1 byte, IPv4 adds 20, UDP adds 8. So the biggest UDP
payload is 215 bytes. The largest app data record in the capture is exactly 215 bytes.
That agreement is a good sign the layer model is right.

## Practical outcomes

| Goal | Verdict |
|---|---|
| Live heart rate on a desktop overlay | not with this tracker, no `180D` service |
| Live heart rate on a rooted Android that pairs | possible, needs the key from that phone |
| Intraday steps and heart rate history | Google Health API, 1 minute buckets |
| Rebuild the client from scratch | everything except the key is documented and available |

## Where to go next

Read [2-how-the-link-works.md](2-how-the-link-works.md) for the layer by layer detail, then
[5-keys.md](5-keys.md) for the key chain. If you want to test a claim yourself, every
number on this page can be reproduced with [7-reproduce.md](7-reproduce.md).
