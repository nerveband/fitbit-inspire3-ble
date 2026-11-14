# 8. Inside the app

Facts below come from the decompiled Google Health app, version 5.12.1, package
`com.fitbit.FitbitMobile`. Class names that still read as prose are the real names, such
as `MobileDataTlsKeyResolver`. Names like `xjl` and `pbz` are obfuscated and were kept as
they are so a reader can find the same file.

## Shape of the app

| Part | What it is |
|---|---|
| Kotlin and Java app | the UI, the network calls, the storage |
| `libxp.so` | the GoldenGate C stack, the same code as the open source repo |
| `com.fitbit.goldengate.bindings` | JNI glue between the two |
| Native libs shipped | `libxp.so`, plus media and image helpers |

## Module map

Directory listing under `com/fitbit/goldengate/`:

| Package | Contents |
|---|---|
| `dtls` | the key resolver that answers the tracker's PSK identity |
| `bindings` | JNI wrappers, plus the public `TlsKeyResolver` base class |
| `coap` | CoAP resources and the endpoint mapper |
| `commands` | connect, pair, dump, GPS and live data handlers |
| `megadump` | the bulk sync resource, `CoapMegadumpDeviceResource` |
| `sync` | `CoapSyncConfigResource`, `CoapSyncStatusResource`, `BackgroundSyncHandler` |
| `bond` | `BondCommandsHandler`, `CoapBondControlResource`, `PeripheralBondCreator` |
| `mobiledata` | converters between mobiledata, protobuf and TLV |
| `node`, `bt`, `peripheral` | node keys, GATT plumbing |
| `tlv`, `protobuf`, `utils` | encoding helpers |
| `wifi`, `filetransfer`, `hub`, `notifications` | other GoldenGate features |

## The DTLS callback, which proves the phone is the server

```java
public final class MobileDataTlsKeyResolver extends TlsKeyResolver {
    public byte[] resolveKey(NodeKey<?> nodeKey, byte[] identity) {
        if (!MobileDataTlsKeyIdExtKt.isMobileDataTlsKeyId(identity)
            || !(nodeKey instanceof BluetoothAddressNodeKey)) {
            return null;
        }
        return mobileDataKeyProvider.b(toMobileDataTlsKeyId(identity).getKeyId());
    }
}
```

Read that twice. The app receives an identity from the peer, checks its shape, checks that
the peer is a Bluetooth address, and returns the key for the id. That is the server side of
a pre shared key handshake, and the peer that supplies the identity is the tracker. This is
the code that confirms the tracker opens the session.

The identity check is strict, and it is written byte by byte
(`MobileDataTlsKeyIdExtKt`):

| Condition | Value |
|---|---|
| total length | 20 bytes |
| byte 0 | 77, `M` |
| byte 1 | 68, `D` |
| byte 2 | 45, `-` |
| byte 11 | 45, `-` |
| key id | hex of bytes 3 to 10, parsed as a long |
| expiry | hex of bytes 12 to 19, parsed as a long |

So the identity string is a routing label. The phone does not need to know which tracker is
calling. It needs the address and the id, and it looks the key up.

The lookup ends in `qpt.b(long)`, which returns the key bytes from the local key store.

## The poll loop

```java
// LiveDataCommandsHandler.readLiveData
new OutgoingRequestBuilder("liveactivity", Method.GET).maxResendCount(0);

// LiveDataCommandsHandler:169
bxlk.interval(1000L, TimeUnit.MILLISECONDS, scheduler);
```

One request per second, no resend on loss. The response body is parsed with
`LiveActivity.Activity.parseFrom(byte[])` and converted with `LiveDataConverter`. So a
missing poll costs one sample, and the next sample comes 1 second later. That is why the
protocol tolerates a lossy link without any retry logic of its own.

## The key store

```java
// xjl.<init>
this.a = "BKS";
this.c = "MobileDataKeyManagerKeyStore.keystore";
this.b = (Settings.Secure.getString(cr, "android_id") + str + Process.myUid()).toCharArray();

// pbz
keyStore.getKey(String.valueOf(keyId), password);
keyStore.setKeyEntry(String.valueOf(keyId), secretKey, password, null);
```

| Detail | Value |
|---|---|
| Store type | BKS |
| File | `MobileDataKeyManagerKeyStore.keystore`, in the app's files directory |
| Alias | the key id as a decimal string |
| Password | `android_id` + mobile data instance id + uid, as chars |
| Entry | a `SecretKey`, no certificate chain |

