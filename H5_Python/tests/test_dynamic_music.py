import random
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest

from dynamic_music import DynamicMusic, MusicSituation


def world():
    return NS(politics=NS(day=0, relations={}, war_goals={}),
              human_player=NS(id=0, tiles=list(range(40)), divisions=[], stability=.72,
                              budget=100, monthly_balance=10),
              simulation_server=NS(current_time="2000-01-01"))


class FakeAudio:
    def __init__(self):
        self.ended = True
        self.ready = True
        self.starts = []
        self.volume = 0
        self.closed = False
        self.broken = set()

    def prepare(self, path):
        pass

    def finished(self):
        return self.ended

    def start(self, path, volume):
        if path in self.broken:
            raise ValueError("broken stream")
        if not self.ready:
            return False
        self.starts.append(path)
        self.volume = volume
        self.ended = False
        return True

    def set_volume(self, volume):
        self.volume = volume

    def close(self):
        self.closed = True


class DynamicMusicTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.TemporaryDirectory()
        self.addCleanup(self.root.cleanup)
        for category in ("economy", "start_war", "war", "bad_times"):
            folder = Path(self.root.name) / category
            folder.mkdir()
            for name in ("a.ogg", "b.ogg", "c.ogg"):
                (folder / name).touch()
        self.game = world()
        self.audio = FakeAudio()
        self.events = []
        self.music = DynamicMusic(self.root.name, backend=self.audio, rng=random.Random(1),
                                  report=lambda kind, **data: self.events.append((kind, data)))
        self.addCleanup(self.music.close)

    def war(self, day=0):
        self.game.politics.relations[0, 1] = NS(at_war=True, war_started_day=day)

    def next_track(self, now):
        self.audio.ended = True
        self.music.update(self.game, now=now)

    def test_incoming_goal_waits_for_eos_and_own_goal_does_not_trigger(self):
        self.game.politics.war_goals[0, 1] = 30
        self.music.update(self.game, now=0)
        self.assertEqual(self.music.current_category, "economy")
        original = self.music.current_path
        self.game.politics.war_goals[1, 0] = 30
        self.music.update(self.game, now=2)
        self.assertEqual(self.music.current_path, original)
        self.assertEqual(len(self.audio.starts), 1)
        self.next_track(3)
        self.assertEqual(self.music.current_category, "start_war")

    def test_opening_is_not_skipped_when_game_advances_during_track(self):
        self.music.update(self.game, now=0)
        self.war()
        self.music.update(self.game, now=1)
        self.game.politics.day = 60
        self.next_track(2)
        self.assertEqual(self.music.current_category, "start_war")
        self.next_track(4)
        self.assertEqual(self.music.current_category, "war")

    def test_peace_cancels_pending_opening_and_war_music(self):
        self.war()
        self.music.update(self.game, now=0)
        self.game.politics.relations[0, 1].at_war = False
        self.next_track(2)
        self.assertEqual(self.music.current_category, "economy")

    def test_opening_lasts_exactly_first_thirty_days(self):
        self.war()
        self.music.update(self.game, now=0)
        self.game.politics.day = 29
        self.next_track(2)
        self.assertEqual(self.music.current_category, "start_war")
        self.game.politics.day = 30
        self.next_track(4)
        self.assertEqual(self.music.current_category, "war")

    def test_new_participant_restarts_thirty_day_opening(self):
        self.war()
        self.music.update(self.game, now=0)
        self.game.politics.day = 100
        self.next_track(2)
        self.assertEqual(self.music.current_category, "war")
        self.game.politics.relations[0, 2] = NS(at_war=True, war_started_day=100)
        self.next_track(4)
        self.assertEqual(self.music.current_category, "start_war")
        self.game.politics.day = 130
        self.next_track(6)
        self.assertEqual(self.music.current_category, "war")

    def test_sharp_battle_escalation_is_latched_with_cooldown(self):
        self.war()
        self.music.update(self.game, now=0)
        self.game.politics.day = 60
        self.next_track(2)
        self.game.battles = {i: NS(attacker=self.game.human_player, defender=object()) for i in range(3)}
        self.music.update(self.game, now=4)
        self.assertEqual(self.music.desired_category, "start_war")
        self.game.politics.day = 70
        self.game.battles.update({i: NS(attacker=self.game.human_player, defender=object()) for i in range(3, 6)})
        self.music.update(self.game, now=5)
        self.assertEqual(self.music.situation.escalation_until, 90)  # cooldown prevents extending to 100
        self.game.politics.day = 100  # music still has not finished
        self.next_track(6)
        self.assertEqual(self.music.current_category, "start_war")
        self.next_track(8)
        self.assertEqual(self.music.current_category, "war")

    def test_cancelled_justification_does_not_play_stale_tension(self):
        self.music.update(self.game, now=0)
        self.game.politics.war_goals[1, 0] = 30
        self.music.update(self.game, now=2)
        self.game.politics.war_goals.clear()
        self.next_track(4)
        self.assertEqual(self.music.current_category, "economy")

    def test_other_countries_war_does_not_change_player_music(self):
        self.game.politics.relations[1, 2] = NS(at_war=True, war_started_day=0)
        self.music.update(self.game, now=0)
        self.assertEqual(self.music.current_category, "economy")

    def test_each_crisis_signal_and_recovery(self):
        cases = [("stability", .2), ("budget", 0),
                 ("divisions", [NS(last_supply_ratio=.1), NS(last_supply_ratio=.8)])]
        for attribute, value in cases:
            game = world()
            game.human_player.monthly_balance = -1
            setattr(game.human_player, attribute, value)
            self.assertEqual(MusicSituation().category(game.politics, game.human_player), "bad_times")
        self.game.human_player.stability = .2
        self.music.update(self.game, now=0)
        self.assertEqual(self.music.current_category, "bad_times")
        self.game.human_player.stability = .7
        self.next_track(2)
        self.assertEqual(self.music.current_category, "economy")

    def test_territory_loss_during_war(self):
        self.music.situation.category(self.game.politics, self.game.human_player)
        self.war()
        self.game.politics.day = 60
        self.music.situation.category(self.game.politics, self.game.human_player)
        self.music.situation.started("start_war")
        self.game.human_player.tiles = [1] * 20
        self.assertEqual(self.music.situation.category(self.game.politics, self.game.human_player), "bad_times")

    def test_shuffle_bag_and_no_immediate_repeat_across_folders(self):
        for index in range(3):
            self.next_track(index * 2)
        names = [p.name for p in self.audio.starts]
        self.assertEqual(len(set(names)), 3)
        self.next_track(8)
        self.assertNotEqual(self.audio.starts[-1].name, names[-1])
        self.game.politics.war_goals[1, 0] = 30
        self.next_track(10)
        self.assertNotEqual(self.audio.starts[-1].name, self.audio.starts[-2].name)
        # The last unused item of the other category can be a copy of the
        # recording just heard. Defer it instead of repeating immediately.
        current = self.music.current_path
        self.music.bags["war"] = [Path(self.root.name) / "war" / current.name]
        self.assertNotEqual(self.music.choose("war").name, current.name)

    def test_volume_and_close(self):
        self.music.update(self.game, now=0)
        self.music.set_volume(0)
        self.assertEqual(self.audio.volume, 0)
        self.assertEqual(len(self.audio.starts), 1)
        self.music.set_volume(2)
        self.assertEqual(self.audio.volume, 1)
        self.music.close()
        self.next_track(10)
        self.assertEqual(len(self.audio.starts), 1)
        self.assertTrue(self.audio.closed)

    def test_loading_does_not_block_or_play_wrong_category(self):
        self.audio.ready = False
        self.music.update(self.game, now=0)
        self.assertEqual(self.audio.starts, [])
        self.game.politics.war_goals[1, 0] = 30
        self.audio.ready = True
        self.music.update(self.game, now=2)
        self.assertEqual(self.music.current_category, "start_war")

    def test_broken_files_are_skipped_and_empty_library_is_safe(self):
        self.audio.broken.update(self.music.tracks["economy"])
        for index in range(5):
            self.music.update(self.game, now=index)
        self.assertEqual(len(self.music.failed), 3)
        self.assertEqual(sum(kind == "music_error" for kind, _ in self.events), 3)
        self.assertTrue(self.audio.starts)
        for tracks in self.music.tracks.values():
            self.music.failed.update(tracks)
        self.next_track(10)

    def test_playlist_does_not_consume_simulation_randomness(self):
        state = random.getstate()
        music = DynamicMusic(self.root.name, backend=FakeAudio())
        self.addCleanup(music.close)
        music.update(self.game, now=0)
        self.assertEqual(state, random.getstate())


if __name__ == "__main__":
    unittest.main()
