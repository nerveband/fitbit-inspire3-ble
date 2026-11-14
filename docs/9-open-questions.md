# 9. Open questions

Each item states what is unknown, why it matters, and what evidence would settle it. None
of these are answered by guessing.

## 1. Does key provisioning require a passing attestation?

**Why it matters.** If the pairing flow demands Play Integrity, a rooted phone with hidden
root may still fail at the step that writes the key store. That decides whether the
rooted phone plan works.

**Evidence that exists.** The app calls `POST v1/devices/attest` before
`PUT v1/devices/register`, and ships the standard `Build.TAGS` check. On a rooted emulator
the app signed in and synced, so the check did not block normal use.

**What would settle it.** A rooted phone that passes or fails the attest call, with the
device log at `v1/devices/attest`, plus the keystore file appearing or not appearing.

## 2. Is the key provisioned at pairing time or at first data session?

**Why it matters.** It changes the requirement: one pair, or one successful encrypted
session.

**Evidence that exists.** The key id has an expiry about a year out, which fits a
provisioned credential with a refresh cycle. `BowieKeyData` carries key material plus an
expiry. The store is written by id.

**What would settle it.** Watch the app's file directory while pairing a tracker on a
rooted phone. If the file appears before any encrypted traffic, it is provisioning time.

## 3. What is the `4EEE1C00` service for?

**Why it matters.** Seven characteristics with mixed properties is a lot of surface to
ignore. It may be a debug channel, a log, or a firmware path.

**What would settle it.** Subscribe to `4EEE1C04`, `4EEE1C05` and `4EEE1C06` during a sync
from a bonded phone and see whether anything arrives.

## 4. What is `AC2F0045` for?

**Why it matters.** One read and one write, no traffic during sync. A test or factory hook
would be interesting.

**What would settle it.** Read the value on a bonded link, and try a write of a known
pattern with the phone's Bluetooth off, watching for a side effect such as a vibration.

## 5. Does the tracker accept a second bonded central?

**Why it matters.** If it does, a rooted phone could pair once, the key could be extracted
once, and a laptop client could then hold its own bond and poll locally.

**Evidence that exists.** An unbonded Mac gets silence, but it never bonded, so this is not
the same experiment.

**What would settle it.** Bond a Mac to the tracker with the phone's Bluetooth off, send the
GattLink reset, and watch for a ClientHello. A single notification would answer the
question.

## 6. Can the 215 byte MTU limit be raised?

**Why it matters.** A larger MTU means fewer round trips on a bulk dump.

**Evidence that exists.** The phone asks for 527 and the tracker grants 247, which looks
like a firmware cap, not a negotiation failure.

**What would settle it.** Ask for 517 from a bonded client and read the granted value. If it
is still 247, the cap is fixed.

## 7. How long does an expiry give?

**Why it matters.** A key that expires needs a refresh path, and an offline client would
stop working at the expiry instant.

**Evidence that exists.** The expiry field is 8 hex characters, so seconds since 1970, and
one observed value sat about a year out.

**What would settle it.** Two captures a few months apart, on the same tracker, comparing
the expiry field.

## 8. Does the bootstrap session carry the key in any encoded form?

**Why it matters.** It is the last unchecked assumption before accepting that the key only
arrives from the cloud.

**Evidence that exists.** 2,861 slices of the decrypted bootstrap session failed as keys.
That rules out a plain copy, not an encoded one.

**What would settle it.** Decode every field of the bootstrap session with the open source
framing and see whether any field is the right length and shape for key material. If the
bootstrap flow never carries key bytes, the cloud claim is closed.

## How to record an answer

When one of these gets resolved, put the measurement in the doc that covers the area, add
the number to the tables, and add a line to [6-what-we-tried.md](6-what-we-tried.md) if the
result is a dead end. Do not replace an open item with a guess.
