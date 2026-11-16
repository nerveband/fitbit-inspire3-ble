# 15. Health Connect, measured

Health Connect is Android's local health store. It is not a live stream, but it is the one health
channel on an Android phone that needs no root and no tracker key. This page records what was
measured on the test device and what it can realistically give.

## Measured on the Galaxy A15

Android 17, SDK 37.

| Check | Result |
|---|---|
| Health Connect controller | `com.google.android.healthconnect.controller`, version 17 |
| framework module | `com.google.android.overlay.modules.healthfitness.forframework` present |
| store state, `dumpsys healthconnect` | database version 26, **size 1308 KB**, so data exists |
| Google Health app (`com.fitbit.FitbitMobile`) | installed, and it **declares** `WRITE_STEPS`, `WRITE_HEART_RATE`, `WRITE_SLEEP`, `WRITE_OXYGEN_SATURATION` and many reads |
| grant state in `dumpsys package` | `granted=false` for those permissions |
| shell command | `cmd healthconnect` exists |

Two conclusions from that table. The store has about 1.3 MB of content. And the Fitbit app is the
kind of app that would be writing into it, though the platform level grant state is not where the
real answer lives: Health Connect permissions are user sensitive and their grants are tracked by
the Health Connect module, so `dumpsys package` is not a reliable read. Confirm in the Health
Connect UI, or by export.

## The shell command is not a reader

`cmd healthconnect` looks promising and is a test harness:

| Subcommand | What it does |
|---|---|
| `get-current-device-id` | device id |
| `advertise-device`, `advertise-current-device` | advertise a fake test device for the shell package |
| `insert-records`, `insert-current-device-records` | write step records for that fake device |
| `read-records` | read back **only** the shell package's own records |
| `delete-records` | delete those |
| `get-device-data-sources` | count of data sources for the shell package |

Measured:

```
$ adb shell cmd healthconnect get-device-data-sources
0
$ adb shell cmd healthconnect read-records
-1
```

So it cannot read another app's records. There is no adb path to the store without root, and even
root would only give you the underlying database file, which is not the useful interface.

## Freshness, and why it matters here

Where the data comes from decides how fresh it is. On the test device the tracker is paired to an
iPhone, so nothing on Android talks to the tracker:

```
tracker  ->  iPhone app  ->  Google cloud  ->  Android app  ->  Health Connect
```

Each hop adds delay, and the app writes when it syncs, which is periodic. Observed behaviour fits:
step counts on the Android side moved only after the iPhone had been used. Expect minutes to tens of
minutes, not seconds.

If the tracker were paired to the Android phone instead, the app would sync over BLE directly, the
last hop would become local, and fresh writes would follow the app's sync cadence. Order of a
minute or a few, still not 1 Hz.

One constraint: a tracker accepts a single Golden Gate owner at a time, so pairing Android displaces
the iPhone app until it is re-paired.

## How to poll it

| Method | What you get | Effort |
|---|---|---|
| Health Connect settings, "Export data" | a zip snapshot of everything, once | minutes |
| A small reader app | `getChanges` polling on a loop, JSONL out | an hour |
| adb or shell | nothing | closed |

A reader app needs four things:

1. `androidx.health.connect:connect-client` in the build.
2. Permission declarations: `android.permission.health.READ_STEPS`, `READ_HEART_RATE`,
   `READ_SLEEP` and the rest of what you want.
3. An activity with the permission rationale intent filter, because Health Connect requires a
   screen that explains the request before the system dialog appears.
4. The user granting each record type in the Health Connect permission sheet.

Then polling is two calls: `getChanges(token)` to learn what changed since last time, and
`readRecords` over a time window when you want the values.

## What Health Connect can and cannot give

| Can give | Cannot give |
|---|---|
| steps, distance, calories, heart rate, sleep, oxygen saturation, HRV, exercise sessions | anything faster than the writer's cadence |
| records with precise start and end times | raw sensor blobs |
| change notifications via `getChanges` | the tracker key, or the encrypted archive |

Compare with the other paths:

| Path | Granularity | Needs |
|---|---|---|
| Health Connect | the writing app's sync cadence, so minutes | nothing but an app with grants |
| Google Health API | 1 minute intraday | OAuth, and a scope Google approves |
| local BLE with the key | 1 Hz | root on one phone, once |

## Next time the phone is connected

Three read-only checks, in order:

1. `adb shell dumpsys healthconnect` for the store size, to see whether it is growing.
2. In the Health Connect UI, Data and access, note whether **Health** appears and with which data
   types. That screen is the ground truth on grants.
3. If it is listed, run the export and inspect the zip: record types, fields, timestamps, gaps.

Step 3 tells you whether a reader app is worth building, and it costs nothing.
