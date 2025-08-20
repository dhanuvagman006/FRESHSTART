
from __future__ import annotations
from move_function import robot_leg_movement
import json
import os
import tempfile

ALLOWED_EMOTIONS = {
    "neutral",
    "sleepy",
    "angry",
    "sad",
    "surprised",
}

ALLOWED_DIRECTIONS = {
    "center",
    "left",
    "right",
    "up",
    "down",
    "upleft",
    "upright",
    "downleft",
    "downright",
}


def get_tool_to_run(function_name: str, function_args: dict):
    """Dispatch a tool call by name.

    Returns a dict with either a successful payload or an error field so the
    model can decide to retry or adjust its request.
    """
    try:
        match function_name:
            case "facial_emotion_update":
                return facial_emotion_update(
                    function_args.get("emotion"), function_args.get("direction")
                )
            case "robot_leg_movement":
                return robot_leg_movement(function_args.get("direction"))
            case _:
                return {
                    "error": f"Unknown tool '{function_name}'.",
                    "available_tools": ["facial_emotion_update"],
                }
    except Exception as e:  # Broad catch to ensure we always return a payload
        return {"error": f"Tool execution failed: {e.__class__.__name__}: {e}"}


CONFIG_FILE = os.path.join(os.path.dirname(__file__), "EYE", "config.json")


def _atomic_write_json(path: str, data: dict):
    """Atomically write JSON to prevent partial writes (Windows-safe)."""
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix="._emotion_", dir=directory, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp:
            json.dump(data, tmp, ensure_ascii=False, indent=2)

        os.replace(tmp_path, path)  
    finally:
        if os.path.exists(tmp_path):  
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def facial_emotion_update(emotion: str | None, direction: str | None):
    """Validate and return an updated emotional state.

    Returns a structured response used in FunctionResponse.response.
    """
    errors = []
    if not emotion:
        errors.append("Missing required argument: emotion")
    elif emotion not in ALLOWED_EMOTIONS:
        errors.append(
            "Invalid emotion. Allowed: " + ", ".join(sorted(ALLOWED_EMOTIONS))
        )
    if not direction:
        errors.append("Missing required argument: direction")
    elif direction not in ALLOWED_DIRECTIONS:
        errors.append(
            "Invalid direction. Allowed: " + ", ".join(sorted(ALLOWED_DIRECTIONS))
        )

    if errors:
        return {"ok": False, "errors": errors}

    persist_error = None
    config_payload = {"emotion": emotion, "direction": direction}
    try:
        _atomic_write_json(CONFIG_FILE, config_payload)
    except Exception as e:  # noqa: BLE001 keep robust
        persist_error = f"Failed to write config: {e.__class__.__name__}: {e}"

    print(f"[facial_emotion_update] emotion={emotion} direction={direction}")

    response = {
        "ok": True,
        "emotion": emotion,
        "direction": direction,
        "message": "Facial emotion state updated.",
    }
    if persist_error:
        response["ok"] = False
        response["persist_error"] = persist_error
    return response