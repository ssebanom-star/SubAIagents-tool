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

# --- Real-time log monitoring ---------------------------------------------

# Max lines retained per live logcat session (ring buffer).
LOG_BUFFER_LINES: int = _int_env("SUBAI_LOG_BUFFER_LINES", 5000)

# Upper bound (seconds) for a single adb_logcat_watch call so a tool never
# blocks the server indefinitely.
LOG_WATCH_MAX_TIMEOUT: int = _int_env("SUBAI_LOG_WATCH_MAX_TIMEOUT", 300)


# --- Sub-agent backend -----------------------------------------------------

# Which backend the chatgpt_* / analyze tools use:
#   "auto"  -> prefer the Codex CLI if present (uses your ChatGPT subscription,
#              no per-token API cost), otherwise fall back to the OpenAI API.
#   "codex" -> always use the Codex CLI.
#   "api"   -> always use the OpenAI API (billed per token).
GPT_BACKEND: str = os.environ.get("SUBAI_GPT_BACKEND", "auto").strip().lower()

# Codex CLI executable. Logging in with "Sign in with ChatGPT" means usage is
# covered by your ChatGPT plan instead of API billing.
CODEX_CMD: str = os.environ.get("SUBAI_CODEX_CMD", "codex").strip()

# Args inserted before the prompt (space-split). `exec` runs non-interactively;
# `--skip-git-repo-check` lets it run outside a git/trusted directory (the MCP
# server's working dir is arbitrary).
CODEX_ARGS: str = os.environ.get(
    "SUBAI_CODEX_ARGS", "exec --skip-git-repo-check"
).strip()

CODEX_TIMEOUT: int = _int_env("SUBAI_CODEX_TIMEOUT", 180)

# Default model for the Codex backend (empty = Codex CLI's own default).
# e.g. "gpt-5-codex", "o4-mini". Per-call `model` args override this.
CODEX_MODEL: str = os.environ.get("SUBAI_CODEX_MODEL", "").strip()


# --- ChatGPT / OpenAI related ---------------------------------------------

OPENAI_API_KEY: str = os.environ.get("OPENAI_API_KEY", "").strip()

# Cost-efficient default; override for heavier tasks.
OPENAI_MODEL: str = os.environ.get("OPENAI_MODEL", "gpt-4o-mini").strip()

# Optional custom endpoint (Azure/OpenAI-compatible gateways).
OPENAI_BASE_URL: str = os.environ.get("OPENAI_BASE_URL", "").strip()

# Cap sub-agent output so delegated work stays cheap and bounded.
OPENAI_MAX_TOKENS: int = _int_env("OPENAI_MAX_TOKENS", 2048)
