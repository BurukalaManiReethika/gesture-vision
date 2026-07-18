# Gesture-Vision (Web Edition)

Real-time hand-gesture-controlled video filters, running fully in the browser + a
Flask/SocketIO backend — deployable on Render.

## Why this architecture

The original desktop version opens a webcam directly with `cv2.VideoCapture(0)`.
That works locally but **cannot work on Render** (or any cloud host): the server
has no camera, only your laptop/phone does. So this version:

1. Captures your webcam **in the browser** (`getUserMedia`).
2. Streams JPEG frames to the Flask server over a WebSocket (Socket.IO).
3. The server runs MediaPipe Hands + OpenCV filters on each frame.
4. The processed frame is streamed back and drawn on the page.

This is the standard pattern for "server-side CV on a live camera feed" web apps.

## Features

- Real-time hand landmark detection (MediaPipe Hands)
- Pinch gesture (thumb tip ↔ index tip) switches filters, with debounce so one
  pinch = one switch
- Filters: Normal, Grayscale, Thermal, Invert, Sketch, Vintage
- Two-hand region mode: when both hands are visible, the current filter is
  applied only inside the rectangle defined by both index fingertips
- Per-connection session state, so multiple users don't interfere with each
  other's gesture state

## Run locally

```bash
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open http://localhost:5000, click **Start Camera**, allow camera access.

## Deploy on Render

1. Push this folder to a GitHub repo.
2. In Render, click **New → Web Service**, connect the repo.
3. Render will auto-detect `render.yaml`. If it doesn't, set manually:
   - **Environment**: Python
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn --worker-class eventlet -w 1 app:app`
   - **Environment Variable**: `PYTHON_VERSION` = `3.11.9`
4. Deploy. Render gives you an HTTPS URL — the browser will only allow webcam
   access over HTTPS or localhost, and Render's URLs are HTTPS by default, so
   this works out of the box.
5. Free-tier Render instances are CPU-only and can spin down when idle, so the
   first request after inactivity will be slow, and per-frame latency will be
   higher than running locally. For smoother performance, use a paid instance
   with more CPU, or lower `SEND_FPS` in `static/js/main.js`.

## Notes / tuning

- `SEND_FPS` in `static/js/main.js` controls how many frames per second are
  sent to the server (default 12). Lower it if the video feels laggy on a
  slow connection or free-tier instance.
- JPEG quality for outgoing/incoming frames is set to keep bandwidth low;
  raise the quality values in `app.py` / `main.js` if you want sharper video
  at the cost of latency.
- The pinch threshold in `app.py` (`pinch_distance` / `pinch_threshold`) is
  relative to frame size — adjust if gestures trigger too easily or not
  easily enough.
