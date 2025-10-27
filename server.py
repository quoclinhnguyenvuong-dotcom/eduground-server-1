# ===============================================================
# Eduground Server - Flask backend (Render compatible)
# ===============================================================

from flask import Flask, jsonify, request, send_from_directory, abort
from flask_cors import CORS
from werkzeug.utils import secure_filename
import os, json, time, zlib, base64, threading, uuid, shutil, requests

# ===============================================================
# CONFIGURATION
# ===============================================================

WEB_DIR = "web"                       # Frontend folder
UPLOADS_DIR = "uploads"               # Uploaded media
DATA_FILE = "messages.json"           # Messages data
GROUP_FILE = "groups.json"            # Groups data
REMINDER_FILE = "reminders.json"      # Reminders
ACCOUNTS_FILE = os.path.join(WEB_DIR, "accounts.json")

TTL_SECONDS_TEXT = 60 * 60 * 24 * 30  # 30 days
TTL_SECONDS_MEDIA = 60 * 60 * 24 * 30 # 30 days
COMPRESS = True
MAX_MEDIA_SIZE = 16 * 1024 * 1024     # 16MB
ALLOWED_EXT = {"png", "jpg", "jpeg", "gif", "mp4", "webm", "mov", "mkv", "pdf", "wav", "mp3", "ogg"}

# Optional AI API (if using reminders auto-summary)
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "gpt-4o-mini"

# Ensure upload folder exists
os.makedirs(UPLOADS_DIR, exist_ok=True)

app = Flask(__name__, static_folder=WEB_DIR, static_url_path="/")
CORS(app)

# ===============================================================
# HELPER FUNCTIONS
# ===============================================================

def load_json(path, default_factory=dict):
    try:
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                json.dump(default_factory(), f, ensure_ascii=False, indent=2)
            return default_factory()
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default_factory()

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
        if isinstance(s, str):
            raw = base64.b64decode(s)
            return json.loads(zlib.decompress(raw).decode("utf-8"))
        return s
    except Exception:
        return []

