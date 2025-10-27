# server.py
# Eduground backend - Render-ready
# Serve static from web/, provide /api/login, /api/messages, /api/groups, /api/upload, /api/admin/clear
# Background prune thread to delete old messages / uploads.

from flask import Flask, jsonify, request, send_from_directory, abort
from flask_cors import CORS
from werkzeug.utils import secure_filename
import os
import json
import time
import threading
import zlib
import base64
import uuid
import shutil
import logging

# -------- CONFIG --------
WEB_DIR = "web"                     # static frontend root
UPLOADS_DIR = "uploads"             # uploaded media stored here
DATA_FILE = "messages.json"         # messages store
GROUP_FILE = "groups.json"          # groups store
REMINDER_FILE = "reminders.json"    # optional reminders store
ACCOUNTS_FILE = os.path.join(WEB_DIR, "accounts.json")

TTL_SECONDS_TEXT = 60 * 60 * 24 * 30   # 30 days for messages
TTL_SECONDS_MEDIA = 60 * 60 * 24 * 30  # 30 days for media
COMPRESS = True                        # compress message arrays to save disk
MAX_MEDIA_SIZE = 16 * 1024 * 1024      # 16 MB
ALLOWED_EXT = {"png", "jpg", "jpeg", "gif", "mp4", "webm", "mov", "mkv", "pdf", "wav", "mp3", "ogg"}

os.makedirs(UPLOADS_DIR, exist_ok=True)

# setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

app = Flask(__name__, static_folder=WEB_DIR, static_url_path='')
CORS(app)


# -------- helpers --------
def load_json(path, default_factory=dict):
    try:
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                json.dump(default_factory(), f, ensure_ascii=False, indent=2)
            return default_factory()
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.exception("load_json error for %s", path)
        return default_factory()

def save_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

def compress_obj(obj):
    try:
        raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        comp = zlib.compress(raw)
        return base64.b64encode(comp).decode("utf-8")
    except Exception:
        return None

def decompress_obj(s):
    try:
        if isinstance(s, str):
            raw = base64.b64decode(s)
            return json.loads(zlib.decompress(raw).decode("utf-8"))
        return s
    except Exception:
        return []

