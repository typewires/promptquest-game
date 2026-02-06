"""Shared fixtures for the PromptQuest test suite.

Sets up headless pygame, provides reusable game dicts and sprite dicts,
and factory fixtures for GameEngine instantiation.
"""

import os
import sys
import json

# CRITICAL: Set SDL dummy driver BEFORE any pygame.init() call.
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pytest
from unittest.mock import patch, MagicMock
from PIL import Image

# On some Python/pygame combos (e.g. Python 3.14 + pygame 2.6),
# pygame.font is a MissingModule.  Provide a lightweight stub so
# GameEngine.__init__ can create fonts without a real display.
import pygame as _pg
import types as _types
try:
    _pg.font.Font(None, 12)
except Exception:
    _font_mod = _types.ModuleType("pygame.font")

    class _StubFont:
        def __init__(self, *a, **kw):
            pass
        def render(self, text, antialias, color, *a, **kw):
            s = _pg.Surface((max(1, len(str(text)) * 8), 20))
            s.fill((0, 0, 0))
            return s
        def size(self, text):
            return (max(1, len(str(text)) * 8), 20)

    _font_mod.Font = _StubFont
    _font_mod.SysFont = lambda *a, **kw: _StubFont()
    _font_mod.init = lambda: None
    _pg.font = _font_mod
    sys.modules["pygame.font"] = _font_mod

# Add project root to path so `import game_generator` works.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import game_generator as gg


# ============================================================
# GAME DICT FIXTURES
# ============================================================

@pytest.fixture
def minimal_game_cure():
    """Minimal valid game dict for a cure quest."""
    return {
        "title": "Test Cure", "story": "Test story", "time_of_day": "day",
        "seed": 12345,
        "player": {"name": "Hero", "sprite_desc": "hero", "start_x": 5, "start_y": 5},
        "npc": {"name": "NPC", "sprite_desc": "npc", "x": 8, "y": 8,
                "dialogue_intro": "Hi", "dialogue_hint": "Do stuff",
                "dialogue_progress": "Good", "dialogue_complete": "Done"},
        "terrain": {"type": "meadow", "features": ["path", "trees"],
                    "layout_style": "winding_road", "theme_tags": []},
        "quest": {
            "type": "cure", "types": ["cure"],
            "goal": "Heal the patient with a remedy",
            "steps": ["Talk", "Gather", "Brew", "Deliver"],
            "items": [
                {"id": "ingredient1", "name": "Herb", "sprite_desc": "herb",
                 "x": 10, "y": 3, "kind": "ingredient"},
                {"id": "ingredient2", "name": "Leaf", "sprite_desc": "leaf",
                 "x": 12, "y": 6, "kind": "ingredient"},
                {"id": "ingredient3", "name": "Dew", "sprite_desc": "dew",
                 "x": 7, "y": 9, "kind": "ingredient"},
            ],
            "cure_items": [
                {"id": "ingredient1", "name": "Herb", "sprite_desc": "herb",
                 "x": 10, "y": 3, "kind": "ingredient"},
                {"id": "ingredient2", "name": "Leaf", "sprite_desc": "leaf",
                 "x": 12, "y": 6, "kind": "ingredient"},
                {"id": "ingredient3", "name": "Dew", "sprite_desc": "dew",
                 "x": 7, "y": 9, "kind": "ingredient"},
            ],
            "mix_station": {"name": "Cauldron", "sprite_desc": "cauldron",
                            "x": 9, "y": 5},
            "npc_healed_sprite_desc": "healthy NPC",
        },
    }


@pytest.fixture
def minimal_game_key_door():
    """Minimal valid game dict for a key_and_door quest."""
    return {
        "title": "Test Key", "story": "Test story", "time_of_day": "day",
        "seed": 12345,
        "player": {"name": "Hero", "sprite_desc": "hero", "start_x": 5, "start_y": 5},
        "npc": {"name": "NPC", "sprite_desc": "npc", "x": 8, "y": 8,
                "dialogue_intro": "Hi", "dialogue_hint": "Find the key",
                "dialogue_progress": "Keep going", "dialogue_complete": "Done"},
        "terrain": {"type": "meadow", "features": ["path", "trees"],
                    "layout_style": "winding_road", "theme_tags": []},
        "quest": {
            "type": "key_and_door", "types": ["key_and_door"],
            "goal": "Unlock the sealed door",
            "steps": ["Open chest", "Get key", "Open door"],
            "items": [],
            "chest": {"name": "Old Chest", "sprite_desc": "chest", "x": 12, "y": 4},
            "key": {"name": "Old Key", "sprite_desc": "key"},
            "door": {"name": "Locked Door", "sprite_desc": "door", "x": 14, "y": 6},
        },
    }


