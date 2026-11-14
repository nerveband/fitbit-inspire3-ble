# 4. Byte layouts

Numbers are little endian unless the layout says otherwise. Network layers are big endian,
as usual.

## GattLink data packet

```
byte 0   bit 7   0, this is data
         bit 6   1 means the sender wants an ACK
         bits 0-4  PSN, 0 to 31
bytes 1+ payload, up to 243 bytes
```

Seen in the capture: `0x6B` is `0110 1011`, a data packet, ACK wanted, PSN 11.

## GattLink control packets

```
80                                  reset request
81  minVer  maxVer  rxWin  txWin    reset complete
```

Real reset completes observed: `81 00 00 08 08`, version 0 to 0, receive window 8,
transmit window 8. The window is the number of unacknowledged packets allowed, so 8 is
small compared to the 32 packet sequence space.

## IPv4 and UDP wrapper

```
45 00            version 4, header 5 words
ll ll            total length, big endian
id id  40 00     identification, flags
40 11  ck ck     TTL 64, protocol 17 UDP, checksum
a9 fe 00 02      source 169.254.0.2
a9 fe 00 03      destination 169.254.0.3
16 34            source port 5684
16 34            destination port 5684
le le            UDP length
00 00            UDP checksum, zero means unused
```

`a9 fe` is how `169.254` appears in hex, which makes `45 00` and `a9 fe 00 02` easy
markers when you scan a capture for the start of an IP packet.

## DTLS record header

```
byte 0     content type: 20 change cipher spec, 21 alert, 22 handshake, 23 application
bytes 1-2  version FE FD, which is DTLS 1.2
bytes 3-4  epoch, 0 during the handshake, 1 afterwards
bytes 5-10 sequence number, 6 bytes, big endian
bytes 11-12 length, big endian
bytes 13+  fragment
```

The epoch is the useful field: records with epoch 0 are handshake and cannot be read, and
records with epoch 1 are application data and also cannot be read, but the counters tell
you the session is alive.

## Handshake inside a record

```
byte 13      handshake type: 1 client hello, 2 server hello, 16 client key exchange,
             20 finished
bytes 14-16  length, 3 bytes, big endian
bytes 17-18  message sequence, big endian
bytes 19-22  fragment offset, 3 bytes, big endian
bytes 23-25  fragment length, 3 bytes, big endian
bytes 26+    body
```

DTLS adds those 3 byte fields to every handshake message, which is the only structural
difference from TLS.

## The key identity, and where to find it

The PSK identity sits at a fixed position in the ClientKeyExchange: a 2 byte length, then
the identity.

```
offset 0     content type 16 (handshake)
offset 13    handshake type 16 (client key exchange)
offset 25    identity length, 2 bytes, big endian, 0x0014 for this device
offset 27    identity, 20 bytes, for example MD-1A2B3C4D-5E6F7A8B
```

Grep any capture for the bytes `4D 44 2D` (`MD-`) and you land on it. The value in this
doc is a made up example; a real link carries a real key id.

Format:

| Part | Bytes | Meaning |
|---|---|---|
| `MD-` | 3 | mobile data |
| key id | 8 hex | the id the phone looks up |
| `-` | 1 | separator |
| expiry | 8 hex | seconds since 1970, hex, when the key stops being valid |

20 characters, plus the 2 byte length field.

## An observed handshake, in order

From handle `0x0058`, one of three sessions on that connection. Direction is from the HCI
direction bit. These sizes were re-measured on a Mac with the open source stack, and they
match: a 101 byte ClientHello, and the same 4 suites filtering down to `0xc0a4`.

| Direction | Record | Size | Content |
|---|---|---|---|
| tracker to phone | handshake | 101 bytes | ClientHello, suites `0xC0A4 0x00A8 0xC037` plus `0x00FF` |
| phone to tracker | handshake | 131 bytes | ServerHello, picked `0xC0A4`, plus hello done |
| tracker to phone | handshake | 122 bytes | ClientKeyExchange, identity length 20 |
| tracker to phone | change cipher spec | 75 bytes | |
| both | application data | 45 to 215 bytes | CoAP, encrypted |

