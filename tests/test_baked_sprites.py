"""Tests for baked sprite loading."""

import json
from PIL import Image
import game_generator as gg


class TestLoadBakedManifest:
    def test_loads_manifest(self, baked_sprites_dir):
        manifest = gg._load_baked_manifest()
        assert isinstance(manifest, dict)
        assert "chest" in manifest
        assert "key" in manifest

    def test_missing_manifest_returns_empty(self, tmp_path):
        from unittest.mock import patch
        with patch.object(gg, "BAKED_MANIFEST_PATH", str(tmp_path / "nonexistent.json")):
            result = gg._load_baked_manifest()
            assert result == {}


class TestLoadBakedSprite:
    def test_loads_existing_sprite(self, baked_sprites_dir):
        img = gg._load_baked_sprite("chest")
        assert isinstance(img, Image.Image)
        assert img.mode == "RGBA"

    def test_missing_sprite_returns_none(self, baked_sprites_dir):
        result = gg._load_baked_sprite("nonexistent_sprite")
        assert result is None

    def test_loads_key_sprite(self, baked_sprites_dir):
        img = gg._load_baked_sprite("key")
        assert isinstance(img, Image.Image)
