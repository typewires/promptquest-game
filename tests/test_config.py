"""Tests for Config defaults and ALLOWED_GOALS."""

import game_generator as gg


class TestConfigDefaults:
    def test_text_model_default(self):
        c = gg.Config()
        assert c.TEXT_MODEL == "gpt-4o-mini"

    def test_image_model_default(self):
        c = gg.Config()
        assert c.IMAGE_MODEL == "gpt-image-1"

    def test_image_quality_default(self):
        c = gg.Config()
        assert c.IMAGE_QUALITY == "medium"

    def test_tile_size(self):
        c = gg.Config()
        assert c.TILE_SIZE == 72

    def test_map_dimensions(self):
        c = gg.Config()
        assert c.MAP_WIDTH == 16
        assert c.MAP_HEIGHT == 12

    def test_player_speed(self):
        c = gg.Config()
        assert c.PLAYER_SPEED == 4

    def test_item_sprites_per_level(self):
        c = gg.Config()
        assert c.ITEM_SPRITES_PER_LEVEL == 1

    def test_force_cure_princess(self):
        c = gg.Config()
        assert c.FORCE_CURE_PRINCESS is True

    def test_image_max_retries(self):
        c = gg.Config()
        assert c.IMAGE_MAX_RETRIES == 4


class TestAllowedGoals:
    def test_allowed_goals_is_list(self):
        assert isinstance(gg.ALLOWED_GOALS, list)

    def test_allowed_goals_contains_cure(self):
        assert "cure" in gg.ALLOWED_GOALS

    def test_allowed_goals_contains_key_and_door(self):
        assert "key_and_door" in gg.ALLOWED_GOALS

    def test_allowed_goals_contains_lost_item(self):
        assert "lost_item" in gg.ALLOWED_GOALS

    def test_allowed_goals_contains_repair_bridge(self):
        assert "repair_bridge" in gg.ALLOWED_GOALS

    def test_allowed_goals_count(self):
        assert len(gg.ALLOWED_GOALS) == 4
