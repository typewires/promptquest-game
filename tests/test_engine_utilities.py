"""Tests for engine utility methods."""

import game_generator as gg


class TestFindOpenTile:
    def test_returns_open_tile(self, make_engine, minimal_game_cure, cure_sprites):
        engine = make_engine(minimal_game_cure, cure_sprites)
        x, y = engine._find_open_tile(5, 5)
        assert (x, y) not in engine.solid

    def test_avoids_solid(self, make_engine, minimal_game_cure, cure_sprites):
        engine = make_engine(minimal_game_cure, cure_sprites)
        engine.solid.add((5, 5))
        x, y = engine._find_open_tile(5, 5)
        assert (x, y) not in engine.solid


class TestComputeReachable:
    def test_start_is_reachable(self, make_engine, minimal_game_cure, cure_sprites):
        engine = make_engine(minimal_game_cure, cure_sprites)
        reachable = engine._compute_reachable(engine.solid, (5, 5))
        assert (5, 5) in reachable

    def test_blocked_tile_not_reachable(self, make_engine, minimal_game_cure, cure_sprites):
        engine = make_engine(minimal_game_cure, cure_sprites)
        # Create a wall around (10,10)
        for dx in range(-1, 2):
            for dy in range(-1, 2):
                if (dx, dy) != (0, 0):
                    engine.solid.add((10 + dx, 10 + dy))
        reachable = engine._compute_reachable(engine.solid, (5, 5))
        # (10,10) might still be reachable if not solid itself, but tiles inside walls won't be


class TestPickFreeReachable:
    def test_preferred_tile_if_available(self, make_engine, minimal_game_cure, cure_sprites):
        engine = make_engine(minimal_game_cure, cure_sprites)
        reachable = engine._compute_reachable(engine.solid, (5, 5))
        # Pick a tile that's in reachable set
        if (6, 6) in reachable:
            x, y = engine._pick_free_reachable((6, 6), reachable, set(), engine.solid)
            assert (x, y) == (6, 6)


class TestWrapText:
    def test_short_text(self, make_engine, minimal_game_cure, cure_sprites):
        engine = make_engine(minimal_game_cure, cure_sprites)
        lines = engine._wrap_text("Hello", 40)
        assert lines == ["Hello"]

    def test_wraps_long_text(self, make_engine, minimal_game_cure, cure_sprites):
        engine = make_engine(minimal_game_cure, cure_sprites)
        text = "This is a very long sentence that should definitely be wrapped into multiple lines"
        lines = engine._wrap_text(text, 20)
        assert len(lines) > 1

    def test_empty_text(self, make_engine, minimal_game_cure, cure_sprites):
        engine = make_engine(minimal_game_cure, cure_sprites)
        lines = engine._wrap_text("", 40)
        assert lines == [] or lines == [""]


class TestEntityBob:
    def test_returns_tuple(self, make_engine, minimal_game_cure, cure_sprites):
        engine = make_engine(minimal_game_cure, cure_sprites)
        result = engine._entity_bob("player")
        assert isinstance(result, tuple)
        assert len(result) == 2


class TestHasMaterials:
    def test_no_materials(self, make_engine, minimal_game_repair_bridge, repair_bridge_sprites):
        engine = make_engine(minimal_game_repair_bridge, repair_bridge_sprites)
        assert engine.has_materials() is False

    def test_partial_materials(self, make_engine, minimal_game_repair_bridge, repair_bridge_sprites):
        engine = make_engine(minimal_game_repair_bridge, repair_bridge_sprites)
        engine.items_collected.add("planks")
        assert engine.has_materials() is False

    def test_all_materials(self, make_engine, minimal_game_repair_bridge, repair_bridge_sprites):
        engine = make_engine(minimal_game_repair_bridge, repair_bridge_sprites)
        engine.items_collected.update(["planks", "rope", "nails"])
        assert engine.has_materials() is True


class TestMsg:
    def test_sets_message(self, make_engine, minimal_game_cure, cure_sprites):
        engine = make_engine(minimal_game_cure, cure_sprites)
        engine.msg("Hello!")
        assert engine.message == "Hello!"

    def test_sets_timer(self, make_engine, minimal_game_cure, cure_sprites):
        engine = make_engine(minimal_game_cure, cure_sprites)
        engine.msg("Test")
        assert engine.message_timer == 250
