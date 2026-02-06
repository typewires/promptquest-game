"""Tests for TerrainRenderer."""

import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import game_generator as gg


def _make_game(terrain_type="meadow", time_of_day="day", layout_style="winding_road",
               features=None, theme_tags=None, seed=42):
    return {
        "time_of_day": time_of_day,
        "seed": seed,
        "terrain": {
            "type": terrain_type,
            "features": features or ["path", "trees", "rocks", "water", "flowers"],
            "layout_style": layout_style,
            "theme_tags": theme_tags or [],
        },
    }


class TestTerrainPaletteSelection:
    def test_day_meadow(self):
        tr = gg.TerrainRenderer(_make_game("meadow", "day"), gg.Config())
        assert tr.palette == gg.TerrainRenderer.PALETTES["day_meadow"]

    def test_night_castle(self):
        tr = gg.TerrainRenderer(_make_game("castle", "night"), gg.Config())
        assert tr.palette == gg.TerrainRenderer.PALETTES["night_castle"]

    def test_day_beach(self):
        tr = gg.TerrainRenderer(_make_game("beach", "day"), gg.Config())
        assert tr.palette == gg.TerrainRenderer.PALETTES["day_beach"]

    def test_unknown_falls_back(self):
        tr = gg.TerrainRenderer(_make_game("swamp", "day"), gg.Config())
        # Should fall back to day_meadow
        assert tr.palette == gg.TerrainRenderer.PALETTES["day_meadow"]

    def test_sunset_fallback(self):
        tr = gg.TerrainRenderer(_make_game("meadow", "sunset"), gg.Config())
        assert tr.palette == gg.TerrainRenderer.PALETTES["sunset_meadow"]


class TestTerrainLayout:
    def test_path_tiles_exist(self):
        tr = gg.TerrainRenderer(_make_game(layout_style="winding_road"), gg.Config())
        assert len(tr.path_tiles) > 0

    def test_water_tiles_exist(self):
        tr = gg.TerrainRenderer(_make_game(layout_style="lake_center"), gg.Config())
        assert len(tr.water_tiles) > 0

    def test_crossroads_layout(self):
        tr = gg.TerrainRenderer(_make_game(layout_style="crossroads"), gg.Config())
        assert len(tr.path_tiles) > 0

    def test_ring_road_layout(self):
        tr = gg.TerrainRenderer(_make_game(layout_style="ring_road"), gg.Config())
        assert len(tr.path_tiles) > 0

    def test_plaza_layout(self):
        tr = gg.TerrainRenderer(_make_game(layout_style="plaza"), gg.Config())
        assert len(tr.path_tiles) > 0

    def test_coastline_layout(self):
        tr = gg.TerrainRenderer(_make_game(layout_style="coastline"), gg.Config())
        assert len(tr.water_tiles) > 0


class TestTerrainSolidTiles:
    def test_water_is_solid(self):
        tr = gg.TerrainRenderer(_make_game(layout_style="lake_center"), gg.Config())
        solid = tr.get_solid_tiles()
        # Water tiles should be in the solid set
        for wt in tr.water_tiles:
            assert wt in solid

    def test_trees_are_solid(self):
        tr = gg.TerrainRenderer(_make_game(features=["trees"]), gg.Config())
        solid = tr.get_solid_tiles()
        for t in tr.trees:
            assert t in solid


class TestTerrainSeedDeterminism:
    def test_same_seed_same_layout(self):
        g = _make_game(seed=12345)
        tr1 = gg.TerrainRenderer(g, gg.Config())
        path1 = frozenset(tr1.path_tiles)
        tr2 = gg.TerrainRenderer(_make_game(seed=12345), gg.Config())
        path2 = frozenset(tr2.path_tiles)
        assert path1 == path2

    def test_different_seed_different_layout(self):
        tr1 = gg.TerrainRenderer(_make_game(seed=111), gg.Config())
        tr2 = gg.TerrainRenderer(_make_game(seed=999), gg.Config())
        # Layouts should differ (very high probability)
        assert tr1.path_tiles != tr2.path_tiles or tr1.trees != tr2.trees


class TestTerrainThemeDecor:
    def test_desert_cacti(self):
        tr = gg.TerrainRenderer(_make_game("desert", theme_tags=["desert"]), gg.Config())
        assert len(tr.cacti) > 0

    def test_beach_shells(self):
        tr = gg.TerrainRenderer(_make_game("beach", theme_tags=["beach"]), gg.Config())
        assert len(tr.shells) > 0

    def test_snow_piles(self):
        tr = gg.TerrainRenderer(_make_game("snow", theme_tags=["snow"]), gg.Config())
        assert len(tr.snow_piles) > 0

    def test_town_crates(self):
        tr = gg.TerrainRenderer(_make_game("town", theme_tags=["town"]), gg.Config())
        assert len(tr.crates) > 0

    def test_ruins_statues(self):
        tr = gg.TerrainRenderer(_make_game("ruins", theme_tags=["ruins"]), gg.Config())
        assert len(tr.statues) > 0
