# 12. The bootstrap session, mapped

A session the tracker offers without any per device key. This page records what it allows,
what it refuses, and what the one resource it does serve contains. Measured on an Inspire 3 in
November 2026 from a Mac.

## How to get one

The tracker sometimes offers a `BOOTSTRAP` PSK identity instead of `MD-<key id>-<expiry>`. The
bootstrap key is public, from the open source bindings:

```
identity  BOOTSTRAP            (9 bytes of ASCII)
key       81 06 54 e3 36 ad ca b0 a0 3c 60 f7 4a a0 b6 fb
```

airLocal's reader accepts only `MD-` identities, so a one line change to its key resolver was
enough to answer `BOOTSTRAP` with that key. Then the handshake completes and the tracker is
reachable. No rooting, no Frida, no app.

## What it authorizes

One session, thirty paths, one connection. Codes are CoAP response codes.

| Code | Meaning | Resources |
|---|---|---|
| `2.05` Content | allowed | `sync/dump` |
| `4.01` Unauthorized | exists, this session may not read it | `liveactivity`, `time`, `sync/status`, `sync/config`, `bond/control`, `app/outbox` |
| `4.05` Method Not Allowed | exists, not by GET | `sync/response`, `pair/display`, `app/inbox`, `sb/records` |
| `4.04` Not Found | no such resource | `settings`, `tiles/config`, `.well-known/core`, `info`, `version`, `device`, `battery`, `status`, `health`, `log`, `debug`, `firmware`, `dfu`, `clock`, `alarm`, `notifications`, `sensor`, `heartrate`, `user` |

Two things fall out of that table.

**The `4.01` against `4.04` split is an existence oracle.** A path that exists answers
`4.01`, a path that does not answers `4.04`. So the CoAP namespace of a Fitbit can be mapped
from any Mac with a public key, without the app and without the device key.

**Only the dump is open.** Everything that reports current state needs the mobile data key.

Queries are refused over bootstrap: `sync/dump?t=primary` and `sync/dump?t=sc` both return
`4.02` Bad Option with a 26 byte protobuf body:

```
0a 15 "gg.proto.errordetails" 10 f6 01
```

So the plain dump is the only form available.

## Probing the methods

Every earlier probe used `GET`. Sending the method each resource actually uses, with an empty
body, separates "wrong method" from "not allowed", because authorization is checked before the
body is parsed:

| Request | Code | Reading |
|---|---|---|
| `PUT /pair/display` | `2.04` Changed | **accepted with no key** |
| `POST /sync/dump`, `PUT /sync/dump` | `4.05` | dump is read only |
| `PUT /sync/response`, `POST /sync/response` | `4.08` | Request Entity Incomplete, so authorized but it wants a body |
| `POST /sb/records` | `4.01` | unauthorized |
| `PUT /sb/records`, `PUT /app/inbox`, `PUT /app/outbox`, `PUT /sync/status` | `4.05` | wrong method |
| `POST /app/inbox` | `4.01` | unauthorized |
| `PUT /bond/control` | `4.01` | unauthorized |
| `POST /bond/control` | `4.05` | wrong method |
| `PUT /sync/config` | `4.01` | unauthorized |
| `PUT /liveactivity`, `POST /liveactivity` | `4.05` | read only |
| `PUT /time` | `4.01` | unauthorized |
| `DELETE /app/outbox` | `4.01` | unauthorized |
| `PUT /tiles/config`, `POST /tiles/config` | `4.04` | no such resource on this firmware |

Two consequences.

**`PUT /pair/display` is open to an unauthenticated peer.** A stranger inside radio range, with
the public bootstrap key, can make the tracker show its pairing prompt. That is worth knowing
about, and it is the only write the bootstrap session allows.

**The namespace is small.** Twenty more guessed names all returned `4.04`: `pairing`, `auth`,
`session`, `key`, `keys`, `md`, `sync`, `ping`, `node`, `hub`, `params`, `stats`, `metric`,
`crashdump`, `dfu/control`, `firmware/version`, `tiles`, `app`, `bond`, `bond/status`. What
exists is the list the app uses, and nothing else.

## Back to back dumps

Four dumps taken in one session, seconds apart:

