"""Tests for GameDesigner class methods."""

import json
import random
from unittest.mock import patch, MagicMock
import game_generator as gg


def _make_designer():
    client = gg.OpenAIClient("sk-fake-key")
    return gg.GameDesigner(client)


# ── _pick_distinct_colors ────────────────────────────────────

class TestPickDistinctColors:
    def test_returns_two_strings(self):
        d = _make_designer()
        c1, c2 = d._pick_distinct_colors()
        assert isinstance(c1, str)
        assert isinstance(c2, str)

    def test_colors_are_different(self):
        d = _make_designer()
        # Run multiple times to check they can be different
        seen_different = False
        for _ in range(20):
            c1, c2 = d._pick_distinct_colors()
            if c1 != c2:
                seen_different = True
                break
        assert seen_different


# ── _pick_archetypes ─────────────────────────────────────────

class TestPickArchetypes:
    def test_returns_two_strings(self):
        d = _make_designer()
        p, n = d._pick_archetypes("a forest adventure", "cure")
        assert isinstance(p, str)
        assert isinstance(n, str)

    def test_cure_quest_biases_archetypes(self):
        d = _make_designer()
        random.seed(42)
        p, n = d._pick_archetypes("help the sick", "cure")
        # For cure, NPC is often princess/prince/queen/king/cleric
        assert isinstance(n, str)

    def test_princess_prompt_picks_princess(self):
        d = _make_designer()
        p, n = d._pick_archetypes("the princess needs help", "lost_item")
        assert p == "princess"

    def test_wizard_prompt_picks_wizard(self):
        d = _make_designer()
        p, n = d._pick_archetypes("a wizard's tower", "lost_item")
        assert p == "wizard"


# ── _flavored_goal / _flavored_steps ─────────────────────────

class TestFlavoredGoal:
    def test_returns_string(self):
        d = _make_designer()
        game = {"terrain": {"type": "meadow"}, "time_of_day": "day", "npc": {"name": "Elder"}}
        quest = {"type": "cure", "items": [{"name": "Herb"}]}
        result = d._flavored_goal(game, quest)
        assert isinstance(result, str)
        assert len(result) > 5


class TestFlavoredSteps:
    def test_cure_steps(self):
        d = _make_designer()
        steps = d._flavored_steps({"type": "cure"})
        assert isinstance(steps, list)
        assert len(steps) >= 3

    def test_key_and_door_steps(self):
        d = _make_designer()
        steps = d._flavored_steps({"type": "key_and_door"})
        assert len(steps) >= 3

    def test_lost_item_steps(self):
        d = _make_designer()
        steps = d._flavored_steps({"type": "lost_item"})
        assert len(steps) >= 3

    def test_repair_bridge_steps(self):
        d = _make_designer()
        steps = d._flavored_steps({"type": "repair_bridge"})
        assert len(steps) >= 3

    def test_unknown_type_fallback(self):
        d = _make_designer()
        steps = d._flavored_steps({"type": "unknown"})
        assert isinstance(steps, list)
        assert len(steps) >= 2


# ── _fallback ────────────────────────────────────────────────

class TestFallback:
    def test_night_prompt(self):
        d = _make_designer()
        g = d._fallback("a dark castle", "cure")
        assert g["time_of_day"] == "night"
        assert g["terrain"]["type"] == "castle"

    def test_forest_prompt(self):
        d = _make_designer()
        g = d._fallback("forest adventure", "cure")
        assert g["terrain"]["type"] == "forest"

    def test_beach_prompt(self):
        d = _make_designer()
        g = d._fallback("ocean waves", "cure")
        assert g["terrain"]["type"] == "beach"

    def test_snow_prompt(self):
        d = _make_designer()
        g = d._fallback("icy winter", "cure")
        assert g["terrain"]["type"] == "snow"

    def test_default_meadow(self):
        d = _make_designer()
        g = d._fallback("an adventure", "cure")
        assert g["terrain"]["type"] == "meadow"

    def test_key_and_door_fallback(self):
        d = _make_designer()
        g = d._fallback("adventure", "key_and_door")
        assert g["quest"]["type"] == "key_and_door"
        assert "chest" in g["quest"]
        assert "key" in g["quest"]
        assert "door" in g["quest"]

    def test_lost_item_fallback(self):
        d = _make_designer()
        g = d._fallback("adventure", "lost_item")
        assert g["quest"]["type"] == "lost_item"

    def test_cure_fallback(self):
        d = _make_designer()
        g = d._fallback("adventure", "cure")
        assert g["quest"]["type"] == "cure"
        assert "mix_station" in g["quest"]


# ── _normalize_game ──────────────────────────────────────────

