"""Tests for GameEngine.buy_good() — shop purchasing."""

import game_generator as gg


class TestBuyGood:
    def _setup_indoor(self, engine):
        ts = engine.config.TILE_SIZE
        shop = engine.buildings[0]
        ex, ey = shop["entrance"]
        engine.player_x = ex * ts
        engine.player_y = ey * ts
        engine.interact()
        # Move near the NPC to allow buying
        nx, ny = engine.current_building["npc_pos"]
        engine.player_x = nx * ts
        engine.player_y = ny * ts

    def test_buy_item(self, make_engine, minimal_game_repair_bridge, repair_bridge_sprites):
        engine = make_engine(minimal_game_repair_bridge, repair_bridge_sprites)
        self._setup_indoor(engine)
        old_money = engine.money
        engine.buy_good(0)
        # Should have bought item 0 (planks, price=20)
        assert engine.money < old_money
        assert "planks" in engine.items_collected

    def test_not_enough_money(self, make_engine, minimal_game_repair_bridge, repair_bridge_sprites):
        engine = make_engine(minimal_game_repair_bridge, repair_bridge_sprites)
        self._setup_indoor(engine)
        engine.money = 0
        engine.buy_good(0)
        assert "planks" not in engine.items_collected

    def test_already_bought(self, make_engine, minimal_game_repair_bridge, repair_bridge_sprites):
        engine = make_engine(minimal_game_repair_bridge, repair_bridge_sprites)
        self._setup_indoor(engine)
        engine.buy_good(0)
        old_money = engine.money
        engine.buy_good(0)
        assert engine.money == old_money  # No double charge

    def test_invalid_index(self, make_engine, minimal_game_repair_bridge, repair_bridge_sprites):
        engine = make_engine(minimal_game_repair_bridge, repair_bridge_sprites)
        self._setup_indoor(engine)
        old_money = engine.money
        engine.buy_good(99)
        assert engine.money == old_money

    def test_negative_index(self, make_engine, minimal_game_repair_bridge, repair_bridge_sprites):
        engine = make_engine(minimal_game_repair_bridge, repair_bridge_sprites)
        self._setup_indoor(engine)
        old_money = engine.money
        engine.buy_good(-1)
        assert engine.money == old_money

    def test_no_building(self, make_engine, minimal_game_repair_bridge, repair_bridge_sprites):
        engine = make_engine(minimal_game_repair_bridge, repair_bridge_sprites)
        # Not inside any building
        engine.buy_good(0)
        assert engine.money == 60  # Unchanged
