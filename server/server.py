# server.py
from flask import Flask, jsonify, request, send_from_directory, abort
from flask_cors import CORS
from werkzeug.utils import secure_filename
import os, json, time, zlib, base64, threading, uuid, shutil

# --- CONFIG ---
WEB_DIR = "web"
UPLOADS_DIR = "uploads"
DATA_FILE = "messages.json"       # compressed by chat room keys
GROUP_FILE = "groups.json"
ACCOUNTS_FILE = "accounts.json"
TTL_SECONDS_TEXT = 60 * 60 * 24 * 60   # 60 days default for text (you said 30/60 earlier; adjust)
TTL_SECONDS_MEDIA = 60 * 60 * 24 * 30  # 30 days for media
COMPRESS = True
MAX_MEDIA_SIZE = 8 * 1024 * 1024  # 8MB max upload

os.makedirs(UPLOADS_DIR, exist_ok=True)

app = Flask(__name__, static_folder=WEB_DIR, static_url_path='/')
CORS(app)

# ---- helpers ----
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
        raw = base64.b64decode(s)
        return json.loads(zlib.decompress(raw).decode("utf-8"))
    except Exception:
        return []

# --- background prune thread ---
def prune_loop():
    while True:
        try:
            # prune messages (keep by TTL)
            msgs_raw = load_json(DATA_FILE, {})
            msgs = {}
            now = time.time()
            for room, val in msgs_raw.items():
                # decompress if string
                arr = val
                if isinstance(val, str):
                    arr = decompress_obj(val)
                # keep messages under TTL_SECONDS_TEXT
                arr2 = [m for m in arr if (now - m.get("time", now)) < TTL_SECONDS_TEXT]
                msgs[room] = arr2
            # save compressed
            out = {k: compress_obj(v) if COMPRESS else v for k, v in msgs.items()}
            save_json(DATA_FILE, out)
        except Exception as e:
            print("Prune messages error:", e)

        # prune uploads older than TTL_SECONDS_MEDIA
        try:
            now = time.time()
            for fname in os.listdir(UPLOADS_DIR):
                p = os.path.join(UPLOADS_DIR, fname)
                if os.path.isfile(p):
                    age = now - os.path.getmtime(p)
                    if age > TTL_SECONDS_MEDIA:
                        try:
                            os.remove(p)
                        except: pass
        except Exception as e:
            print("Prune uploads error:", e)

        time.sleep(60 * 60)  # run every hour

threading.Thread(target=prune_loop, daemon=True).start()

# ---- static / index routes ----
@app.route('/')
def index():
    return send_from_directory(WEB_DIR, 'index.html')

@app.route('/<path:fp>')
def static_proxy(fp):
    # serve from web folder (HTML, assets)
    if os.path.exists(os.path.join(WEB_DIR, fp)):
        return send_from_directory(WEB_DIR, fp)
    # serve uploads
    if os.path.exists(os.path.join(UPLOADS_DIR, fp)):
        return send_from_directory(UPLOADS_DIR, fp)
    return abort(404)

# ---- API: accounts / login ----
@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json(force=True)
    user = data.get("username")
    pw = data.get("password")
    if not user or pw is None:
        return jsonify({"ok": False, "error": "Missing credentials"}), 400
    accounts = load_json(ACCOUNTS_FILE, {})
    # accounts expected: { "username": {"password":"..","role":".."}, ... }
    entry = accounts.get(user)
    if not entry:
        # try case-insensitive match (useful when names have diacritics)
        for k, v in accounts.items():
            if k.lower() == user.lower():
                entry = v
                user = k
                break
    if entry and entry.get("password") == pw:
        return jsonify({"ok": True, "user": user, "role": entry.get("role", "student")})
    return jsonify({"ok": False, "error": "Invalid credentials"}), 401

# ---- API: messages ----
@app.route('/api/messages', methods=['GET'])
def api_messages_get():
    # returns decompressed messages dict: { room: [...] }
    raw = load_json(DATA_FILE, {})
    out = {}
    for k, v in raw.items():
        if isinstance(v, str):
            out[k] = decompress_obj(v)
        else:
            out[k] = v
    return jsonify(out)

@app.route('/api/messages', methods=['POST'])
def api_messages_post():
    data = request.get_json(force=True)
    room = data.get("chat_id")
    if not room:
        return jsonify({"ok": False, "error": "missing chat_id"}), 400
    # sanity fields
    msg = {
        "id": str(uuid.uuid4()),
        "from": data.get("from", "unknown"),
        "text": data.get("text", "")[:10000],
        "type": data.get("type", "text"),
        "media": data.get("media", None),
        "reply_to": data.get("reply_to"),
        "meta": data.get("meta", {}),
        "time": int(time.time())
    }
    raw = load_json(DATA_FILE, {})
    # decompress if needed
    arr = []
    if room in raw:
        if isinstance(raw[room], str):
            arr = decompress_obj(raw[room])
        else:
            arr = raw[room]
    arr.append(msg)
    # compress and save
    raw[room] = compress_obj(arr) if COMPRESS else arr
    save_json(DATA_FILE, raw)
    return jsonify({"ok": True, "msg_id": msg["id"]})

# ---- API: groups ----
@app.route('/api/groups', methods=['GET'])
def api_groups_get():
    g = load_json(GROUP_FILE, {})
    return jsonify(g)

@app.route('/api/groups', methods=['POST'])
def api_groups_post():
    g = request.get_json(force=True)
    gid = g.get("id") or str(uuid.uuid4())
    groups = load_json(GROUP_FILE, {})
    groups[gid] = g
    save_json(GROUP_FILE, groups)
    return jsonify({"ok": True, "id": gid})

# ---- API: file upload (media) ----
ALLOWED_EXT = set(["png","jpg","jpeg","gif","mp4","webm","mov","mkv","pdf"])
def allowed(fname):
    ext = fname.rsplit(".",1)[-1].lower() if "." in fname else ""
    return ext in ALLOWED_EXT

@app.route('/api/upload', methods=['POST'])
def api_upload():
    if 'file' not in request.files:
        return jsonify({"ok": False, "error": "no file"}), 400
    f = request.files['file']
    if f.filename == "":
        return jsonify({"ok": False, "error": "empty filename"}), 400
    if not allowed(f.filename):
        return jsonify({"ok": False, "error": "file type not allowed"}), 400
    fname = secure_filename(str(uuid.uuid4()) + "-" + f.filename)
    dest = os.path.join(UPLOADS_DIR, fname)
    f.save(dest)
    size = os.path.getsize(dest)
    if size > MAX_MEDIA_SIZE:
        # remove and reject
        try: os.remove(dest)
        except: pass
        return jsonify({"ok": False, "error": "file too large"}), 400
    url = f"/{UPLOADS_DIR}/{fname}"
    return jsonify({"ok": True, "url": url, "name": fname})

# ---- admin endpoint: clear all (restricted in UI to devtool role) ----
@app.route('/api/admin/clear', methods=['POST'])
def admin_clear():
    # simple api key via header or body for demo. In production protect properly.
    key = request.headers.get("X-ADMIN-KEY") or request.json.get("key") if request.is_json else None
    accounts = load_json(ACCOUNTS_FILE, {})
    if key != accounts.get("devtool", {}).get("password"):
        return jsonify({"ok": False, "error": "forbidden"}), 403
    # remove data
    save_json(DATA_FILE, {})
    # remove uploads
    try:
        shutil.rmtree(UPLOADS_DIR)
        os.makedirs(UPLOADS_DIR, exist_ok=True)
    except Exception as e:
        print("clear uploads err", e)
    return jsonify({"ok": True})

# ---- run ----
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
