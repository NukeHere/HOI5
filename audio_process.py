"""Independent audio event loop; the game sends small, nonblocking commands."""
import multiprocessing
from pathlib import Path
from queue import Empty, Full
import time


def audio_main(commands, states, config):
    import pyglet
    from dynamic_music import DynamicMusic, StreamingMusic
    music = DynamicMusic(directory=config.get("directory"), playlists=config.get("playlists"),
                         volume=config["volume"], backend=StreamingMusic())
    effects = []
    sources = {}
    state = dict(pid=multiprocessing.current_process().pid, sequence=0, error_sequence=0, effect_sequence=0,
                 category=None, path=None, music_volume=config["volume"], sound_volume=config["sound_volume"])
    def report(kind, **data):
        if kind == "music_track":
            state["sequence"] += 1
            state.update(category=data["category"], path=data["track"])
        else:
            state["error_sequence"] += 1
            state["error"] = dict(kind=kind, **data)
    music.report = report
    next_status = 0
    running = True
    try:
        while running:
            for _ in range(64):
                try:
                    message = commands.get_nowait()
                except Empty:
                    break
                operation = message[0]
                if operation == "close":
                    running = False
                    break
                if operation == "category":
                    music.desired_category = message[1]
                elif operation == "music_volume":
                    music.set_volume(message[1])
                    state["music_volume"] = music.volume
                elif operation == "sound_volume":
                    state["sound_volume"] = message[1]
                    for player, gain in effects:
                        player.volume = gain * message[1]
                elif operation == "effect" and len(effects) < 16:
                    path, gain = message[1:]
                    try:
                        if path not in sources:
                            if len(sources) >= 32:
                                sources.pop(next(iter(sources)))
                            sources[path] = pyglet.media.load(path, streaming=False)
                        player = pyglet.media.Player()
                        player.volume = gain * state["sound_volume"]
                        player.queue(sources[path])
                        player.play()
                        effects.append((player, gain))
                        state["effect_sequence"] += 1
                    except Exception as error:
                        report("effect_error", track=path, error=str(error))
            pyglet.clock.tick()
            pyglet.app.platform_event_loop.dispatch_posted_events()
            if running:
                music.update()
            for player, gain in effects[:]:
                if player.source is None:
                    player.delete()
                    effects.remove((player, gain))
            if time.monotonic() >= next_status:
                player = music.backend.player
                state.update(time=player.time if player else 0, effects=len(effects), heartbeat=time.monotonic())
                try:
                    states.put_nowait(dict(state))
                except Full:
                    # Never wait for the rendering process, even if it is frozen.
                    try:
                        states.get_nowait()
                    except Empty:
                        pass
                next_status = time.monotonic() + .05
            time.sleep(.005)
    finally:
        music.close()
        for player, _ in effects:
            player.pause()
            player.delete()


class ProcessAudio:
    def __init__(self, directory=None, volume=.6, playlists=None, report=None, sound_volume=.8):
        from dynamic_music import MusicSituation
        context = multiprocessing.get_context("spawn")
        self.commands = context.Queue(maxsize=64)
        self.states = context.Queue(maxsize=2)
        self.process = context.Process(target=audio_main, args=(self.commands, self.states,
            dict(directory=directory, volume=volume, playlists=playlists, sound_volume=sound_volume)),
            name="game-audio", daemon=True)
        self.process.start()
        self.report = report or (lambda *args, **kwargs: None)
        self.situation = MusicSituation()
        self.closed = False
        self.current_path = None
        self.current_category = None
        self.next_review = 0
        self.status = {}
        self.controls = {"music_volume": volume, "sound_volume": sound_volume}
        self.sequence = self.error_sequence = 0

    def poll(self):
        for _ in range(8):
            try:
                self.status = self.states.get_nowait()
            except Empty:
                break
        self.current_category = self.status.get("category")
        path = self.status.get("path")
        self.current_path = Path(path) if path else None
        sequence = self.status.get("sequence", 0)
        if sequence != self.sequence:
            self.sequence = sequence
            self.situation.started(self.current_category)
            self.report("music_track", category=self.current_category, track=path, process=self.process.pid)
        errors = self.status.get("error_sequence", 0)
        if errors != self.error_sequence:
            self.error_sequence = errors
            self.report("music_error", details=self.status.get("error"), process=self.process.pid)

    def send(self, command):
        if self.closed:
            return False
        try:
            self.commands.put_nowait(command)
            return True
        except Full:
            return False

    def update(self, game=None, now=None):
        if self.closed:
            return
        self.poll()
        if not self.process.is_alive():
            self.report("music_error", error=f"Audio process exited: {self.process.exitcode}")
            self.close()
            return
        now = time.monotonic() if now is None else now
        if game is not None and now >= self.next_review:
            self.controls["category"] = self.situation.category(game.politics, game.human_player, game.battles.values())
            self.next_review = now + 1
        # Retry coalesced controls after queue saturation, without blocking a frame.
        for operation, value in list(self.controls.items()):
            if self.send((operation, value)):
                self.controls.pop(operation)

    def set_volume(self, volume):
        self.controls["music_volume"] = max(0, min(1, volume))

    def set_sound_volume(self, volume):
        self.controls["sound_volume"] = max(0, min(1, volume))

    def play_effect(self, path, volume=1):
        return self.send(("effect", str(Path(path).resolve()), max(0, min(1, volume))))

    def close(self):
        if self.closed:
            return
        self.send(("close",))
        self.closed = True
        self.process.join(timeout=.3)
        if self.process.is_alive():
            self.process.terminate()
            self.process.join(timeout=.3)
        self.commands.cancel_join_thread()
        self.commands.close()
        self.states.close()