@pytest.fixture
def minimal_game_lost_item():
    """Minimal valid game dict for a lost_item quest."""
    return {
        "title": "Test Lost", "story": "Test story", "time_of_day": "day",
        "seed": 12345,
        "player": {"name": "Hero", "sprite_desc": "hero", "start_x": 5, "start_y": 5},
        "npc": {"name": "NPC", "sprite_desc": "npc", "x": 8, "y": 8,
                "dialogue_intro": "Hi", "dialogue_hint": "Find it",
                "dialogue_progress": "Good", "dialogue_complete": "Done"},
        "terrain": {"type": "meadow", "features": ["path", "trees"],
                    "layout_style": "winding_road", "theme_tags": []},
        "quest": {
            "type": "lost_item", "types": ["lost_item"],
            "goal": "Find and return the lost item",
            "steps": ["Search", "Find", "Return"],
            "items": [{"id": "lost_item", "name": "Locket", "sprite_desc": "locket",
                        "x": 10, "y": 10, "kind": "lost_item"}],
            "lost_item": {"id": "lost_item", "name": "Locket", "sprite_desc": "locket",
                          "x": 10, "y": 10, "kind": "lost_item"},
        },
    }


@pytest.fixture
def minimal_game_repair_bridge():
    """Minimal valid game dict for a repair_bridge quest."""
    return {
        "title": "Test Bridge", "story": "Test story", "time_of_day": "day",
        "seed": 12345,
        "player": {"name": "Hero", "sprite_desc": "hero", "start_x": 2, "start_y": 2},
        "npc": {"name": "NPC", "sprite_desc": "npc", "x": 4, "y": 4,
                "dialogue_intro": "Hi", "dialogue_hint": "Fix bridge",
                "dialogue_progress": "Good", "dialogue_complete": "Done"},
        "terrain": {"type": "meadow", "features": ["path", "trees"],
                    "layout_style": "winding_road", "theme_tags": []},
        "quest": {
            "type": "repair_bridge", "types": ["repair_bridge"],
            "goal": "Repair the broken bridge",
            "steps": ["Visit shop", "Buy materials", "Fix bridge"],
            "items": [],
            "repair_materials": [
                {"id": "planks", "name": "Planks", "sprite_desc": "planks"},
                {"id": "rope", "name": "Rope", "sprite_desc": "rope"},
                {"id": "nails", "name": "Nails", "sprite_desc": "nails"},
            ],
        },
    }


@pytest.fixture
def minimal_game_stacked():
    """Game dict with stacked goals (cure + lost_item)."""
    return {
        "title": "Test Stacked", "story": "Test", "time_of_day": "day",
        "seed": 99999,
        "player": {"name": "Hero", "sprite_desc": "hero", "start_x": 5, "start_y": 5},
        "npc": {"name": "Elder", "sprite_desc": "npc", "x": 8, "y": 8,
                "dialogue_intro": "Hi", "dialogue_hint": "Do both",
                "dialogue_progress": "Keep going", "dialogue_complete": "All done"},
        "terrain": {"type": "meadow", "features": ["path", "trees"],
                    "layout_style": "winding_road", "theme_tags": []},
        "quest": {
            "type": "cure", "types": ["cure", "lost_item"],
            "goal": "Heal and find item",
            "steps": ["Talk", "Gather", "Brew", "Deliver", "Find lost item", "Return it"],
            "items": [
                {"id": "ingredient1", "name": "Herb", "sprite_desc": "herb",
                 "x": 10, "y": 3, "kind": "ingredient"},
                {"id": "ingredient2", "name": "Leaf", "sprite_desc": "leaf",
                 "x": 12, "y": 6, "kind": "ingredient"},
                {"id": "ingredient3", "name": "Dew", "sprite_desc": "dew",
                 "x": 7, "y": 9, "kind": "ingredient"},
                {"id": "lost_item", "name": "Locket", "sprite_desc": "locket",
                 "x": 10, "y": 10, "kind": "lost_item"},
            ],
            "cure_items": [
                {"id": "ingredient1", "name": "Herb", "sprite_desc": "herb",
                 "x": 10, "y": 3, "kind": "ingredient"},
                {"id": "ingredient2", "name": "Leaf", "sprite_desc": "leaf",
                 "x": 12, "y": 6, "kind": "ingredient"},
                {"id": "ingredient3", "name": "Dew", "sprite_desc": "dew",
                 "x": 7, "y": 9, "kind": "ingredient"},
            ],
            "lost_item": {"id": "lost_item", "name": "Locket", "sprite_desc": "locket",
                          "x": 10, "y": 10, "kind": "lost_item"},
            "mix_station": {"name": "Cauldron", "sprite_desc": "cauldron",
                            "x": 9, "y": 5},
            "npc_healed_sprite_desc": "healthy NPC",
        },
    }


