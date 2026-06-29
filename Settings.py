import json
from pathlib import Path


SETTINGS_PATH = Path(__file__).resolve().parent / "user_settings.json"

DEFAULT_SETTINGS = {
    "sound_volume": 0.8,
    "music_volume": 0.6,
    "fullscreen": False,
    "resolution_index": 1,
}


def _clamp_float(value, default, minimum=0.0, maximum=1.0):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, number))


def _clamp_resolution_index(value, max_index):
    try:
        index = int(value)
    except (TypeError, ValueError):
        return DEFAULT_SETTINGS["resolution_index"]
    return max(0, min(max_index, index))


def load_settings(resolutions=None):
    settings = DEFAULT_SETTINGS.copy()
    if SETTINGS_PATH.exists():
        try:
            loaded_settings = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            if isinstance(loaded_settings, dict):
                settings.update(loaded_settings)
        except (OSError, json.JSONDecodeError):
            pass

    max_resolution_index = len(resolutions) - 1 if resolutions else DEFAULT_SETTINGS["resolution_index"]
    return {
        "sound_volume": _clamp_float(settings.get("sound_volume"), DEFAULT_SETTINGS["sound_volume"]),
        "music_volume": _clamp_float(settings.get("music_volume"), DEFAULT_SETTINGS["music_volume"]),
        "fullscreen": bool(settings.get("fullscreen")),
        "resolution_index": _clamp_resolution_index(settings.get("resolution_index"), max_resolution_index),
    }


def save_settings(sound_volume, music_volume, fullscreen, resolution_index, resolutions=None):
    max_resolution_index = len(resolutions) - 1 if resolutions else DEFAULT_SETTINGS["resolution_index"]
    settings = {
        "sound_volume": _clamp_float(sound_volume, DEFAULT_SETTINGS["sound_volume"]),
        "music_volume": _clamp_float(music_volume, DEFAULT_SETTINGS["music_volume"]),
        "fullscreen": bool(fullscreen),
        "resolution_index": _clamp_resolution_index(resolution_index, max_resolution_index),
    }
    SETTINGS_PATH.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    return settings


def _close_window_safely(window):
    if window is None:
        return
    try:
        window.close()
    except Exception:
        pass


def _window_has_attached_canvas(window):
    context = getattr(window, "context", None)
    if context is None or getattr(context, "canvas", None) is None:
        return False
    try:
        window.switch_to()
    except Exception:
        return False
    return getattr(context, "canvas", None) is not None


def create_window_with_fallback(arcade_module, title, settings, resolutions):
    try:
        import pyglet
    except Exception:
        pyglet = None

    attempts = [
        (settings["resolution_index"], settings["fullscreen"]),
        (DEFAULT_SETTINGS["resolution_index"], False),
        (0, False),
    ]
    seen = set()
    last_error = None

    for resolution_index, fullscreen in attempts:
        resolution_index = _clamp_resolution_index(resolution_index, len(resolutions) - 1)
        attempt_key = (resolution_index, bool(fullscreen))
        if attempt_key in seen:
            continue
        seen.add(attempt_key)

        width, height = resolutions[resolution_index]
        window = None
        existing_windows = set(getattr(pyglet.app, "windows", [])) if pyglet else set()
        try:
            window = arcade_module.Window(int(width), int(height), title)
            if fullscreen:
                window.set_fullscreen(True)
            if not _window_has_attached_canvas(window):
                raise RuntimeError("Window canvas has not been attached")
            if attempt_key != (settings["resolution_index"], settings["fullscreen"]):
                save_settings(
                    settings["sound_volume"],
                    settings["music_volume"],
                    bool(fullscreen),
                    resolution_index,
                    resolutions,
                )
            return window
        except Exception as exc:
            last_error = exc
            print(f"Window creation failed for {width}x{height}, fullscreen={fullscreen}: {exc}")
            _close_window_safely(window)
            if pyglet:
                for orphan_window in list(getattr(pyglet.app, "windows", [])):
                    if orphan_window not in existing_windows:
                        _close_window_safely(orphan_window)

    raise last_error
