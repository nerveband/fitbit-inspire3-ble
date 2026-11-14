# 2. How the link works, layer by layer

Each layer has a small job and a small set of parameters. This page lists them in order,
bottom to top, with the measured values.

| Layer | Job | Measured parameters |
|---|---|---|
| BLE | carry bytes between two radios | bonded link, MTU 247 |
| GATT | expose the two ends of one pipe | write `ABBAFF01`, notify `ABBAFF02` |
| GattLink | turn a narrow lossy pipe into a reliable stream | PSN 5 bits, ACK at half window or 200 ms, resend 4 s |
| IPv4 | address two peers inside the pipe | `169.254.0.2` to `169.254.0.3`, TTL set, checksum valid |
| UDP | demultiplex one port | `5684` to `5684` |
| DTLS 1.2 | encrypt and authenticate | PSK, `0xC0A4`, 16 byte key |
| CoAP | name resources and carry small bodies | `GET liveactivity`, 1000 ms |
| Protobuf | encode the record | `LiveActivity.Activity` |

## BLE and GATT

The tracker offers five services and 23 characteristics. The interesting one is a single
pipe with one end for writes and one end for notifications. Both ends sit in service
`ABBAFF00-E56A-484C-B832-8B17CF6CBFE8`.

ATT MTU, measured on five separate connections: the phone asks for 527, the tracker
answers 247. So a notification carries at most 244 bytes of value.

That number drives the whole stack. Work it down:

```
247  ATT MTU
 -3  ATT notification header (opcode, handle)
244  GattLink payload
 -1  GattLink data header
243  IPv4 packet
-20  IPv4 header
223  UDP datagram
 -8  UDP header
215  DTLS record
```

The largest DTLS application record in the capture is 215 bytes. The stack model matches
the bytes exactly.

## GattLink

GattLink exists because a BLE characteristic is a narrow tube that can drop or reorder
packets. It gives the layers above a reliable, ordered stream.

Packet header, one byte:

| Bits | Meaning |
|---|---|
| bit 7 clear | this is a data packet |
| bit 6 | the sender wants an ACK |
| bits 0 to 4 | packet sequence number, PSN, 0 to 31 |
| rest | payload |

The PSN is 5 bits, so the sequence space is 32 packets. An ACK-only packet carries the
highest PSN received. Control packets set bit 7 and use the low bits as a subtype:

| Byte | Packet |
|---|---|
| `0x80` | reset request, no payload |
| `0x81` | reset complete, 4 payload bytes: min version, max version, receive window, transmit window |

Timers come from the published design notes (`docs/src/architecture/gattlink.md` in the
GoldenGate repo):

| Behaviour | Value |
|---|---|
| Send an ACK | when half the window needs acking, or 200 ms have passed |
| Resend an unacked packet | after 4 seconds |
| Give up | after consecutive missed ACKs, and raise a stall event |
| Reset handshake | each peer sends a reset request, retries on a timer, and waits for a reset complete |

Both peers run the same state machine, so either side may open the pipe. This is why a
laptop can send `0x80` and get a polite no.

## IPv4 and UDP

The tracker and the phone each hold a link local address:

| Side | Address |
|---|---|
| Phone, the central | `169.254.0.2` |
| Tracker, the peripheral | `169.254.0.3` |

Headers in the capture are ordinary IPv4: version 4, header length 5 words, protocol 17
for UDP, total length set, header checksum present and correct. Both sides use port
`5684`, which is the CoAP port.

## DTLS, and who is the client

DTLS 1.2 record headers are visible even when the payload is not. In the capture the
tracker sends the ClientHello, and the phone answers with a ServerHello. So for this
stack:

| Role | Party |
|---|---|
| DTLS client, sends ClientHello and the key identity | the tracker |
| DTLS server, resolves the key by id and completes the handshake | the phone app |

That ordering surprised the author too. The direction comes from the HCI direction bit in
the trace, and it was cross checked: on the same connection 1237 ATT notifications arrive
from the tracker while 599 write commands leave the phone, so the direction labels are
not swapped.

The suites the client offers are exactly the three in the open source
`DtlsOptions.defaultCipherSuites`:

| Suite | Name | Picked |
|---|---|---|
| `0xC0A4` | `TLS_PSK_WITH_AES_128_CCM` | yes |
| `0x00A8` | `TLS_PSK_WITH_AES_128_GCM_SHA256` | no |
| `0xC037` | `TLS_ECDHE_PSK_WITH_AES_128_CBC_SHA` | no |
| `0x00FF` | renegotiation SCSV, not a real suite | no |

Extensions in the ClientHello: elliptical curves `0x000A`, EC point formats `0x000B`,
encrypt then MAC `0x0016`, extended master secret `0x0017`, session ticket `0x0023`.

The client sends its key identity in the ClientKeyExchange, in clear: a 2 byte length
then 20 bytes.

## CoAP

CoAP keeps the HTTP idea and throws away the weight. A request is 4 bytes of header plus
a token plus options. The app builds requests with `OutgoingRequestBuilder`, and the live
activity request sets `maxResendCount(0)`, so a lost poll is simply dropped and the next
poll comes one second later.

Resources named in the app code:

| Resource | Use |
|---|---|
| `liveactivity` | the once per second record |
| `/sync/dump` | the bulk upload of stored data |
| `/sync/response` | the phone's acknowledgement of a dump |
| `/sync/config`, `/sync/status` | sync settings and state |
| `pair/display` | show a pairing code on the device screen |
| `bond/control` | manage the bond |
| `app/inbox`, `app/outbox`, `tiles/config` | apps |
| `sb/records` | sensor records |

Blockwise transfer exists in the library (`CoapBlockwiseResponseListener`,
`jni_gg_coap_client_block`), so large bodies arrive in numbered blocks. That matters for
`/sync/dump`, where a day of data can be far larger than 215 bytes.

## Protobuf

The live activity body is a protobuf message, `LiveActivity.Activity`. The app parses it
with `LiveActivity.Activity.parseFrom(byte[])` and converts it with `LiveDataConverter`.

Fields: timestamp, steps, elevation, calories, distance, active minutes, heart rate,
heart rate confidence, daily zone minutes, weekly zone minutes.

## Two Fitbit stacks

| Stack | Service names | Security | Used by |
|---|---|---|---|
| SLS, also called airlink | `adabXXXX` | challenge and response, weaker | older trackers |
| GoldenGate | `ABBAFF00`, `ABBAFD00` | DTLS 1.2 PSK | Inspire 3 and current devices |

Most public notes describe SLS. This device is not SLS: there is no `adab` service, and
there is no plain live data characteristic. If a guide mentions `558dfa00` or a 16 byte
live data frame, it is describing the old stack.
