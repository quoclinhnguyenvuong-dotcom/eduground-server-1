# server.py
# EduGround backend — stable Render-ready version

from flask import Flask, jsonify, request, send_from_directory, abort
from flask_cors import CORS
from werkzeug.utils import secure_filename
import os, json, time, zlib, base64, threading, uuid, shutil, requests

# ---------- CONFIG ----------
WEB_DIR = "web"
UPLOADS_DIR = "uploads"
DATA_FILE = "messages.json"
GROUP_FILE = "groups.json"
REMINDER_FILE = "reminders.json"
ACCOUNTS_FILE = os.path.join(WEB_DIR, "accounts.json")

TTL_SECONDS_TEXT = 60 * 60 * 24 * 30    # 30 days
TTL_SECONDS_MEDIA = 60 * 60 * 24 * 15   # 15 days
COMPRESS = True
MAX_MEDIA_SIZE = 8 * 1024 * 1024
ALLOWED_EXT = {"png", "jpg", "jpeg", "gif", "mp4", "webm", "mov", "mkv", "pdf"}

OPENROUTER_API_KEY = os.environ.get("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")
OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "z-ai/glm-4.5-air:free"

os.makedirs(UPLOADS_DIR, exist_ok=True)

app = Flask(__name__, static_folder=WEB_DIR, static_url_path="/static")
CORS(app)


# ---------- HELPERS ----------
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


def allowed_filename(fname):
    return "." in fname and fname.rsplit(".", 1)[-1].lower() in ALLOWED_EXT


# ---------- BACKGROUND PRUNE ----------
def prune_loop():
    while True:
        try:
            msgs_raw = load_json(DATA_FILE, {})
            msgs = {}
            now = time.time()
            for room, val in msgs_raw.items():
                arr = decompress_obj(val) if isinstance(val, str) else val
                arr2 = [m for m in arr if (now - m.get("time", now)) < TTL_SECONDS_TEXT]
                msgs[room] = compress_obj(arr2) if COMPRESS else arr2
            save_json(DATA_FILE, msgs)
        except Exception as e:
            print("Prune messages error:", e)

        try:
            now = time.time()
            for fname in os.listdir(UPLOADS_DIR):
                p = os.path.join(UPLOADS_DIR, fname)
                if os.path.isfile(p):
                    age = now - os.path.getmtime(p)
                    if age > TTL_SECONDS_MEDIA:
                        try:
                            os.remove(p)
                            print("🗑️ Removed old upload:", fname)
                        except Exception as e:
                            print("Remove upload error:", e)
        except Exception as e:
            print("Prune uploads error:", e)

        time.sleep(60 * 60)  # run hourly


threading.Thread(target=prune_loop, daemon=True).start()


# ---------- STATIC ROUTES ----------
@app.route("/")
def index():
    return send_from_directory(WEB_DIR, "index.html")


@app.route("/<path:fp>")
def static_proxy(fp):
    web_path = os.path.join(WEB_DIR, fp)
    upload_path = os.path.join(UPLOADS_DIR, fp)
    if os.path.exists(web_path) and os.path.isfile(web_path):
        return send_from_directory(WEB_DIR, fp)
    elif os.path.exists(upload_path) and os.path.isfile(upload_path):
        return send_from_directory(UPLOADS_DIR, fp)
    else:
        return abort(404)


# ---------- LOGIN ----------
@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(force=True)
    user = data.get("username")
    pw = data.get("password")

    if not user or pw is None:
        return jsonify({"ok": False, "error": "Missing credentials"}), 400

    accounts = load_json(ACCOUNTS_FILE, {}).get("users", [])
    for entry in accounts:
        if entry["username"].lower() == user.lower() and entry["password"] == pw:
            return jsonify({"ok": True, "user": entry["username"], "role": entry["role"]})
    return jsonify({"ok": False, "error": "Invalid credentials"}), 401


