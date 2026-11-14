# What a Fitbit Inspire 3 says over Bluetooth

This repo explains, in plain English, how a Fitbit Inspire 3 talks to a phone over
Bluetooth. It is based on one person looking at one tracker they own, plus the
open source code Google publishes for that Bluetooth stack.

You do not need to be a Bluetooth expert to read this. Every hard word is explained
where it first appears.

## The short version

| Question | Answer |
|---|---|
| Can an app read the tracker directly, without the cloud? | Yes, but only with a secret key. |
| Does the tracker send live data once per second? | Yes. The phone app asks for it every 1 second during use. |
| Can anyone with a Bluetooth sniffer read that data? | No. All of it is encrypted on the link. |
| Is there any public way to get the secret key? | No. Not from Google's API, not from the air, not from the device. |
| Can you read anything at all without the key? | Yes. The tracker answers basic identity questions: maker, model, firmware. |
| What does the secret key actually guard? | The data channel. Everything else is open or useless. |

## How the research was done

1. Recorded the Bluetooth traffic between an iPhone and the tracker.
2. Took apart the Android app to see what it asks the tracker for.
3. Read the open source Bluetooth stack that Google publishes.
4. Connected a Mac straight to the tracker to see what a stranger can read.

The last step is the interesting one. It shows both what is open and exactly where
the lock is.

## What is in this repo

| File | What it covers |
|---|---|
| [docs/1-the-short-version.md](docs/1-the-short-version.md) | The whole story in one page |
| [docs/2-how-the-link-works.md](docs/2-how-the-link-works.md) | The layers, from radio to app data |
| [docs/3-gatt-map.md](docs/3-gatt-map.md) | Every service and setting the tracker offers |
| [docs/4-packets.md](docs/4-packets.md) | What the bytes look like |
| [docs/5-keys.md](docs/5-keys.md) | Where the keys live and why one is out of reach |
| [docs/6-what-we-tried.md](docs/6-what-we-tried.md) | The dead ends, and what each one proved |
| [docs/7-reproduce.md](docs/7-reproduce.md) | Step by step, if you want to check the work |
| [AGENTS.md](AGENTS.md) | Notes for AI agents working with this repo |
| [tools/](tools/) | The small scripts used to read captures and talk to the tracker |

## Three facts worth remembering

**The tracker is a small computer that speaks the internet.** It does not use normal
Bluetooth data channels. It runs an internet style link over Bluetooth, between two
made up addresses, `169.254.0.2` and `169.254.0.3`, on port `5684`. That is the same
port the CoAP protocol uses, and CoAP is a small cousin of HTTP.

**The encryption sits at the bottom, not the top.** The link is wrapped in a security
layer called DTLS. Everything above it is invisible without the key.

**The key comes from the cloud, not from the tracker.** The phone app asks Google's
server for the key. The tracker received the same key earlier. So reading the key
from the air is impossible, and reading it from the tracker needs hardware surgery.

## What this is not

This is not a tool to read other people's trackers. It is not a way around the
Google Health app. It does not include any real key, serial number, or account
detail. Device addresses and identifiers in these notes are shortened on purpose.

## Licence

MIT. Use it, quote it, fix it.
