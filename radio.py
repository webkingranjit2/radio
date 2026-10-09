import os
import time
import random
import queue
import threading
import subprocess
import requests
from flask import Flask, Response

app = Flask(__name__)

API_KEY = "AIzaSyCies-uvd8a-2yN0vSWCdxEXEVONT0Pja4"
PLAYLIST_ID = "PLLounUW9rgqHr6YYR7r4oQOIeqdCZ7gO8"

clients = []
clients_lock = threading.Lock()

def get_shuffled_playlist():
    url = f"https://www.googleapis.com/youtube/v3/playlistItems?part=snippet&maxResults=50&playlistId={PLAYLIST_ID}&key={API_KEY}"
    try:
        response = requests.get(url)
        data = response.json()
        video_urls = []
        if "items" in data:
            for item in data["items"]:
                video_id = item["snippet"]["resourceId"]["videoId"]
                video_urls.append(f"https://www.youtube.com/watch?v={video_id}")
        random.shuffle(video_urls)
        return video_urls
    except Exception as e:
        print("API Error:", e)
        return []

def master_broadcaster():
    # সার্ভার চালুর সাথে সাথে একটি ডামি বাইট বা লুপ বজায় রাখা
    while True:
        video_urls = get_shuffled_playlist()
        if not video_urls:
            print("Playlist empty or API limit reached. Retrying in 10s...")
            time.sleep(10)
            continue
            
        for v_url in video_urls:
            try:
                print(f"Fetching audio for: {v_url}")
                cmd = [
                    'yt-dlp', 
                    '--cookies', 'cookies.txt', 
                    '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    '-g', '-f', 'bestaudio', 
                    v_url
                ]
                stream_output = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                
                if stream_output.returncode != 0:
                    print(f"Skipping restricted/error video: {v_url}")
                    continue
                
                stream_url = stream_output.stdout.strip().split('\n')[0]
                
                ffmpeg_cmd = [
                    'ffmpeg', '-i', stream_url, '-vn', '-f', 'mp3', '-ab', '128k', 'pipe:1'
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
                print(f"Streaming Error: {e}")
                time.sleep(2)
                continue

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
    return "Radio Server is Live and Running!"

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