class TestNormalizeGame:
    def test_adds_seed(self):
        d = _make_designer()
        game = {
            "player": {"name": "Hero", "sprite_desc": "hero", "start_x": 5, "start_y": 5},
            "npc": {"name": "Elder", "sprite_desc": "npc", "x": 8, "y": 8,
                    "dialogue_intro": "Hi", "dialogue_hint": "Go",
                    "dialogue_progress": "Good", "dialogue_complete": "Done"},
            "terrain": {"type": "meadow"},
            "quest": {"type": "lost_item", "goal": "", "steps": [], "items": []},
        }
        result = d._normalize_game(game)
        assert "seed" in result
        assert isinstance(result["seed"], int)

    def test_normalizes_quest_types(self):
        d = _make_designer()
        game = {
            "player": {"name": "Hero", "sprite_desc": "hero", "start_x": 5, "start_y": 5},
            "npc": {"name": "Elder", "sprite_desc": "npc", "x": 8, "y": 8,
                    "dialogue_intro": "Hi", "dialogue_hint": "Go",
                    "dialogue_progress": "Good", "dialogue_complete": "Done"},
            "terrain": {"type": "meadow"},
            "quest": {"type": "cure", "goal": "", "steps": [], "items": []},
        }
        result = d._normalize_game(game)
        assert "types" in result["quest"]
        assert "cure" in result["quest"]["types"]

    def test_cure_adds_mix_station(self):
        d = _make_designer()
        game = {
            "player": {"name": "Hero", "sprite_desc": "hero", "start_x": 5, "start_y": 5},
            "npc": {"name": "Elder", "sprite_desc": "npc", "x": 8, "y": 8,
                    "dialogue_intro": "Hi", "dialogue_hint": "Go",
                    "dialogue_progress": "Good", "dialogue_complete": "Done"},
            "terrain": {"type": "meadow"},
            "quest": {"type": "cure", "goal": "", "steps": [], "items": [
                {"id": "i1", "name": "Herb", "sprite_desc": "herb", "x": 1, "y": 1},
                {"id": "i2", "name": "Leaf", "sprite_desc": "leaf", "x": 2, "y": 2},
                {"id": "i3", "name": "Dew", "sprite_desc": "dew", "x": 3, "y": 3},
            ]},
        }
        result = d._normalize_game(game)
        assert result["quest"].get("mix_station") is not None

    def test_key_and_door_adds_chest_key_door(self):
        d = _make_designer()
        game = {
            "player": {"name": "Hero", "sprite_desc": "hero", "start_x": 5, "start_y": 5},
            "npc": {"name": "Elder", "sprite_desc": "npc", "x": 8, "y": 8,
                    "dialogue_intro": "Hi", "dialogue_hint": "Go",
                    "dialogue_progress": "Good", "dialogue_complete": "Done"},
            "terrain": {"type": "meadow"},
            "quest": {"type": "key_and_door", "goal": "", "steps": [], "items": []},
        }
        result = d._normalize_game(game)
        assert result["quest"].get("chest") is not None
        assert result["quest"].get("key") is not None
        assert result["quest"].get("door") is not None

    def test_repair_bridge_adds_materials(self):
        d = _make_designer()
        game = {
            "player": {"name": "Hero", "sprite_desc": "hero", "start_x": 5, "start_y": 5},
            "npc": {"name": "Elder", "sprite_desc": "npc", "x": 8, "y": 8,
                    "dialogue_intro": "Hi", "dialogue_hint": "Go",
                    "dialogue_progress": "Good", "dialogue_complete": "Done"},
            "terrain": {"type": "meadow"},
            "quest": {"type": "repair_bridge", "goal": "", "steps": [], "items": []},
        }
        result = d._normalize_game(game)
        assert result["quest"].get("repair_materials") is not None
        mat_ids = [m["id"] for m in result["quest"]["repair_materials"]]
        assert "planks" in mat_ids
        assert "rope" in mat_ids
        assert "nails" in mat_ids

    def test_stacked_goals(self):
        d = _make_designer()
        game = {
            "player": {"name": "Hero", "sprite_desc": "hero", "start_x": 5, "start_y": 5},
            "npc": {"name": "Elder", "sprite_desc": "npc", "x": 8, "y": 8,
                    "dialogue_intro": "Hi", "dialogue_hint": "Go",
                    "dialogue_progress": "Good", "dialogue_complete": "Done"},
            "terrain": {"type": "meadow"},
            "quest": {"type": "cure", "goal": "", "steps": [], "items": []},
        }
        result = d._normalize_game(game, quest_plan_override=["cure", "lost_item"])
        assert "cure" in result["quest"]["types"]
        assert "lost_item" in result["quest"]["types"]
        assert result["quest"].get("lost_item") is not None
        assert result["quest"].get("mix_station") is not None


# ── design_game (mocked) ─────────────────────────────────────

class TestDesignGame:
    @patch.object(gg.OpenAIClient, "generate_text")
    def test_returns_dict(self, mock_gen):
        fake_game = {
            "title": "Test Game",
            "story": "A test story",
            "time_of_day": "day",
            "player": {"name": "Hero", "sprite_desc": "hero", "start_x": 5, "start_y": 5},
            "npc": {"name": "Elder", "sprite_desc": "npc", "x": 8, "y": 8,
                    "dialogue_intro": "Hi", "dialogue_hint": "Go",
                    "dialogue_progress": "Good", "dialogue_complete": "Done"},
            "terrain": {"type": "meadow", "features": ["path", "trees"]},
            "quest": {"type": "cure", "goal": "Heal the NPC",
                      "steps": ["Talk", "Gather", "Mix", "Deliver"],
                      "items": [
                          {"id": "i1", "name": "Herb", "sprite_desc": "herb", "x": 10, "y": 3},
                          {"id": "i2", "name": "Leaf", "sprite_desc": "leaf", "x": 12, "y": 6},
                          {"id": "i3", "name": "Dew", "sprite_desc": "dew", "x": 7, "y": 9},
                      ],
                      "mix_station": {"name": "Cauldron", "sprite_desc": "cauldron", "x": 9, "y": 5},
                      "npc_healed_sprite_desc": "healed NPC"},
        }
        mock_gen.return_value = json.dumps(fake_game)
        d = _make_designer()
        result = d.design_game("test prompt")
        assert isinstance(result, dict)
        assert "quest" in result
        assert "player" in result

    @patch.object(gg.OpenAIClient, "generate_text")
    def test_fallback_on_bad_json(self, mock_gen):
        mock_gen.return_value = "NOT VALID JSON{{{]]]"
        d = _make_designer()
        result = d.design_game("test prompt")
        # Should still return a valid game dict via fallback
        assert isinstance(result, dict)
        assert "quest" in result
        assert "player" in result
