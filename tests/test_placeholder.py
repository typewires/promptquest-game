"""Tests for _placeholder sprite generation."""

from PIL import Image
import game_generator as gg


def _make_client():
    return gg.OpenAIClient("sk-fake-key")


class TestPlaceholder:
    def test_returns_rgba_image(self):
        client = _make_client()
        img = client._placeholder("a hero", role="player")
        assert isinstance(img, Image.Image)
        assert img.mode == "RGBA"

    def test_size_is_64x64(self):
        client = _make_client()
        img = client._placeholder("a hero", role="player")
        assert img.size == (64, 64)

    def test_has_non_transparent_pixels(self):
        client = _make_client()
        img = client._placeholder("a hero", role="player")
        px = img.load()
        count = sum(1 for y in range(64) for x in range(64) if px[x, y][3] > 0)
        assert count > 0

    def test_key_placeholder(self):
        client = _make_client()
        img = client._placeholder("brass key", role="key")
        assert img.size == (64, 64)
        px = img.load()
        count = sum(1 for y in range(64) for x in range(64) if px[x, y][3] > 0)
        assert count > 0

    def test_chest_placeholder(self):
        client = _make_client()
        img = client._placeholder("wooden chest", role="chest")
        assert img.size == (64, 64)

    def test_door_placeholder(self):
        client = _make_client()
        img = client._placeholder("stone door", role="door")
        assert img.size == (64, 64)

    def test_cauldron_placeholder(self):
        client = _make_client()
        img = client._placeholder("iron cauldron", role="cauldron")
        assert img.size == (64, 64)

    def test_npc_placeholder(self):
        client = _make_client()
        img = client._placeholder("wise sage", role="npc")
        assert img.size == (64, 64)

    def test_wizard_placeholder(self):
        client = _make_client()
        img = client._placeholder("wizard in a robe", role="player")
        assert img.size == (64, 64)

    def test_princess_placeholder(self):
        client = _make_client()
        img = client._placeholder("princess in a dress", role="npc")
        assert img.size == (64, 64)

    def test_king_placeholder(self):
        client = _make_client()
        img = client._placeholder("a king with crown", role="npc")
        assert img.size == (64, 64)