| Order | Header bytes 5 to 8 | Size | Blocks |
|---|---|---|---|
| 1 | `b8 20 2e 52` | 36,453 | 2277 |
| 2 | `ba 20 2e 52` | 36,629 | 2288 |
| 3 | `bc 20 2e 52` | 36,805 | 2299 |
| 4 | `be 20 2e 52` | 32,165 | 2009 |

Three things follow.

**Byte 5 is a counter that advances by 2 per dump.** The rest of the header, including the wire
id, is fixed.

**While data accumulates the archive grows by 11 blocks, or 176 bytes, per dump.** Then it
dropped by 290 blocks, which looks like trimming of the oldest records rather than a new format.

**Consecutive dumps share zero 16 byte blocks.** With a growing log and a fixed IV, the shared
prefix would repeat in the ciphertext. It does not, so encryption is not deterministic: the IV
or nonce is fresh per dump, or derived from that counter.

## What the dump contains

Three dumps across a few minutes, all `2.05`:

| Time | Body size |
|---|---|
| 13:56 | 39,061 bytes |
| 13:57 | 36,229 bytes |
| 13:58 | 33,077 bytes |

The size is not fixed, and it fell over the three reads, which fits a rolling buffer rather
than a growing log.

Layout, from the bytes:

| Region | Size | Content |
|---|---|---|
| header | 21 bytes | plaintext |
| ciphertext | the rest | always a multiple of 16 |

Header, with the device id redacted:

```
03 04 00 00 02  b4 20 2e 52  <6 byte wire id>  01 40 01 00 00 00
```

| Offset | Bytes | Note |
|---|---|---|
| 0 | `03 04` | version or type |
| 2 | `00 00 02` | constant across dumps |
| 5 | `b4`, then `b6` | changes between dumps, increments |
| 6 to 8 | `20 2e 52` | constant across dumps |
| 9 | 6 bytes | the device wire id, in clear |
| 15 | `01 40 01 00 00 00` | constant across dumps |

The ciphertext shows no structure at all:

| Test | Result |
|---|---|
| Length divisible by 16 | yes, 2263 blocks in the 36,229 byte dump |
| Duplicate 16 byte blocks | zero, at every alignment tested |
| Deflate, zlib or gzip at the start | no |
| Entropy | 7.99 bits per byte |

No duplicate blocks across 2,263 of them is what a random stream looks like. That does not
prove a particular mode, but it rules out ECB over the sort of repetitive record data a step
counter would produce.

The three dumps share no ciphertext and no header, so each dump is encrypted independently.

## Why this matters more than it looks

Google hands 36 KB of encrypted health data to anyone who asks with a key that is printed in
their own open source repository. That is a deliberate design: the dump is protected by the
envelope cipher, not by the transport credential.

The consequence is a clean split:

| Goal | Gate |
|---|---|
| Pull stored history off the tracker locally | none, bootstrap is enough |
| Read that history | the envelope key, which is not public |
| Read live data at 1 Hz | the per device mobile data key |

So the transport credential guards *current* state, and the envelope cipher guards *stored*
state. Two different locks, two different keys, and only one of them is available from a phone.

## Two operational notes

**The tracker gets tired.** After roughly fifteen to twenty connect, handshake and abort cycles
the tracker stops advertising and every handshake times out. Movement or a button press brings
it back. Batch requests into one session, which is why the sweep mode exists.

**Identities vary.** The same tracker offered `MD-<key id>-<expiry>` in some runs and
`BOOTSTRAP` in others. The bootstrap identity appeared after failed mobile data handshakes,
which hints at a fallback, but that is a guess and is listed as open in
[9-open-questions.md](9-open-questions.md).

## Reproducing it

The local patch is not published. It changes one function in airLocal's `reader.c`, adding a
branch that answers the `BOOTSTRAP` identity with the public key, plus a `sweep` mode that
walks a comma separated path list inside one DTLS session:

```
fitbit-air-reader read --device UUID --key-file bootstrap.bin --key-id 4D****** \
  --output out.bin --type sweep --paths "sync/dump,liveactivity,sync/status"
```

Standard output is one line per path: `path`, `code`, `payload bytes`.
