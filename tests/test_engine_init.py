"""Tests for GameEngine construction and state defaults."""

import game_generator as gg


class TestEngineInit:
    def test_creates_engine(self, make_engine, minimal_game_cure, cure_sprites):
        engine = make_engine(minimal_game_cure, cure_sprites)
        assert engine is not None
        assert engine.running is True

    def test_level_index_starts_at_zero(self, make_engine, minimal_game_cure, cure_sprites):
        engine = make_engine(minimal_game_cure, cure_sprites)
        assert engine.level_index == 0

    def test_scene_starts_outdoor(self, make_engine, minimal_game_cure, cure_sprites):
        engine = make_engine(minimal_game_cure, cure_sprites)
        assert engine.scene == "outdoor"

    def test_game_not_won(self, make_engine, minimal_game_cure, cure_sprites):
        engine = make_engine(minimal_game_cure, cure_sprites)
        assert engine.game_won is False

    def test_inventory_empty(self, make_engine, minimal_game_cure, cure_sprites):
        engine = make_engine(minimal_game_cure, cure_sprites)
        assert engine.inventory == []

    def test_money_initialized(self, make_engine, minimal_game_cure, cure_sprites):
        engine = make_engine(minimal_game_cure, cure_sprites)
        assert engine.money == 60

    def test_buildings_created(self, make_engine, minimal_game_cure, cure_sprites):
        engine = make_engine(minimal_game_cure, cure_sprites)
        assert len(engine.buildings) == 2
        names = [b["name"] for b in engine.buildings]
        assert "Shop" in names
        assert "Inn" in names

    def test_cure_quest_state(self, make_engine, minimal_game_cure, cure_sprites):
        engine = make_engine(minimal_game_cure, cure_sprites)
        assert engine.npc_healed is False
        assert engine.mixed_potion is False
        assert engine.potion_given is False

    def test_key_door_quest_state(self, make_engine, minimal_game_key_door, key_door_sprites):
        engine = make_engine(minimal_game_key_door, key_door_sprites)
        assert engine.chest_opened is False
        assert engine.key_spawned is False
        assert engine.key_collected is False
        assert engine.door_opened is False

    def test_lost_item_quest_state(self, make_engine, minimal_game_lost_item, minimal_sprites):
        engine = make_engine(minimal_game_lost_item, minimal_sprites)
        assert engine.lost_item_found is False
        assert engine.lost_item_returned is False

    def test_repair_bridge_state(self, make_engine, minimal_game_repair_bridge, repair_bridge_sprites):
        engine = make_engine(minimal_game_repair_bridge, repair_bridge_sprites)
        assert engine.bridge_repaired is False
        assert len(engine.bridge_tiles) == 2

    def test_quest_types_set(self, make_engine, minimal_game_cure, cure_sprites):
        engine = make_engine(minimal_game_cure, cure_sprites)
        assert "cure" in engine.quest_types

    def test_stacked_quest_types(self, make_engine, minimal_game_stacked, cure_sprites):
        engine = make_engine(minimal_game_stacked, cure_sprites)
        assert "cure" in engine.quest_types
        assert "lost_item" in engine.quest_types
