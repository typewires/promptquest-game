"""Tests for goal tracking: _all_goals_complete, _quest_step_states, _quest_progress, stacked goals."""

import game_generator as gg


class TestAllGoalsComplete:
    def test_cure_incomplete(self, make_engine, minimal_game_cure, cure_sprites):
        engine = make_engine(minimal_game_cure, cure_sprites)
        assert engine._all_goals_complete() is False

    def test_cure_complete(self, make_engine, minimal_game_cure, cure_sprites):
        engine = make_engine(minimal_game_cure, cure_sprites)
        engine.npc_healed = True
        assert engine._all_goals_complete() is True

    def test_key_door_incomplete(self, make_engine, minimal_game_key_door, key_door_sprites):
        engine = make_engine(minimal_game_key_door, key_door_sprites)
        assert engine._all_goals_complete() is False

    def test_key_door_complete(self, make_engine, minimal_game_key_door, key_door_sprites):
        engine = make_engine(minimal_game_key_door, key_door_sprites)
        engine.door_opened = True
        assert engine._all_goals_complete() is True

    def test_lost_item_incomplete(self, make_engine, minimal_game_lost_item, minimal_sprites):
        engine = make_engine(minimal_game_lost_item, minimal_sprites)
        assert engine._all_goals_complete() is False

    def test_lost_item_complete(self, make_engine, minimal_game_lost_item, minimal_sprites):
        engine = make_engine(minimal_game_lost_item, minimal_sprites)
        engine.lost_item_returned = True
        assert engine._all_goals_complete() is True

    def test_repair_bridge_incomplete(self, make_engine, minimal_game_repair_bridge, repair_bridge_sprites):
        engine = make_engine(minimal_game_repair_bridge, repair_bridge_sprites)
        assert engine._all_goals_complete() is False

    def test_repair_bridge_complete(self, make_engine, minimal_game_repair_bridge, repair_bridge_sprites):
        engine = make_engine(minimal_game_repair_bridge, repair_bridge_sprites)
        engine.bridge_repaired = True
        assert engine._all_goals_complete() is True


class TestStackedGoals:
    def test_stacked_incomplete_when_one_done(self, make_engine, minimal_game_stacked, cure_sprites):
        engine = make_engine(minimal_game_stacked, cure_sprites)
        engine.npc_healed = True
        # lost_item_returned is still False
        assert engine._all_goals_complete() is False

    def test_stacked_complete_when_all_done(self, make_engine, minimal_game_stacked, cure_sprites):
        engine = make_engine(minimal_game_stacked, cure_sprites)
        engine.npc_healed = True
        engine.lost_item_returned = True
        assert engine._all_goals_complete() is True


class TestQuestStepStates:
    def test_returns_list_of_tuples(self, make_engine, minimal_game_cure, cure_sprites):
        engine = make_engine(minimal_game_cure, cure_sprites)
        steps = engine._quest_step_states()
        assert isinstance(steps, list)
        assert all(isinstance(s, tuple) and len(s) == 2 for s in steps)

    def test_first_step_is_talk(self, make_engine, minimal_game_cure, cure_sprites):
        engine = make_engine(minimal_game_cure, cure_sprites)
        steps = engine._quest_step_states()
        assert "Talk" in steps[0][0]

    def test_talk_step_starts_false(self, make_engine, minimal_game_cure, cure_sprites):
        engine = make_engine(minimal_game_cure, cure_sprites)
        steps = engine._quest_step_states()
        assert steps[0][1] is False

    def test_talk_step_becomes_true(self, make_engine, minimal_game_cure, cure_sprites):
        engine = make_engine(minimal_game_cure, cure_sprites)
        engine.talked_to_npc = True
        steps = engine._quest_step_states()
        assert steps[0][1] is True


class TestQuestProgress:
    def test_progress_format(self, make_engine, minimal_game_cure, cure_sprites):
        engine = make_engine(minimal_game_cure, cure_sprites)
        done, total, label = engine._quest_progress()
        assert isinstance(done, int)
        assert isinstance(total, int)
        assert "/" in label

    def test_progress_starts_at_zero(self, make_engine, minimal_game_cure, cure_sprites):
        engine = make_engine(minimal_game_cure, cure_sprites)
        done, total, _ = engine._quest_progress()
        assert done == 0
        assert total > 0
