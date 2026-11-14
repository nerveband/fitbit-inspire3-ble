# 1. The short version

A Fitbit Inspire 3 is a small tracker with no screen. It talks to a phone with
Bluetooth Low Energy, which people shorten to BLE. This page gives the whole result
before any detail.

## What the tracker does when a phone connects

1. It offers a short list of services. A service is a group of settings and channels.
2. Most of that list is boring identity data. Maker name, model number, firmware.
3. One service is the real pipe. It has two settings: one the phone writes into, and
   one the tracker sends data out from.
4. Above that pipe the tracker runs a small internet. Two fixed addresses, one port,
   normal internet packet headers.
5. On top of that it runs DTLS, a security layer. DTLS is the encrypted cousin of TLS,
   the thing that makes the little padlock in a browser work.
6. Inside DTLS it speaks CoAP. CoAP is a light version of HTTP for small devices.
7. Inside CoAP the phone asks for things by name, for example "live activity", and the
   tracker answers with a small binary record that includes heart rate.

## What the phone actually asks for

The Android app is not shy about it. The code asks for live activity every 1,000
milliseconds. That is once per second. Each answer holds a timestamp, steps, distance,
calories, floors, heart rate, and a confidence value for the heart rate.

So the tracker can hand out heart rate once per second. That part is not a rumour, it
is what the app already does.

## Where the wall is

DTLS with a pre shared key does one thing well: nothing above it can be read without
the key. This link uses exactly that mode. The key is 16 bytes and belongs to one
tracker.

Where does the key come from? The phone asks Google's cloud for it, using the person's
own login. The tracker was given the same key earlier, when it was set up. The key is
never sent over Bluetooth.

So there are only three ways to get it:

| Way | Result |
|---|---|
| Listen to the Bluetooth link | Impossible. The key is not in the air. |
| Ask Google's public API | Impossible. No such endpoint exists. |
| Read the phone's own storage | Possible, but the phone must be unlocked at the system level |

The third one is not a hack of the tracker. It is reading your own app's private file
on your own phone. That needs a rooted Android phone or a jailbroken iPhone.

## What is open, with no key at all

A stranger can connect to the tracker and read:

| Question | Answer from the tracker |
|---|---|
| Who made you? | `Fitbit` |
| Which model? | `63` |
| What firmware? | `63.<version>` |

That is it. Everything else either needs the key or stays silent. The data pipe accepts
writes from a stranger and never answers. It only talks to a phone it has bonded with,
and it only sends encrypted data after that.

## The one sentence summary

The tracker happily tells you what it is, refuses to tell you what it measured, and the
only shortcut around that refusal is reading the key out of your own phone.
