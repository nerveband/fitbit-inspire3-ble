# 11. The historical dump envelope, and whether it can be broken

Short answer: no, not by attacking the cipher. The realistic way in is to get the plaintext
where it already exists, and that is on the tracker and on Google's backend, not on the wire.

## What is actually known about the envelope

`GET /sync/dump` returns a body that is **already encrypted by the tracker** before DTLS ever
wraps it. Two independent observations, ours and airLocal's:

| Observation | Value |
|---|---|
| First bytes | `03 04 00 00 02` |
| Prefix before ciphertext | 21 bytes, empirical |
| Remainder length | always a multiple of 16 |
| Inner format | not decoded publicly |

21 bytes is an odd size, which hints at structure rather than a plain IV. Two readings fit:

1. A 5 byte header plus a 16 byte IV, then ciphertext blocks in CBC
2. A 21 byte header where the IV sits at some offset inside it

Nobody has published which. What the shape rules out is a stream cipher or plain
compression: a length that is always a multiple of 16 with a fixed prefix says block cipher
with a block-aligned body.

Separately, airLocal confirmed the envelope does **not** decrypt with the mobile data key. So
it is a second key, not the transport credential.

## Why "breakable" is the wrong frame

| Attack | Verdict |
|---|---|
| Brute force the key | no. AES-128 has 2^128 keys. At 10^12 keys per second that is about 10^19 years |
| Known plaintext attack | no. Steps and heart rate are low entropy, but that is exactly what modern ciphers are designed to resist |
| Frequency analysis | no. It only bites on ECB over long runs of repeated data, and even then needs repeated blocks |
| Statistical or algebraic shortcut on AES | no. There is no practical one |
| Differential power analysis | needs the physical chip while it decrypts, so it destroys the tracker |

So the answer to "would a block cipher be breakable" is: a sound block cipher, with a random
key, in a mode that is not catastrophically wrong, is not breakable by any amount of
compute a person can rent. That is the design goal, and it holds here.

## The attack classes that do sometimes work

Worth listing, because "not breakable" is not the same as "nothing can go wrong".

**One: find the key.** Best odds by a wide margin. The key is somewhere in the tracker
firmware, in the app, or in a backend response. A hook on the right function, or a flash
read, ends the problem. This is how the DTLS key was obtained too.

**Two: an unauthenticated mode.** If the envelope is CBC with no MAC, then flipping bytes in
ciphertext block N corrupts block N and changes block N+1 in a predictable way. If a tampered
body were accepted, a value like step count could be rewritten without knowing the key. This
is the classic bit flipping attack, and it is the only cipher-level trick that applies.

The reason to doubt it here: airLocal observed tracker challenge verification and commitment
fields after a backend response. That pattern suggests integrity is checked, which closes the
trick. It is not proven either way.

**Three: a padding oracle.** Works only if something decrypts attacker chosen ciphertext and
leaks whether the padding was valid. A cloud upload endpoint that returns one generic error
gives no signal. Also a bad idea for reasons outside crypto.

**Four: a weak or shared key.** If the envelope key were derived from the serial number, or
shared across all devices, someone would have published it by now. The fact that no public
work decodes historical dumps after years of people trying is weak evidence that the key is
per device and strong.

## Where the plaintext actually exists

Follow the data and the interesting boundary is obvious:

| Stage | Where | Plaintext |
|---|---|---|
| Tracker flash | inside the device | yes |
| Tracker to phone over DTLS | the air | no, encrypted once by the tracker, then again by DTLS |
| CoAP body on the phone | app memory | no, still the tracker's envelope |
| Upload to the backend | internet, TLS | no |
| Backend decode | Google servers | yes |
| Backend reply, cached as `cache/sync-*.bin` | phone storage | **yes** |

So the plaintext does reach the phone, but only after the backend has decoded it. That is
the place to look, and it needs a real sync with a real account, plus a hook on the response
path. airLocal's own notes list this as remaining research, so it is not done in public
either.

## Practical conclusion

| Goal | Route |
|---|---|
| Live data at 1 Hz | solved. DTLS key, then `GET /liveactivity` on a Mac |
| Historical data, own account | hook the app where decoded backend responses land |
| Historical data, no backend | needs the envelope key, which nobody has published |
| Break the envelope by force | not a thing |

The lesson from this project is the same twice over. The cryptography is fine. The weak
point is where the key is stored, and the phone holds it in a plain file.

## Related

- [5-keys.md](5-keys.md) for where the transport key lives
- [10-prior-art.md](10-prior-art.md) for who has done what already
- [9-open-questions.md](9-open-questions.md) for the questions this does not answer
