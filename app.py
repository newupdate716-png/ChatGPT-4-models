from flask import Flask, request, Response, jsonify
import requests, json, re
from user_agent import generate_user_agent as a

app = Flask(__name__)

# 🔐 Nonce সংগ্রহ করার ফাংশন
def get_nonce(session, url):
    try:
        r = session.get(url, headers={'User-Agent': a()}, timeout=10)
        r.raise_for_status()
        
        patterns = [
            r'var\s+mwai_nonce\s*=\s*["\']([a-f0-9]+)["\']',
            r'"nonce":"([a-f0-9]+)"',
            r'name=["\'](?:wp-)?nonce["\']\s+content=["\']([a-f0-9]+)["\']',
            r'x-wp-nonce:\s*["\']?([a-f0-9]+)["\']?'
        ]

        for p in patterns:
            m = re.search(p, r.text, re.I)
            if m: return m.group(1)
    except:
        pass
    return None

@app.route("/chat", methods=["GET", "POST"])
def chat():
    # ইউজার মেসেজ রিসিভ করা
    if request.method == "GET":
        message = request.args.get("message", "Hello")
    else:
        message = (request.json or {}).get("message", "Hello")

    session = requests.Session()
    base_url = "https://www.free-ai-online.com/"
    
    nonce = get_nonce(session, base_url)
    if not nonce:
        return jsonify({"status": "error", "message": "Could not fetch nonce"}), 403

    payload = {
        "botId": "default",
        "messages": [],
        "newMessage": message,
        "stream": True
    }

    headers = {
        "User-Agent": a(),
        "Accept": "text/event-stream",
        "Content-Type": "application/json",
        "X-WP-Nonce": nonce,
        "Referer": base_url,
        "Origin": base_url
    }

    try:
        r = session.post(
            f"{base_url}wp-json/mwai-ui/v1/chats/submit",
            json=payload,
            headers=headers,
            stream=True,
            timeout=30
        )

        full_response = "" # সব ডাটা এখানে জমা হবে

        # ⚡ লুপের মাধ্যমে সব ডাটা আগে সংগ্রহ করা হচ্ছে
        for line in r.iter_lines(decode_unicode=True):
            if line and line.startswith("data:"):
                try:
                    raw_json = line[5:].strip()
                    data = json.loads(raw_json)

                    if data.get("type") == "live":
                        chunk = data.get("data", "")
                        full_response += chunk # প্রতিটি শব্দ জোড়া দেওয়া হচ্ছে
                    
                    if data.get("type") == "end":
                        break
                except:
                    continue

        # শেষে সব ডাটা একসাথে "data:" ফরম্যাটে পাঠানো হচ্ছে
        return Response(f"data: {full_response.strip()}\n\n", mimetype="text/event-stream")

    except Exception as e:
        return Response(f"data: Error occurred: {str(e)}\n\n", mimetype="text/event-stream")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, threaded=True)
