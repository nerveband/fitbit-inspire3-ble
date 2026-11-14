# 3. The GATT map

Read from a Mac with CoreBluetooth, with the phone's Bluetooth off so the tracker was
free. Five services, 23 characteristics. Properties are hex: `0x02` read, `0x04` write
without response, `0x08` write, `0x10` notify, `0x12` read and notify, `0x20` indicate,
`0x30` combinations.

Advertising: name `Inspire 3`, advertised service `FD62`. The tracker advertises only when
no phone holds the link, which is why the phone's Bluetooth has to be off for this work.

## Connection parameters

| Item | Value |
|---|---|
| ATT MTU requested by the phone | 527 |
| ATT MTU granted by the tracker | 247 |
| Largest notification value | 244 bytes |
| GattLink reset write accepted | yes |
| Notifications received without a bond | 0 |

## `180A`, Device Information

Standard Bluetooth. Every value reads with no key and no bond.

| Characteristic | Name | Value |
|---|---|---|
| `2A29` | manufacturer | `Fitbit` |
| `2A24` | model number | `63` |
| `2A26` | firmware revision | `63.<version>` |
| `2A25` | serial number | rotates between connections |
| `2A27` | hardware revision | empty |
| `2A28` | software revision | empty |
| `2A23` | system id | `0000000000000000` |
| `2A2A` | IEEE regulatory flag | `00` |
| `2A50` | plug and play id | zeros |

The serial value changed between two connections, so it is a rotating identifier and not
a fixed serial. Do not treat it as a stable device id.

## `ABBAFD00-E56A-484C-B832-8B17CF6CBFE8`, status pair

Fitbit's `abbaXXXX` naming family. Two readable values and one plain read.

| Characteristic | Props | Value read |
|---|---|---|
| `ABBAFD01` | `0x12` | `180000004800f70000`, 9 bytes |
| `ABBAFD02` | `0x12` | `01000000000000`, 7 bytes |
| `ABBAFD03` | `0x02` | short value |

`ABBAFD01` looks like a version or capability block: `0x00000018` is 24, `0x00000048` is
72, `0x000000f7` is 247, which matches the ATT MTU. The rest is not identified.

## `ABBAFF00-E56A-484C-B832-8B17CF6CBFE8`, the data pipe

The only service that matters for data.

| Characteristic | Props | Direction |
|---|---|---|
| `ABBAFF01` | `0x04` write without response | phone writes GattLink bytes here |
| `ABBAFF02` | `0x10` notify | tracker pushes GattLink bytes here |

Write without response means no per packet ACK at the ATT level. GattLink supplies the
reliability instead, which is why its ACK logic exists.

## `AC2F0045-8182-4BE5-91E0-2992E6B40EBB`, unidentified

| Characteristic | Props |
|---|---|
| `AC2F0145` | `0x02` read |
| `AC2F2745` | `0x08` write |

Purpose unknown. It is not the sync path: no traffic appears on it during a sync.

## `4EEE1C00-4133-479B-8663-02C84BDC14BE`, unidentified

Seven characteristics with mixed properties. Listed so nobody has to rediscover them.

| Characteristic | Props |
|---|---|
| `4EEE1C01` | `0x30` |
| `4EEE1C02` | `0x0c` |
| `4EEE1C03` | `0x02` |
| `4EEE1C04` | `0x20` |
| `4EEE1C05` | `0x10` |
| `4EEE1C06` | `0x1a` |
| `4EEE1C07` | `0x2a` |

A plausible guess is a debug or log channel, but nothing confirms it. Do not build on it.

## Handles versus UUIDs

In the phone capture the pipe used handles `0x0042` and `0x0044` on one connection and
different numbers on the next. Handles are assigned per connection by the operating
system. Always match characteristics by UUID. A parser that matches handles breaks on
reconnect, which cost an hour during this work.

## Why a bare GATT probe sees nothing

This section records an early mistake, because the mistake is instructive. A hand written
CoreBluetooth probe wrote the GattLink reset byte and then waited. Nothing came back, and
the first version of these notes concluded that the tracker ignores strangers. That
conclusion was wrong.

The truth, measured later with the full stack: the tracker answers a reset request, sends
its own reset request, completes the handshake, and then opens DTLS **toward the Mac** at
once. See [docs/2](2-how-the-link-works.md) and [docs/6](6-what-we-tried.md). A probe that
only writes one byte never completes the reset, so the tracker is waiting for a reset
complete that never arrives, and both sides sit in silence.

So the pipe is not closed to a laptop. It is closed to an incomplete implementation.

What a bare probe saw:

| Step | Result |
|---|---|
| Connect, no pairing | accepted |
| Read all of `180A` | full values returned |
| Read `ABBAFD01`, `ABBAFD02`, `ABBAFD03` | values returned |
| Subscribe to `ABBAFF02` | accepted |
| Write `0x80` reset request to `ABBAFF01` | accepted, no error |
| Wait for the reset complete, `0x81` | nothing, because the probe never sent one back |
| Wait for any DTLS record | nothing, for the same reason |

That is the shape of a half open handshake, not a refusal. Compare
[6-what-we-tried.md](6-what-we-tried.md) item 5 for the corrected run.

## Link status values, measured

Reading the status values on a live Mac connection returned:

| Field | Value |
|---|---|
| connection interval | 30.00 ms |
| slave latency | 0 |
| supervision timeout | 720 ms |
| MTU | 247, which is 244 bytes of payload |
| bonded | yes, the tracker has bonded to a host before |
| encrypted | no, this link is not encrypted yet |
| data length extension | off |

The stack log also calls `AC2F2745` the ephemeral characteristic, which fits a value that
changes per connection.
