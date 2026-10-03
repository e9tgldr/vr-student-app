# vr-student-app fail-safe server (multi-headset).
#   - HTTP 0.0.0.0:8000  -> Quest (USB adb reverse localhost:8000) + desktop
#   - HTTPS 0.0.0.0:8443 -> Quest (Wi-Fi, self-signed cert)
# API (all JSON):
#   GET  /api/state   -> { studentsOnline, students:[{id,name,online,lastSeen,
#                         currentApp}], studentOnline, student:{...}, blockedApps,
#                         blockedTopics, searches, events }
#   POST /api/student {sid, name, app, search}  -> per-headset heartbeat
#   POST /api/teacher {action, app}             -> block|allow|blockAll|allowAll
#                                                  blockTopic|allowTopic
# Rules (blocked apps / topics) are CLASS-WIDE; each headset reports its own
# live state. State persists to vr-state.json so restarts keep decisions.
import json
import os
import ssl
import sys
import threading
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.abspath(__file__))
CERT_DIR = os.path.join(ROOT, "certs")
CERT_FILE = os.path.join(CERT_DIR, "cert.pem")
KEY_FILE = os.path.join(CERT_DIR, "cert.key")
STATE_PATH = os.path.join(ROOT, "vr-state.json")
PORTS_HTTPS = list(range(8443, 8450))
PORTS_HTTP = list(range(8000, 8006))
ONLINE_WINDOW = 6          # seconds without a heartbeat before a headset is "offline"
DEFAULT_SID = "default"

APP_NAMES = {
    "calc": "Калькулятор",
    "notes": "Тэмдэглэл",
    "browser": "Интернет",
    "game": "Тоглоом",
}

TOPICS = {
    "math": "математик дасгал",
    "history": "Монгол түүх",
    "gamedl": "тоглоом татах",
    "tiktok": "TikTok",
}

LOCK = threading.Lock()


def _default_state():
    return {
        "blockedApps": ["game"],  # demo starts with the game blocked
        "blockedTopics": [],      # teacher-blocked search topics
        "students": {},           # sid -> {name, firstSeen, lastSeen, currentApp}
        "events": [],
        "searches": [],
    }


def _auto_name(index):
    """Fallback label: 'Сурагч N' by insertion order (index is 0-based)."""
    return "Сурагч %d" % (index + 1)


def _load_state():
    base = _default_state()
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return base
        if isinstance(data.get("blockedApps"), list):
            base["blockedApps"] = data["blockedApps"]
        base["blockedTopics"] = data.get("blockedTopics") or []
        base["searches"] = data.get("searches") or []
        base["events"] = data.get("events") or []
        students = data.get("students")
        if isinstance(students, dict):
            for sid, st in students.items():
                if not isinstance(st, dict):
                    continue
                base["students"][sid] = {
                    "name": st.get("name") or _auto_name(len(base["students"])),
                    "firstSeen": st.get("firstSeen") or time.time(),
                    "lastSeen": st.get("lastSeen", 0) or 0,
                    "currentApp": st.get("currentApp"),
                }
        elif isinstance(data.get("student"), dict):
            # migrate the old single-student state file
            old = data["student"]
            base["students"][DEFAULT_SID] = {
                "name": _auto_name(0),
                "firstSeen": time.time(),
                "lastSeen": old.get("lastSeen", 0) or 0,
                "currentApp": old.get("currentApp"),
            }
        return base
    except Exception:
        return base


STATE = _load_state()


def _student(sid, name=None):
    """Fetch (or create) the record for one headset."""
    st = STATE["students"].get(sid)
    if st is None:
        st = {
            "name": name or _auto_name(len(STATE["students"])),
            "firstSeen": time.time(),
            "lastSeen": 0,
            "currentApp": None,
        }
        STATE["students"][sid] = st
    elif name:
        st["name"] = name
    return st


def _sid_or_default(raw):
    sid = str(raw or "").strip()[:32]
    return sid or DEFAULT_SID


def _save_state():
    try:
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(STATE, f, ensure_ascii=False)
    except Exception:
        pass


