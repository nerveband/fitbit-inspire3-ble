# 5. Keys: the chain, the storage, the three doors

Three secrets exist. Two are shipped in every copy of the app. One is different for every
tracker, and that one closes the data.

## The two shop keys

Both are in the Apache 2.0 GoldenGate repo, in
`platform/android/goldengate/GoldenGateBindings/src/main/kotlin/com/fitbit/goldengate/bindings/dtls/`:

| Resolver | Key | Purpose |
|---|---|---|
| `HelloTlsKeyResolver` | fixed test key | a development self test |
| `BootstrapTlsKeyResolver` | fixed bootstrap key | the first secure session during setup |

Both are identical on every install. Anyone can read them from the repository. They are
not secrets in any useful sense.

The bootstrap key is how a new tracker and a new phone establish a session before the per
device key exists. During setup, the tracker and the phone use it to exchange enough
information to provision the real key, which is the part that is not public.

## The per device key

16 bytes, one per tracker, and it is what the data session uses.

| Claim | Evidence |
|---|---|
| It is not on the Bluetooth link | searched the whole capture for it, and for a shifted copy |
| It is not inside the bootstrap session | 2,861 candidate slices of that session were tried, all failed |
| The app gets it from the cloud | `BowieApi.fetchKey` and the device keys endpoint exist in the app |
| The public API will not give it | 27 methods, no key endpoint |
| The tracker holds a copy | it decrypts what the phone sends, so it must |
| The phone holds a copy | it must answer the handshake, so it must |

Note the direction: the tracker opens the secure session and presents its key id. The
phone resolves that id to a key. So the phone must hold the key before the tracker
connects, which is why the app keeps a store indexed by key id.

## The store, on Android

From the decompiled app, version 5.12.1.

| Item | Value | Where |
|---|---|---|
| Type | `BKS`, a Java key store format | `xjl.<init>`, field `a` |
| File name | `MobileDataKeyManagerKeyStore.keystore` | `xjl.java:93` |
| Location | the app's private files directory | `Context.getFilesDir` |
| Entry alias | the key id as a decimal string | `pbz.java:54`, `b` method |
| Entry value | a `SecretKey`, no certificate chain | `pbz.java:54`, `setKeyEntry(alias, key, password, null)` |
| Password | `Settings.Secure android_id` plus the mobile data instance id plus `Process.myUid()` | `xjl.java:93` |

That password recipe is the weak point, and it is the reason root helps. `android_id` is
readable, the instance id is in app storage, the uid is a small number. None of it is in
hardware. A BKS file with a known password opens with any Java key store library.

The store is filled from the device record the app already caches from the cloud:
`user/-/devices/device/<id>` returns a `keys` array, and the app writes each entry by id.

`BowieApi.fetchKey` exists in the code but has no live call site in 5.12.1. It is dead
code, or a fallback that never runs. Do not plan around it.

## The store, on iOS

The same key lives in the app's keychain item. Reading it needs a jailbreak, or a
keychain dump from a backup, which modern iOS does not allow for this kind of item.

## Why the public API cannot supply it

Google publishes a machine readable description of the Health API. Both channels:

| Channel | URL |
|---|---|
| v4 | `health.googleapis.com/$discovery/rest?version=v4` |
| v4beta | `health.googleapis.com/$discovery/rest?version=v4beta` |

Both list 27 methods. Two concern devices:

| Method | Scope | Returns |
|---|---|---|
| `users.pairedDevices.list` | `googlehealth.settings.readonly` | name, model, battery, last sync, features, Bluetooth address |
| `users.pairedDevices.get` | `googlehealth.settings.readonly` | the same for one device |

No method returns a key, a secret, or a provisioning token. This is not a permission
problem that a broader scope would solve. The capability is absent.

## Why the tracker will not supply it

The key is in the tracker's memory. Reading it means reading the flash chip, which means
opening the case, and on current models it likely means defeating read protection. It was
done on 2015 era Fitbits. There is no public report of it on an Inspire 3, and the attempt
destroys the tracker.

## The three doors

| Door | Requirement | Effort | Result |
|---|---|---|---|
| Rooted Android that has the app signed in and the tracker paired | an unlockable bootloader | hours | key readable from a file |
| Jailbroken iPhone | a working jailbreak for that iOS version | hours | key readable from the keychain |
| Anything else | none | any | no key |

There is no fourth door. The protocol being open source does not help, because the
security is one shared secret that sits outside the protocol.

## What the key unlocks, and what it does not

With the key you can decrypt the DTLS session and read or replay CoAP. That gives live
activity, sync dumps, and control requests, all local, at the native rate.

With the key you cannot read another person's tracker, because each tracker has its own
key, and you cannot read the account, because account data goes over the internet, not
over Bluetooth.

## Handling the key

If you extract a key: it is a credential for one device. Keep it out of git, out of logs,
and out of any note you publish. If it leaks, the tracker can be read by anyone in radio
range who also has the framing, which is public.
