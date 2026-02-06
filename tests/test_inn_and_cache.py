import os

import pytest
from PIL import Image

import game_generator as gg


def _img(color=(255, 0, 0, 255), size=(64, 64)):
    return Image.new("RGBA", size, color)


def test_inn_lobby_and_room_have_distinct_collision_layouts():
    cfg = gg.Config
    lobby = gg.InteriorRenderer(cfg, theme="inn_lobby", door_x=cfg.MAP_WIDTH // 2)
    room = gg.InteriorRenderer(cfg, theme="inn_room", door_x=cfg.MAP_WIDTH // 2)

    lobby_solid = lobby.get_solid_tiles()
    room_solid = room.get_solid_tiles()

    # Lobby has reception blockers near y=3 and table blockers in lounge.
    assert (5, 3) in lobby_solid
    assert (10, 3) in lobby_solid
    assert (2, 8) in lobby_solid
    # Room has bed footprint blockers.
    assert (4, 4) in room_solid
    assert (8, 6) in room_solid
    # Main bottom doorway should remain passable for exit in both.
    assert (cfg.MAP_WIDTH // 2, cfg.MAP_HEIGHT - 1) not in lobby_solid
    assert (cfg.MAP_WIDTH // 2, cfg.MAP_HEIGHT - 1) not in room_solid


def test_cleanup_sprite_rgba_removes_green_background_and_halo():
    # Build a tiny sprite with pure green matte + semitransparent green halo.
    img = Image.new("RGBA", (4, 4), (0, 255, 0, 255))
    px = img.load()
    px[1, 1] = (120, 80, 70, 255)  # character pixel
    px[2, 2] = (40, 200, 40, 180)  # halo-like green spill

    out = gg.GameEngine._cleanup_sprite_rgba(img)
    out_px = out.load()

    assert out_px[0, 0][3] == 0  # removed green matte
    assert out_px[1, 1][3] > 0   # character retained
    assert out_px[2, 2][3] < 180  # halo alpha reduced


def test_sprite_generator_reuses_shop_and_inn_npcs(monkeypatch):
    # Keep this test deterministic and fast.
    old_item_budget = gg.Config.ITEM_SPRITES_PER_LEVEL
    gg.Config.ITEM_SPRITES_PER_LEVEL = 0

    reuse_shop = _img((10, 20, 30, 255))
    reuse_inn = _img((40, 50, 60, 255))
    player = _img((70, 80, 90, 255))

    def fake_baked(key):
        if key == "item_generic":
            return _img((200, 200, 200, 255))
        return None

    monkeypatch.setattr(gg, "_load_baked_sprite", fake_baked)

    calls = {"count": 0}

    def fake_gen(self, desc, role, theme):
        calls["count"] += 1
        return _img((120, 120, 180, 255))

    monkeypatch.setattr(gg.SpriteGenerator, "_gen", fake_gen, raising=True)

    game = {
        "player": {"sprite_desc": "hero"},
        "npc": {"sprite_desc": "npc"},
        "quest": {"type": "lost_item", "items": []},
        "terrain": {"type": "meadow"},
        "time_of_day": "day",
        "story": "demo",
        "_reuse_sprites": {"npc_shop": reuse_shop, "npc_inn": reuse_inn},
    }

    sg = gg.SpriteGenerator(client=None, delay=0)
    sprites = sg.generate_all(game, reuse_player_sprite=player)

    assert sprites["npc_shop"] is reuse_shop
    assert sprites["npc_inn"] is reuse_inn
    # We still generate at least the main outdoor NPC.
    assert calls["count"] >= 1

    gg.Config.ITEM_SPRITES_PER_LEVEL = old_item_budget
