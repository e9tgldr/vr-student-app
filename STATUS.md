# vr-student-app — STATUS (2026-09-21: MULTI-HEADSET + block sound, LIVE Quest 3S test)

## THE REAL CONCEPT (user's words: "hidden overlay, everything is fine, but
## apps searches and it streams live to the teacher")

- Student sees NO vr-guardian branding. Launcher is neutral ("Миний сургалт",
  no status line, no branding). They use apps + search NORMALLY.
- Every app open AND every search silently streams to the laptop (heartbeats
  900 ms). vr-guardian only SURFACES on restriction (БАГШ ТҮГЖЛЭЭ banner,
  auto-close, grey tiles, refused search) — that's the money moment.
- Teacher laptop = live stream per headset: student cards with connection dot,
  current app, per-app block, per-TOPIC block (Хайлтын шүүлтүүр: математик
  дасгал / Монгол түүх / тоглоом татах / TikTok), live search history (blocked
  ones red+bold), event feed (red for violations).

## NEW v3 (2026-09-21) — verified

- **MULTI-HEADSET.** `serve_app.py` keeps a per-headset record keyed by `sid`:
  `students: {sid: {name, firstSeen, lastSeen, currentApp}}`. Rules
  (`blockedApps` / `blockedTopics`) stay CLASS-WIDE. Public state adds
  `students[]`, `studentsOnline`, `studentsTotal` (legacy `student` /
  `studentOnline` kept for old clients).
- **Headset identity** (student.html): `?id=q1&name=Сурагч%201` → else
  localStorage `vr_sid` → else random `q####`. Works on file:// too
  (localStorage failure falls back to `q-demo`).
- **Names in the live stream**: events and searches carry `sid` + `name`
  ("Сурагч 2: Апп нээлээ: Калькулятор"); auto-name = "Сурагч N" by connection
  order; unmigrated old state files become "Сурагч 1".
- **teacher.html**: new Сурагчид section (one card per headset: dot, last-seen,
  open app, tag ИДЭВХТЭЙ / ЛОББИ / ХОЛБООГҮЙ / ХОРИГЛОСОН АПП НЭЭЛТТЭЙ),
  "Холбогдоогүйг цэвэрлэх" action (`forgetOffline`), events carry a `kind`
  (info | block | search | violation) instead of `!!` prefix guessing.
- **Block sound** (student.html): WebAudio two-tone "denied" (520→330 Hz
  square) on blocked-tile click, refused search, and auto-close. No asset file.
  Autoplay policy: armed by the first click / `enter-vr` (armAudio).
- **Cert renewed** for the current Wi-Fi IP → `certs/make_cert.py` now reports
  "covers 192.168.7.73 + localhost, expires 2028-12-24". NOTE: that script needs
  `cryptography`, which the uv python 3.11.15 does NOT have — run it with
  `C:\Users\hi\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe`.

## Verified (2026-09-21)

- **REAL HARDWARE**: the user's **Meta Quest 3S** (adb serial 340YC10GBG0ZRJ,
  `C:\Users\hi\bin\platform-tools\adb.exe`) opened
  `http://localhost:8000/student.html?id=q1&name=Quest%201` through
  `adb reverse tcp:8000 tcp:8000` and registered live as **Сурагч 1** —
  `studentsOnline: 1`, heartbeats every 900 ms. This is the first verified
  headset→server link for the multi-headset build.
- `_test_multi.py` (regression test, run against the live server): 23/23 PASS —
  3 students registered/online, per-student currentApp, blockedCurrent flips on
  teacher block, auto-close violation logged, 2 searches (1 blocked) with names,
  blockAll names all 4 apps, allowAll clears, unknown action rejected,
  forgetOffline keeps live students, both pages 200 + Cache-Control no-store.
  Re-run: `<uv-python> _test_multi.py` with the server up.
- `_check_js.js` (inline-script syntax gate, node vm): both HTML files OK.
- `py_compile serve_app.py` → 0.
- Chrome headless render (works; the vision-toolkit html_screenshot times out):
  `chrome --headless=new --no-proxy-server --dump-dom file:///…/_teacher_preview.html`
  → "Сурагчид (3 идэвхтэй / 3 бүртгэлтэй)" + 3 cards with correct names/apps/tags;
  student.html file:// screenshot → launcher + 4 tiles render fine.
