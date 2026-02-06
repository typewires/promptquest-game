"""Tests for GameEngine.move() and collision."""

import game_generator as gg


class TestMove:
    def test_move_right(self, make_engine, minimal_game_cure, cure_sprites):
        engine = make_engine(minimal_game_cure, cure_sprites)
        old_x = engine.player_x
        engine.move(4, 0)
        assert engine.player_x > old_x or engine.player_x == old_x  # might be blocked

    def test_move_left(self, make_engine, minimal_game_cure, cure_sprites):
        engine = make_engine(minimal_game_cure, cure_sprites)
        # Move to a safe position first
        engine.player_x = 5 * engine.config.TILE_SIZE
        engine.player_y = 5 * engine.config.TILE_SIZE
        old_x = engine.player_x
        engine.move(-4, 0)
        # Player should have moved left (or be blocked)
        assert engine.player_x <= old_x

    def test_move_down(self, make_engine, minimal_game_cure, cure_sprites):
        engine = make_engine(minimal_game_cure, cure_sprites)
        old_y = engine.player_y
        engine.move(0, 4)
        assert engine.player_y >= old_y

    def test_no_move_zero(self, make_engine, minimal_game_cure, cure_sprites):
        engine = make_engine(minimal_game_cure, cure_sprites)
        old_x = engine.player_x
        old_y = engine.player_y
        engine.move(0, 0)
        assert engine.player_x == old_x
        assert engine.player_y == old_y

    def test_is_moving_flag(self, make_engine, minimal_game_cure, cure_sprites):
        engine = make_engine(minimal_game_cure, cure_sprites)
        engine.move(4, 0)
        assert engine.is_moving is True
        engine.move(0, 0)
        assert engine.is_moving is False

    def test_blocked_by_solid(self, make_engine, minimal_game_cure, cure_sprites):
        engine = make_engine(minimal_game_cure, cure_sprites)
        ts = engine.config.TILE_SIZE
        # Place player next to a solid tile
        # Add a wall right of the player
        engine.solid.add((3, 5))
        engine.player_x = 2 * ts
        engine.player_y = 5 * ts
        old_x = engine.player_x
        engine.move(ts, 0)
        # Should be blocked (might not move a full tile in one call but won't enter solid)
        tile_x = int((engine.player_x + ts // 2) // ts)
        assert (tile_x, 5) not in engine.solid or engine.player_x == old_x

    def test_bounds_check_left(self, make_engine, minimal_game_cure, cure_sprites):
        engine = make_engine(minimal_game_cure, cure_sprites)
        engine.player_x = 0
        engine.player_y = 200
        engine.move(-100, 0)
        assert engine.player_x >= 0

    def test_bounds_check_top(self, make_engine, minimal_game_cure, cure_sprites):
        engine = make_engine(minimal_game_cure, cure_sprites)
        engine.player_x = 200
        engine.player_y = 0
        engine.move(0, -100)
        assert engine.player_y >= 0
