import os, sys, tempfile, types, threading, time, socket, json
REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, REPO)
tmp = tempfile.mkdtemp(prefix="vt5_")
from config import settings_store
from app.database import db as db_mod
settings_store.SETTINGS_PATH = os.path.join(tmp, "settings.json")
db_mod.DB_PATH = os.path.join(tmp, "vigitrack.db")
class FakeCam:
    def __init__(self, *a, **k): self.camera_name = "X"; self.notifier = types.SimpleNamespace(audio_enabled=True)
    def start(self): pass
    def get_thresholds(self): return {}
st = types.ModuleType("app.stream.camera_manager"); st.CameraManager = FakeCam; sys.modules["app.stream.camera_manager"] = st
os.environ["VIGITRACK_DESKTOP"] = "1"
import webview  # real pywebview import, window NOT started
sys.modules["webview"] = webview
import desktop
from run import create_app
import urllib.request
app = create_app(); desktop.add_frontend(app)
from waitress import serve
port = desktop.free_port()
threading.Thread(target=serve, kwargs={"app": app, "host": "127.0.0.1", "port": port, "threads": 4, "_quiet": True}, daemon=True).start()
desktop.wait_for_server(port)
base = f"http://127.0.0.1:{port}"
def get(path):
    try:
        with urllib.request.urlopen(base + path, timeout=10) as r:
            return r.status, r.headers.get("Content-Type"), r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Content-Type"), e.read()
res = []
def chk(n, c, x=""):
    res.append(c); print(("PASS " if c else "FAIL ") + n + (f" [{x}]" if x else ""))
s, ct, body = get("/")
chk("hub index served", s == 200 and b"<div id=\"root\">" in body, f"{s} {ct}")
s, ct, body = get("/login")
chk("SPA route /login falls back to index", s == 200 and b"<div id=\"root\">" in body)
s, ct, body = get("/assets/logo.png")
chk("logo asset served", s == 200 and ct == "image/png", f"{s} {ct}")
s, ct, body = get("/api/setup/status")
j = json.loads(body)
chk("setup status: no code needed in desktop mode", s == 200 and j["setup_required"] is True and j["setup_code_required"] is False, str(j))
s, ct, body = get("/api/nope")
chk("unknown API path is 404, not the hub", s == 404)
s, ct, body = get("/api/incidents")
chk("protected API still requires login", s == 401)
s, ct, body = get("/%2e%2e/%2e%2e/etc/passwd")
chk("path traversal blocked", s != 200 or b"root:" not in body)
print(f"\n{sum(res)}/{len(res)} checks passed")

