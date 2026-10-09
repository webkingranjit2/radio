import os
import time
import queue
import threading
import subprocess
from flask import Flask, Response

app = Flask(__name__)

# আপনার নির্দিষ্ট ইউটিউব ভিডিও লিংক
VIDEO_URL = "https://youtu.be/yKbFhvKbXxw"

clients = []
clients_lock = threading.Lock()

def master_broadcaster():
    """একই ভিডিও বারবার লুপ আকারে ব্যাকগ্রাউন্ডে স্ট্রিম করতে থাকবে"""
    while True:
        try:
            print(f"Fetching audio stream for video...")
            cmd = [
                'yt-dlp', 
                '--cookies', 'cookies.txt', 
                '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                '-g', '-f', 'bestaudio', 
                VIDEO_URL
            ]
            stream_output = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
            if stream_output.returncode != 0:
                print("Error fetching video stream. Retrying in 5 seconds...")
                time.sleep(5)
                continue
            
            stream_url = stream_output.stdout.strip().split('\n')[0]
            
            # FFmpeg দিয়ে অডিও স্ট্রিম লুপ করা
            ffmpeg_cmd = [
                'ffmpeg', '-re', '-i', stream_url, '-vn', '-f', 'mp3', '-ab', '128k', 'pipe:1'
            ]
            process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            
            while True:
                chunk = process.stdout.read(4096)
                if not chunk:
                    break  # গান শেষ হলে আবার লুপের শুরুতে গিয়ে রি-প্লে হবে
                
                with clients_lock:
                    for q in clients:
                        try:
                            q.put_nowait(chunk)
                        except queue.Full:
                            pass
                            
            process.terminate()
        except Exception as e:
            print(f"Streaming Error: {e}")
            time.sleep(3)

# ব্যাকগ্রাউন্ড মাস্টার ব্রডকাস্টার চালু করা হলো
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
    return "Radio Server is Live and Streaming Single Video 24/7!"

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
