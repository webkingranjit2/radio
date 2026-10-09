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

# গ্লোবাল ক্লায়েন্ট কিউ এবং লক (সবার জন্য একই স্ট্রিম সিঙ্ক রাখতে)
clients = []
clients_lock = threading.Lock()

def get_shuffled_playlist():
    """ইউটিউব প্লেলিস্ট ফেচ করে র্যান্ডমলি সাজাবে"""
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
    """মাস্টার ব্রডকাস্টার: ব্যাকগ্রাউন্ডে একা একা 24/7 চলতে থাকবে এবং সবার জন্য স্ট্রিম জেনারেট করবে"""
    while True:
        video_urls = get_shuffled_playlist()
        if not video_urls:
            time.sleep(10)
            continue
            
        for v_url in video_urls:
            try:
                # yt-dlp দিয়ে ইউটিউব লিংক থেকে অডিও স্ট্রিম বের করা
                cmd = ['yt-dlp', '-g', '-f', 'bestaudio', v_url]
                stream_url = subprocess.check_output(cmd).decode('utf-8').strip().split('\n')[0]
                
                # FFmpeg দিয়ে এমপিথ্রি স্ট্রিমে কনভার্ট করা
                ffmpeg_cmd = [
                    'ffmpeg', '-i', stream_url, '-vn', '-f', 'mp3', '-ab', '128k', 'pipe:1'
                ]
                process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                
                while True:
                    chunk = process.stdout.read(4096)
                    if not chunk:
                        break
                    
                    # সমস্ত কানেক্টেড ইউজারকে রিয়েল-টাইমে একই বাইট বা অংশ পাঠানো
                    with clients_lock:
                        for q in clients:
                            try:
                                q.put_nowait(chunk)
                            except queue.Full:
                                pass # স্লো কানেকশন স্কিপ করবে যাতে লাইভ সিঙ্ক নষ্ট না হয়
                                
                process.terminate()
            except Exception as e:
                print("Streaming Error:", e)
                time.sleep(3)

# সার্ভার চালু হওয়ার সাথেই ব্যাকগ্রাউন্ডে মাস্টার ব্রডকাস্টার চালু হয়ে যাবে
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

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

