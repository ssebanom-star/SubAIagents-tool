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


# --- Background jobs & repeated execution ----------------------------------

# Max output lines retained per background job (ring buffer).
BG_BUFFER_LINES: int = _int_env("SUBAI_BG_BUFFER_LINES", 5000)

# Upper bound (seconds) for a single bg_wait / adb_wait_for_device call.
BG_WAIT_MAX_TIMEOUT: int = _int_env("SUBAI_BG_WAIT_MAX_TIMEOUT", 600)

# Safety cap on iterations for adb_repeat_shell.
REPEAT_MAX_TIMES: int = _int_env("SUBAI_REPEAT_MAX_TIMES", 500)


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

# Default per-call timeout when a tool doesn't specify one. The AI can pass a
# larger `timeout` per call for heavier tasks, clamped to CODEX_MAX_TIMEOUT.
CODEX_TIMEOUT: int = _int_env("SUBAI_CODEX_TIMEOUT", 300)

# Hard ceiling for any single sub-agent call (protects against runaway).
CODEX_MAX_TIMEOUT: int = _int_env("SUBAI_CODEX_MAX_TIMEOUT", 1800)

# Default model for the Codex backend. Fixed to gpt-5.6-luna (OpenAI's fast,
# low-cost GPT-5.6 tier, selectable in Codex with a ChatGPT plan). Override via
# SUBAI_CODEX_MODEL, or per-call `model` args.
CODEX_MODEL: str = os.environ.get("SUBAI_CODEX_MODEL", "gpt-5.6-luna").strip()


# --- ChatGPT / OpenAI related ---------------------------------------------

OPENAI_API_KEY: str = os.environ.get("OPENAI_API_KEY", "").strip()

# Cost-efficient default; override for heavier tasks.
OPENAI_MODEL: str = os.environ.get("OPENAI_MODEL", "gpt-4o-mini").strip()

# Optional custom endpoint (Azure/OpenAI-compatible gateways).
OPENAI_BASE_URL: str = os.environ.get("OPENAI_BASE_URL", "").strip()

# Cap sub-agent output so delegated work stays cheap and bounded.
OPENAI_MAX_TOKENS: int = _int_env("OPENAI_MAX_TOKENS", 2048)
