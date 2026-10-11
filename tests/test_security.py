"""Tests for secret redaction (utils/security.py)."""

import pytest

from utils.security import scrub_secrets


class TestScrubSecrets:
    def test_redacts_sk_style_key(self):
        text = "Authorization failed for sk-abc123DEF456ghi789"
        assert "sk-abc123DEF456ghi789" not in scrub_secrets(text)
        assert "***" in scrub_secrets(text)

    def test_redacts_bearer_token(self):
        text = "headers={'Authorization': 'Bearer eyJhbGciOiJIUzI1NiJ9.abc123'}"
        out = scrub_secrets(text)
        assert "eyJhbGciOiJIUzI1NiJ9.abc123" not in out

    def test_redacts_explicit_extra_secret(self):
        text = "key=my-custom-format-key-999 used in request"
        out = scrub_secrets(text, "my-custom-format-key-999")
        assert "my-custom-format-key-999" not in out
        assert "***" in out

    def test_short_extra_secret_ignored(self):
        # Tiny strings are not treated as secrets (avoids nuking normal text).
        assert scrub_secrets("abc", "abc") == "abc"

    def test_none_becomes_empty_string(self):
        assert scrub_secrets(None) == ""

    def test_non_string_is_coerced(self):
        assert scrub_secrets(12345) == "12345"

    def test_plain_text_untouched(self):
        text = "created directory src/components successfully"
        assert scrub_secrets(text) == text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
