# 14. No-root options, and why each one fails

A shared premise worth correcting: the mobile data key lives in a file that only root can open, so
any claim of a rootless shortcut needs a specific mechanism. This page tests each candidate and
records the answer.

## The gate, in one line

The key sits in the app's private directory, so the question is never "can we read a file", it is
"can an unprivileged process make a privileged one hand it over". Everything below is an attempt
at that second question.

## Candidate 1: `am dumpheap` on the live app

**The claim.** `am dumpheap <pid> <path>` runs in `system_server`, so it is not limited by the app's
sandbox, and a `SecretKeySpec` holding the raw key would land in the HPROF.

**Why it fails.** The shell command reaches the app, but the app's runtime is the part that
refuses. Capacities are gated by the target's own manifest flags, not by the caller's privileges:
heap dumps are allowed for a **debuggable** or **profileable** process. Measured on the app:

| Manifest attribute | Value |
|---|---|
| `android:debuggable` | absent, so false |
| `android:profileable` | absent, so false |
| `android:allowBackup` | false, so `adb backup` is closed too |
| `android:extractNativeLibs` | false |
| `android:usesCleartextTraffic` | false |

So the dump is refused before the key is ever a question. Two further problems even if it worked:
the key is only resident during a handshake, and a modern app produces a heap dump in the
hundreds of megabytes to gigabytes range.

**Cost to falsify.** One command, thirty seconds. Run it on any installed app, read the error.

## Candidate 2: re-provision instead of extracting

**The claim.** The store is just a cache of cloud-provisioned keys, so pair the tracker somewhere
easier and capture the fresh key.

**Why it fails.** Pairing writes another copy into another app's private directory. The tracker
announces `MD-<key id>-<expiry>` and never sends the key, so re-pairing moves the wall, it does not
remove it. The only version of this idea that works is "pair on a phone you can read", which is the
root path with extra steps.

## Candidate 3: downgrade the app

**The claim.** Install an older build with `adb install -d`, keeping data, and hope it logged the
key or had a looser component.

**State of the evidence.** Two builds were decompiled, 4.44.2 from June 2025 and 5.12.1 from
November 2026. Both use the same BKS store, the same password recipe, the same resolver, and neither
logs key material. A downgrade also risks the app's own integrity checks. Cheap to try on a spare
device, low expected value.

## Candidate 4: an exported component

**The claim.** If the app exposes a provider or service without a permission, another app can call
it and ask for data.

**Measured, offline, on the 5.12.1 manifest:**

| Item | Count |
|---|---|
| components | 114 |
| exported | 40 |
| exported with no permission declared | 29 |
| providers | 6, all `exported: false` except one |
| that one provider | `com.fitbit.platform.externalapp.ExternalAppsRequestContentProvider`, flag omitted, so it defaults to false at modern target SDKs |

The exported set is activities and services for deep links, Fast Pair, Wear, and notification
handling. None of them serve the key store. The one provider whose name suggests it talks to other
apps is the one worth confirming on a device with `dumpsys package`, and its default is already
closed.

So the component surface is not a route to the key. It is a route to at most a deep-link screen.

## Candidate 5: ask the cloud

`BowieApi.fetchKey` is `GET user/-/devices/device/{encoded-id}/keys.json`, so the endpoint exists.
It needs the app's own authenticated session, and those credentials also live in the app's private
storage. Same wall, one layer up.

## Candidate 6: Read the key off the tracker instead

The tracker holds it in protected flash, and the dump it hands out is encrypted with a different
key. Covered in [11-crypto-notes.md](11-crypto-notes.md).

## Candidate 7: Health Connect

Correct that it needs no root. Wrong for the key. It is a real but separate path for data, measured
and written up in [15-health-connect.md](15-health-connect.md).

## Verdict

| Candidate | Rootless | Gets the key |
|---|---|---|
| `am dumpheap` | yes, but gated | no |
| re-provision | yes | no |
| downgrade | yes | unproven, unlikely |
| exported component | yes | no |
| cloud endpoint | yes | no, needs app tokens |
| tracker side | no | no |
| Health Connect | yes | no, data only |
| read the app's store | no | yes |

Anything that actually yields the key involves reading another app's private storage, and that is
root, or a memory-safety bug in Android itself. If a rootless route exists, it will be a bug, not a
configuration.

## If you want to hunt that bug anyway

Order by cost, not by ambition:

| Target | Why | Effort |
|---|---|---|
| `ExternalAppsRequestContentProvider` state on a live device | cheapest open question, one `dumpsys` line | minutes |
| the app's own exported services | userland, crashes point at the bug | days |
| the app's parsers, fed over its own deep links and intents | userland | days to weeks |
| the kernel, from shell | months, and a panic costs you the session | research grade |

The last row is the expensive one. It is also the one that requires a working corruption oracle
before any result means anything.
