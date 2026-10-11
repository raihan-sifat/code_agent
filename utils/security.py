"""Secret redaction helpers.

Any string that may be logged or surfaced in the GUI (agent messages, API
errors, tool output) should be passed through :func:`scrub_secrets` so an API
key can never end up in the log pane or on disk.
"""

import re
from typing import Any


_SECRET_PATTERNS = [
    # DeepSeek / OpenAI style keys: sk-xxxxxxxx...
    re.compile(r"\bsk-[A-Za-z0-9_\-]{8,}\b"),
    # Bearer tokens in headers that may leak into error text.
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._\-]{8,}"),
]


def scrub_secrets(text: Any, *extra_secrets: str) -> str:
    """Return ``text`` with known keys/tokens replaced by ``***``.

    ``extra_secrets`` allows redacting the exact key currently entered in the
    GUI, which may not match the generic patterns (e.g. a custom key format).
    """
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)

    for secret in extra_secrets:
        if secret and len(secret) >= 4:
            text = text.replace(secret, "***")

    for pattern in _SECRET_PATTERNS:
        text = pattern.sub("***", text)

    return text
