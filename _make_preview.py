# temp: build a local preview of teacher.html with the live /api/state baked in
# (the screenshot tool only accepts local files, so fetch() is stubbed)
import json
import urllib.request

ROOT = r"C:\Users\hi\Documents\vr-student-app"
state = json.loads(urllib.request.urlopen("http://127.0.0.1:8000/api/state", timeout=5).read().decode("utf-8"))
html = open(ROOT + r"\teacher.html", encoding="utf-8").read()

stub = (
    "<script>(function(){var S=%s;"
    "window.fetch=function(){return Promise.resolve({json:function(){return Promise.resolve(S);}});};"
    "})();</script>"
) % json.dumps(state, ensure_ascii=False).replace("</", "<\\/")

html = html.replace("<body>", "<body>" + stub, 1)
out = ROOT + r"\_teacher_preview.html"
open(out, "w", encoding="utf-8").write(html)
print("wrote", out, "students:", [(s["name"], s["online"], s["currentApp"]) for s in state["students"]])
