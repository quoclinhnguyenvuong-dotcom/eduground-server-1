from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

API_URL = "https://openrouter.ai/api/v1/chat/completions"
API_KEY = "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"

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    message = data.get("message", "")
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "deepseek/deepseek-chat",
        "messages": [
            {"role": "system", "content": "Bạn là trợ lý học tập thông minh của nền tảng Eduground."},
            {"role": "user", "content": message}
        ]
    }

    response = requests.post(API_URL, headers=headers, json=payload)
    return jsonify(response.json())

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)