def _event(kind, msg, sid=None):
    st = STATE["students"].get(sid) if sid else None
    STATE["events"].append({
        "t": time.strftime("%H:%M:%S"),
        "kind": kind,                      # info | block | search | violation
        "msg": msg,
        "sid": sid,
        "name": st["name"] if st else None,
    })
    del STATE["events"][:-80]


def _record_search(sid, topic_id, blocked):
    st = STATE["students"].get(sid)
    STATE["searches"].append({
        "t": time.strftime("%H:%M:%S"),
        "topic": topic_id,
        "label": TOPICS[topic_id],
        "blocked": bool(blocked),
        "sid": sid,
        "name": st["name"] if st else None,
    })
    del STATE["searches"][:-60]


def _is_online(st):
    ls = st.get("lastSeen", 0) or 0
    return ls > 0 and (time.time() - ls) < ONLINE_WINDOW


def _student_public(sid, st):
    return {
        "id": sid,
        "name": st["name"],
        "online": _is_online(st),
        "lastSeen": int(st["lastSeen"] * 1000) if st.get("lastSeen") else None,
        "currentApp": st.get("currentApp"),
        "blockedCurrent": bool(st.get("currentApp")) and st.get("currentApp") in STATE["blockedApps"],
    }


def _public_state():
    students = [
        _student_public(sid, st)
        for sid, st in sorted(STATE["students"].items(), key=lambda kv: kv[1]["firstSeen"])
    ]
    online = [s for s in students if s["online"]]
    first = students[0] if students else {"lastSeen": None, "currentApp": None}
    return {
        "studentsOnline": len(online),
        "studentsTotal": len(students),
        "students": students,
        # legacy single-student fields (kept so older pages keep working)
        "studentOnline": len(online) > 0,
        "student": {
            "lastSeen": first.get("lastSeen"),
            "currentApp": first.get("currentApp"),
            "blockedApps": list(STATE["blockedApps"]),
        },
        "blockedApps": list(STATE["blockedApps"]),
        "blockedTopics": list(STATE["blockedTopics"]),
        "searches": list(STATE["searches"]),
        "events": list(STATE["events"]),
    }


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):  # keep the console readable
        pass

    def end_headers(self):
        # never cache during a demo — edits show up on refresh
        self.send_header("Cache-Control", "no-store")
        SimpleHTTPRequestHandler.end_headers(self)

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/api/state"):
            with LOCK:
                return self._json(_public_state())
        return SimpleHTTPRequestHandler.do_GET(self)

    def do_POST(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
            data = json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            data = {}
        if not isinstance(data, dict):
            data = {}

        if self.path.startswith("/api/student"):
            sid = _sid_or_default(data.get("sid"))
            raw_name = data.get("name")
            name = (str(raw_name).strip()[:24] or None) if raw_name else None
            with LOCK:
                st = _student(sid, name)
                st["lastSeen"] = time.time()
                prev = st.get("currentApp")
                cur = data.get("app") if data.get("app") in APP_NAMES else None
                if cur != prev:
                    if cur:
                        _event("info", "Апп нээлээ: %s" % APP_NAMES[cur], sid)
                    elif prev:
                        if prev in STATE["blockedApps"]:
                            _event("violation",
                                   "Апп автоматаар хаагдлаа: %s (түгжсэн)" % APP_NAMES[prev], sid)
                        else:
                            _event("info", "Апп хаалаа: %s" % APP_NAMES[prev], sid)
                st["currentApp"] = cur
                search = data.get("search")
                if search in TOPICS:
                    blocked = search in STATE["blockedTopics"]
                    if blocked:
                        _event("violation",
                               "ХОРИГЛОСОН хайлт оруулсан: %s" % TOPICS[search], sid)
                    else:
                        _event("search", "Хайлт: %s" % TOPICS[search], sid)
                    _record_search(sid, search, blocked)
                _save_state()
            return self._json({"ok": True})

        if self.path.startswith("/api/teacher"):
            action = data.get("action")
            app = data.get("app")
            with LOCK:
                if action == "block" and app in APP_NAMES:
                    if app not in STATE["blockedApps"]:
                        STATE["blockedApps"].append(app)
                        _event("block", "Багш: %s түгжлээ" % APP_NAMES[app])
                    else:
                        _event("info", "Багш: %s аль хэдийн түгжсэн" % APP_NAMES[app])
                elif action == "allow" and app in APP_NAMES:
                    if app in STATE["blockedApps"]:
                        STATE["blockedApps"].remove(app)
                        _event("block", "Багш: %s нээлээ" % APP_NAMES[app])
                    else:
                        _event("info", "Багш: %s аль хэдийн нээлттэй" % APP_NAMES[app])
                elif action == "blockAll":
                    STATE["blockedApps"] = list(APP_NAMES.keys())
                    _event("block", "Багш: БҮГДИЙГ түгжлээ (багшийн горим)")
                elif action == "allowAll":
                    STATE["blockedApps"] = []
                    _event("block", "Багш: Бүгдийг нээлээ")
                elif action == "blockTopic" and app in TOPICS:
                    if app not in STATE["blockedTopics"]:
                        STATE["blockedTopics"].append(app)
                        _event("block", "Багш: хайлтыг түгжлээ — %s" % TOPICS[app])
                    else:
                        _event("info", "Багш: %s аль хэдийн түгжсэн" % TOPICS[app])
                elif action == "allowTopic" and app in TOPICS:
                    if app in STATE["blockedTopics"]:
                        STATE["blockedTopics"].remove(app)
                        _event("block", "Багш: хайлтыг нээлээ — %s" % TOPICS[app])
                    else:
                        _event("info", "Багш: %s аль хэдийн нээлттэй" % TOPICS[app])
                elif action == "forgetOffline":
                    gone = [s for s, st in STATE["students"].items() if not _is_online(st)]
                    for s in gone:
                        STATE["students"].pop(s, None)
                    _event("info", "Багш: холбогдоогүй сурагчдыг цэвэрлэв (%d)" % len(gone))
                else:
                    return self._json({"ok": False, "error": "unknown action"})
                _save_state()
                st = _public_state()
            return self._json({"ok": True, "msg": "Хийгдлээ", "state": st})

        self.send_error(404)
        return None


def make_server(port, handler):
    return ThreadingHTTPServer(("0.0.0.0", port), handler)


def start_https():
    if not (os.path.exists(CERT_FILE) and os.path.exists(KEY_FILE)):
        print("[HTTPS] SKIPPED — no cert. HTTP still works.")
        return None
    try:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(CERT_FILE, KEY_FILE)
    except Exception as exc:
        print("[HTTPS] SKIPPED — cert load failed: %r. HTTP still works." % exc)
        return None
    handler = partial(QuietHandler, directory=ROOT)
    for port in PORTS_HTTPS:
        try:
            srv = make_server(port, handler)
        except OSError:
            print("[HTTPS] port %d busy, trying next..." % port)
            continue
        srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        print("[HTTPS] serving ->  https://%s:%d  (and https://localhost:%d)" % (MY_IP, port, port))
        return srv
    print("[HTTPS] all ports busy — HTTPS disabled, HTTP still works.")
    return None


def start_http():
    handler = partial(QuietHandler, directory=ROOT)
    for port in PORTS_HTTP:
        try:
            srv = make_server(port, handler)
        except OSError:
            print("[HTTP]  port %d busy, trying next..." % port)
            continue
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        print("[HTTP]  serving ->  http://%s:%d   (Quest USB + desktop)" % (MY_IP, port))
        return srv
    print("[HTTP] all ports busy — nothing left to try.")
    return None


def pick_ip():
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
        finally:
            s.close()
    except Exception:
        return "127.0.0.1"


if __name__ == "__main__":
    MY_IP = pick_ip()
    print("=" * 62)
    print(" vr-student-app server  (Ctrl+C to stop)")
    print("=" * 62)
    start_https()
    http_srv = start_http()
    if not http_srv:
        print("FATAL: could not bind any HTTP port.")
        sys.exit(1)
    print("-" * 62)
    print(" Student (Quest USB):  http://localhost:8000/student.html")
    print(" Student (Wi-Fi):      https://%s:8443/student.html" % MY_IP)
    print(" Teacher dashboard:    http://localhost:8000/teacher.html")
    print("=" * 62)
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        print("\nServer stopped.")
