"""Tests for DeepSeekClient response mapping and retry logic (no network)."""

import time
import pytest
from types import SimpleNamespace

import openai
import httpx2

from api.deepseek_client import DeepSeekClient, _is_socks_proxy_configured


class FakeMessage:
    def __init__(self, role="assistant", content=None, tool_calls=None):
        self.role = role
        self.content = content
        self.tool_calls = tool_calls


def make_client(message=None, create=None):
    """DeepSeekClient wired to a fake OpenAI-compatible transport."""
    client = DeepSeekClient.__new__(DeepSeekClient)
    client.api_key = "sk-test"
    client.model = "deepseek-chat"

    if create is None:
        resp = SimpleNamespace(choices=[SimpleNamespace(message=message)])
        create = lambda **kwargs: resp

    client.client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )
    return client


class TestChatResponseMapping:
    def test_no_tool_calls_key_when_absent(self):
        """Regression: the result must not carry a tool_calls key at all when
        the model made no tool calls (null leaked to the API before)."""
        client = make_client(FakeMessage(content="hello"))
        result = client.chat(messages=[{"role": "user", "content": "hi"}])
        assert result["role"] == "assistant"
        assert result["content"] == "hello"
        assert "tool_calls" not in result

    def test_none_content_becomes_empty_string(self):
        client = make_client(FakeMessage(content=None))
        result = client.chat(messages=[])
        assert result["content"] == ""

    def test_tool_calls_are_mapped(self):
        tc = SimpleNamespace(
            id="call_42",
            type="function",
            function=SimpleNamespace(name="create_file", arguments='{"path":"a.py"}'),
        )
        client = make_client(FakeMessage(content="", tool_calls=[tc]))
        result = client.chat(messages=[])
        assert result["tool_calls"] == [{
            "id": "call_42",
            "type": "function",
            "function": {"name": "create_file", "arguments": '{"path":"a.py"}'},
        }]

    def test_tools_and_temperature_forwarded(self):
        captured = {}

        def create(**kwargs):
            captured.update(kwargs)
            return SimpleNamespace(choices=[SimpleNamespace(message=FakeMessage(content="ok"))])

        client = make_client(create=create)
        tools = [{"type": "function", "function": {"name": "t"}}]
        client.chat(messages=[{"role": "user", "content": "x"}], tools=tools, temperature=0.5)
        assert captured["model"] == "deepseek-chat"
        assert captured["tools"] is tools
        assert captured["temperature"] == 0.5
        assert "stream" not in captured

    def test_tools_omitted_when_none(self):
        captured = {}

        def create(**kwargs):
            captured.update(kwargs)
            return SimpleNamespace(choices=[SimpleNamespace(message=FakeMessage(content="ok"))])

        client = make_client(create=create)
        client.chat(messages=[])
        assert "tools" not in captured


class TestRetryWithBackoff:
    def test_success_first_try(self):
        client = make_client()
        assert client._retry_with_backoff(lambda: "result") == "result"

    def test_retryable_error_then_success(self, monkeypatch):
        monkeypatch.setattr(time, "sleep", lambda s: None)
        attempts = {"n": 0}

        def flaky():
            attempts["n"] += 1
            if attempts["n"] < 3:
                raise openai.APIConnectionError(request=httpx2.Request("GET", "http://x"))
            return "recovered"

        client = make_client()
        assert client._retry_with_backoff(flaky) == "recovered"
        assert attempts["n"] == 3

    def test_retryable_error_exhausts_and_raises(self, monkeypatch):
        monkeypatch.setattr(time, "sleep", lambda s: None)
        attempts = {"n": 0}

        def always_fails():
            attempts["n"] += 1
            raise openai.APIConnectionError(request=httpx2.Request("GET", "http://x"))

        client = make_client()
        with pytest.raises(openai.APIConnectionError):
            client._retry_with_backoff(always_fails)
        assert attempts["n"] == 4  # 1 initial + 3 retries

    def test_unexpected_error_raises_immediately(self, monkeypatch):
        monkeypatch.setattr(time, "sleep", lambda s: None)
        attempts = {"n": 0}

        def fails():
            attempts["n"] += 1
            raise ValueError("not retryable")

        client = make_client()
        with pytest.raises(ValueError):
            client._retry_with_backoff(fails)
        assert attempts["n"] == 1


class TestTestKey:
    def test_valid_key_returns_true(self):
        client = make_client(create=lambda **kw: SimpleNamespace(choices=[]))
        ok, msg = client.test_key()
        assert ok is True

    def test_auth_error_returns_false_without_leaking(self):
        def create(**kwargs):
            resp = httpx2.Response(401, request=httpx2.Request("POST", "http://x"))
            raise openai.AuthenticationError(
                "bad key sk-secret123456789", response=resp, body=None
            )

        client = make_client(create=create)
        ok, msg = client.test_key()
        assert ok is False
        assert "Invalid API key" in msg
        assert "sk-secret123456789" not in msg

    def test_generic_error_is_scrubbed(self):
        def create(**kwargs):
            raise ValueError("boom sk-secret123456789")

        client = make_client(create=create)
        ok, msg = client.test_key()
        assert ok is False
        assert "sk-secret123456789" not in msg

    def test_max_tokens_is_small(self):
        captured = {}

        def create(**kwargs):
            captured.update(kwargs)
            return SimpleNamespace(choices=[])

        client = make_client(create=create)
        client.test_key()
        assert captured["max_tokens"] == 5


class TestSocksProxyDetection:
    def test_detects_lowercase_all_proxy(self):
        assert _is_socks_proxy_configured({"all_proxy": "socks5://127.0.0.1:7890"})

    def test_detects_uppercase_socks_scheme(self):
        assert _is_socks_proxy_configured({"ALL_PROXY": "SOCKS5://127.0.0.1:7890"})

    def test_plain_http_proxy_is_not_socks(self):
        assert not _is_socks_proxy_configured({"https_proxy": "http://127.0.0.1:7890"})

    def test_empty_env(self):
        assert not _is_socks_proxy_configured({})

    def test_socks_in_https_proxy_detected(self):
        assert _is_socks_proxy_configured({"HTTPS_PROXY": "socks4://127.0.0.1:1080"})


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
