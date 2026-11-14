# 3. The GATT map

This is what the tracker offers when a Mac connects to it and asks for everything. It
was read with CoreBluetooth, the macOS Bluetooth API, with the phone switched off so
the tracker was free.

The tracker advertises as `Inspire 3` with service `FD62`. It only advertises while no
phone holds it.

## Services and characteristics

Five services, 23 characteristics. `props` is in hex. `0x02` read, `0x04` write without
response, `0x08` write, `0x10` notify, `0x12` read and notify, `0x20` indicate.

### `180A` Device Information

This one is standard Bluetooth. Every device has something like it.

| Characteristic | Meaning | Read value |
|---|---|---|
| `2A29` | maker | `Fitbit` |
| `2A24` | model number | `63` |
| `2A26` | firmware | `63.<version>` |
| `2A25` | serial style id | changes between connections |
| `2A27` | hardware version | empty |
| `2A28` | software version | empty |
| `2A23` | system id | all zeros |
| `2A2A` | radio certificate flag | `00` |
| `2A50` | plug and play id | zeros |

All of it reads with no key and no pairing. The serial style value changed between two
connections, so it is a rotating id, not a fixed serial.

### `ABBAFD00-E56A-484C-B832-8B17CF6CBFE8`

The `abbaXXXX` family is a Fitbit naming pattern. This one looks like a control or
status service.

| Characteristic | props | Notes |
|---|---|---|
| `ABBAFD01` | 0x12 | readable, answers `180000004800f70000` |
| `ABBAFD02` | 0x12 | readable, answers `01000000000000` |
| `ABBAFD03` | 0x02 | readable |

### `ABBAFF00-E56A-484C-B832-8B17CF6CBFE8`

This is the data pipe. Two characteristics, one each way.

| Characteristic | props | Use |
|---|---|---|
| `ABBAFF01` | 0x04 | phone writes GattLink bytes here |
| `ABBAFF02` | 0x10 | tracker pushes GattLink bytes here |

### `AC2F0045-8182-4BE5-91E0-2992E6B40EBB`

Not identified yet. It has one readable and one writable setting.

| Characteristic | props |
|---|---|
| `AC2F0145` | 0x02 read |
| `AC2F2745` | 0x08 write |

### `4EEE1C00-4133-479B-8663-02C84BDC14BE`

Seven characteristics with mixed abilities. Purpose unknown. Kept here so someone else
does not have to rediscover it.

| Characteristic | props |
|---|---|
| `4EEE1C01` | 0x30 |
| `4EEE1C02` | 0x0c |
| `4EEE1C03` | 0x02 |
| `4EEE1C04` | 0x20 |
| `4EEE1C05` | 0x10 |
| `4EEE1C06` | 0x1a |
| `4EEE1C07` | 0x2a |

## Handles, if you work from a capture

In the phone capture the data pipe showed up on handles `0x0042` and `0x0044`. Handles
are numbers the operating system assigns per connection. They change between
connections, so always match on UUID, not on handle.

## What happens when a stranger connects

| Action | Result |
|---|---|
| Connect with no pairing | allowed |
| Read Device Information | allowed, every value |
| Read `ABBAFD01`, `ABBAFD02` | allowed |
| Subscribe to `ABBAFF02` | allowed, no error |
| Write `0x80` reset request to `ABBAFF01` | accepted, no error |
| Read anything after that | nothing comes back |
| Notifications | zero, in every attempt |

So the tracker is polite to strangers and gives them nothing. The data pipe only works
with a phone that has bonded with it, which is why a laptop cannot open the link even
though the open source code for the protocol is sitting right there.

## Why pairing cannot be forced from a laptop

Bluetooth pairing normally starts when something asks for a value it is not allowed to
see without a secure link. On this tracker, every readable value is readable by
anybody. There is no locked door to knock on, so the operating system never starts
pairing, so the tracker never learns the laptop is a friend, so the data pipe stays
quiet.

That is a design choice by Fitbit, and a good one from their side.
