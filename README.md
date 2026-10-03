# vr-student-app

A working demo of **VR classroom supervision**: the teacher sees, live, which app each student has open in their headset and what they searched — without the student ever knowing they are being watched.

The surveillance is silent. The enforcement is not.

## The idea

The student puts on a headset and uses it normally. No branding, no status bar, no indication anything is happening. Every app they open and every search they run is quietly streamed to the teacher's laptop on a heartbeat.

`vr-guardian` only ever *surfaces* at the moment of restriction — a **БАГШ ТҮГЖЛЭЭ** (teacher forbade) banner, the app closes itself, the tile greys out, the search comes back refused. That moment is the whole product. Everything before it is invisible by design.

## What runs

A single-file Python server with two listeners:

| Port | Protocol | Use |
|---|---|---|
| 8000 | HTTP | Quest over USB (`adb reverse tcp:8000`) |
| 8443 | HTTPS | Quest over Wi-Fi, self-signed cert |

**No headset app, no install, no APK.** `student.html` is served straight to the headset browser. That is deliberate — it means the demo runs on any headset immediately, with no sideloading step to explain.

## Teacher view

A live dashboard, one card per headset:

- connection dot and last-seen heartbeat
- current app per student
- per-app block / allow
- **per-topic search block** — Хайлтын шүүлтүүр: mathematics revision, Mongolian history, downloading games, TikTok
- live search history, with refused queries in red
- event feed, violations highlighted

## Multi-headset

Each headset has its own record keyed by `sid`, so a class of any size works:

```
GET /api/state
GET /api/state -> studentsOnline, students[], blockedApps, blockedTopics, searches, events
POST /api/student  {sid, name, app, search}   heartbeat
POST /api/teacher  {action, app}              block | allow | blockAll | allowAll
                                              blockTopic | allowTopic
```

Rules stay **class-wide** while each headset reports its own live state — one teacher decides for everyone, but the dashboard still shows who is doing what. State persists to `vr-state.json`, so restarting the server does not lose the teacher's decisions.

## Running it

```powershell
.\_deploy-app.ps1          # serve and point a headset at it
.\VR-FAILSAFE.ps1 -Check   # verify everything is reachable
.\VR-FAILSAFE.ps1 -Watch   # continuous health check
```

Re-issue `certs\make_cert.py` after your IP changes — the self-signed cert is bound to the address.

`_test_multi.py` is the multi-headset regression test.

## Screenshots

`_shot_teacher.png` · `_shot_app.png` · `_shot_quest.png`

## Notes

`_kt/` is deliberately excluded from this repository. Those are Meta's Spatial SDK sample sources, kept locally for reference; they are not my code and are not redistributable.

See [STATUS.md](STATUS.md) for the full build history and the current verified feature set.