import eventlet
eventlet.monkey_patch()

import base64
import time

import cv2
import numpy as np
import mediapipe as mp
from flask import Flask, render_template, request
from flask_socketio import SocketIO

app = Flask(__name__)
app.config["SECRET_KEY"] = "gesture-vision-secret"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet", max_http_buffer_size=10_000_000)

mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils

FILTERS = ["Normal", "Grayscale", "Thermal", "Invert", "Sketch", "Vintage"]

# Per-connection state so multiple users don't share gesture state
SESSIONS = {}


def get_session(sid):
    if sid not in SESSIONS:
        SESSIONS[sid] = {
            "hands": mp_hands.Hands(
                model_complexity=0,
                max_num_hands=2,
                min_detection_confidence=0.6,
                min_tracking_confidence=0.5,
            ),
            "filter_index": 0,
            "pinch_active": False,
            "last_switch_time": 0.0,
        }
    return SESSIONS[sid]


def apply_filter(frame, filter_name):
    if filter_name == "Grayscale":
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

    if filter_name == "Thermal":
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        return cv2.applyColorMap(gray, cv2.COLORMAP_JET)

    if filter_name == "Invert":
        return cv2.bitwise_not(frame)

    if filter_name == "Sketch":
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        inverted = cv2.bitwise_not(gray)
        blurred = cv2.GaussianBlur(inverted, (21, 21), 0)
        inverted_blur = cv2.bitwise_not(blurred)
        sketch = cv2.divide(gray, inverted_blur, scale=256.0)
        return cv2.cvtColor(sketch, cv2.COLOR_GRAY2BGR)

    if filter_name == "Vintage":
        kernel = np.array(
            [[0.272, 0.534, 0.131],
             [0.349, 0.686, 0.168],
             [0.393, 0.769, 0.189]]
        )
        sepia = cv2.transform(frame, kernel)
        sepia = np.clip(sepia, 0, 255).astype(np.uint8)
        rows, cols = frame.shape[:2]
        kernel_x = cv2.getGaussianKernel(cols, cols / 2.5)
        kernel_y = cv2.getGaussianKernel(rows, rows / 2.5)
        vignette_mask = kernel_y * kernel_x.T
        vignette_mask = vignette_mask / vignette_mask.max()
        for c in range(3):
            sepia[:, :, c] = sepia[:, :, c] * vignette_mask
        return sepia

    return frame


def landmark_px(landmark, w, h):
    return int(landmark.x * w), int(landmark.y * h)


def pinch_distance(hand_landmarks, w, h):
    thumb = landmark_px(hand_landmarks.landmark[mp_hands.HandLandmark.THUMB_TIP], w, h)
    index = landmark_px(hand_landmarks.landmark[mp_hands.HandLandmark.INDEX_FINGER_TIP], w, h)
    dist = np.hypot(thumb[0] - index[0], thumb[1] - index[1])
    return dist, thumb, index


def process_frame(frame, state):
    h, w = frame.shape[:2]
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    rgb.flags.writeable = False
    results = state["hands"].process(rgb)

    pinch_this_frame = False
    index_tips = []

    if results.multi_hand_landmarks:
        for hand_landmarks in results.multi_hand_landmarks:
            dist, thumb_pt, index_pt = pinch_distance(hand_landmarks, w, h)
            index_tips.append(index_pt)

            pinch_threshold = 0.06 * max(w, h) / 2  # scales roughly with frame size
            is_pinching = dist < pinch_threshold
            if is_pinching:
                pinch_this_frame = True

            mp_drawing.draw_landmarks(
                frame, hand_landmarks, mp_hands.HAND_CONNECTIONS,
                mp_drawing.DrawingSpec(color=(0, 255, 120), thickness=2, circle_radius=2),
                mp_drawing.DrawingSpec(color=(255, 255, 255), thickness=1),
            )
            cv2.line(frame, thumb_pt, index_pt, (0, 255, 255) if is_pinching else (120, 120, 120), 2)

    now = time.time()
    if pinch_this_frame and not state["pinch_active"] and (now - state["last_switch_time"]) > 0.6:
        state["filter_index"] = (state["filter_index"] + 1) % len(FILTERS)
        state["last_switch_time"] = now
    state["pinch_active"] = pinch_this_frame

    current_filter = FILTERS[state["filter_index"]]

    if len(index_tips) == 2:
        (x1, y1), (x2, y2) = index_tips
        x_min, x_max = sorted([x1, x2])
        y_min, y_max = sorted([y1, y2])
        x_min, y_min = max(0, x_min), max(0, y_min)
        x_max, y_max = min(w, x_max), min(h, y_max)
        if x_max - x_min > 10 and y_max - y_min > 10:
            region = frame[y_min:y_max, x_min:x_max]
            filtered_region = apply_filter(region, current_filter)
            frame[y_min:y_max, x_min:x_max] = filtered_region
            cv2.rectangle(frame, (x_min, y_min), (x_max, y_max), (0, 255, 255), 2)
        else:
            frame = apply_filter(frame, current_filter)
    elif len(index_tips) == 1:
        frame = apply_filter(frame, current_filter)
    else:
        frame = apply_filter(frame, current_filter)

    cv2.putText(frame, f"Filter: {current_filter}", (16, 34),
                cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 0), 4, cv2.LINE_AA)
    cv2.putText(frame, f"Filter: {current_filter}", (16, 34),
                cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 120), 2, cv2.LINE_AA)

    return frame, current_filter


@app.route("/")
def index():
    return render_template("index.html", filters=FILTERS)


@socketio.on("connect")
def on_connect():
    get_session(request_sid())


@socketio.on("disconnect")
def on_disconnect():
    sid = request_sid()
    state = SESSIONS.pop(sid, None)
    if state:
        state["hands"].close()


def request_sid():
    return request.sid


@socketio.on("frame")
def on_frame(data):
    sid = request_sid()
    state = get_session(sid)

    try:
        header, encoded = data.split(",", 1)
        img_bytes = base64.b64decode(encoded)
        np_arr = np.frombuffer(img_bytes, dtype=np.uint8)
        frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        if frame is None:
            return
    except Exception:
        return

    frame, current_filter = process_frame(frame, state)

    ok, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
    if not ok:
        return
    out_b64 = "data:image/jpeg;base64," + base64.b64encode(buffer).decode("utf-8")
    socketio.emit("processed_frame", {"image": out_b64, "filter": current_filter}, to=sid)


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
