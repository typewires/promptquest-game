"""Tests for GameEngine.check_pickups() — item collection."""

import game_generator as gg


class TestItemPickup:
    def test_collect_item(self, make_engine, minimal_game_cure, cure_sprites):
        engine = make_engine(minimal_game_cure, cure_sprites)
        ts = engine.config.TILE_SIZE
        # Place player exactly on item 0
        item = engine.items[0]
        engine.player_x = item["x"] * ts
        engine.player_y = item["y"] * ts
        engine.check_pickups()
        assert item["id"] in engine.items_collected
        assert item["name"] in engine.inventory

    def test_lost_item_flag(self, make_engine, minimal_game_lost_item, minimal_sprites):
        engine = make_engine(minimal_game_lost_item, minimal_sprites)
        ts = engine.config.TILE_SIZE
        # Find the lost item
        for item in engine.items:
            if item.get("kind") == "lost_item":
                engine.player_x = item["x"] * ts
                engine.player_y = item["y"] * ts
                engine.check_pickups()
                assert engine.lost_item_found is True
                return
        # If we get here, no lost item was found in items list
        assert False, "No lost_item kind in items"

    def test_key_pickup(self, make_engine, minimal_game_key_door, key_door_sprites):
        engine = make_engine(minimal_game_key_door, key_door_sprites)
        ts = engine.config.TILE_SIZE
        # Simulate chest opened and key spawned
        engine.chest_opened = True
        engine.key_spawned = True
        engine.key_pos = (engine.chest["x"], engine.chest["y"])
        engine.player_x = engine.key_pos[0] * ts
        engine.player_y = engine.key_pos[1] * ts
        engine.check_pickups()
        assert engine.key_collected is True

    def test_ingredient_counting(self, make_engine, minimal_game_cure, cure_sprites):
        engine = make_engine(minimal_game_cure, cure_sprites)
        ts = engine.config.TILE_SIZE
        ingredients = [it for it in engine.items if it.get("kind") == "ingredient"]
        for item in ingredients:
            engine.player_x = item["x"] * ts
            engine.player_y = item["y"] * ts
            engine.check_pickups()
        # All ingredients should be collected
        for item in ingredients:
            assert item["id"] in engine.items_collected

    def test_no_double_pickup(self, make_engine, minimal_game_cure, cure_sprites):
        engine = make_engine(minimal_game_cure, cure_sprites)
        ts = engine.config.TILE_SIZE
        item = engine.items[0]
        engine.player_x = item["x"] * ts
        engine.player_y = item["y"] * ts
        engine.check_pickups()
        inv_count = len(engine.inventory)
        engine.check_pickups()
        assert len(engine.inventory) == inv_count  # No duplicate
