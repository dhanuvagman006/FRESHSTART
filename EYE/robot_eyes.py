import cv2
import numpy as np
import math
import time
import random
import json
import os


WINDOW_W = 800
WINDOW_H = 400
EYE_RADIUS = 140
PUPIL_RADIUS = 41
EYE_GAP = 120  
PUPIL_TRAVEL = EYE_RADIUS - PUPIL_RADIUS - 20  
SMOOTHING = 0.2  # 0..1 (higher = faster response, lower = smoother)
CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.json')
CONFIG_POLL_INTERVAL = 0.5  # seconds

# Blinking parameters
BLINK_MIN_INTERVAL = 3.0
BLINK_MAX_INTERVAL = 7.0
BLINK_CLOSE_DURATION = 0.09  # seconds to close
BLINK_HOLD_DURATION = 0.03   # eye fully closed
BLINK_OPEN_DURATION = 0.10   # seconds to reopen

def ease_in_out_sine(x: float) -> float:
    return 0.5 - 0.5 * math.cos(math.pi * x)

cap = None  # Camera removed for minimal version

# Create a named window
cv2.namedWindow('Robot Eyes', cv2.WINDOW_NORMAL)
cv2.resizeWindow('Robot Eyes', WINDOW_W, WINDOW_H)

# State for smoothing
pupil_offset_left = np.array([0.0, 0.0])
pupil_offset_right = np.array([0.0, 0.0])

# Blink state
next_blink_time = time.time() + random.uniform(BLINK_MIN_INTERVAL, BLINK_MAX_INTERVAL)
current_blink_start = None  # time when blink started
last_config_load = 0.0
config = {"emotion": "neutral", "direction": "center"}

# Helper functions

# (All gaze detection code removed for minimal build)


def draw_eye(canvas, center, pupil_offset, blink_amount: float, emotion: str):
    # Eye white
    cv2.circle(canvas, center, EYE_RADIUS, (240, 240, 245), -1, lineType=cv2.LINE_AA)
    cv2.circle(canvas, center, EYE_RADIUS, (60, 60, 80), 4, lineType=cv2.LINE_AA)

    # Metallic radial shading (simple rings)
    for r, alpha in [(int(EYE_RADIUS*0.85), 15), (int(EYE_RADIUS*0.6), 25)]:
        cv2.circle(canvas, center, r, (220, 220, 230), 2, lineType=cv2.LINE_AA)

    pupil_center = (int(center[0] + pupil_offset[0]), int(center[1] + pupil_offset[1]))
    if blink_amount < 0.98:  # hide pupil when almost fully closed
        # Dark blue iris (BGR) - outer ring slightly brighter than inner
        # Limbal ring (darker edge)
        cv2.circle(canvas, pupil_center, PUPIL_RADIUS, (80, 40, 30), -1, lineType=cv2.LINE_AA)
        # Iris color
        cv2.circle(canvas, pupil_center, int(PUPIL_RADIUS*0.9), (220, 150, 80), -1, lineType=cv2.LINE_AA) # Bright blue
        # Pupil
        cv2.circle(canvas, pupil_center, int(PUPIL_RADIUS*0.45), (10, 10, 10), -1, lineType=cv2.LINE_AA)
        # Highlight
        highlight_center = (int(pupil_center[0] - PUPIL_RADIUS*0.3), int(pupil_center[1] - PUPIL_RADIUS*0.3))
        cv2.circle(canvas, highlight_center, int(PUPIL_RADIUS*0.35), (255, 255, 255), -1, lineType=cv2.LINE_AA)

    # Emotion adjustments (eyelid shaping)
    # We'll modify blink_amount effective coverage and add partial lid positions.
    emotion_upper_extra = 0.0
    emotion_lower_extra = 0.0
    if emotion == 'sleepy':
        # half closed look
        emotion_upper_extra = 0.45  # add baseline closure
    elif emotion == 'angry':
        emotion_upper_extra = 0.20
    elif emotion == 'sad':
        emotion_lower_extra = 0.20
    elif emotion == 'surprised':
        # widen (negative closure)
        emotion_upper_extra = -0.15
        emotion_lower_extra = -0.10

    effective_closure = np.clip(blink_amount + max(0.0, emotion_upper_extra), 0.0, 1.0)
    # Draw eyelid (top moving down, slight bottom assist) based on blink_amount or emotion
    if effective_closure > 0 or emotion_lower_extra != 0 or emotion_upper_extra < 0:
        cover_color_top = (30, 35, 50)
        cover_color_bottom = (25, 30, 40)
        frac = effective_closure
        # Top eyelid: cover proportion up to full diameter
        cover_h_top = int(frac * 2 * EYE_RADIUS)
        y0 = center[1] - EYE_RADIUS
        # Clip rectangle to canvas
        y1 = min(center[1] - EYE_RADIUS + cover_h_top, center[1] + EYE_RADIUS)
        if y1 > y0:
            cv2.rectangle(canvas, (center[0]-EYE_RADIUS-2, y0-2), (center[0]+EYE_RADIUS+2, y1), cover_color_top, -1)
        # Bottom eyelid: small upward movement for realism (30% of top travel)
        base_bottom_frac = frac * 0.3 + max(0.0, emotion_lower_extra)
        base_bottom_frac = max(0.0, base_bottom_frac + (-emotion_lower_extra if emotion_lower_extra < 0 else 0))
        cover_h_bottom = int(base_bottom_frac * 2 * EYE_RADIUS)
        yb0 = center[1] + EYE_RADIUS - cover_h_bottom
        yb1 = center[1] + EYE_RADIUS
        if yb0 < yb1:
            cv2.rectangle(canvas, (center[0]-EYE_RADIUS-2, yb0), (center[0]+EYE_RADIUS+2, yb1+2), cover_color_bottom, -1)
        # Re-draw eye border outline on top
        cv2.circle(canvas, center, EYE_RADIUS, (60, 60, 80), 4, lineType=cv2.LINE_AA)


