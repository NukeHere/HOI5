"""Windows smoke: hold the parent GIL in C for 13 s; audio must keep changing tracks."""
import ctypes
import json
from pathlib import Path
import sys
import time
import wave

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audio_process import ProcessAudio
from runtime_diagnostics import RuntimeDiagnostics


def main():
    root = Path("logs/diagnostics/audio-pvo-camera/native-check")
    root.mkdir(parents=True, exist_ok=True)
    path = root / "half-second.wav"
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(22050)
        output.writeframes(b"\0\0" * 11025)
    audio = ProcessAudio(playlists={"economy": [path.resolve()]}, volume=0, sound_volume=0)
    monitor = RuntimeDiagnostics(dict(test="GIL-held native call"), directory=root / "runtime")
    try:
        deadline = time.monotonic() + 10
        while not audio.status.get("sequence") and time.monotonic() < deadline:
            audio.update()
            time.sleep(.01)
        assert audio.status.get("sequence"), audio.status
        before = audio.status["sequence"]
        monitor.start_native_watchdog()
        sleep = ctypes.PyDLL("kernel32").Sleep
        sleep.argtypes = [ctypes.c_uint32]
        sleep.restype = None
        sleep(13_000)  # PyDLL deliberately holds the GIL, unlike ctypes.CDLL.
        monitor.stop_native_watchdog()
        audio.poll()
        dump = monitor.path.with_suffix(".stacks.txt").read_text(encoding="utf-8")
        result = dict(native_dump="Timeout" in dump, tracks_during_freeze=audio.status["sequence"] - before,
                      audio_pid=audio.process.pid, heartbeat_age=time.monotonic() - audio.status["heartbeat"])
        assert result["native_dump"] and result["tracks_during_freeze"] > 10, result
        (root / "result.json").write_text(json.dumps(result, indent=2))
        print(json.dumps(result), flush=True)
    finally:
        monitor.stop_native_watchdog()
        audio.close()


if __name__ == "__main__":
    main()
