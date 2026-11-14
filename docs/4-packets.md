# 4. What the bytes look like

Three packet formats matter. All numbers are little endian unless stated.

## GattLink control packets

Control packets have the top bit set in the first byte.

| First byte | Meaning |
|---|---|
| `0x80` | reset request, one byte |
| `0x81` | reset complete, five bytes |

A reset complete carries a version range and two window sizes:

```
81  minVer  maxVer  rxWindow  txWindow
```

The real ones seen in a capture were `81 00 00 08 08`: version 0 to 0, receive window
8, transmit window 8.

## GattLink data packets

Data packets have the top bit clear.

```
bit 7     0        (this is a data packet)
bit 6     with ack requested
bits 0-4  packet number, 0 to 31
rest      payload
```

A payload that starts `00 45 00 00 ...` is a data packet, number 0, no ack requested,
and the payload starts with an IPv4 header.

## The IPv4 and UDP wrapper

Inside the payload:

```
45 00   version 4, header length 5 words
.. ..   total length, big endian
.. ..   id, flags
.. ..   time to live, protocol (11 = UDP)
.. ..   header checksum
169 254 0 2      source address
169 254 0 3      destination address
16 34            source port 5684, big endian
16 34            destination port 5684
..               payload, which is a DTLS record
```

`16 34` is hex for 5684, which is the CoAP port.

## DTLS record types

First byte of the UDP payload tells you what kind of record it is.

| Byte | Type |
|---|---|
| `14` | change cipher spec |
| `15` | alert |
| `16` | handshake |
| `17` | application data |

The next two bytes are the DTLS version, `FE FD` for DTLS 1.2. A normal session shows a
few handshake records, one change cipher spec, then application data forever.

## The identity string inside the handshake

The handshake is not encrypted, so the key label is readable:

```
MD-<keyId 8 hex>-<expiry 8 hex>
```

Twenty characters in total. The tracker ignores anything that does not match the shape.
This is the only part of the security setup you can see.

## LiveData frames on the older stack

For completeness, because many blog posts describe this one. Older Fitbits push live
data on a single characteristic as a flat record:

| Offset | Type | Field |
|---|---|---|
| 0 | u32 | timestamp in seconds |
| 4 | i32 | steps |
| 8 | i32 | distance |
| 12 | i16 | calories |
| 14 | i16 | floors, divided by 10 |
| 16 | i16 | unknown, present when length is 18 or more |
| 18 | u8 | heart rate |
| 19 | u8 | heart rate confidence, present when length is 20 |

Minimum length 16 bytes. The Inspire 3 does not use this: it has no such
characteristic, and no service `558dfa00`.

## The live activity record on the new stack

Inside CoAP, the answer to a `liveactivity` request is a small binary structure. The
fields the app reads are: timestamp, steps, elevation, calories, distance, active
minutes, heart rate, heart rate confidence, daily zone minutes, weekly zone minutes.

The app asks again every 1,000 milliseconds. Measured on a real link, the steady state
was five records each way every five seconds: exactly one per second, matching the code.

## How to read a capture without going mad

Two traps, both real:

1. Handles change. Match characteristics by UUID.
2. Fragmented writes are not reassembled for you by some tools. Tshark quietly gave
   empty values on the data characteristic. A small parser that joins fragments by
   packet number works better.

The `tools/` folder has a parser that does both.