On the Mac run the stack logged the decision directly:

```
dumping 'client hello, ciphersuitelist' (8 bytes)
trying ciphersuite: 0xc0a4 (TLS-PSK-WITH-AES-128-CCM)
selected ciphersuite: TLS-PSK-WITH-AES-128-CCM
resolving PSK identity, size=20
```

With a wrong 16 byte key the same run ended here:

```
mbedtls_cipher_auth_decrypt() returned -25344 (-0x6300)
```

`0x6300` is `MBEDTLS_ERR_SSL_INVALID_MAC`. The Finished message did not authenticate, so
the handshake stopped. That is the whole wall in one line: correct key, MAC verifies,
session opens. Wrong key, MAC fails, session dies.

On that phone capture the server hello and the key exchange repeated three times before
the change cipher spec arrived. That is DTLS retransmission over a lossy ATT pipe, and it
is normal behaviour, not an error.

## Application data sizes

| Size | Count on `0x0058` | Guess |
|---|---|---|
| 215 | 190 each way | largest record, a full 244 byte notification minus 29 byte overhead |
| 58 | 95 | poll request, text resource name plus tag |
| 56, 57 | many | poll request variants |
| 45 | several | smallest record, near empty CoAP body |

DTLS with CCM adds 8 bytes of explicit nonce and 8 bytes of tag, plus the 13 byte record
header. So a 45 byte record carries about 16 bytes of CoAP. A poll request with a
4 byte CoAP header, a token, and the `liveactivity` path option fits that.

## CoAP request, before encryption

```
byte 0    version 1 in the top 2 bits, type, token length
byte 1    code, 0x01 for GET
bytes 2+  token
options   Uri-Path, one option per path segment
0xFF      payload marker, then the body if any
```

`liveactivity` is a single path segment, so one Uri-Path option of 11 bytes, which is
option delta 11 with a 1 byte length prefix.

## The live activity body

A protobuf message, `LiveActivity.Activity`. Field numbers, confirmed independently by the
open source reader and by the app's generated class:

| Field | Meaning | Unit |
|---|---|---|
| 1 | timestamp | seconds |
| 2 | steps | count |
| 3 | distance | **millimetres** |
| 4 | calories | kcal |
| 5 | elevation | floors or gain |
| 6 | very active minutes | count |
| 7 | heart rate | bpm |
| 8 | heart rate confidence | enum |
| 9 | daily active zone minutes | count |
| 10 | weekly active zone minutes | count |

Heart rate confidence values: `0` invalid, `1` tentative, `2` good, `3` microstill. A zero
or invalid heart rate is not a measurement. Distance is divided by 1,000,000 for
kilometres, which is why field 3 is millimetres.

A live activity response on a working link is 24 bytes, so the message is small and mostly
delta free.

Protobuf is not self describing, so a dump without a schema is unreadable by eye. Use the
generated class or a matching `.proto`.

## The older LiveData frame, for reference

Older trackers push this on a single characteristic with no encryption beyond the link.
Listed because many guides still describe it.

| Offset | Type | Field |
|---|---|---|
| 0 | u32 | timestamp, seconds |
| 4 | i32 | steps |
| 8 | i32 | distance |
| 12 | i16 | calories |
| 14 | i16 | floors divided by 10 |
| 16 | i16 | unknown, present when length is 18 or more |
| 18 | u8 | heart rate |
| 19 | u8 | heart rate confidence, present when length is 20 |

Minimum length 16 bytes. The Inspire 3 does not send this. It has no such characteristic.

## Two parser traps

**Handles change.** Match by UUID, not by handle number.

**Fragmentation is real.** An IP packet can span several ATT writes. A tool that prints
ATT values one at a time will show fragments, and tshark printed empty values on the
GattLink characteristic for this reason. Join the fragments by GattLink PSN first, then
parse the IP packet.
