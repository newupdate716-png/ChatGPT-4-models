from flask import Flask, request, Response
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

    def generate():
        session = requests.Session()
        base_url = "https://www.free-ai-online.com/"
        
        nonce = get_nonce(session, base_url)
        if not nonce:
            yield "data: Error: Could not fetch security token (nonce)\n\n"
            return

        payload = {
            "botId": "default", # 'GPT-5' এর বদলে 'default' বেশি স্থিতিশীল
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
                timeout=20
            )

            # ⚡ ডুপ্লিকেট রোধ করার জন্য লুপ
            for line in r.iter_lines(decode_unicode=True):
                if line and line.startswith("data:"):
                    try:
                        # 'data: ' অংশটুকু বাদ দিয়ে JSON লোড করা
                        raw_json = line[5:].strip()
                        data = json.loads(raw_json)

                        # শুধুমাত্র 'live' টাইপের ডাটা থেকে টেক্সট নেওয়া
                        if data.get("type") == "live":
                            chunk = data.get("data", "")
                            if chunk:
                                yield f"data: {chunk}\n\n"
                        
                        # শেষ হয়ে গেলে লুপ বন্ধ করা
                        if data.get("type") == "end":
                            break
                    except:
                        continue
        except Exception as e:
            yield f"data: Connection Error: {str(e)}\n\n"

    return Response(generate(), mimetype="text/event-stream")

if __name__ == "__main__":
    # Vercel বা অন্য প্ল্যাটফর্মে হোস্টিং এর জন্য 0.0.0.0 ব্যবহার করা হয়েছে
    app.run(host="0.0.0.0", port=5000, threaded=True)