import os
import time
import queue
import threading
import requests
from flask import Flask, Response

app = Flask(__name__)

# আপনার দেওয়া ডিরেক্ট এমপি থ্রি লিংক
MP3_URL = "https://freeweb24.page.gd/mp3/arijit/Bangla_Romantic/01_Thik_Emon_Ebhabe.mp3"

clients = []
clients_lock = threading.Lock()

def master_broadcaster():
    """ডিরেক্ট এমপি থ্রি ফাইলটি লুপ আকারে ব্যাকগ্রাউন্ডে স্ট্রিম করতে থাকবে"""
    while True:
        try:
            print("Connecting to direct MP3 stream...")
            response = requests.get(MP3_URL, stream=True)
            if response.status_code == 200:
                for chunk in response.iter_content(chunk_size=4096):
                    if chunk:
                        with clients_lock:
                            for q in clients:
                                try:
                                    q.put_nowait(chunk)
                                except queue.Full:
                                    pass
            else:
                print(f"Failed to fetch MP3. Status code: {response.status_code}")
                time.sleep(5)
        except Exception as e:
            print(f"Broadcaster Error: {e}")
            time.sleep(5)

# ব্যাকগ্রাউন্ড ব্রডকাস্টার চালু করা হলো
threading.Thread(target=master_broadcaster, daemon=True).start()

@app.route('/stream')
def stream():
    q = queue.Queue(maxsize=200)
    with clients_lock:
        clients.append(q)
        
    def generate():
        try:
            while True:
                chunk = q.get()
                yield chunk
        except GeneratorExit:
            with clients_lock:
                if q in clients:
                    clients.remove(q)

    return Response(generate(), mimetype='audio/mpeg')

@app.route('/')
def home():
    return "Direct MP3 Radio Server is Live and Running!"

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