- Live student page in headless Chrome against the running server:
  `… --dump-dom http://127.0.0.1:8000/student.html?id=qa&name=Chrome-Headset`
  → launcher built, no fatal banner, and the server registered sid `qa`
  (URL param → localStorage id → heartbeat chain verified).
- Blocked-tile render on the real page: with `blockedApps: ["game"]` the game
  tile carries "хориглосон".
- HTTPS :8443 and HTTP :8000 both 200 (student.html, teacher.html, api/state).

## RUN

- powershell -ExecutionPolicy Bypass -File VR-FAILSAFE.ps1   (fix+verify)
- powershell -ExecutionPolicy Bypass -File VR-FAILSAFE.ps1 -Watch  (daemon)
- -Check / -StopWatch / -Stop  (status / stop daemon / stop server)
- Quest (USB): http://localhost:8000/student.html
- Teacher (PC browser): http://localhost:8000/teacher.html
- Wi-Fi: https://192.168.7.73:8443/student.html (cert covers this IP)
- 2nd headset: same URL + `?id=q2&name=Сурагч%202`
- Step-by-step Quest script: TEST-CHECKLIST.md

## CLEAN RESET (needed because old daemon raced a reset once)

1. kill watch daemon(s): Get-CimInstance Win32_Process | CommandLine like
   '*vr-student-app*VR-FAILSAFE*Watch*' → Stop-Process (exclude $PID!)
2. VR-FAILSAFE.ps1 -Stop
3. delete vr-state.json
4. VR-FAILSAFE.ps1 (start), then -Watch (daemon)
NEVER match your own powershell process when filtering by CommandLine.

The REAL vr-guardian demo (user pivot: NOT the 3D classroom — that stays in
C:\Users\hi\Documents\vr-school-demo as a separate pitch scene).

## SEARCH FLOW (verified end-to-end 2026-09-18 17:34, still current)

- student.html Интернет tile → Хайлт screen: 4 topic chips (2x2). Pinch =
  search → POST /api/student {app:'browser', search:topicId, sid, name} →
  server logs "Хайлт: X" or violation "ХОРИГЛОСОН хайлт оруулсан: X" +
  searches[] entry {t, topic, label, blocked, sid, name}. Blocked topic in VR:
  chip stays clickable but shows Багш зөвшөөрөхгүй! banner + red result line.

## API (current)

- GET  /api/state → {studentsOnline, studentsTotal, students:[{id,name,online,
  lastSeen,currentApp,blockedCurrent}], studentOnline, student:{…legacy…},
  blockedApps, blockedTopics, searches, events}
- POST /api/student {sid, name, app, search} — heartbeat (sid optional → 'default')
- POST /api/teacher {action: block|allow|blockAll|allowAll|blockTopic|
  allowTopic|forgetOffline, app}
- State persists to vr-state.json (old single-`student` files migrate safely).

## GOTCHAS (added v3)

- `str(None)` is the STRING "None" — the first cut of the name field stored
  "None" as a student name. Always test `raw_name` truthiness before `str()`.
- `_auto_name`/`_load_state` ordering: STATE is built at import time, so name
  helpers must not read the global STATE during load (NameError → silently
  resets state; the loader catches everything).
- The vision-toolkit `vision_html_screenshot` times out (Chrome DevTools
  handshake) and rejects http URLs — use `chrome.exe --headless=new
  --no-proxy-server --screenshot/--dump-dom file:///…` instead. To capture LIVE
  data that a local file cannot fetch, bake a fetch() stub into a temp copy
  (`_make_preview.py`).

## NEXT

- [ ] In-headset click test: put the Quest on, click Тоглоом (blocked) → expect
      the denied tone + "Багшийн зөвшөөрөл шаардлагатай"; then unblock from the
      laptop and re-block while an app is open → БАГШ ТҮГЖЛЭЭ + auto-close
      (server side already verified; the VR interaction itself is untested).
- [ ] Per-student block (block one headset's app, not the whole class)
- [ ] Real apps later (this is the supervision-shell demo with stub content)
