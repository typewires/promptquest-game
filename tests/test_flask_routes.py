"""Tests for Flask routes (GET / and POST /generate)."""

import json
from unittest.mock import patch, MagicMock
from PIL import Image
import game_generator as gg


class TestIndexRoute:
    def test_get_index(self, flask_client):
        resp = flask_client.get("/")
        assert resp.status_code == 200
        assert b"Game Generator" in resp.data


class TestGenerateRoute:
    @patch.object(gg.SpriteGenerator, "generate_all")
    @patch.object(gg.GameDesigner, "design_game")
    def test_generate_success(self, mock_design, mock_sprites, flask_client):
        mock_design.return_value = {
            "title": "Test",
            "story": "Story",
            "time_of_day": "day",
            "seed": 123,
            "player": {"name": "H", "sprite_desc": "h", "start_x": 5, "start_y": 5},
            "npc": {"name": "N", "sprite_desc": "n", "x": 8, "y": 8,
                    "dialogue_intro": "Hi", "dialogue_hint": "Go",
                    "dialogue_progress": "OK", "dialogue_complete": "Done"},
            "terrain": {"type": "meadow", "features": ["path"],
                        "layout_style": "winding_road", "theme_tags": []},
            "quest": {
                "type": "lost_item", "types": ["lost_item"],
                "goal": "Find it", "steps": ["A", "B", "C"],
                "items": [{"id": "lost_item", "name": "Locket", "sprite_desc": "l",
                           "x": 5, "y": 5, "kind": "lost_item"}],
                "lost_item": {"id": "lost_item", "name": "Locket", "sprite_desc": "l",
                              "x": 5, "y": 5, "kind": "lost_item"},
            },
        }
        mock_sprites.return_value = {
            "player": Image.new("RGBA", (64, 64), (0, 0, 255, 255)),
            "npc": Image.new("RGBA", (64, 64), (255, 0, 0, 255)),
            "npc_shop": Image.new("RGBA", (64, 64), (0, 255, 0, 255)),
            "npc_inn": Image.new("RGBA", (64, 64), (255, 255, 0, 255)),
            "item": Image.new("RGBA", (64, 64), (255, 0, 255, 255)),
            "item2": Image.new("RGBA", (64, 64), (255, 0, 255, 255)),
        }
        resp = flask_client.post("/generate", json={
            "apiKey": "sk-fake",
            "prompt": "a meadow",
            "levels": 1,
            "biomeByLevel": ["snow", "", ""],
            "quality": "low",
        })
        data = json.loads(resp.data)
        assert data["success"] is True
        called_prompt = mock_design.call_args[0][0]
        assert "Level 1 Biome: snow." in called_prompt

    def test_generate_missing_key(self, flask_client):
        resp = flask_client.post("/generate", json={
            "prompt": "test",
            "levels": 1,
        })
        data = json.loads(resp.data)
        # Should fail because apiKey is missing
        assert data["success"] is False or resp.status_code != 200

    @patch.object(gg.SpriteGenerator, "generate_all")
    @patch.object(gg.GameDesigner, "design_game")
    def test_level1_style_only_and_followup_randomizable(self, mock_design, mock_sprites, flask_client):
        mock_design.return_value = {
            "title": "Test",
            "story": "Story",
            "time_of_day": "day",
            "seed": 123,
            "player": {"name": "H", "sprite_desc": "h", "start_x": 5, "start_y": 5},
            "npc": {"name": "N", "sprite_desc": "n", "x": 8, "y": 8,
                    "dialogue_intro": "Hi", "dialogue_hint": "Go",
                    "dialogue_progress": "OK", "dialogue_complete": "Done"},
            "terrain": {"type": "meadow", "features": ["path"], "layout_style": "winding_road", "theme_tags": []},
            "quest": {"type": "lost_item", "types": ["lost_item"], "goal": "Find it", "steps": ["A"], "items": []},
        }
        mock_sprites.return_value = {
            "player": Image.new("RGBA", (64, 64), (0, 0, 255, 255)),
            "npc": Image.new("RGBA", (64, 64), (255, 0, 0, 255)),
            "npc_shop": Image.new("RGBA", (64, 64), (0, 255, 0, 255)),
            "npc_inn": Image.new("RGBA", (64, 64), (255, 255, 0, 255)),
            "item": Image.new("RGBA", (64, 64), (255, 0, 255, 255)),
            "item2": Image.new("RGBA", (64, 64), (255, 0, 255, 255)),
        }
        prompt = (
            "A lantern-lit fantasy world.\n"
            "Time: night\n"
            "Level 1 Biome: snow\n"
            "Level 2 Biome: ruins\n"
            "Level 3 Biome: beach\n"
            "Level 1 NPC looks like: sick princess. goal is cure\n"
            "Level 2 NPC looks like: archivist. goal is lost_item\n"
            "Level 3 NPC looks like: captain. goal is key_and_door\n"
            "Hero look: red scarf alchemist.\n"
            "NPC look: pale gown princess.\n"
        )
        resp = flask_client.post("/generate", json={
            "apiKey": "sk-fake",
            "prompt": prompt,
            "levels": 3,
            "quality": "low",
        })
        data = json.loads(resp.data)
        assert data["success"] is True
        assert mock_design.call_count == 3
        p1 = mock_design.call_args_list[0][0][0]
        p2 = mock_design.call_args_list[1][0][0]
        p3 = mock_design.call_args_list[2][0][0]
        assert "Hero look:" in p1
        assert "NPC look:" in p1
        assert "Hero look:" not in p2
        assert "NPC look:" not in p2
        assert "Level 2 Biome: ruins." in p2
        assert "Level 2 Time:" in p2
        assert "Level 3 Biome: beach." in p3
        assert "Level 3 Time:" in p3