BKS is a plain Java key store. Given the file and the password, any library can open it.
`pyjks` does, which is what `tools/extract_mobile_data_key.py` uses. None of this is in
hardware, so root on Android is enough.

## Where the keys come from

| Path | Definition | Used |
|---|---|---|
| `BowieApi.fetchKey` | `GET user/-/devices/device/{encoded-id}/keys.json` returns `BowieKeys` | defined, zero call sites in 5.12.1 |
| cached device record | `user/-/devices/device/<id>` includes a `keys` array | yes, this fills the store |

`BowieKeys` holds a config of key entries, each with an id, key material and expiry. Since
`fetchKey` has no caller in the decompiled sources, the keys arrive inside the device
record that the app already caches for the device list.

That matters for anyone planning a rooted phone: the phone needs an account with the
tracker already paired on the account, and it needs one real Bluetooth session so the app
writes the store.

## Pairing, and a check worth knowing about

The pairing flow contains an attestation service:

| Call | Endpoint |
|---|---|
| attest the phone | `POST v1/devices/attest` |
| register the tracker | `PUT v1/devices/register` |
| tie tracker to user | `PUT v1/affiliation/user/-/device/{wireId}?useProtobufResponse=true` |

`registerDevice` returns a protobuf with one string field, so it is a registration
identifier, not key material.

The app also ships the standard Play Integrity sample logic: it compares the caller
signature against known Google hashes and checks `Build.TAGS` for `test-keys`. On a rooted
emulator the app still signed in and synced account data, so this check did not block the
app during the test. Whether the pairing step that provisions the key store requires a
passing attestation is not known. Treat it as the main risk for a rooted phone plan, and
test with the account already holding the paired tracker.

## The app never decrypts the stored archive

This matters for anyone hoping to read history without the tracker key. The upload path in
`sbe.java` and `qsb.java`:

| Endpoint | Purpose |
|---|---|
| `devices/client/tracker/data/pair` | body encoded, sent with a pairing token |
| `devices/client/tracker/data/validate` | validation |
| `devices/client/tracker/data/sync` | the dump upload |
| `devices/client/tracker/data/ack` | acknowledgement with `ackToken` |

The body leaves the app as an encoded blob, `base64` or `hex` according to the
`Device-Data-Encoding` header, built by a small enum (`sbd`) with exactly those two values. There
is no decrypt call on that path, and no key is passed to it.

The `challengesRun` and `challengeResults` fields look like cryptography and are not. They are
counts of sync validation outcomes, from an enum `scj` whose values are `APP_BACKOFF`,
`SYNCLAIR_BACKOFF`, `MOBILETRACK_BACKOFF`, `RATE_LIMIT`, `INVALID_TIME_STAMP`,
`OATH_ACCESS_TOKEN`, `VALIDATION`, `SERVER_RESPONSE`, `NOT_LINKED_TRACKER`,
`DEVICE_IMPAIRED`. That is telemetry about why a sync was retried.

The AES code that does exist in the app belongs to other features: `jii` wraps a data source in
`AES/CBC/PKCS7Padding` and is constructed by `jit`, a class with `uri` and `drmInitData`, so it
is media decryption. Others are Android key store helpers and library internals.

Conclusion: the plaintext of a stored archive exists on the tracker and on Google's backend, and
nowhere in the app. Hooking the app gives you the ciphertext, unless you catch the moment a
backend reply is cached.

## Things that looked useful and were not

| Item | Why not |
|---|---|
| `BowieApi.fetchKey` | no call site, so it is not the live path |
| the emulator | rooted, but no radio, so no peer to provision a key for |
| `SpecialMtuHandlingRequiredChecker` | a compatibility fix for specific phones, no data path |
| `4EEE1C00` service | no traffic during sync |

## How to check any claim on this page

```
jadx -d jadx_out app.apk
grep -rn "MobileDataTlsKeyResolver\|MobileDataTlsKeyIdExtKt" jadx_out/sources
grep -rn "MobileDataKeyManagerKeyStore" jadx_out/sources
grep -rn "interval(1000L" jadx_out/sources
grep -rn "fetchKey" jadx_out/sources
grep -rn "v1/devices/register" jadx_out/sources
```

Each grep lands on one file, and each file is short. That is the whole method: read the
callback that touches the key, and read the loop that sets the rate.
