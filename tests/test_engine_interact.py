"""Tests for GameEngine.interact() — NPC, chest, door, bridge, mix station, buildings."""

import game_generator as gg


class TestNPCInteraction:
    def test_talk_to_npc(self, make_engine, minimal_game_cure, cure_sprites):
        engine = make_engine(minimal_game_cure, cure_sprites)
        ts = engine.config.TILE_SIZE
        npc = engine.game["npc"]
        engine.player_x = npc["x"] * ts
        engine.player_y = npc["y"] * ts
        engine.interact()
        assert engine.talked_to_npc is True

    def test_npc_sets_quest_known(self, make_engine, minimal_game_cure, cure_sprites):
        engine = make_engine(minimal_game_cure, cure_sprites)
        ts = engine.config.TILE_SIZE
        npc = engine.game["npc"]
        engine.player_x = npc["x"] * ts
        engine.player_y = npc["y"] * ts
        engine.interact()
        assert engine.quest_known is True


class TestCureCompletion:
    def test_cure_heals_npc(self, make_engine, minimal_game_cure, cure_sprites):
        engine = make_engine(minimal_game_cure, cure_sprites)
        ts = engine.config.TILE_SIZE
        # Collect all ingredients
        for item in engine.items:
            if item.get("kind") == "ingredient":
                engine.items_collected.add(item["id"])
                engine.inventory.append(item["name"])
        # Mix potion
        engine.player_x = engine.mix_station["x"] * ts
        engine.player_y = engine.mix_station["y"] * ts
        engine.interact()
        assert engine.mixed_potion is True
        # Deliver to NPC
        npc = engine.game["npc"]
        engine.player_x = npc["x"] * ts
        engine.player_y = npc["y"] * ts
        engine.talked_to_npc = True
        engine.interact()
        assert engine.npc_healed is True


class TestLostItemReturn:
    def test_return_lost_item(self, make_engine, minimal_game_lost_item, minimal_sprites):
        engine = make_engine(minimal_game_lost_item, minimal_sprites)
        ts = engine.config.TILE_SIZE
        engine.lost_item_found = True
        engine.talked_to_npc = True
        npc = engine.game["npc"]
        engine.player_x = npc["x"] * ts
        engine.player_y = npc["y"] * ts
        engine.interact()
        assert engine.lost_item_returned is True


class TestMixStation:
    def test_mix_without_ingredients(self, make_engine, minimal_game_cure, cure_sprites):
        engine = make_engine(minimal_game_cure, cure_sprites)
        ts = engine.config.TILE_SIZE
        engine.player_x = engine.mix_station["x"] * ts
        engine.player_y = engine.mix_station["y"] * ts
        engine.interact()
        assert engine.mixed_potion is False

    def test_mix_with_all_ingredients(self, make_engine, minimal_game_cure, cure_sprites):
        engine = make_engine(minimal_game_cure, cure_sprites)
        ts = engine.config.TILE_SIZE
        for item in engine.items:
            if item.get("kind") == "ingredient":
                engine.items_collected.add(item["id"])
        engine.player_x = engine.mix_station["x"] * ts
        engine.player_y = engine.mix_station["y"] * ts
        engine.interact()
        assert engine.mixed_potion is True
        assert "Healing Potion" in engine.inventory


class TestChestKeyDoor:
    def test_open_chest(self, make_engine, minimal_game_key_door, key_door_sprites):
        engine = make_engine(minimal_game_key_door, key_door_sprites)
        ts = engine.config.TILE_SIZE
        engine.player_x = engine.chest["x"] * ts
        engine.player_y = engine.chest["y"] * ts
        engine.interact()
        assert engine.chest_opened is True
        assert engine.key_spawned is True

    def test_door_locked_without_key(self, make_engine, minimal_game_key_door, key_door_sprites):
        engine = make_engine(minimal_game_key_door, key_door_sprites)
        ts = engine.config.TILE_SIZE
        engine.player_x = engine.door["x"] * ts
        engine.player_y = engine.door["y"] * ts
        engine.interact()
        assert engine.door_opened is False

    def test_door_opens_with_key(self, make_engine, minimal_game_key_door, key_door_sprites):
        engine = make_engine(minimal_game_key_door, key_door_sprites)
        ts = engine.config.TILE_SIZE
        engine.key_collected = True
        engine.player_x = engine.door["x"] * ts
        engine.player_y = engine.door["y"] * ts
        engine.interact()
        assert engine.door_opened is True


class TestBridgeRepair:
    def test_bridge_no_materials(self, make_engine, minimal_game_repair_bridge, repair_bridge_sprites):
        engine = make_engine(minimal_game_repair_bridge, repair_bridge_sprites)
        ts = engine.config.TILE_SIZE
        bt = list(engine.bridge_tiles)[0]
        engine.player_x = (bt[0] - 1) * ts
        engine.player_y = bt[1] * ts
        engine.interact()
        assert engine.bridge_repaired is False

    def test_bridge_with_materials(self, make_engine, minimal_game_repair_bridge, repair_bridge_sprites):
        engine = make_engine(minimal_game_repair_bridge, repair_bridge_sprites)
        ts = engine.config.TILE_SIZE
        engine.items_collected.update(["planks", "rope", "nails"])
        bt = list(engine.bridge_tiles)[0]
        engine.player_x = (bt[0] - 1) * ts
        engine.player_y = bt[1] * ts
        engine.interact()
        assert engine.bridge_repaired is True


class TestBuildingEnterExit:
    def test_enter_building(self, make_engine, minimal_game_cure, cure_sprites):
        engine = make_engine(minimal_game_cure, cure_sprites)
        ts = engine.config.TILE_SIZE
        shop = engine.buildings[0]
        ex, ey = shop["entrance"]
        engine.player_x = ex * ts
        engine.player_y = ey * ts
        engine.interact()
        assert engine.scene == "indoor"
        assert engine.current_building is not None

    def test_exit_building(self, make_engine, minimal_game_cure, cure_sprites):
        engine = make_engine(minimal_game_cure, cure_sprites)
        ts = engine.config.TILE_SIZE
        # Enter shop
        shop = engine.buildings[0]
        ex, ey = shop["entrance"]
        engine.player_x = ex * ts
        engine.player_y = ey * ts
        engine.interact()
        assert engine.scene == "indoor"
        # Now exit
        exit_x, exit_y = engine.current_building["exit"]
        engine.player_x = exit_x * ts
        engine.player_y = exit_y * ts
        engine.interact()
        assert engine.scene == "outdoor"
