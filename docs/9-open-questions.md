# 9. Open questions

Each item states what is unknown, why it matters, and what evidence would settle it. Items
that public work has since closed are marked, with a link to
[10-prior-art.md](10-prior-art.md).

## 1. Does key provisioning require a passing attestation?

**Why it matters.** If the pairing flow demands Play Integrity, a rooted phone with hidden
root may still fail at the step that writes the key store.

**Evidence that exists.** The app calls `POST v1/devices/attest` before
`PUT v1/devices/register`, and ships the standard `Build.TAGS` check. A rooted emulator
signed in and synced, so the check did not block normal use.

**Narrowed by public work.** airLocal exported a working key from a rooted phone with the
app already signed in and the tracker already paired. That is the case that matters here: a
phone that has the tracker on its account. So for this route, attestation does not appear to
be the blocker. Marked as narrowed, not closed, because a fresh pairing on a rooted phone
was not documented by them either.

## 2. Is the key provisioned at pairing time or at first encrypted session?

**Why it matters.** It changes the requirement: one pair, or one successful encrypted
session.

**Evidence that exists.** The key id carries an expiry about a year out, which fits a
provisioned credential with a refresh cycle. The store is written by key id. airLocal's
bootstrap guide says initial provisioning must be complete before the key can be exported,
which points at pairing or first sync.

**What would settle it.** Watch the app's file directory while pairing a tracker on a rooted
phone. If the file appears before any encrypted traffic, it is provisioning time.

## 3. What is the `4EEE1C00` service for?

**Why it matters.** Seven characteristics with mixed properties is a lot of surface to ignore.

**What would settle it.** Subscribe to `4EEE1C04`, `4EEE1C05` and `4EEE1C06` during a sync
from a bonded phone and see whether anything arrives.

## 4. What is `AC2F0045` for?

**Why it matters.** One read and one write, no traffic during sync.

**Narrowed.** The stack log calls the `AC2F2745` value the "ephemeral characteristic", which
fits a per connection value. Role still unconfirmed.

## 5. Does the tracker accept a second bonded central?

**Closed: yes.** Measured on this device. A Mac with the full open source stack connected, the
tracker completed GattLink and opened DTLS toward the Mac. airLocal went further and completed
the whole bonding sequence, including `PUT /bond/control` with `08 78` and verified link
encryption, then read `/liveactivity` with the phone switched off. See
[6-what-we-tried.md](6-what-we-tried.md) item 5b and
[10-prior-art.md](10-prior-art.md).

The remaining limit is that the tracker accepts only one Golden Gate owner at a time, so the
app and a local client must take turns.

## 6. Can the 215 byte MTU limit be raised?

**Why it matters.** A larger MTU means fewer round trips on a bulk dump.

**Evidence that exists.** The phone asks for 527 and the tracker grants 247. The stack IP MTU
is 1280, so the limit is the ATT layer, not the stack.

**What would settle it.** Ask for 517 from a bonded client and read the granted value. If it
is still 247, the cap is fixed in firmware.

## 7. How long does an expiry give?

**Why it matters.** A key that expires needs a refresh path, and an offline client would stop
working at the expiry instant.

**Evidence that exists.** The expiry field is 8 hex characters, seconds since 1970. One
observed value sat about a year out, and the tracker offered the same key id and expiry
across an iOS capture and a Mac run weeks apart.

**Also useful.** airLocal's resolver matches the identity **by key id only** and ignores the
expiry suffix. So an expired suffix still resolves if the key is present, which suggests the
expiry is enforced elsewhere or not at all. That needs a test to confirm.

## 8. Does the bootstrap session carry the key in any encoded form?

**Why it matters.** It was the last hope of skipping the per device key.

**Closed, with a twist.** Measured on this device. DTLS completes with the **public** bootstrap
key. Live resources return `4.01`, but `GET /sync/dump` returns `2.05` with 33 to 39 KB of
stored data. So bootstrap authorizes the encrypted archive and nothing live. Map and dump
layout in [12-bootstrap-session.md](12-bootstrap-session.md).

**Still open from this.** What makes the tracker offer `BOOTSTRAP` rather than
`MD-<key id>-<expiry>`? Both were observed on the same Mac, in the same hour.

## 9. New: can the historical dump envelope be opened without the backend?

**Why it matters.** It is the difference between live local data and a full local archive.

**Evidence that exists.** A 21 byte prefix, a body length that is always a multiple of 16, and
no decryption with the transport key. Analysis in [11-crypto-notes.md](11-crypto-notes.md).

**What would settle it.** Either the envelope key, found in firmware or in a backend request,
or a hook where a decoded backend response lands in the app's cache.

## How to record an answer

When one of these gets resolved, put the measurement in the doc that covers the area, add the
number to the tables, and add a line to [6-what-we-tried.md](6-what-we-tried.md) if the result
is a dead end. Do not replace an open item with a guess.
