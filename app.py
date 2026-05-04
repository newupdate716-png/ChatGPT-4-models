from flask import Flask, request, Response
import requests, json, re
from user_agent import generate_user_agent as a

app = Flask(__name__)

# 🔐 Get nonce
def get_nonce(session, url):
    r = session.get(url, headers={'User-Agent': a()})
    r.raise_for_status()

    patterns = [
        r'var\s+mwai_nonce\s*=\s*["\']([a-f0-9]+)["\']',
        r'"nonce":"([a-f0-9]+)"',
        r'<meta\s+name=["\']wp-nonce["\']\s+content=["\']([a-f0-9]+)["\']',
        r'<meta\s+name=["\']nonce["\']\s+content=["\']([a-f0-9]+)["\']',
        r'x-wp-nonce:\s*["\']?([a-f0-9]+)["\']?'
    ]

    for p in patterns:
        m = re.search(p, r.text, re.I)
        if m:
            return m.group(1)

    return None


@app.route("/chat", methods=["GET", "POST"])
def chat():
    message = request.args.get("message") if request.method == "GET" else (request.json or {}).get("message", "Hello")

    def generate():
        session = requests.Session()
        base_url = "https://www.free-ai-online.com/"

        nonce = get_nonce(session, base_url)
        if not nonce:
            yield "data: Error getting nonce\n\n"
            return

        payload = {
            "botId": "GPT-5",
            "customId": None,
            "contextId": None,
            "messages": [{"role": "assistant", "content": "", "who": "AI: "}],
            "newMessage": message,
            "newFileId": None,
            "newFileIds": None,
            "stream": True
        }

        headers = {
            "User-Agent": a(),
            "Accept": "text/event-stream",
            "Content-Type": "application/json",
            "x-wp-nonce": nonce,
            "origin": base_url
        }

        r = session.post(
            base_url + "wp-json/mwai-ui/v1/chats/submit",
            data=json.dumps(payload),
            headers=headers,
            stream=True
        )

        # ⚡ STREAM LOOP (NO DUPLICATE)
        for line in r.iter_lines(decode_unicode=True):
            if line and line.startswith("data:"):
                try:
                    data = json.loads(line[6:])

                    if data.get("type") == "live":
                        chunk = data.get("data", "")
                        yield f"data:{chunk}\n\n"   # no extra space

                    elif data.get("type") == "end":
                        break  # ❌ final duplicate skip

                except:
                    pass

    return Response(generate(), mimetype="text/event-stream")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, threaded=True)
