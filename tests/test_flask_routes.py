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
