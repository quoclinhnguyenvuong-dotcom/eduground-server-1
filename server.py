# server.py – EduGround Backend (Render-ready version)
# ----------------------------------------------------
# Features:
# - Serve static frontend in /web
# - Login API reads from web/data/accounts.json
# - Messages, Groups, Reminders JSON stored locally
# - File uploads to /uploads
# - No enforced login server-side (handled by frontend)
# - Clean periodic data pruning
# - Compatible with Render.com deployment

from flask import Flask, jsonify, request, send_from_directory, abort
from flask_cors import CORS
from werkzeug.utils import secure_filename
import os, json, time, zlib, base64, threading, uuid, shutil

# ===================== CONFIG =====================
WEB_DIR = "web"
UPLOADS_DIR = "uploads"
DATA_FILE = "messages.json"
GROUP_FILE = "groups.json"
REMINDER_FILE = "reminders.json"
ACCOUNTS_FILE = os.path.join(WEB_DIR, "data", "accounts.json")

os.makedirs(UPLOADS_DIR, exist_ok=True)
for f in [DATA_FILE, GROUP_FILE, REMINDER_FILE]:
    if not os.path.exists(f):
        with open(f, "w", encoding="utf-8") as ff:
            json.dump({}, ff, ensure_ascii=False, indent=2)

# Retention policy (30 days)
TTL_TEXT = 60 * 60 * 24 * 30
TTL_MEDIA = 60 * 60 * 24 * 30
MAX_MEDIA_SIZE = 16 * 1024 * 1024
ALLOWED_EXT = {"png","jpg","jpeg","gif","mp4","webm","mov","mkv","pdf","wav","mp3","ogg"}

app = Flask(__name__, static_folder=WEB_DIR, static_url_path="")
CORS(app)

# ===================== HELPERS =====================
def load_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default if default is not None else {}

def save_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

def compress_obj(obj):
    raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    return base64.b64encode(zlib.compress(raw)).decode("utf-8")

def decompress_obj(s):
    try:
        raw = base64.b64decode(s)
        return json.loads(zlib.decompress(raw).decode("utf-8"))
    except Exception:
        return []

def allowed_filename(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT

# ===================== PRUNING THREAD =====================
def prune_loop():
    while True:
        now = time.time()
        try:
            msgs = load_json(DATA_FILE, {})
            new_msgs = {}
            for k, v in msgs.items():
                arr = decompress_obj(v) if isinstance(v, str) else v
                arr = [m for m in arr if now - m.get("time", now) < TTL_TEXT]
                new_msgs[k] = compress_obj(arr)
            save_json(DATA_FILE, new_msgs)
        except Exception as e:
            print("Prune message error:", e)

        try:
            for f in os.listdir(UPLOADS_DIR):
                path = os.path.join(UPLOADS_DIR, f)
                if os.path.isfile(path):age = now - os.path.getmtime(path)
                    if age > TTL_MEDIA:
                        os.remove(path)
        except Exception as e:
            print("Prune upload error:", e)

        time.sleep(3600)  # every hour

threading.Thread(target=prune_loop, daemon=True).start()

# ===================== STATIC =====================
@app.route("/")
def index():
    return send_from_directory(WEB_DIR, "login.html")

@app.route("/<path:path>")
def static_proxy(path):
    web_path = os.path.join(WEB_DIR, path)
    if os.path.isfile(web_path):
        return send_from_directory(WEB_DIR, path)
    upload_path = os.path.join(UPLOADS_DIR, path)
    if os.path.isfile(upload_path):
        return send_from_directory(UPLOADS_DIR, path)
    return abort(404)

# ===================== API =====================

# ---------- LOGIN ----------
@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(force=True)
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    accounts = load_json(ACCOUNTS_FILE, {"users": []}).get("users", [])

    for acc in accounts:
        if acc["username"].lower() == username.lower() and acc["password"] == password:
            return jsonify({"ok": True, "user": acc["username"], "role": acc["role"]})
    return jsonify({"ok": False, "error": "Invalid credentials"}), 401


# ---------- MESSAGES ----------
@app.route("/api/messages", methods=["GET", "POST"])
def api_messages():
    if request.method == "GET":
        data = load_json(DATA_FILE, {})
        out = {k: decompress_obj(v) for k, v in data.items()}
        return jsonify(out)

    payload = request.get_json(force=True)
    room = payload.get("chat_id")
    if not room:
        return jsonify({"ok": False, "error": "missing chat_id"}), 400

    msg = {
        "id": str(uuid.uuid4()),
        "from": payload.get("from", "unknown"),
        "text": payload.get("text", ""),
        "time": int(time.time())
    }
    data = load_json(DATA_FILE, {})
    arr = decompress_obj(data.get(room, ""))
    arr.append(msg)
    data[room] = compress_obj(arr)
    save_json(DATA_FILE, data)
    return jsonify({"ok": True, "msg_id": msg["id"]})


# ---------- GROUPS ----------
@app.route("/api/groups", methods=["GET", "POST"])
def api_groups():
    if request.method == "GET":
        return jsonify(load_json(GROUP_FILE, {}))
    g = request.get_json(force=True)
    gid = g.get("id") or str(uuid.uuid4())
    groups = load_json(GROUP_FILE, {})
    groups[gid] = g
    save_json(GROUP_FILE, groups)
    return jsonify({"ok": True, "id": gid})


# ---------- UPLOAD ----------
@app.route("/api/upload", methods=["POST"])
def api_upload():
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "no file"}), 400
    f = request.files["file"]
    if not allowed_filename(f.filename):
        return jsonify({"ok": False, "error": "file type not allowed"}), 400fname = secure_filename(f"{uuid.uuid4()}-{f.filename}")
    dest = os.path.join(UPLOADS_DIR, fname)
    f.save(dest)

    if os.path.getsize(dest) > MAX_MEDIA_SIZE:
        os.remove(dest)
        return jsonify({"ok": False, "error": "file too large"}), 400

    return jsonify({"ok": True, "url": f"/{UPLOADS_DIR}/{fname}"})


# ---------- REMINDERS ----------
@app.route("/api/reminders", methods=["GET", "POST"])
def api_reminders():
    if request.method == "GET":
        return jsonify(load_json(REMINDER_FILE, {}))

    r = request.get_json(force=True)
    rid = str(uuid.uuid4())
    reminders = load_json(REMINDER_FILE, {})
    reminders[rid] = {
        "id": rid,
        "teacher": r.get("teacher"),
        "class": r.get("class"),
        "summary": r.get("summary"),
        "timestamp": int(time.time())
    }
    save_json(REMINDER_FILE, reminders)
    return jsonify({"ok": True, "id": rid})

# -------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)