from flask import Flask, jsonify, request
from flask_cors import CORS
import json, os

app = Flask(__name__)
CORS(app)

# ====== FILE PATHS ======
MSG_FILE = 'messages.json'
GRP_FILE = 'groups.json'

# ====== LOAD JSON SAFELY ======
def load_json(path):
    if not os.path.exists(path):
        with open(path, 'w', encoding='utf-8') as f:
            f.write('{}')
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        try:
            return json.load(f)
        except:
            return {}

def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ====== BASIC ROUTES ======
@app.route('/')
def home():
    return jsonify({"status": "Eduground server running", "version": "v2.0"})

@app.route('/gun', methods=['GET', 'POST'])
def gun_placeholder():
    return jsonify({"msg": "Gun relay placeholder (Render)"})

# ====== MESSAGES API ======
@app.route('/messages', methods=['GET', 'POST'])
def handle_messages():
    if request.method == 'GET':
        data = load_json(MSG_FILE)
        return jsonify(data)

    elif request.method == 'POST':
        msg = request.get_json(force=True)
        all_msgs = load_json(MSG_FILE)
        chat_id = msg.get('chat_id')
        if not chat_id:
            return jsonify({"error": "missing chat_id"}), 400

        if chat_id not in all_msgs:
            all_msgs[chat_id] = []
        all_msgs[chat_id].append(msg)
        save_json(MSG_FILE, all_msgs)
        return jsonify({"status": "ok", "stored": len(all_msgs[chat_id])})

# ====== GROUPS API ======
@app.route('/groups', methods=['GET', 'POST'])
def handle_groups():
    if request.method == 'GET':
        data = load_json(GRP_FILE)
        return jsonify(data)
    elif request.method == 'POST':
        g = request.get_json(force=True)
        all_grps = load_json(GRP_FILE)
        gid = g.get('id')
        if not gid:
            return jsonify({"error": "missing id"}), 400
        all_grps[gid] = g
        save_json(GRP_FILE, all_grps)
        return jsonify({"status": "ok"})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