def allowed_filename(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT

# ===============================================================
# BACKGROUND CLEANUP (TTL)
# ===============================================================

def prune_loop():
    while True:
        try:
            msgs_raw = load_json(DATA_FILE, {})
            msgs_out = {}
            now = time.time()
            for room, val in msgs_raw.items():
                arr = decompress_obj(val) if isinstance(val, str) else val
                arr = [m for m in arr if (now - m.get("time", now)) < TTL_SECONDS_TEXT]
                msgs_out[room] = compress_obj(arr) if COMPRESS else arr
            save_json(DATA_FILE, msgs_out)
        except Exception as e:
            print("⚠️ prune messages:", e)

        try:
            now = time.time()
            for fname in os.listdir(UPLOADS_DIR):
                path = os.path.join(UPLOADS_DIR, fname)
                if os.path.isfile(path):
                    if (now - os.path.getmtime(path)) > TTL_SECONDS_MEDIA:
                        os.remove(path)
        except Exception as e:
            print("⚠️ prune uploads:", e)

        time.sleep(3600)  # every hour

threading.Thread(target=prune_loop, daemon=True).start()

# ===============================================================
# STATIC ROUTES
# ===============================================================

@app.route("/")
def index():
    return send_from_directory(WEB_DIR, "index.html")

@app.route("/<path:filename>")
def serve_static(filename):
    web_path = os.path.join(WEB_DIR, filename)
    upload_path = os.path.join(UPLOADS_DIR, filename)
    if os.path.isfile(web_path):
        return send_from_directory(WEB_DIR, filename)
    elif os.path.isfile(upload_path):
        return send_from_directory(UPLOADS_DIR, filename)
    else:
        return abort(404)

# ===============================================================
# LOGIN SYSTEM
# ===============================================================

@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(force=True)
    username = data.get("username")
    password = data.get("password")

    accounts = load_json(ACCOUNTS_FILE, {}).get("users", [])
    user = next((u for u in accounts if u["username"].lower() == username.lower()), None)
    if not user:
        return jsonify({"ok": False, "error": "User not found"}), 401

    if user["password"] == password:
        return jsonify({"ok": True, "user": user["username"], "role": user["role"]})
    else:
        return jsonify({"ok": False, "error": "Invalid password"}), 401

# ===============================================================
# MESSAGES
# ===============================================================

@app.route("/api/messages", methods=["GET", "POST"])
def api_messages():
    if request.method == "GET":
        raw = load_json(DATA_FILE, {})
        out = {k: decompress_obj(v) if isinstance(v, str) else v for k, v in raw.items()}
        return jsonify(out)
    else:
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

        raw = load_json(DATA_FILE, {})
        arr = decompress_obj(raw[room]) if room in raw else []
        arr.append(msg)
        raw[room] = compress_obj(arr) if COMPRESS else arr
        save_json(DATA_FILE, raw)
        return jsonify({"ok": True, "msg_id": msg["id"]})

# ===============================================================
# GROUPS
# ===============================================================

@app.route("/api/groups", methods=["GET", "POST"])
def api_groups():
    if request.method == "GET":
        return jsonify(load_json(GROUP_FILE, {}))
    else:
        g = request.get_json(force=True)
        gid = g.get("id") or str(uuid.uuid4())
        groups = load_json(GROUP_FILE, {})
        groups[gid] = g
        save_json(GROUP_FILE, groups)
        return jsonify({"ok": True, "id": gid})

# ===============================================================
# FILE UPLOADS
# ===============================================================

@app.route("/api/upload", methods=["POST"])
def api_upload():
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "No file"}), 400
    f = request.files["file"]
    if f.filename == "":
        return jsonify({"ok": False, "error": "Empty filename"}), 400
    if not allowed_filename(f.filename):
        return jsonify({"ok": False, "error": "File type not allowed"}), 400

    fname = secure_filename(str(uuid.uuid4()) + "-" + f.filename)
    dest = os.path.join(UPLOADS_DIR, fname)
    f.save(dest)
    if os.path.getsize(dest) > MAX_MEDIA_SIZE:
        os.remove(dest)
        return jsonify({"ok": False, "error": "File too large"}), 400
    url = f"/uploads/{fname}"
    return jsonify({"ok": True, "url": url, "name": fname})

# ===============================================================
# REMINDERS (Teacher only for editing)
# ===============================================================

@app.route("/api/reminders", methods=["GET", "POST"])
def api_reminders():
    reminders = load_json(REMINDER_FILE, {})
    if request.method == "GET":
        return jsonify(reminders)

    data = request.get_json(force=True)
    username = data.get("username", "unknown")
    role = data.get("role", "student")

    if role != "teacher":
        return jsonify({"ok": False, "error": "Permission denied"}), 403

    rid = str(uuid.uuid4())
    reminder = {
        "id": rid,
        "teacher": username,
        "title": data.get("title", "Không tiêu đề"),
        "content": data.get("content", ""),
        "time": int(time.time())
    }
    reminders[rid] = reminder
    save_json(REMINDER_FILE, reminders)
    return jsonify({"ok": True, "id": rid})

# ===============================================================
# ADMIN: CLEAR ALL
# ===============================================================

@app.route("/api/admin/clear", methods=["POST"])
def admin_clear():
    data = request.get_json(force=True)
    key = data.get("key")
    accounts = load_json(ACCOUNTS_FILE, {}).get("users", [])
    dev = next((u for u in accounts if u["username"] == "devtool"), None)
    if not dev or key != dev["password"]:
        return jsonify({"ok": False, "error": "Forbidden"}), 403

    save_json(DATA_FILE, {})
    save_json(GROUP_FILE, {})
    save_json(REMINDER_FILE, {})
    shutil.rmtree(UPLOADS_DIR, ignore_errors=True)
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    return jsonify({"ok": True})

# ===============================================================
# RUN APP
# ===============================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