# ============================================================
# SPRITE FIXTURES
# ============================================================

def _make_sprite(color=(128, 128, 128, 255)):
    return Image.new("RGBA", (64, 64), color)


@pytest.fixture
def minimal_sprites():
    """Minimal PIL Image sprites dict for any quest type."""
    return {
        "player": _make_sprite((0, 0, 255, 255)),
        "npc": _make_sprite((255, 0, 0, 255)),
        "npc_shop": _make_sprite((0, 255, 0, 255)),
        "npc_inn": _make_sprite((255, 255, 0, 255)),
        "item": _make_sprite((255, 0, 255, 255)),
        "item2": _make_sprite((255, 0, 255, 255)),
    }


@pytest.fixture
def cure_sprites(minimal_sprites):
    s = dict(minimal_sprites)
    s["npc_sick"] = _make_sprite((200, 200, 200, 255))
    s["npc_healed"] = _make_sprite((100, 255, 100, 255))
    s["mix_station"] = _make_sprite((0, 200, 0, 255))
    return s


@pytest.fixture
def key_door_sprites(minimal_sprites):
    s = dict(minimal_sprites)
    s["chest"] = _make_sprite((139, 69, 19, 255))
    s["key"] = _make_sprite((255, 215, 0, 255))
    s["door"] = _make_sprite((101, 67, 33, 255))
    return s


@pytest.fixture
def repair_bridge_sprites(minimal_sprites):
    s = dict(minimal_sprites)
    s["mat_planks"] = _make_sprite((150, 100, 50, 255))
    s["mat_rope"] = _make_sprite((200, 180, 140, 255))
    s["mat_nails"] = _make_sprite((100, 100, 100, 255))
    return s


# ============================================================
# GAME ENGINE FACTORY
# ============================================================

@pytest.fixture
def make_engine():
    """Factory: make_engine(game_dict, sprites_dict) -> GameEngine (headless)."""
    import pygame
    engines = []

    def _factory(game, sprites):
        levels = [{"game": game, "sprites": sprites}]
        config = gg.Config()
        engine = gg.GameEngine(levels, config)
        engines.append(engine)
        return engine

    yield _factory
    pygame.quit()


# ============================================================
# MOCK OPENAI CLIENT / GAME DESIGNER
# ============================================================

@pytest.fixture
def mock_openai_client():
    return gg.OpenAIClient("sk-fake-test-key-000000")


@pytest.fixture
def mock_game_designer(mock_openai_client):
    return gg.GameDesigner(mock_openai_client)


# ============================================================
# FLASK TEST CLIENT
# ============================================================

@pytest.fixture
def flask_client():
    gg.app.config["TESTING"] = True
    with gg.app.test_client() as client:
        yield client


# ============================================================
# TEMP BAKED SPRITES DIR
# ============================================================

@pytest.fixture
def baked_sprites_dir(tmp_path):
    """Temp assets/sprites/ with manifest + PNGs. Patches module paths."""
    manifest = {"chest": "chest.png", "key": "key.png"}
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest))

    _make_sprite((139, 69, 19, 255)).save(str(tmp_path / "chest.png"))
    _make_sprite((255, 215, 0, 255)).save(str(tmp_path / "key.png"))

    with patch.object(gg, "BAKED_SPRITES_DIR", str(tmp_path)), \
         patch.object(gg, "BAKED_MANIFEST_PATH", str(manifest_path)):
        yield tmp_path
