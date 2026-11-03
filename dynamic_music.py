"""Client-only music selection. Tracks finish naturally; the simulation owns no audio."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import random
import time
import logging


CATEGORIES = ("economy", "start_war", "war", "bad_times")
OPENING_WAR_DAYS = 30


def release_source(source):
    # WMFSource releases COM objects in __del__; StreamingSource has delete().
    delete = getattr(source, "delete", None)
    if delete is not None:
        delete()


class MusicSituation:
    def __init__(self):
        self.seen_wars = set()
        self.pending_wars = set()
        self.peak_territory = 0
        self.last_battle_count = 0
        self.last_escalation_day = -OPENING_WAR_DAYS
        self.escalation_until = -1
        self.pending_escalation = False

    def category(self, politics, player, battles=()):
        if player is None:
            return "economy"
        wars = {(tuple(pair), relation.war_started_day) for pair, relation in politics.relations.items()
                if player.id in pair and relation.at_war}
        self.pending_wars.intersection_update(wars)
        self.pending_wars.update(wars - self.seen_wars)
        self.seen_wars = wars
        incoming = any(target == player.id for actor, target in politics.war_goals if actor != player.id)
        opening = any(0 <= politics.day - day < OPENING_WAR_DAYS for _, day in wars)
        battle_count = sum(battle.attacker is player or battle.defender is player for battle in battles)
        if not wars:
            self.pending_escalation = False
            self.escalation_until = -1
            self.last_escalation_day = -OPENING_WAR_DAYS
        elif (battle_count >= max(3, self.last_battle_count + 3, self.last_battle_count * 2)
              and politics.day - self.last_escalation_day >= OPENING_WAR_DAYS):
            self.pending_escalation = True
            self.escalation_until = politics.day + OPENING_WAR_DAYS
            self.last_escalation_day = politics.day
        self.last_battle_count = battle_count
        tiles = len(player.tiles)
        self.peak_territory = max(self.peak_territory, tiles)
        # A new war must get an opening track even if game speed advances a
        # month before the currently playing peaceful track has ended.
        if incoming or opening or self.pending_wars or self.pending_escalation or politics.day < self.escalation_until:
            return "start_war"
        divisions = player.divisions
        unsupplied = sum(d.last_supply_ratio < .3 for d in divisions)
        crisis = (player.stability < .4
                  or player.budget <= 0 and player.monthly_balance < 0
                  or bool(divisions) and unsupplied * 2 >= len(divisions)
                  or bool(wars) and tiles < self.peak_territory * .75)
        if crisis:
            return "bad_times"
        return "war" if wars else "economy"

    def started(self, category):
        if category == "start_war":
            self.pending_wars.clear()
            self.pending_escalation = False


class StreamingMusic:
    """Probe/open one upcoming stream off-thread; all Player/GL work stays on the UI thread."""
    def __init__(self):
        from pyglet import media
        self.media = media
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="music-loader")
        self.future = None
        self.loading_path = None
        self.player = None
        self.closed = False

    @staticmethod
    def release(future):
        if not future.cancelled() and future.exception() is None:
            release_source(future.result())

    def prepare(self, path):
        if self.future is not None and self.loading_path != path:
            if not self.future.done():
                return
            self.release(self.future)
            self.future = None
        if self.future is None:
            self.loading_path = path
            self.future = self.executor.submit(self.media.load, str(path), streaming=True)

    def finished(self):
        return self.player is None or self.player.source is None

    def start(self, path, volume):
        if self.loading_path != path or self.future is None or not self.future.done():
            return False
        future, self.future = self.future, None
        source = future.result()
        self.stop_player()
        try:
            self.player = self.media.Player()
            self.player.volume = volume
            self.player.loop = False
            self.player.queue(source)
            self.player.play()
        except Exception:
            queued = self.player is not None and self.player.source is source
            self.stop_player()
            if not queued:
                release_source(source)
            raise
        return True

    def set_volume(self, volume):
        if self.player is not None:
            self.player.volume = volume

    def stop_player(self):
        if self.player is not None:
            self.player.pause()
            source = self.player.source
            self.player.delete()
            if source is not None:
                release_source(source)
            self.player = None

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.stop_player()
        if self.future is not None:
            self.future.add_done_callback(self.release)
            self.future.cancel()
            self.future = None
        self.executor.shutdown(wait=False, cancel_futures=True)


class DynamicMusic:
    def __init__(self, directory=None, volume=.6, backend=None, rng=None, report=None, playlists=None):
        directory = Path(directory or Path(__file__).parent / "music")
        if playlists is None:
            self.tracks = {key: sorted(path for path in (directory / key).glob("*")
                                      if path.is_file() and path.suffix.lower() in {".ogg", ".mp3", ".wav", ".flac"})
                           for key in CATEGORIES}
        else:
            self.tracks = {key: [Path(path) for path in playlists.get(key, [])] for key in CATEGORIES}
        self.backend = backend or StreamingMusic()
        self.rng = rng or random.Random()  # Never consume the simulation's RNG.
        self.report = report or self.report_error
        self.situation = MusicSituation()
        self.bags = {}
        self.failed = set()
        self.desired_category = "economy"
        self.current_category = None
        self.current_path = None
        self.upcoming = None
        self.next_review = 0
        self.volume = max(0, min(1, volume))
        self.closed = False

    @staticmethod
    def report_error(kind, **data):
        if kind == "music_error":
            logging.getLogger(__name__).warning("Music playback failed: %s", data)

    def available_category(self):
        for key in dict.fromkeys((self.desired_category, "war" if self.desired_category == "start_war" else "economy", *CATEGORIES)):
            if any(path not in self.failed for path in self.tracks[key]):
                return key
        return None

    def choose(self, category):
        bag = [path for path in self.bags.get(category, []) if path not in self.failed]
        if not bag:
            bag = [path for path in self.tracks[category] if path not in self.failed]
            self.rng.shuffle(bag)
        # Several folders contain copies of the same track. Avoid immediate
        # repeats across categories as well as within a shuffled playlist.
        previous = self.current_path.name.casefold() if self.current_path else None
        if all(path.name.casefold() == previous for path in bag):
            alternatives = [path for path in self.tracks[category]
                            if path not in self.failed and path.name.casefold() != previous]
            if alternatives:
                self.bags[category] = bag
                return self.rng.choice(alternatives)
        for index, path in enumerate(bag):
            if path.name.casefold() != previous:
                bag[0], bag[index] = bag[index], bag[0]
                break
        path = bag.pop(0)
        self.bags[category] = bag
        return path

    def set_volume(self, volume):
        self.volume = max(0, min(1, volume))
        self.backend.set_volume(self.volume)

    def update(self, game=None, now=None):
        if self.closed:
            return
        now = time.monotonic() if now is None else now
        if game is not None and now >= self.next_review:
            self.desired_category = self.situation.category(game.politics, game.human_player,
                                                            getattr(game, "battles", {}).values())
            self.next_review = now + 1
        category = self.available_category()
        if category is None:
            return
        if self.upcoming is None or self.upcoming[0] != category:
            # Return an unused preselection to its bag when the situation changes.
            if self.upcoming and self.upcoming[1] not in self.failed:
                self.bags.setdefault(self.upcoming[0], []).append(self.upcoming[1])
            self.upcoming = (category, self.choose(category))
        category, path = self.upcoming
        try:
            self.backend.prepare(path)
            if self.backend.finished() and self.backend.start(path, self.volume):
                self.current_category, self.current_path = category, path
                self.upcoming = None
                self.situation.started(category)
                self.report("music_track", category=category, track=str(path),
                            game_time=str(game.simulation_server.current_time) if game else "menu")
        except Exception as error:
            # A missing decoder or corrupt file must not stop the game loop.
            self.failed.add(path)
            self.upcoming = None
            self.report("music_error", track=str(path), error=str(error))

    def close(self):
        self.closed = True
        self.backend.close()
