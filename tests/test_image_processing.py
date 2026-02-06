"""Tests for OpenAIClient image processing methods (no API calls)."""

from PIL import Image
import game_generator as gg


def _make_client():
    return gg.OpenAIClient("sk-fake-key")


# ── _remove_green_bg ─────────────────────────────────────────

class TestRemoveGreenBg:
    def test_pure_green_becomes_transparent(self):
        client = _make_client()
        img = Image.new("RGBA", (4, 4), (0, 255, 0, 255))
        result = client._remove_green_bg(img)
        # All pixels should be transparent
        for y in range(4):
            for x in range(4):
                assert result.getpixel((x, y))[3] == 0

    def test_non_green_preserved(self):
        client = _make_client()
        img = Image.new("RGBA", (4, 4), (200, 50, 50, 255))
        result = client._remove_green_bg(img)
        # Red pixels should remain opaque
        for y in range(4):
            for x in range(4):
                assert result.getpixel((x, y))[3] == 255

    def test_near_white_removed(self):
        client = _make_client()
        img = Image.new("RGBA", (4, 4), (245, 245, 245, 255))
        result = client._remove_green_bg(img)
        for y in range(4):
            for x in range(4):
                assert result.getpixel((x, y))[3] == 0

    def test_mixed_image(self):
        client = _make_client()
        img = Image.new("RGBA", (2, 2), (0, 0, 0, 0))
        px = img.load()
        px[0, 0] = (0, 255, 0, 255)   # green → transparent
        px[1, 0] = (200, 50, 50, 255)  # red → keep
        px[0, 1] = (50, 50, 200, 255)  # blue → keep
        px[1, 1] = (250, 250, 250, 255)  # near-white → transparent
        result = client._remove_green_bg(img)
        assert result.getpixel((0, 0))[3] == 0    # green removed
        assert result.getpixel((1, 0))[3] == 255   # red kept
        assert result.getpixel((0, 1))[3] == 255   # blue kept
        assert result.getpixel((1, 1))[3] == 0    # near-white removed


# ── _fit_to_square ───────────────────────────────────────────

class TestFitToSquare:
    def test_output_is_square(self):
        client = _make_client()
        img = Image.new("RGBA", (64, 32), (255, 0, 0, 255))
        result = client._fit_to_square(img, size=128)
        assert result.size == (128, 128)

    def test_transparent_image_returns_original(self):
        client = _make_client()
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        result = client._fit_to_square(img, size=128)
        # When all pixels are transparent, the function returns the original unchanged
        assert result.size == (64, 64)

    def test_content_preserved(self):
        client = _make_client()
        img = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
        px = img.load()
        for y in range(10, 20):
            for x in range(10, 20):
                px[x, y] = (255, 0, 0, 255)
        result = client._fit_to_square(img, size=64)
        # Result should have some non-transparent pixels
        count = sum(1 for y in range(64) for x in range(64) if result.getpixel((x, y))[3] > 0)
        assert count > 0


# ── _crop_to_largest_component ───────────────────────────────

class TestCropToLargestComponent:
    def test_single_component(self):
        client = _make_client()
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        px = img.load()
        for y in range(20, 40):
            for x in range(20, 40):
                px[x, y] = (255, 0, 0, 255)
        result = client._crop_to_largest_component(img)
        assert result.size[0] <= 64
        assert result.size[1] <= 64

    def test_empty_image_unchanged(self):
        client = _make_client()
        img = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
        result = client._crop_to_largest_component(img)
        assert result.size == (32, 32)


# ── _component_areas ─────────────────────────────────────────

class TestComponentAreas:
    def test_single_block(self):
        client = _make_client()
        img = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
        px = img.load()
        for y in range(5, 10):
            for x in range(5, 10):
                px[x, y] = (255, 0, 0, 255)
        areas = client._component_areas(img)
        assert len(areas) == 1
        assert areas[0] == 25  # 5x5

    def test_two_separate_blocks(self):
        client = _make_client()
        img = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
        px = img.load()
        # Block 1: 4x4 = 16 pixels
        for y in range(0, 4):
            for x in range(0, 4):
                px[x, y] = (255, 0, 0, 255)
        # Block 2: 2x2 = 4 pixels (separated)
        for y in range(20, 22):
            for x in range(20, 22):
                px[x, y] = (0, 0, 255, 255)
        areas = client._component_areas(img)
        assert len(areas) == 2
        assert areas[0] == 16  # largest first
        assert areas[1] == 4

    def test_empty_image(self):
        client = _make_client()
        img = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
        areas = client._component_areas(img)
        assert areas == []


# ── _nontransparent_pixels ───────────────────────────────────

class TestNontransparentPixels:
    def test_fully_opaque(self):
        client = _make_client()
        img = Image.new("RGBA", (10, 10), (255, 0, 0, 255))
        assert client._nontransparent_pixels(img) == 100

    def test_fully_transparent(self):
        client = _make_client()
        img = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
        assert client._nontransparent_pixels(img) == 0

    def test_partial(self):
        client = _make_client()
        img = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
        px = img.load()
        for x in range(5):
            px[x, 0] = (255, 0, 0, 255)
        assert client._nontransparent_pixels(img) == 5


# ── _extract_largest_sprite ──────────────────────────────────

class TestExtractLargestSprite:
    def test_square_image_unchanged(self):
        client = _make_client()
        img = Image.new("RGBA", (64, 64), (255, 0, 0, 255))
        result = client._extract_largest_sprite(img)
        # Square image should not be split
        assert result.size[0] <= 64

    def test_empty_image_unchanged(self):
        client = _make_client()
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        result = client._extract_largest_sprite(img)
        assert result.size == (64, 64)
