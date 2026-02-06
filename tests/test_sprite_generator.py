"""Tests for SpriteGenerator (with mocked image generation)."""

from unittest.mock import patch, MagicMock
from PIL import Image
import game_generator as gg


def _fake_image(*args, **kwargs):
    return Image.new("RGBA", (64, 64), (128, 128, 128, 255))


class TestSpriteGeneratorGenerateAll:
    @patch.object(gg.OpenAIClient, "generate_image", side_effect=_fake_image)
    @patch("game_generator._load_baked_sprite", return_value=None)
    def test_cure_sprites(self, mock_baked, mock_img, minimal_game_cure):
        client = gg.OpenAIClient("sk-fake")
        client.last_image_was_fallback = False
        sg = gg.SpriteGenerator(client, delay=0)
        sprites = sg.generate_all(minimal_game_cure)
        assert "player" in sprites
        assert "npc" in sprites
        assert "npc_shop" in sprites
        assert "npc_inn" in sprites
        assert "npc_sick" in sprites or "npc" in sprites
        assert "mix_station" in sprites
        assert "npc_healed" in sprites

    @patch.object(gg.OpenAIClient, "generate_image", side_effect=_fake_image)
    @patch("game_generator._load_baked_sprite", return_value=None)
    def test_key_door_sprites(self, mock_baked, mock_img, minimal_game_key_door):
        client = gg.OpenAIClient("sk-fake")
        client.last_image_was_fallback = False
        sg = gg.SpriteGenerator(client, delay=0)
        sprites = sg.generate_all(minimal_game_key_door)
        assert "chest" in sprites
        assert "key" in sprites
        assert "door" in sprites

    @patch.object(gg.OpenAIClient, "generate_image", side_effect=_fake_image)
    @patch("game_generator._load_baked_sprite", return_value=None)
    def test_repair_bridge_sprites(self, mock_baked, mock_img, minimal_game_repair_bridge):
        client = gg.OpenAIClient("sk-fake")
        client.last_image_was_fallback = False
        sg = gg.SpriteGenerator(client, delay=0)
        sprites = sg.generate_all(minimal_game_repair_bridge)
        assert "mat_planks" in sprites
        assert "mat_rope" in sprites
        assert "mat_nails" in sprites

    @patch.object(gg.OpenAIClient, "generate_image", side_effect=_fake_image)
    @patch("game_generator._load_baked_sprite", return_value=None)
    def test_reuses_player_sprite(self, mock_baked, mock_img, minimal_game_cure):
        client = gg.OpenAIClient("sk-fake")
        client.last_image_was_fallback = False
        sg = gg.SpriteGenerator(client, delay=0)
        reuse = Image.new("RGBA", (64, 64), (0, 0, 255, 255))
        sprites = sg.generate_all(minimal_game_cure, reuse_player_sprite=reuse)
        assert sprites["player"] is reuse

    @patch.object(gg.OpenAIClient, "generate_image", side_effect=_fake_image)
    def test_baked_sprite_used(self, mock_img, minimal_game_key_door):
        baked = Image.new("RGBA", (64, 64), (255, 0, 0, 255))
        def mock_load(key):
            if key == "chest":
                return baked
            return None
        with patch("game_generator._load_baked_sprite", side_effect=mock_load):
            client = gg.OpenAIClient("sk-fake")
            client.last_image_was_fallback = False
            sg = gg.SpriteGenerator(client, delay=0)
            sprites = sg.generate_all(minimal_game_key_door)
            assert sprites["chest"] is baked
