import logging
import os
import time
from typing import Optional, List, Dict, Any, Generator, Tuple
from openai import OpenAI, DefaultHttpxClient, APIConnectionError, APITimeoutError, RateLimitError, APIError, AuthenticationError

from utils.security import scrub_secrets

logger = logging.getLogger(__name__)

# Environment variables httpx checks for proxy configuration.
_PROXY_ENV_VARS = (
    "all_proxy", "ALL_PROXY",
    "http_proxy", "HTTP_PROXY",
    "https_proxy", "HTTPS_PROXY",
)


def _is_socks_proxy_configured(env: Optional[Dict[str, str]] = None) -> bool:
    """Return True when an environment variable requests a SOCKS proxy.

    httpx needs the optional ``socksio`` dependency for SOCKS proxies; if it is
    missing every request fails with a RuntimeError. A frozen build does not
    bundle it, so when a SOCKS proxy is present we bypass the environment and
    connect directly. Plain HTTP(S) proxies are still honoured.
    """
    env = os.environ if env is None else env
    for name in _PROXY_ENV_VARS:
        value = env.get(name) or ""
        if value.lower().startswith("socks"):
            return True
    return False


class DeepSeekClient:
    """Client for DeepSeek API using OpenAI compatible endpoints."""
    
    def __init__(self, api_key: str, model: str = "deepseek-chat"):
        """Initialize with API key. Base URL: https://api.deepseek.com"""
        self.api_key = api_key
        self.model = model

        # A SOCKS proxy in the environment would otherwise make httpx raise
        # "Using SOCKS proxy, but the 'socksio' package is not installed".
        # Ignore the environment in that case and talk to DeepSeek directly.
        http_client = None
        if _is_socks_proxy_configured():
            logger.info("SOCKS proxy detected in environment; bypassing it for the API client.")
            http_client = DefaultHttpxClient(trust_env=False)

        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://api.deepseek.com",
            http_client=http_client,
        )

    def test_key(self) -> Tuple[bool, str]:
        """Validate the API key with one tiny request.

        Returns ``(True, message)`` when the key works, else ``(False, message)``
        with a scrubbed error (the key itself never appears in the message).
        """
        try:
            self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=5,
            )
            return True, "API key is valid."
        except AuthenticationError:
            return False, "Invalid API key (authentication failed)."
        except Exception as e:
            return False, scrub_secrets(str(e), self.api_key)
    
    def _retry_with_backoff(self, func, *args, **kwargs):
        max_retries = 3
        base_delay = 1.0
        
        for attempt in range(max_retries + 1):
            try:
                return func(*args, **kwargs)
            except (APIConnectionError, APITimeoutError, RateLimitError, APIError) as e:
                if attempt == max_retries:
                    logger.error("Failed after %s retries. Error: %s", max_retries, scrub_secrets(str(e), self.api_key))
                    raise
                
                delay = base_delay * (2 ** attempt)
                logger.warning("API call failed: %s. Retrying in %ss (Attempt %s/%s)", scrub_secrets(str(e), self.api_key), delay, attempt + 1, max_retries)
                time.sleep(delay)
            except Exception as e:
                logger.error("Unexpected error: %s", scrub_secrets(str(e), self.api_key))
                raise

    def chat(self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None, temperature: float = 0.0) -> Dict[str, Any]:
        """Send chat completion request. Returns dict with 'role', 'content', 'tool_calls' keys."""
        logger.info(f"Sending chat request with model {self.model}")
        
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if tools:
            kwargs["tools"] = tools
            
        def _call_api():
            return self.client.chat.completions.create(**kwargs)
            
        response = self._retry_with_backoff(_call_api)
        choice = response.choices[0].message

        # NOTE: only include the "tool_calls" key when there are actual tool
        # calls. Sending `tool_calls: null` in an assistant message is rejected
        # by the API on the next turn.
        result = {
            "role": choice.role,
            "content": choice.content or "",
        }

        if choice.tool_calls:
            result["tool_calls"] = []
            for tc in choice.tool_calls:
                result["tool_calls"].append({
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                })
                
        return result

    def chat_stream(self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None, temperature: float = 0.0) -> Generator[Dict[str, Any], None, None]:
        """Streaming version. Yields partial content strings for real-time display."""
        logger.info(f"Sending streaming chat request with model {self.model}")
        
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }
        if tools:
            kwargs["tools"] = tools
            
        def _call_api():
            return self.client.chat.completions.create(**kwargs)
            
        response = self._retry_with_backoff(_call_api)
        
        for chunk in response:
            if chunk.choices and len(chunk.choices) > 0:
                delta = chunk.choices[0].delta
                if delta.content is not None:
                    yield {"content": delta.content}
