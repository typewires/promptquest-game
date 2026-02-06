"""Tests for InteriorRenderer."""

import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import game_generator as gg


class TestInteriorRendererInit:
    def test_shop_theme(self):
        ir = gg.InteriorRenderer(gg.Config(), theme="shop")
        assert ir.theme == "shop"

    def test_inn_theme(self):
        ir = gg.InteriorRenderer(gg.Config(), theme="inn")
        assert ir.theme == "inn"

    def test_default_door_x(self):
        c = gg.Config()
        ir = gg.InteriorRenderer(c, theme="shop")
        assert ir.door_x == c.MAP_WIDTH // 2

    def test_custom_door_x(self):
        ir = gg.InteriorRenderer(gg.Config(), theme="shop", door_x=5)
        assert ir.door_x == 5

    def test_theme_colors_differ(self):
        shop = gg.InteriorRenderer(gg.Config(), theme="shop")
        inn = gg.InteriorRenderer(gg.Config(), theme="inn")
        assert shop.floor != inn.floor or shop.wall != inn.wall


class TestInteriorSolidTiles:
    def test_walls_are_solid(self):
        c = gg.Config()
        ir = gg.InteriorRenderer(c, theme="shop")
        solid = ir.get_solid_tiles()
        # Top and bottom walls
        for x in range(c.MAP_WIDTH):
            assert (x, 0) in solid
        # Left and right walls
        for y in range(c.MAP_HEIGHT):
            assert (0, y) in solid
            assert (c.MAP_WIDTH - 1, y) in solid

    def test_doorway_carved(self):
        c = gg.Config()
        door_x = c.MAP_WIDTH // 2
        ir = gg.InteriorRenderer(c, theme="shop", door_x=door_x)
        solid = ir.get_solid_tiles()
        assert (door_x, c.MAP_HEIGHT - 1) not in solid

    def test_shop_counter_blocks(self):
        c = gg.Config()
        ir = gg.InteriorRenderer(c, theme="shop")
        solid = ir.get_solid_tiles()
        cx = c.MAP_WIDTH // 2
        assert (cx, 6) in solid or (cx - 1, 6) in solid

    def test_inn_beds_block(self):
        c = gg.Config()
        ir = gg.InteriorRenderer(c, theme="inn")
        solid = ir.get_solid_tiles()
        # Left bed area
        assert (2, 3) in solid or (3, 3) in solid
