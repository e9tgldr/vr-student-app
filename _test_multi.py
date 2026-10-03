# temp end-to-end test for the multi-headset API (run against a live server)
import json
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8000"
fails = []


def post(path, body):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.loads(r.read().decode("utf-8"))


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=5) as r:
        return r.status, r.read().decode("utf-8"), dict(r.headers)


def check(label, cond, detail=""):
    print(("PASS  " if cond else "FAIL  ") + label + ("  " + detail if detail else ""))
    if not cond:
        fails.append(label)


# --- 3 students heartbeat ---
post("/api/student", {"sid": "q1", "name": "Сурагч 1", "app": None})
post("/api/student", {"sid": "q2", "app": None})
post("/api/student", {"sid": "q3", "app": None, "name": "Бат"})
_, body, _ = get("/api/state")
s = json.loads(body)
check("3 students registered", len(s["students"]) == 3, str([x["name"] for x in s["students"]]))
check("studentsOnline == 3", s["studentsOnline"] == 3, str(s["studentsOnline"]))
check("names kept/auto", sorted(x["name"] for x in s["students"]) == sorted(["Сурагч 1", "Бат", s["students"][1]["name"]]),
      str([x["name"] for x in s["students"]]))
check("legacy studentOnline true", s["studentOnline"] is True)
check("legacy student.currentApp null", s["student"]["currentApp"] is None)
check("blockedApps default = game", s["blockedApps"] == ["game"], str(s["blockedApps"]))

# --- student opens an allowed app ---
post("/api/student", {"sid": "q2", "app": "calc"})
s = json.loads(get("/api/state")[1])
q2 = [x for x in s["students"] if x["id"] == "q2"][0]
check("q2 currentApp = calc", q2["currentApp"] == "calc", str(q2["currentApp"]))
check("q2 blockedCurrent false", q2["blockedCurrent"] is False)
check("event carries student name", any(e.get("name") == q2["name"] and "Апп нээлээ" in e["msg"] for e in s["events"]),
      json.dumps(s["events"][-1:], ensure_ascii=False))

# --- teacher blocks calc -> q2's open app is a violation when it closes ---
post("/api/teacher", {"action": "block", "app": "calc"})
s = json.loads(get("/api/state")[1])
q2 = [x for x in s["students"] if x["id"] == "q2"][0]
check("q2 blockedCurrent true after block", q2["blockedCurrent"] is True)
post("/api/student", {"sid": "q2", "app": None})
s = json.loads(get("/api/state")[1])
check("auto-close violation logged", any(e["kind"] == "violation" and "автоматаар хаагдлаа" in e["msg"] for e in s["events"]),
      json.dumps(s["events"][-1], ensure_ascii=False))

# --- search stream: blocked vs allowed, per student ---
post("/api/teacher", {"action": "blockTopic", "app": "tiktok"})
post("/api/student", {"sid": "q1", "app": "browser", "search": "tiktok"})
post("/api/student", {"sid": "q3", "app": "browser", "search": "math"})
s = json.loads(get("/api/state")[1])
check("2 searches recorded", len(s["searches"]) == 2, json.dumps(s["searches"], ensure_ascii=False))
check("blocked search flagged", any(r["blocked"] and r["topic"] == "tiktok" for r in s["searches"]))
check("allowed search flagged", any((not r["blocked"]) and r["topic"] == "math" for r in s["searches"]))
check("search carries student name", all(r.get("name") for r in s["searches"]))
check("blockedTopics = tiktok", s["blockedTopics"] == ["tiktok"], str(s["blockedTopics"]))

# --- master block / allow ---
j = post("/api/teacher", {"action": "blockAll"})
check("blockAll response has state", j.get("ok") is True and len(j["state"]["blockedApps"]) == 4)
check("blockAll names all 4 apps", set(j["state"]["blockedApps"]) == {"calc", "notes", "browser", "game"})
post("/api/teacher", {"action": "allowAll"})
s = json.loads(get("/api/state")[1])
check("allowAll clears", s["blockedApps"] == [])
check("unknown action rejected", post("/api/teacher", {"action": "nope"}).get("ok") is False)

# --- forget offline ---
post("/api/teacher", {"action": "forgetOffline"})
s = json.loads(get("/api/state")[1])
check("forgetOffline keeps live students", s["studentsTotal"] == 3, str(s["studentsTotal"]))

# --- pages served ---
for page in ("/student.html", "/teacher.html"):
    code, text, hdrs = get(page)
    check(page + " 200", code == 200)
    check(page + " no-store", hdrs.get("Cache-Control") == "no-store", str(hdrs.get("Cache-Control")))

print("-" * 50)
print("FAILURES: %d" % len(fails))
for f in fails:
    print("  - " + f)
