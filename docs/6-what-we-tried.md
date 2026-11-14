# 6. What we tried, and what each failure proved

A failure that teaches you where the wall is worth more than a guess. This page lists
every dead end so nobody repeats it.

## 1. Decode the pairing traffic and look for the key

**What was done.** Recorded a full pairing between an iPhone and the tracker. Decoded
the GattLink layer, found the DTLS handshake, and read the identity strings.

**What happened.** Three secure sessions per pairing. One called `BOOTSTRAP`, two
called `MD-<keyid>-<expiry>`. The bootstrap session decrypted with the public key. The
two data sessions did not, and the key was nowhere in the decrypted bootstrap bytes.

**What it proved.** The transport can be mapped by listening. The data cannot.

## 2. Try every 16 byte slice as the key

**What was done.** Took the decrypted bootstrap session, slid a 16 byte window across
all of it, 2,861 candidates, and tried each as the session key.

**What happened.** Every candidate failed.

**What it proved.** The key is not hiding in the pairing traffic in plain, shifted, or
re ordered form. This is the important negative result.

## 3. Use an Android emulator with the real app

**What was done.** Installed the real app on a rooted Android emulator, signed in, let
it sync. The emulator can be rooted because it is a developer build.

**What happened.** The app worked, pulled account data, and even showed the tracker in
its device list with battery level. The key file never appeared.

**Why.** The key is fetched on the way to a real Bluetooth connection. The emulator's
radio is fake and points at nothing. Tapping "sync" reached the Bluetooth check and
stopped there.

**What it proved.** Root alone is not enough. You need root on a device that can also
reach the tracker.

## 4. Bridge the Mac's radio into the emulator

There is a community project that gives the Android emulator real Bluetooth. It was
investigated and ruled out: it works by giving the app a library to call. Our app is
closed source and will never call that library. No good.

**What it proved.** Android's emulator has no transparent radio passthrough on macOS.

## 5. Connect from a Mac and read everything

**What was done.** Switched the phone's Bluetooth off so the tracker was free, then
connected from a Mac and asked for every service, every characteristic, and every
readable value.

**What happened.** Full access to identity data. Maker, model, firmware. Two status
values. Then the tracker accepted a subscribe, accepted a GattLink reset write, and
never sent a single notification.

**What it proved.** The data pipe only serves a bonded, registered phone. A laptop
cannot become one, because no value on the device demands a secure link, so pairing
never starts.

## 6. Ask Google's public API for the key

**What was done.** Read Google's published API description for the health API, both
stable and beta channels.

**What happened.** 27 methods. Two about devices. They return name, model, battery,
last sync, features, Bluetooth address. No key, ever.

**What it proved.** There is no permission to ask for, because the endpoint does not
exist. Please stop suggesting this one.

## 7. Use the older unauthenticated data characteristic

Older Fitbits have a live data characteristic that public notes say could be read after
a simple challenge. The Inspire 3 does not have it. No service `558dfa00`, no such
characteristic. Not applicable.

## Summary table

| Approach | Cost | Outcome |
|---|---|---|
| Bluetooth capture and decode | hours | protocol fully mapped, no key |
| Slice brute force | hours | confirmed the key is not present |
| Rooted emulator with real app | half a day | account data yes, key no |
| Mac central, full GATT | an hour | identity only, data pipe silent |
| Public API | minutes | no such endpoint |
| Rooted real phone that can pair | a phone | the only path that should work |
| Physical flash read of the tracker | risky | would work, destroys the device |

## The takeaway

If you want this data faster than the cloud, buy a device that streams it openly, or
use the cloud. If you specifically want to prove the tracker can be read locally, get a
cheap Android phone whose bootloader unlocks, because that is the only honest path.
