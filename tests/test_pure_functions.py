"""Tests for pure/stateless utility functions at module level."""

import game_generator as gg


# ── normalize_goal_type ──────────────────────────────────────

class TestNormalizeGoalType:
    def test_valid_cure(self):
        assert gg.normalize_goal_type("cure") == "cure"

    def test_valid_key_and_door(self):
        assert gg.normalize_goal_type("key_and_door") == "key_and_door"

    def test_valid_lost_item(self):
        assert gg.normalize_goal_type("lost_item") == "lost_item"

    def test_valid_repair_bridge(self):
        assert gg.normalize_goal_type("repair_bridge") == "repair_bridge"

    def test_none_input(self):
        assert gg.normalize_goal_type(None) is None

    def test_empty_string(self):
        assert gg.normalize_goal_type("") is None

    def test_unknown_value(self):
        assert gg.normalize_goal_type("combat") is None

    def test_strips_whitespace(self):
        assert gg.normalize_goal_type("  cure  ") == "cure"

    def test_case_insensitive(self):
        assert gg.normalize_goal_type("CURE") == "cure"
        assert gg.normalize_goal_type("Key_And_Door") == "key_and_door"


# ── parse_goal_plan ──────────────────────────────────────────

class TestParseGoalPlan:
    def test_single_valid(self):
        assert gg.parse_goal_plan("cure") == ["cure"]

    def test_multiple_valid(self):
        assert gg.parse_goal_plan("cure,key_and_door,lost_item") == ["cure", "key_and_door", "lost_item"]

    def test_filters_invalid(self):
        assert gg.parse_goal_plan("cure,combat,lost_item") == ["cure", "lost_item"]

    def test_none_input(self):
        assert gg.parse_goal_plan(None) == []

    def test_empty_string(self):
        assert gg.parse_goal_plan("") == []

    def test_all_invalid(self):
        assert gg.parse_goal_plan("combat,fight") == []

    def test_whitespace_values(self):
        result = gg.parse_goal_plan(" cure , lost_item ")
        assert "cure" in result
        assert "lost_item" in result


# ── infer_goal_from_prompt ───────────────────────────────────

class TestInferGoalFromPrompt:
    def test_heal_keyword(self):
        assert gg.infer_goal_from_prompt("heal the sick villager") == "cure"

    def test_cure_keyword(self):
        assert gg.infer_goal_from_prompt("cure the princess") == "cure"

    def test_sick_keyword(self):
        assert gg.infer_goal_from_prompt("a sick NPC needs help") == "cure"

    def test_key_keyword(self):
        assert gg.infer_goal_from_prompt("find the key to unlock the gate") == "key_and_door"

    def test_door_keyword(self):
        assert gg.infer_goal_from_prompt("open the door to the castle") == "key_and_door"

    def test_lost_keyword(self):
        assert gg.infer_goal_from_prompt("a lost heirloom somewhere") == "lost_item"

    def test_missing_keyword(self):
        assert gg.infer_goal_from_prompt("find the missing artifact") == "lost_item"

    def test_bridge_keyword(self):
        assert gg.infer_goal_from_prompt("repair the broken bridge") == "repair_bridge"

    def test_no_match(self):
        assert gg.infer_goal_from_prompt("a sunny meadow adventure") is None

    def test_empty_string(self):
        assert gg.infer_goal_from_prompt("") is None

    def test_none_input(self):
        assert gg.infer_goal_from_prompt(None) is None


# ── extract_env_hints ────────────────────────────────────────

class TestExtractEnvHints:
    def test_night_time(self):
        h = gg.extract_env_hints("a moonlit garden at midnight")
        assert h["time_of_day"] == "night"

    def test_sunset_time(self):
        h = gg.extract_env_hints("a harbor at dusk")
        assert h["time_of_day"] == "sunset"

    def test_dawn_time(self):
        h = gg.extract_env_hints("sunrise over the hills")
        assert h["time_of_day"] == "dawn"

    def test_day_time(self):
        h = gg.extract_env_hints("a sunny afternoon in the meadow")
        assert h["time_of_day"] == "day"

    def test_no_time(self):
        h = gg.extract_env_hints("a quiet place")
        assert h["time_of_day"] is None

    def test_desert_terrain(self):
        h = gg.extract_env_hints("a desert oasis")
        assert h["terrain"] == "desert"

    def test_beach_terrain(self):
        h = gg.extract_env_hints("a seaside town")
        assert h["terrain"] == "beach"

    def test_snow_terrain(self):
        h = gg.extract_env_hints("a snowy blizzard")
        assert h["terrain"] == "snow"

    def test_town_terrain(self):
        h = gg.extract_env_hints("a busy village market")
        assert h["terrain"] == "town"

    def test_forest_terrain(self):
        h = gg.extract_env_hints("deep in the woods")
        assert h["terrain"] == "forest"

    def test_castle_terrain(self):
        h = gg.extract_env_hints("inside the castle keep")
        assert h["terrain"] == "castle"

    def test_ruins_terrain(self):
        h = gg.extract_env_hints("an ancient temple")
        assert h["terrain"] == "ruins"

    def test_oasis_layout(self):
        h = gg.extract_env_hints("an oasis in the desert")
        assert h["layout_style"] == "oasis"

    def test_market_layout(self):
        h = gg.extract_env_hints("a bustling bazaar")
        assert h["layout_style"] == "market_street"

    def test_coastline_layout(self):
        h = gg.extract_env_hints("a seaside coast")
        assert h["layout_style"] == "coastline"

    def test_theme_tags_populated(self):
        h = gg.extract_env_hints("a desert oasis at night with ruins")
        assert isinstance(h["theme_tags"], list)
        assert "desert" in h["theme_tags"]
        assert "oasis" in h["theme_tags"]
        assert "night" in h["theme_tags"]
        assert "ruins" in h["theme_tags"]

    def test_empty_prompt(self):
        h = gg.extract_env_hints("")
        assert h["time_of_day"] is None
        assert h["terrain"] is None
        assert h["layout_style"] is None
        assert h["theme_tags"] == []

    def test_none_prompt(self):
        h = gg.extract_env_hints(None)
        assert h["time_of_day"] is None


