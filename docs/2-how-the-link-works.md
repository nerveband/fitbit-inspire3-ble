# 2. How the link works

This page walks down the link from the radio to the heart rate number. Each layer only
cares about the layer under it. That is why each one is simple to describe.

```
heart rate record             the thing you want
CoAP requests                 a small HTTP, resource names like "liveactivity"
DTLS 1.2 with a pre shared key   encryption, one 16 byte key
IPv4 and UDP                  two fixed addresses, port 5684
GattLink                      numbered packets, ACKs, a reset handshake
GATT                          two settings: write here, hear back there
BLE                           the radio link, bonded
```

## BLE and GATT, in one paragraph

BLE is the low power radio. GATT is the shape of what you can do with it. A tracker
offers services, each service holds characteristics, and each characteristic holds a
value you can read, write, or subscribe to. When you subscribe, the tracker pushes new
values to you as they change. That push is called a notification.

## GattLink, the part people miss

GattLink is Fitbit's own small protocol. It exists because a BLE characteristic is a
very narrow tube: a few dozen bytes at a time, and the radio can drop or reorder them.
GattLink makes that tube behave like a reliable stream.

It does three things:

1. A reset handshake. One side sends `0x80`. The other answers `0x81` with a version
   range and two window sizes. Until that happens, neither side sends data.
2. Numbered data packets. The first byte carries a small packet number, and a flag
   that says "please acknowledge this".
3. Acknowledgements. The receiver confirms which numbers arrived. Missing ones get sent
   again.

It is all open source, Apache 2.0, in the `golden-gate` repo, file `gg_gattlink.c`.

## The fake internet inside

The next layer up is a surprise for most people. The tracker and the phone each have a
made up internet address:

| Side | Address |
|---|---|
| Phone | `169.254.0.2` |
| Tracker | `169.254.0.3` |
| Port, both ways | `5684` |

`169.254.x.x` is the range computers use when they cannot find a normal network. Here
it is used on purpose, as a private two node network.

So the payload of a GattLink data packet is a real IPv4 packet, with a real UDP header
inside it. That is why the bytes `45 00` show up early in the packet: `0x45` is the
first byte of an IPv4 header.

## DTLS, the lock

On port 5684 the two sides run DTLS version 1.2. DTLS is TLS for links that can lose
packets. This link uses a cipher suite called `TLS_PSK_WITH_AES_128_CCM`. PSK means pre
shared key: no certificates, no public key exchange, just a 16 byte secret both sides
already know.

The first thing a client sends is its identity string. That string is readable, even
though the rest is not. It looks like this:

```
MD-1A2B3C4D-5E6F7A8B
```

Break it in three parts:

| Part | Meaning |
|---|---|
| `MD` | mobile data |
| `1A2B3C4D` | key id, in hex |
| `6B1836DA` | expiry time, in hex seconds since 1970 |

The values above are a made up example. On a real link they are different.
That is how a key id can be quoted without knowing the key. The trailer in the
handshake is a label, not a secret.

## CoAP, the actual conversation

CoAP looks like HTTP but shorter. Instead of URLs it uses short resource names. The app
uses these, taken from its own code:

| Resource | Used for |
|---|---|
| `liveactivity` | the once per second record |
| `/sync/dump` | the big upload of stored data, called megadump |
| `/sync/response` | the phone's reply to a dump |
| `/sync/config`, `/sync/status` | sync settings and state |
| `pair/display` | show a pairing code on the device |
| `bond/control` | manage the bond |
| `app/inbox`, `app/outbox`, `tiles/config` | apps and watch faces |
| `sb/records` | sensor records |

Inside `liveactivity` the answer is a small binary record. Fields: timestamp, steps,
distance, calories, floors, heart rate, heart rate confidence, daily and weekly zone
minutes.

## The newer and older Fitbit families

Two stacks exist in the app. The older one, called SLS or airlink, uses services named
`adabXXXX`. The newer one, GoldenGate, is the internet style stack above.

The Inspire 3 uses GoldenGate. You can tell from the traffic alone: IPv4 packets, UDP
port 5684, DTLS. No `adab` service is present. That matters because most blog posts
about Fitbit Bluetooth describe the old stack.

## Why the internet inside matters

It means the phone never needed special Fitbit code to carry the bytes. It only needed
a working GattLink pipe, and then normal networking did the rest. It also means a
patient person with a laptop and the open source code can rebuild the whole stack,
which is exactly what the notes in this repo prepare for. The only part that cannot be
rebuilt is the 16 byte key.
