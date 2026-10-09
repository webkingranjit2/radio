import os
import time
import queue
import threading
import subprocess
from flask import Flask, Response

app = Flask(__name__)

VIDEO_URL = "https://youtu.be/yKbFhvKbXxw"

clients = []
clients_lock = threading.Lock()

def master_broadcaster():
    while True:
        try:
            print("Fetching direct stream URL with cookies and android client...")
            cmd = [
                'yt-dlp', 
                '--cookies', 'cookies.txt',
                '--extractor-args', 'youtube:player_client=android',
                '--no-warnings', 
                '-g', 
                '-f', 'bestaudio', 
                VIDEO_URL
            ]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
            if result.returncode != 0:
                print(f"Error fetching URL: {result.stderr}")
                time.sleep(5)
                continue
                
            stream_url = result.stdout.strip().split('\n')[0]
            print("Stream URL obtained successfully, starting ffmpeg...")
            
            ffmpeg_cmd = [
                'ffmpeg', '-re', '-i', stream_url, '-vn', '-f', 'mp3', '-ab', '128k', 'pipe:1'
            ]
            process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            
            while True:
                chunk = process.stdout.read(4096)
                if not chunk:
                    break
                
                with clients_lock:
                    for q in clients:
                        try:
                            q.put_nowait(chunk)
                        except queue.Full:
                            pass
                            
            process.terminate()
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(3)

threading.Thread(target=master_broadcaster, daemon=True).start()

@app.route('/stream')
def stream():
    q = queue.Queue(maxsize=100)
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
    return "Radio is Running!"

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
