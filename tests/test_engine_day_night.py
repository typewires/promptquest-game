"""Tests for day/night toggle and sleeping."""

import game_generator as gg


class TestToggleDayNight:
    def test_day_to_night(self, make_engine, minimal_game_cure, cure_sprites):
        engine = make_engine(minimal_game_cure, cure_sprites)
        engine.game["time_of_day"] = "day"
        result = engine._toggle_day_night()
        assert result == "night"

    def test_night_to_day(self, make_engine, minimal_game_cure, cure_sprites):
        engine = make_engine(minimal_game_cure, cure_sprites)
        engine.game["time_of_day"] = "night"
        result = engine._toggle_day_night()
        assert result == "day"

    def test_sunset_to_day(self, make_engine, minimal_game_cure, cure_sprites):
        engine = make_engine(minimal_game_cure, cure_sprites)
        engine.game["time_of_day"] = "sunset"
        result = engine._toggle_day_night()
        assert result == "day"


class TestWakeFromSleep:
    def test_wake_changes_time(self, make_engine, minimal_game_cure, cure_sprites):
        engine = make_engine(minimal_game_cure, cure_sprites)
        engine.game["time_of_day"] = "day"
        engine.sleeping = True
        engine.sleep_end_ms = 0
        engine._wake_from_sleep(early=False)
        assert engine.sleeping is False
        assert engine.game["time_of_day"] == "night"

    def test_wake_early(self, make_engine, minimal_game_cure, cure_sprites):
        engine = make_engine(minimal_game_cure, cure_sprites)
        engine.game["time_of_day"] = "day"
        engine.sleeping = True
        engine.sleep_end_ms = 99999999
        engine._wake_from_sleep(early=True)
        assert engine.sleeping is False

    def test_not_sleeping_noop(self, make_engine, minimal_game_cure, cure_sprites):
        engine = make_engine(minimal_game_cure, cure_sprites)
        engine.sleeping = False
        old_time = engine.game["time_of_day"]
        engine._wake_from_sleep(early=False)
        assert engine.game["time_of_day"] == old_time
