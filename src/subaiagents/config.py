"""Centralized configuration read from environment variables.

All tunables live here so both the ADB wrapper and the ChatGPT sub-agent
read from a single, documented place.
"""

from __future__ import annotations

import os


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


# --- ADB related -----------------------------------------------------------

# Explicit path to adb(.exe). If empty, the wrapper auto-discovers it.
ADB_PATH: str = os.environ.get("ADB_PATH", "").strip()

# Default device serial used when a tool call omits `serial`.
ADB_DEFAULT_SERIAL: str = os.environ.get("ADB_DEFAULT_SERIAL", "").strip()

# Timeout (seconds) applied to every adb subprocess call.
ADB_TIMEOUT: int = _int_env("SUBAI_TIMEOUT", 60)

# Where screenshots are saved on the host running this server.
SCREENSHOT_DIR: str = os.environ.get(
    "SUBAI_SCREENSHOT_DIR",
    os.path.join(os.getcwd(), "adb_screenshots"),
).strip()


# --- ChatGPT / OpenAI related ---------------------------------------------

OPENAI_API_KEY: str = os.environ.get("OPENAI_API_KEY", "").strip()

# Cost-efficient default; override for heavier tasks.
OPENAI_MODEL: str = os.environ.get("OPENAI_MODEL", "gpt-4o-mini").strip()

# Optional custom endpoint (Azure/OpenAI-compatible gateways).
OPENAI_BASE_URL: str = os.environ.get("OPENAI_BASE_URL", "").strip()

# Cap sub-agent output so delegated work stays cheap and bounded.
OPENAI_MAX_TOKENS: int = _int_env("OPENAI_MAX_TOKENS", 2048)
