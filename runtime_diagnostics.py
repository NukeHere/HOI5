"""Persist GUI exceptions and stacks of frames that stop making progress."""
from datetime import datetime, timezone
from functools import wraps
import json
from pathlib import Path
import sys
import threading
import time
import traceback
import weakref
import faulthandler


class RuntimeDiagnostics:
    native_owner = None
    def __init__(self, metadata, directory=None, timeout=8):
        directory = Path(directory or Path(__file__).parent / "logs" / "runtime")
        self.timeout = timeout
        self.thread_id = threading.get_ident()
        self.active = None
        self.heartbeat = None
        self.last_context = {}
        self.worker = None
        self.last_reported = None
        self.metadata = dict(metadata)
        self.path = directory / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f") + ".jsonl")
        self.text_path = directory.parent / "debug.log"
        self.last_day = None
        self.error = ""
        self.lock = threading.Lock()
        self.native_file = None
        self.native_armed_at = 0
        try:
            directory.mkdir(parents=True, exist_ok=True)
            self.text_path.write_text("HOI5 debug log — timestamps in UTC\n", encoding="utf-8")
            (directory / "latest.json").write_text(json.dumps(dict(log=str(self.path), **self.metadata),
                ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError as error:
            self.error = str(error)
        self.write("session", **self.metadata)

    def write(self, kind, **data):
        try:
            record = dict(kind=kind, utc=datetime.now(timezone.utc).isoformat(), **data)
            with self.lock:
                with self.path.open("a", encoding="utf-8") as output:
                    output.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
                with self.text_path.open("a", encoding="utf-8") as output:
                    output.write(f"[{record['utc']}] {kind}\n")
                    for key, value in data.items():
                        output.write(f"  {key}: {value}\n")
        except OSError as error:
            self.error = str(error)

    def begin(self, phase, context):
        self.active = (time.perf_counter(), dict(phase=phase, **context))
        if self.native_file and time.perf_counter() - self.native_armed_at >= 1:
            self.arm_native_watchdog()
        self.last_context = dict(phase=phase, **context)
        if self.worker is None:
            self.worker = threading.Thread(target=self.watch, args=(weakref.ref(self),), daemon=True,
                                           name="game-frame-watchdog")
            self.worker.start()

    def start_native_watchdog(self):
        previous = RuntimeDiagnostics.native_owner
        if previous is not None and previous is not self:
            previous.stop_native_watchdog()
        try:
            if self.native_file is None:
                self.native_file = self.path.with_suffix(".stacks.txt").open("a", encoding="utf-8")
                self.native_file.write(json.dumps(self.metadata, ensure_ascii=False) + "\n")
                self.native_file.flush()
            RuntimeDiagnostics.native_owner = self
            self.arm_native_watchdog()
            self.write("native_watchdog", stack_file=str(self.path.with_suffix(".stacks.txt")), timeout_seconds=max(12, self.timeout))
        except (OSError, RuntimeError, ValueError) as error:
            self.error = str(error)
            self.stop_native_watchdog()

    def arm_native_watchdog(self):
        if self.native_file:
            faulthandler.cancel_dump_traceback_later()
            faulthandler.dump_traceback_later(max(12, self.timeout), repeat=True, file=self.native_file)
            self.native_armed_at = time.perf_counter()

    def stop_native_watchdog(self):
        owner = RuntimeDiagnostics.native_owner
        if owner is self:
            faulthandler.cancel_dump_traceback_later()
            RuntimeDiagnostics.native_owner = None
        if self.native_file:
            self.native_file.close()
            self.native_file = None

    def stage(self, name, game_time=None, player=None):
        active = self.active
        if active:
            context = dict(active[1], subsystem=name)
            if game_time is not None:
                context.update(game_time=str(game_time), player=player)
            self.active = (active[0], context)

    def poll(self, now=None):
        active = self.active
        now = time.perf_counter() if now is None else now
        if not active and self.heartbeat is not None:
            active = (self.heartbeat, dict(self.last_context, phase="event_loop"))
        if not active or now - active[0] < self.timeout or active[0] == self.last_reported:
            return
        self.last_reported = active[0]
        frame = sys._current_frames().get(self.thread_id)
        self.write("stalled_frame", elapsed_seconds=now - active[0], **active[1],
                   stack="".join(traceback.format_stack(frame)) if frame else "Thread unavailable")

    @staticmethod
    def watch(reference):
        while True:
            time.sleep(1)
            monitor = reference()
            if monitor is None:
                return
            monitor.poll()
            del monitor

    def finish(self):
        active, self.active = self.active, None
        self.heartbeat = time.perf_counter()
        if active:
            elapsed = time.perf_counter() - active[0]
            if elapsed >= .5:
                self.write("slow_frame", elapsed_seconds=elapsed, **active[1])

    def checkpoint(self, game):
        day = game.politics.day
        if self.last_day == day:
            return
        self.last_day = day
        self.write("day", game_time=str(game.simulation_server.current_time),
            speed=game.simulation_server.speed_level, paused=game.simulation_server.paused,
            countries=[dict(id=p.id, budget=round(p.budget, 2), divisions=len(p.divisions),
                construction=len(p.construction_queue), training=len(game.recruitment.queues[p.id]))
                for p in game.players])


def diagnose_frame(phase):
    def decorate(operation):
        @wraps(operation)
        def wrapper(game, *args, **kwargs):
            monitor = getattr(game, "runtime_diagnostics", None)
            if monitor is None:
                return operation(game, *args, **kwargs)
            context = dict(game_time=str(game.simulation_server.current_time),
                panel=game.active_top_panel_key, zoom=game.world_camera.zoom,
                map_layer=getattr(game, "map_layer", None),
                news_archive=getattr(game, "news_archive_open", False),
                news_popup=getattr(game, "news_popup_id", None))
            context.update(ui_paused=getattr(game, "paused", False),
                           mouse_position=getattr(game, "last_pointer_position", None),
                           camera_drag=getattr(game, "is_dragging", False))
            if phase in ("mouse_drag", "mouse_motion"):
                context.update(arguments=args, camera_drag=getattr(game, "is_dragging", False))
            monitor.begin(phase, context)
            if phase.startswith("input_"):
                monitor.write("input", event=phase, arguments=args, **context)
            try:
                result = operation(game, *args, **kwargs)
                if phase.startswith("input_"):
                    monitor.write("input_result", event=phase,
                        paused=getattr(game.simulation_server, "paused", None),
                        selected_divisions=sorted(getattr(game, "selected_division_ids", ())),
                        selection_drag=getattr(game, "division_selection_drag_active", False))
                if phase == "update":
                    monitor.checkpoint(game)
                return result
            except Exception:
                active = monitor.active
                monitor.write("exception", context=active[1] if active else {}, traceback=traceback.format_exc())
                raise
            finally:
                monitor.finish()
        return wrapper
    return decorate
