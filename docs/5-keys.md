# 5. Keys: where they live and why one is out of reach

There are three different secrets in play. Two are public. One is not, and that one is
the whole story.

## Secret one and two: the shop keys

Every copy of the Fitbit app, on every phone, ships with two keys:

| Name | Who uses it | Public? |
|---|---|---|
| `hello` | a self test during development | yes, in the open source repo |
| `BOOTSTRAP` | the first secure session during pairing | yes, in the open source repo |

They are in the GoldenGate repo, files `HelloTlsKeyResolver.kt` and
`BootstrapTlsKeyResolver.kt`, Apache 2.0. Anyone can read them. They are the same in
every install, so they are not really secrets.

`BOOTSTRAP` is how a brand new tracker and a brand new phone say hello safely. It lets
the two sides swap public keys and prove who they are, and it is the moment the per
device key can be agreed.

## Secret three: the per device key

This one is 16 bytes, different for every tracker, and it guards the actual data.

Facts, all checked:

| Fact | How it was checked |
|---|---|
| It never crosses the Bluetooth link | a full pairing capture was searched for it |
| It is not hidden in the bootstrap session | every 16 byte window of that session was tried as a key and all failed |
| The app asks Google's cloud for it | the app code calls a device keys endpoint |
| Google's public API does not offer it | the API has 27 methods, none returns a key |
| The tracker has its own copy | otherwise it could not decrypt what the phone sends |

## Where the phone keeps it

On Android the Google Health app puts the key in a small key store file in its own
private folder. This is not the hardware protected Android key store. It is a plain
file with a password:

| Detail | Value |
|---|---|
| File name | `MobileDataKeyManagerKeyStore.keystore` |
| File type | BKS, a Java key store format |
| Entry name | the key id as a decimal number |
| Password | phone id plus an app instance id plus the app's user number |

That matters because a plain file with a password can be opened by anyone who can read
the file and the password. On Android that means root. No chip level trickery, no
hardware key store barrier.

On iOS the same key sits in the phone keychain, which needs a jailbreak to read.

## Why the cloud will not hand it over

This was checked properly, not guessed. Google publishes a machine readable list of
everything their health API can do. Both the stable and the beta channel have 27
methods. The only two about devices are:

| Method | Returns |
|---|---|
| list paired devices | name, model, battery, last sync, features, Bluetooth address |
| get one paired device | the same fields for one device |

No key. No secret. No provisioning call. So this is not a permission problem, it is a
designed absence. The key belongs to the app, not to the API.

## Why the tracker will not hand it over

The tracker holds the key in its own memory. Reading it would mean taking the tracker
apart and reading the flash chip. That is possible in principle, and was done on 2015
era Fitbits with no read protection. It has not been publicly done on current models.
It also destroys the tracker, which is not a good trade for a step counter.

## Why the open source stack does not help

GoldenGate is Apache 2.0. The framing, the ACKs, the CoAP layer, the cipher suite name,
all readable. Having the code is not the same as having the key. This is the point
people miss: the protocol being open does not make the data open, because the security
is one shared secret sitting outside the protocol.

## The only three doors

| Door | Needs | Result |
|---|---|---|
| Rooted Android phone that the app runs on | a phone with an unlockable bootloader | key readable from a file |
| Jailbroken iPhone | a jailbreak | key readable from the keychain |
| Hashed out by hand | nothing | no, the key is not derivable |

Everything else, sniffing, cloud APIs, protocol knowledge, cleverness, stops at the same
wall. That is not pessimism, it is what three separate experiments showed. See
[6-what-we-tried.md](6-what-we-tried.md).