def is_allowed_filename(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT

def accounts_map_from_file():
    """
    Returns dict mapping username -> {password, role}
    Supports two formats:
      1) { "username": { "password": "...", "role":"..." }, ... }
      2) { "users": [ { "username":"u", "password":"p", "role":"r" }, ... ] }
    """
    raw = load_json(ACCOUNTS_FILE, {})
    if not raw:
        return {}
    if isinstance(raw, dict) and "users" in raw and isinstance(raw["users"], list):
        out = {}
        for u in raw["users"]:
            name = u.get("username")
            if name:
                out[name] = {"password": u.get("password", ""), "role": u.get("role", "student")}
        return out
    # else assume mapping
    # if values are non-dict (e.g. single password string) — normalize
    out = {}
    for k, v in raw.items():
        if isinstance(v, dict):
            out[k] = {"password": v.get("password", ""), "role": v.get("role", "student")}
        else:
            # assume v is password string
            out[k] = {"password": str(v), "role": "student"}
    return out


# -------- background prune thread --------
def prune_loop():
    while True:
        try:
            # prune messages
            msgs_raw = load_json(DATA_FILE, {})
            now = time.time()
            msgs_out = {}
            for room, val in msgs_raw.items():
                arr = decompress_obj(val) if isinstance(val, str) else val
                if not isinstance(arr, list):
                    arr = []
                filtered = [m for m in arr if (now - m.get("time", now)) < TTL_SECONDS_TEXT]
                msgs_out[room] = compress_obj(filtered) if COMPRESS else filtered
            save_json(DATA_FILE, msgs_out)
        except Exception:
            logging.exception("Error pruning messages")

        try:
            # prune uploads
            now = time.time()
            for fname in os.listdir(UPLOADS_DIR):
                p = os.path.join(UPLOADS_DIR, fname)
                if os.path.isfile(p):
                    age = now - os.path.getmtime(p)
                    if age > TTL_SECONDS_MEDIA:
                        try:
                            os.remove(p)
                            logging.info("Pruned upload %s", fname)
                        except Exception:
                            logging.exception("Could not remove upload %s", fname)
        except Exception:
            logging.exception("Error pruning uploads")

        # sleep 1 hour
        time.sleep(60 * 60)

# start thread daemon
threading.Thread(target=prune_loop, daemon=True).start()


# -------- static routes --------
@app.route("/")
def index():
    index_path = os.path.join(WEB_DIR, "index.html")
    if os.path.exists(index_path):
        return send_from_directory(WEB_DIR, "index.html")
    return jsonify({"status": "no index"}), 200

@app.route("/<path:fp>")
def static_proxy(fp):
    # if file exists in web dir serve it
    web_path = os.path.join(WEB_DIR, fp)
    if os.path.exists(web_path) and os.path.isfile(web_path):
        return send_from_directory(WEB_DIR, fp)
    # else if file exists in uploads serve
    upload_path = os.path.join(UPLOADS_DIR, fp)
    if os.path.exists(upload_path) and os.path.isfile(upload_path):
        return send_from_directory(UPLOADS_DIR, fp)
    # fallback 404
    return abort(404)


# -------- API: login --------
@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(force=True)
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if not username or not password:
        return jsonify({"ok": False, "error": "Missing credentials"}), 400

    accounts = accounts_map_from_file()
    entry = accounts.get(username)
    if not entry:
        # case-insensitive search
        for k, v in accounts.items():
            if k.lower() == username.lower():
                entry = v
                username = k
                break
    if not entry:
        return jsonify({"ok": False, "error": "Unknown user"}), 401

    if entry.get("password") == password:
        return jsonify({"ok": True, "user": username, "role": entry.get("role", "student")})
    else:
        return jsonify({"ok": False, "error": "Invalid credentials"}), 401


# -------- API: messages (get/post) --------
@app.route("/api/messages", methods=["GET"])
def api_messages_get():
    raw = load_json(DATA_FILE, {})
    out = {}
    for k, v in raw.items():
        out[k] = decompress_obj(v) if isinstance(v, str) else v
    return jsonify(out)

@app.route("/api/messages", methods=["POST"])
def api_messages_post():
    data = request.get_json(force=True)
    room = data.get("chat_id")
    if not room:
        return jsonify({"ok": False, "error": "missing chat_id"}), 400

    msg = {
        "id": str(uuid.uuid4()),
        "from": data.get("from", "unknown"),
        "text": data.get("text", "")[:20000],
        "type": data.get("type", "text"),
        "media": data.get("media"),
        "reply_to": data.get("reply_to"),
        "meta": data.get("meta", {}),
        "time": int(time.time())
    }

    raw = load_json(DATA_FILE, {})
    if room in raw and isinstance(raw[room], str):
        arr = decompress_obj(raw[room])
    else:
        arr = raw.get(room, [])
        if not isinstance(arr, list):
            arr = []

    arr.append(msg)
    raw[room] = compress_obj(arr) if COMPRESS else arr
    save_json(DATA_FILE, raw)
    return jsonify({"ok": True, "msg_id": msg["id"]})


# -------- API: groups (get/post) --------
@app.route("/api/groups", methods=["GET"])
def api_groups_get():
    return jsonify(load_json(GROUP_FILE, {}))

@app.route("/api/groups", methods=["POST"])
def api_groups_post():
    g = request.get_json(force=True)
    gid = g.get("id") or str(uuid.uuid4())
    groups = load_json(GROUP_FILE, {})
    groups[gid] = g
    save_json(GROUP_FILE, groups)
    return jsonify({"ok": True, "id": gid})


# -------- API: upload --------
@app.route("/api/upload", methods=["POST"])
def api_upload():
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "no file"}), 400
    f = request.files["file"]
    if f.filename == "":
        return jsonify({"ok": False, "error": "empty filename"}), 400
    if not is_allowed_filename(f.filename):
        return jsonify({"ok": False, "error": "file type not allowed"}), 400

    fname = secure_filename(str(uuid.uuid4()) + "-" + f.filename)
    dest = os.path.join(UPLOADS_DIR, fname)
    try:
        f.save(dest)
    except Exception:
        logging.exception("Failed save upload")
        return jsonify({"ok": False, "error": "save failed"}), 500

    if os.path.getsize(dest) > MAX_MEDIA_SIZE:
        try:
            os.remove(dest)
        except Exception:
            pass
        return jsonify({"ok": False, "error": "file too large"}), 400

    url = f"/{UPLOADS_DIR}/{fname}"
    return jsonify({"ok": True, "url": url, "name": fname})


# -------- API: reminders (simple store) --------
@app.route("/api/reminders", methods=["GET", "POST"])
def api_reminders():
    if request.method == "GET":
        return jsonify(load_json(REMINDER_FILE, {}))
    data = request.get_json(force=True)
    rid = data.get("id") or str(uuid.uuid4())
    reminders = load_json(REMINDER_FILE, {})
    reminders[rid] = data
    save_json(REMINDER_FILE, reminders)
    return jsonify({"ok": True, "id": rid})


# -------- API: admin clear (protected) --------
@app.route("/api/admin/clear", methods=["POST"])
def api_admin_clear():
    key = request.headers.get("X-ADMIN-KEY") or (request.json.get("key") if request.is_json else None)
    if not key:
        return jsonify({"ok": False, "error": "missing admin key"}), 400

    accounts = accounts_map_from_file()
    dev_pw = None
    # find admin/devtool account password
    for uname, entry in accounts.items():
        if uname.lower() in ("devtool", "admin", "dev"):
            dev_pw = entry.get("password")
            break

    if key != dev_pw:
        return jsonify({"ok": False, "error": "forbidden"}), 403

    # clear messages file and uploads
    save_json(DATA_FILE, {})
    try:
        if os.path.exists(UPLOADS_DIR):
            for fname in os.listdir(UPLOADS_DIR):
                p = os.path.join(UPLOADS_DIR, fname)
                try:
                    if os.path.isfile(p):
                        os.remove(p)
                except Exception:
                    logging.exception("remove upload failed %s", p)
    except Exception:
        logging.exception("clear uploads failed")

    return jsonify({"ok": True})


# -------- run --------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    logging.info("Starting Eduground server on port %s", port)
    app.run(host="0.0.0.0", port=port, debug=True)