def map_direction_vec(vec2):
    scale = PUPIL_TRAVEL
    v = np.array(vec2, dtype=float)
    norm = np.linalg.norm(v)
    if norm > 1.0:
        v /= norm
    return v * scale

try:
    while True:
        # --- Blink state update ---
        now = time.time()
        blink_amount = 0.0
        if current_blink_start is None and now >= next_blink_time:
            current_blink_start = now
        if current_blink_start is not None:
            t = now - current_blink_start
            total = BLINK_CLOSE_DURATION + BLINK_HOLD_DURATION + BLINK_OPEN_DURATION
            if t < BLINK_CLOSE_DURATION:
                blink_amount = ease_in_out_sine(t / BLINK_CLOSE_DURATION)
            elif t < BLINK_CLOSE_DURATION + BLINK_HOLD_DURATION:
                blink_amount = 1.0
            elif t < total:
                t_open = (t - BLINK_CLOSE_DURATION - BLINK_HOLD_DURATION) / BLINK_OPEN_DURATION
                blink_amount = ease_in_out_sine(1 - t_open)
            else:
                blink_amount = 0.0
                current_blink_start = None
                next_blink_time = now + random.uniform(BLINK_MIN_INTERVAL, BLINK_MAX_INTERVAL)

        # Reload config periodically
        if now - last_config_load >= CONFIG_POLL_INTERVAL:
            try:
                with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            except Exception:
                pass
            last_config_load = now

        direction = config.get('direction', 'center')
        emotion = config.get('emotion', 'neutral')

        # Smoothly return to center before applying direction
        pupil_offset_left *= (1 - SMOOTHING)
        pupil_offset_right *= (1 - SMOOTHING)

        canvas = np.zeros((WINDOW_H, WINDOW_W, 3), dtype=np.uint8)
        canvas[:] = (0, 0, 0)

        # Compute eye centers
        center_y = WINDOW_H // 2
        center_x = WINDOW_W // 2
        left_center = (center_x - EYE_GAP//2 - EYE_RADIUS, center_y)
        right_center = (center_x + EYE_GAP//2 + EYE_RADIUS, center_y)

        # Apply direction override
        direction_map = {
            'center': (0.0, 0.0),
            'right': (-1.0, 0.0),
            'left': (1.0, 0.0),
            'up': (0.0, -1.0),
            'down': (0.0, 1.0),
            'upright': (-0.7, -0.7),
            'upleft': (0.7, -0.7),
            'downright': (-0.7, 0.7),
            'downleft': (0.7, 0.7)
        }
        if direction in direction_map:
            target = map_direction_vec(direction_map[direction])
            pupil_offset_left = (1-SMOOTHING)*pupil_offset_left + SMOOTHING*target
            pupil_offset_right = (1-SMOOTHING)*pupil_offset_right + SMOOTHING*target

        draw_eye(canvas, left_center, pupil_offset_left, blink_amount, emotion)
        draw_eye(canvas, right_center, pupil_offset_right, blink_amount, emotion)

        cv2.imshow('Robot Eyes', canvas)
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
finally:
    # No resources to release beyond OpenCV windows
    cv2.destroyAllWindows()