# ---------- MESSAGES ----------
@app.route("/api/messages", methods=["GET", "POST"])
def api_messages():
    if request.method == "GET":
        raw = load_json(DATA_FILE, {})
        out = {k: decompress_obj(v) if isinstance(v, str) else v for k, v in raw.items()}
        return jsonify(out)

    data = request.get_json(force=True)
    room = data.get("chat_id")
    if not room:
        return jsonify({"ok": False, "error": "missing chat_id"}), 400

    msg = {
        "id": str(uuid.uuid4()),
        "from": data.get("from", "unknown"),
        "text": data.get("text", ""),
        "type": data.get("type", "text"),
        "media": data.get("media"),
        "reply_to": data.get("reply_to"),
        "meta": data.get("meta", {}),
        "time": int(time.time())
    }

    raw = load_json(DATA_FILE, {})
    arr = decompress_obj(raw[room]) if room in raw and isinstance(raw[room], str) else raw.get(room, [])
    arr.append(msg)
    raw[room] = compress_obj(arr) if COMPRESS else arr
    save_json(DATA_FILE, raw)

    return jsonify({"ok": True, "msg_id": msg["id"]})


# ---------- GROUPS ----------
@app.route("/api/groups", methods=["GET", "POST"])
def api_groups():
    if request.method == "GET":
        return jsonify(load_json(GROUP_FILE, {}))

    g = request.get_json(force=True)
    gid = g.get("id") or str(uuid.uuid4())
    groups = load_json(GROUP_FILE, {})
    groups[gid] = gsave_json(GROUP_FILE, groups)
    return jsonify({"ok": True, "id": gid})


# ---------- UPLOAD ----------
@app.route("/api/upload", methods=["POST"])
def api_upload():
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "no file"}), 400

    f = request.files["file"]
    if f.filename == "":
        return jsonify({"ok": False, "error": "empty filename"}), 400
    if not allowed_filename(f.filename):
        return jsonify({"ok": False, "error": "file type not allowed"}), 400

    fname = secure_filename(str(uuid.uuid4()) + "-" + f.filename)
    dest = os.path.join(UPLOADS_DIR, fname)
    f.save(dest)

    if os.path.getsize(dest) > MAX_MEDIA_SIZE:
        os.remove(dest)
        return jsonify({"ok": False, "error": "file too large"}), 400

    url = f"/{UPLOADS_DIR}/{fname}"
    return jsonify({"ok": True, "url": url, "name": fname})


# ---------- REMINDERS ----------
@app.route("/api/reminders", methods=["GET", "POST"])
def api_reminders():
    if request.method == "GET":
        return jsonify(load_json(REMINDER_FILE, {}))

    data = request.get_json(force=True)
    text = data.get("text", "")
    user = data.get("user", "unknown")

    if not text.strip():
        return jsonify({"ok": False, "error": "empty text"}), 400

    reminder = {
        "id": str(uuid.uuid4()),
        "user": user,
        "text": text,
        "summary": summarize_text(text),
        "time": int(time.time())
    }

    reminders = load_json(REMINDER_FILE, {})
    reminders[reminder["id"]] = reminder
    save_json(REMINDER_FILE, reminders)

    return jsonify({"ok": True, "id": reminder["id"], "summary": reminder["summary"]})


def summarize_text(text):
    if not OPENROUTER_API_KEY:
        return "Tóm tắt: " + text[:100] + ("..." if len(text) > 100 else "")

    try:
        payload = {
            "model": OPENROUTER_MODEL,
            "messages": [
                {"role": "system", "content": "Summarize the teacher's reminder clearly and briefly."},
                {"role": "user", "content": text}
            ],
            "max_tokens": 200
        }
        headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
        resp = requests.post(OPENROUTER_ENDPOINT, json=payload, headers=headers, timeout=20)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
    except Exception as e:
        print("AI summary error:", e)
    return text[:100] + ("..." if len(text) > 100 else "")


# ---------- ADMIN CLEAR ----------
@app.route("/api/admin/clear", methods=["POST"])
def admin_clear():
    key = request.headers.get("X-ADMIN-KEY")
    accounts = load_json(ACCOUNTS_FILE, {}).get("users", [])
    devtool_pw = next((u["password"] for u in accounts if u["username"] == "devtool"), None)
    if key != devtool_pw:
        if user_role != "admin":
    return jsonify({"ok": False, "error": "forbidden"}), 403

save_json(DATA_FILE, {})
    try:
        shutil.rmtree(UPLOADS_DIR)
        os.makedirs(UPLOADS_DIR, exist_ok=True)
    except Exception as e:
        print("Clear uploads error:", e)

    return jsonify({"ok": True})


# ---------- RUN ----------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
