# Fitbit Inspire 3, Bluetooth link notes

Reverse engineering notes for one device: a Fitbit Inspire 3, firmware `63.<version>`,
product id 63. The notes cover the Bluetooth stack it speaks, the bytes it sends, and the
one secret that keeps the data closed.

Everything here was measured on a device the author owns, or read out of open source
code, or read out of the app's own decompiled code. Facts that are not measured are
marked as such. See [AGENTS.md](AGENTS.md) for the confidence rules.

## The stack, with the parameters

```
LiveActivity.Activity    protobuf: timestamp, steps, distance, calories, hr, ...
CoAP                     GET liveactivity every 1000 ms, maxResendCount 0
DTLS 1.2                 TLS_PSK_WITH_AES_128_CCM (0xC0A4), 16 byte key
IPv4 / UDP               169.254.0.2 -> 169.254.0.3, port 5684 both ways
GattLink                 1 byte header, PSN 0..31, ACK at half window or 200 ms
ATT / GATT               MTU 247, data on ABBAFF01 write, ABBAFF02 notify
BLE                      bonded link, 1 second connection interval in use
```

## Measured facts

| Fact | Value | How |
|---|---|---|
| Stack family | GoldenGate, not the older SLS / `adab` stack | capture shows IPv4 and DTLS |
| Link addresses | `169.254.0.2` client, `169.254.0.3` tracker | IPv4 headers in the capture |
| Transport | UDP, port `5684` both directions | UDP headers |
| Security | DTLS 1.2 (`FE FD`) with pre shared key | record headers, handshake |
| Cipher suites offered | `0xC0A4`, `0x00A8`, `0xC037`, plus `0xFF` SCSV | ClientHello bytes |
| Cipher suite picked | `0xC0A4` PSK-AES128-CCM | ServerHello bytes |
| DTLS client | the tracker, not the phone | see [docs/2](docs/2-how-the-link-works.md) |
| Key identity | 20 byte string `MD-<keyid>-<expiry>`, cleartext | ClientKeyExchange bytes |
| ATT MTU | phone asks 527, tracker grants 247, so 244 bytes of payload | ATT exchange MTU, and a Mac run |
| Largest UDP payload | 215 bytes, which is exactly 247 - 3 - 1 - 20 - 8 | frame sizes |
| Poll rate | 1 request per second, 293 pairs in 16.7 minutes | CoAP app data cadence |
| Sessions per connection | 3 DTLS sessions, one bootstrap plus two data | separate handshakes |
| GATT | 5 services, 23 characteristics | macOS CoreBluetooth enumeration |
| Readable without a bond | identity and status values | macOS probe |
| Mac as a second central | works, the tracker completes GattLink and opens DTLS toward the Mac | measured 2026-11 |
| Wrong key failure mode | `MBEDTLS_ERR_SSL_INVALID_MAC`, `-0x6300` | measured with a fake key |
| Public bootstrap key | completes DTLS on this device | measured with a patched reader |
| Bootstrap session authorizes | `GET /sync/dump` only, 33 to 39 KB of data | CoAP path sweep |
| Everything else over bootstrap | `4.01` on live resources, `4.04` on paths that do not exist | CoAP path sweep |
| Key location | BKS file in the app's private folder, plain, password protected | decompiled app |
| Public API for the key | none, 27 methods, 2 about devices, both metadata only | Google discovery documents |

## The wall

The DTLS layer uses a pre shared key. The key is 16 bytes and belongs to one tracker.
It is not on the air, not in the bootstrap session, and not in any public API.

| Path | Needs | Works |
|---|---|---|
| Decode the capture | a sniffer | protocol yes, plaintext no |
| Bare GATT probe | nothing | identity yes, then a half open handshake |
| Full stack on a Mac with the wrong key | an hour of building | invalid MAC, no data |
| Google Health API | OAuth with `googlehealth.settings.readonly` | device metadata only |
| Read the app's keystore | a rooted Android or a jailbroken iPhone | the actual key |

That last row is the only row that ends with a key. Everything else stops at the same wall
for the same reason. Public work reached the same conclusion; see
[docs/10-prior-art.md](docs/10-prior-art.md).

## Repo map

| File | Contents |
|---|---|
| [docs/1-the-short-version.md](docs/1-the-short-version.md) | the result, in one page, with numbers |
| [docs/2-how-the-link-works.md](docs/2-how-the-link-works.md) | every layer and its parameters |
| [docs/3-gatt-map.md](docs/3-gatt-map.md) | services, characteristics, properties, read values |
| [docs/4-packets.md](docs/4-packets.md) | byte layouts and an annotated handshake |
| [docs/5-keys.md](docs/5-keys.md) | the key chain, the keystore internals, the three doors |
| [docs/6-what-we-tried.md](docs/6-what-we-tried.md) | seven dead ends and what each one proved |
| [docs/7-reproduce.md](docs/7-reproduce.md) | commands to redo every measurement |
| [docs/8-app-internals.md](docs/8-app-internals.md) | the app's classes, resources and polling loop |
| [docs/9-open-questions.md](docs/9-open-questions.md) | what is still unknown, and what would settle it |
| [docs/10-prior-art.md](docs/10-prior-art.md) | who has already solved what, with links |
| [docs/11-crypto-notes.md](docs/11-crypto-notes.md) | the dump envelope, and why breaking it is not the way |
| [docs/12-bootstrap-session.md](docs/12-bootstrap-session.md) | the no-key session, its namespace map, and the dump it hands out |
| [tools/](tools/) | pklg parser, session decoder, CoreBluetooth probes, key extractor |

## If you only want the practical answer

The Inspire 3 can hand out heart rate once per second, but only to a client holding the
device key. A standard BLE heart rate overlay cannot use it, because the tracker does not
expose the standard Heart Rate service (`180D`). For a live overlay, use a chest strap or
a watch that broadcasts `180D`. For history and intraday minutes, the Google Health API
is fine.

## Licence

MIT.
