"""Tests for OpenAIClient (with mocked HTTP requests)."""

import json
import base64
from io import BytesIO
from unittest.mock import patch, MagicMock
from PIL import Image
import game_generator as gg


def _make_client():
    return gg.OpenAIClient("sk-fake-key-000000")


def _fake_text_response(content: str):
    """Build a fake requests.Response for text generation."""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "choices": [{"message": {"content": content}}]
    }
    resp.raise_for_status = MagicMock()
    return resp


def _fake_image_response():
    """Build a fake requests.Response for image generation with a base64 PNG."""
    img = Image.new("RGBA", (1024, 1024), (0, 255, 0, 255))
    buf = BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "data": [{"b64_json": b64}]
    }
    resp.raise_for_status = MagicMock()
    return resp


class TestOpenAIClientInit:
    def test_stores_api_key(self):
        c = _make_client()
        assert c.api_key == "sk-fake-key-000000"

    def test_headers_contain_bearer(self):
        c = _make_client()
        assert "Bearer sk-fake-key-000000" in c.headers["Authorization"]

    def test_fallback_flags_default(self):
        c = _make_client()
        assert c.last_image_was_fallback is False
        assert c.last_image_error is None


class TestGenerateText:
    @patch("requests.post")
    def test_returns_content(self, mock_post):
        mock_post.return_value = _fake_text_response('{"title": "Test"}')
        c = _make_client()
        result = c.generate_text("create a game")
        assert result == '{"title": "Test"}'

    @patch("requests.post")
    def test_calls_openai_endpoint(self, mock_post):
        mock_post.return_value = _fake_text_response("{}")
        c = _make_client()
        c.generate_text("test prompt")
        args, kwargs = mock_post.call_args
        assert "chat/completions" in args[0]


class TestGenerateImage:
    @patch("requests.post")
    def test_returns_pil_image(self, mock_post):
        mock_post.return_value = _fake_image_response()
        c = _make_client()
        result = c.generate_image("a hero", role="player")
        assert isinstance(result, Image.Image)

    @patch("requests.post")
    def test_image_is_rgba(self, mock_post):
        mock_post.return_value = _fake_image_response()
        c = _make_client()
        result = c.generate_image("a hero", role="player")
        assert result.mode == "RGBA"

    @patch("requests.post")
    def test_fallback_on_error(self, mock_post):
        import requests as req
        error_resp = MagicMock()
        error_resp.status_code = 400
        error_resp.text = "Bad request"
        mock_post.return_value.raise_for_status.side_effect = req.exceptions.HTTPError(response=error_resp)
        c = _make_client()
        result = c.generate_image("a hero", role="player")
        # Should return placeholder
        assert isinstance(result, Image.Image)
        assert c.last_image_was_fallback is True
