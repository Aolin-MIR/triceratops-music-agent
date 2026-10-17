"""Keep API credentials out of user-visible failures and persisted traces."""
import os
import re


def redact_error(value: object) -> str:
    text = str(value)
    for name in ("QWEN_API_KEY", "OPENAI_API_KEY", "TRICERATOPS_SETUP_KEY"):
        secret = os.environ.get(name, "")
        if secret:
            text = text.replace(secret, "[REDACTED]")
    return re.sub(r"sk-[A-Za-z0-9_-]{6,}", "[REDACTED]", text)
