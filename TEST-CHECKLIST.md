# vr-student-app — Quest test checklist (multi-headset)

Server must be UP (`VR-FAILSAFE.ps1 -Check`). Teacher dashboard opens first:
**http://localhost:8000/teacher.html** (laptop browser).

## Plan A — USB (needs adb authorized)

1. Put the headset on: a **"Allow USB debugging?"** prompt must be accepted
   (otherwise `adb devices` reports `unauthorized` and step 2 does nothing).
2. On the laptop:
   `C:\Users\hi\bin\platform-tools\adb.exe reverse tcp:8000 tcp:8000`
3. In the Quest browser open: **http://localhost:8000/student.html**
   (`http://localhost` counts as a secure context, so Enter VR works — no cert warning.)

## Plan B — Wi-Fi (no cable, one extra tap)

1. Quest and laptop on the **same Wi-Fi** (cert covers the laptop's current Wi-Fi IP).
2. Open **https://192.168.7.73:8443/student.html** → "Advanced" → "Proceed"
   (self-signed cert) → **Enter VR**.
3. If the laptop's IP changed: re-run `certs\make_cert.py` then `VR-FAILSAFE.ps1 -Stop`
   and `VR-FAILSAFE.ps1`.

## A second / third headset

Open the same URL plus an id, e.g.
`…/student.html?id=q2&name=Сурагч%202` (name is optional — it will be
auto-named "Сурагч 2", "Сурагч 3" … in connection order).
Without `?id=` each headset generates its own id once and remembers it.

## What to show the principal (3 clicks)

1. **Restrict live** — headset is in Тоглоом (game). Teacher presses **Түгжих**
   on Тоглоом → headset shows the red **БАГШ ТҮГЖЛЭЭ** banner, a "denied" tone
   plays, and the app auto-closes back to the launcher; the tile turns grey with
   a red "хориглосон" tag. The teacher feed logs
   *Апп автоматаар хаагдлаа: Тоглоом (түгжсэн)*.
2. **Search supervision** — student uses Интернет → Хайлт and taps a topic chip.
   Every search appears live on the laptop (Хайлтын түүх), tagged with the
   student's name. Block a topic in **Хайлтын шүүлтүүр** → the chip turns
   "Хориатай хайлт", the student gets **Багш зөвшөөрөхгүй!** and the log line
   goes red.
3. **Whole class** — **БҮГДИЙГ ТҮГЖИХ** greys every tile on every headset at once;
   **БҮГДИЙГ НЭЭХ** restores.

Notes:
- The app is deliberately **unbranded** on the headset ("Миний сургалт") — the
  student sees vr-guardian only at the moment of restriction.
- Sound needs one prior interaction (browser autoplay policy): click once or
  enter VR before the demo. `enter-vr` arms the audio automatically.
- The demo starts with **Тоглоом blocked** — reset freely, it is the money moment.

## If something looks wrong

- Server down → `VR-FAILSAFE.ps1` (fix + verify) / `-Check` / `-Stop`.
- "Сурагч холбогдоогүй" on the laptop → the headset page is not polling; check
  the URL and that the laptop's firewall rule covers the python path
  (see STATUS.md gotchas).
- Duplicate "Сурагч 1/2/3" rows from earlier tests → press **Холбогдоогүйг цэвэрлэх**
  on the dashboard.
- Full clean reset: stop daemon (`-StopWatch`), `VR-FAILSAFE.ps1 -Stop`, delete
  `vr-state.json`, `VR-FAILSAFE.ps1`, `VR-FAILSAFE.ps1 -Watch`.