# ── parse_level_goal_overrides ───────────────────────────────

class TestParseLevelGoalOverrides:
    def test_empty_prompt(self):
        assert gg.parse_level_goal_overrides("") == {}

    def test_none_prompt(self):
        assert gg.parse_level_goal_overrides(None) == {}

    def test_no_directives(self):
        assert gg.parse_level_goal_overrides("a sunny day in the meadow") == {}

    def test_single_goal(self):
        result = gg.parse_level_goal_overrides("Level 1: cure")
        assert result == {1: ["cure"]}

    def test_multiple_goals(self):
        result = gg.parse_level_goal_overrides("Level 2: cure, lost_item")
        assert result == {2: ["cure", "lost_item"]}

    def test_multiple_levels(self):
        result = gg.parse_level_goal_overrides("Level 1: cure\nLevel 3: key_and_door")
        assert result == {1: ["cure"], 3: ["key_and_door"]}

    def test_case_insensitive(self):
        result = gg.parse_level_goal_overrides("level 1: repair_bridge")
        assert result == {1: ["repair_bridge"]}


# ── parse_level_biome_overrides / build_biome_plans ─────────

class TestParseLevelBiomeOverrides:
    def test_empty_prompt(self):
        assert gg.parse_level_biome_overrides("") == {}

    def test_directive_form(self):
        result = gg.parse_level_biome_overrides("Level 2 Biome: snow")
        assert result == {2: "snow"}

    def test_level_tail_form(self):
        result = gg.parse_level_biome_overrides("Level 3: key_and_door in desert ruins")
        assert result == {3: "desert"}

    def test_filters_invalid(self):
        result = gg.parse_level_biome_overrides("Level 1 Biome: moon")
        assert result == {}


class TestBuildBiomePlans:
    def test_prompt_override_wins(self):
        plans = gg.build_biome_plans(
            prompt="Level 1 Biome: snow",
            by_level_raw=["desert", "", ""],
            level_count=1,
        )
        assert plans == ["snow"]

    def test_ui_used_when_no_prompt_override(self):
        plans = gg.build_biome_plans(
            prompt="a quiet town",
            by_level_raw=["beach", "ruins", ""],
            level_count=2,
        )
        assert plans == ["beach", "ruins"]

    def test_random_fallback_when_unspecified(self):
        plans = gg.build_biome_plans(
            prompt="a quiet place",
            by_level_raw=["", "", ""],
            level_count=3,
        )
        assert len(plans) == 3
        assert all(p in gg.ALLOWED_BIOMES for p in plans)


# ── build_quest_plans ────────────────────────────────────────

class TestBuildQuestPlans:
    def test_prompt_override_wins_over_ui(self):
        plans = gg.build_quest_plans(
            prompt="Level 1: repair_bridge",
            by_level_raw=[["cure"], [], []],
            level_count=1,
        )
        assert plans == [["repair_bridge"]]

    def test_ui_used_when_no_prompt_override(self):
        plans = gg.build_quest_plans(
            prompt="a calm world",
            by_level_raw=[["cure", "lost_item"], [], []],
            level_count=1,
        )
        assert plans == [["cure", "lost_item"]]

    def test_random_fallback_when_neither_prompt_nor_ui_specifies(self):
        plans = gg.build_quest_plans(
            prompt="a calm world",
            by_level_raw=[[], [], []],
            level_count=3,
        )
        assert len(plans) == 3
        for level in plans:
            assert len(level) == 1
            assert level[0] in gg.ALLOWED_GOALS


# ── _looks_like_princess ─────────────────────────────────────

class TestLooksLikePrincess:
    def test_princess_in_name(self):
        assert gg._looks_like_princess({"name": "Princess Luna"}) is True

    def test_princess_in_desc(self):
        assert gg._looks_like_princess({"sprite_desc": "a princess in a dress"}) is True

    def test_no_princess(self):
        assert gg._looks_like_princess({"name": "Elder", "sprite_desc": "old man"}) is False

    def test_empty_dict(self):
        assert gg._looks_like_princess({}) is False

    def test_case_insensitive(self):
        assert gg._looks_like_princess({"name": "PRINCESS"}) is True
