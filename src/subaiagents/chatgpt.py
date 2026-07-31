"""ChatGPT sub-agent.

Delegates auxiliary / boilerplate coding and lookups so the primary Claude
Code agent spends fewer tokens: Claude decides *what* to delegate, the
sub-agent produces the bulk output, and only the result flows back.

Two backends (see config.GPT_BACKEND):
  * "codex" — shells out to the Codex CLI (`codex exec`). If you sign in with
    "Sign in with ChatGPT", usage is covered by your ChatGPT subscription, so
    there is NO per-token API cost. This is the default when `codex` is found.
  * "api"   — calls the OpenAI API with OPENAI_API_KEY (billed per token).
"""

from __future__ import annotations

import shutil
import subprocess
from typing import Optional

from . import config

_client = None
_client_error: Optional[str] = None

# Runtime-selectable default model (set via set_model). Empty = use the
# backend's configured/built-in default. Per-call `model` args still win.
_runtime_model: str = ""


def set_model(model: str) -> dict:
    """Set the default model for subsequent sub-agent calls (both backends).

    Pass an empty string to clear the override and fall back to the configured
    default. Per-call `model` arguments still take precedence over this.
    """
    global _runtime_model
    _runtime_model = (model or "").strip()
    return get_model()


def get_model() -> dict:
    """Report the current backend and effective default model."""
    backend = _select_backend()
    if backend == "codex":
        default = config.CODEX_MODEL or "(Codex CLI default)"
    else:
        default = config.OPENAI_MODEL
    return {
        "ok": True,
        "backend": backend,
        "runtime_override": _runtime_model or None,
        "effective_default": _runtime_model or default,
        "note": "Per-call model= arguments override this default.",
    }


def _get_client():
    """Lazily build the OpenAI client so a missing key never crashes startup."""
    global _client, _client_error
    if _client is not None or _client_error is not None:
        return _client

    if not config.OPENAI_API_KEY:
        _client_error = (
            "No sub-agent backend available. Recommended (no extra cost): "
            "install the Codex CLI (npm install -g @openai/codex) and run "
            "`codex login` to use your ChatGPT subscription. Alternatively set "
            "OPENAI_API_KEY to use the OpenAI API (billed per token)."
        )
        return None

    try:
        from openai import OpenAI
    except ImportError:
        _client_error = (
            "The 'openai' package is not installed. Run: pip install openai"
        )
        return None

    kwargs = {"api_key": config.OPENAI_API_KEY}
    if config.OPENAI_BASE_URL:
        kwargs["base_url"] = config.OPENAI_BASE_URL
    _client = OpenAI(**kwargs)
    return _client


def _codex_candidates() -> list:
    """Common Codex CLI install locations (mainly Windows).

    The MCP server is often launched by an app with a PATH that differs from an
    interactive shell, so `shutil.which` can miss codex even when it is
    installed. We fall back to these absolute locations.
    """
    import os

    exp = os.path.expandvars
    return [
        exp(r"%LOCALAPPDATA%\Programs\OpenAI\Codex\bin\codex.exe"),
        exp(r"%LOCALAPPDATA%\Programs\OpenAI\Codex\codex.exe"),
        exp(r"%USERPROFILE%\AppData\Local\Programs\OpenAI\Codex\bin\codex.exe"),
        exp(r"%APPDATA%\npm\codex.cmd"),
        exp(r"%APPDATA%\npm\codex.exe"),
        exp(r"%ProgramFiles%\OpenAI\Codex\bin\codex.exe"),
        exp(r"%USERPROFILE%\scoop\apps\codex\current\codex.exe"),
        os.path.expanduser("~/.local/bin/codex"),
        "/usr/local/bin/codex",
        "/opt/homebrew/bin/codex",
    ]


def find_codex() -> Optional[str]:
    """Locate the Codex CLI: explicit path -> PATH -> common install dirs."""
    import os

    cmd = config.CODEX_CMD
    if os.path.isfile(cmd):
        return cmd
    found = shutil.which(cmd)
    if found:
        return found
    for candidate in _codex_candidates():
        if candidate and os.path.isfile(candidate):
            return candidate
    return None


def _codex_executable() -> Optional[str]:
    """Return the Codex CLI path if available, else None."""
    return find_codex()


def _select_backend() -> str:
    """Decide which backend to use based on config and availability."""
    if config.GPT_BACKEND == "codex":
        return "codex"
    if config.GPT_BACKEND == "api":
        return "api"
    # auto: prefer the no-extra-cost Codex CLI when present.
    return "codex" if _codex_executable() else "api"


def _resolve_timeout(explicit: Optional[int]) -> int:
    """Per-call timeout: explicit (if >0) clamped to the ceiling, else default."""
    if explicit and explicit > 0:
        return min(int(explicit), config.CODEX_MAX_TIMEOUT)
    return config.CODEX_TIMEOUT


def _codex_chat(system: str, user: str, model: str = "",
                timeout: Optional[int] = None) -> dict:
    """Run the sub-agent via the Codex CLI (uses your ChatGPT subscription)."""
    exe = _codex_executable()
    if not exe:
        return {
            "ok": False,
            "content": "",
            "error": (
                f"Codex CLI ('{config.CODEX_CMD}') not found. Install it "
                "(npm install -g @openai/codex) and run `codex login` to sign "
                "in with your ChatGPT account — no API key needed. Or set "
                "SUBAI_GPT_BACKEND=api to use the OpenAI API instead."
            ),
        }

    import os
    import tempfile

    prompt = f"{system}\n\n{user}" if system else user
    args = config.CODEX_ARGS.split()

    # Model selection: explicit arg > runtime override (already folded into
    # `model` by _chat) > configured Codex default > Codex's own default.
    effective_model = model or config.CODEX_MODEL
    if effective_model and "-m" not in args and "--model" not in args:
        args = args + ["-m", effective_model]

    # Capture just the final agent message to a temp file (clean output without
    # the streaming preamble). Only add it for `exec` runs that don't set it.
    last_msg_file = None
    if "exec" in args and "--output-last-message" not in args:
        fd, last_msg_file = tempfile.mkstemp(prefix="subai_codex_", suffix=".txt")
        os.close(fd)
        args = args + ["--output-last-message", last_msg_file]

    eff_timeout = _resolve_timeout(timeout)
    cmd = [exe] + args + [prompt]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=eff_timeout,
            # Critical: give codex an empty stdin (EOF) so it never blocks
            # waiting for input when there is no TTY (as under the MCP server).
            stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired:
        _cleanup(last_msg_file)
        return {"ok": False, "content": "",
                "error": (f"Codex CLI timed out after {eff_timeout}s. "
                          "Pass a larger `timeout` for heavier tasks "
                          f"(ceiling {config.CODEX_MAX_TIMEOUT}s)."),
                "backend": "codex"}
    except Exception as exc:  # noqa: BLE001
        _cleanup(last_msg_file)
        return {"ok": False, "content": "", "error": f"Codex CLI error: {exc}"}

    # Prefer the clean last-message file; fall back to stdout.
    content = ""
    if last_msg_file and os.path.isfile(last_msg_file):
        try:
            with open(last_msg_file, "r", encoding="utf-8") as fh:
                content = fh.read().strip()
        except OSError:
            pass
    _cleanup(last_msg_file)
    if not content:
        content = proc.stdout.strip()

    if proc.returncode != 0:
        return {
            "ok": False,
            "content": content,
            "error": (proc.stderr.strip() or
                      f"Codex CLI exited with code {proc.returncode}. "
                      "If not logged in, run `codex login`."),
            "backend": "codex",
        }
    return {"ok": True, "content": content, "backend": "codex",
            "model": effective_model or "(Codex CLI default)",
            "timeout_used": eff_timeout,
            "cost": "covered by ChatGPT subscription (no API billing)"}


def _cleanup(path: Optional[str]) -> None:
    if not path:
        return
    import os
    try:
        os.remove(path)
    except OSError:
        pass


def _chat(system: str, user: str, model: Optional[str] = None,
          timeout: Optional[int] = None, default_model: str = "") -> dict:
    # Precedence: explicit per-call model > runtime override > operation-specific
    # default (e.g. review) > backend default.
    chosen = (model or "").strip() or _runtime_model or default_model

    if _select_backend() == "codex":
        return _codex_chat(system, user, model=chosen, timeout=timeout)

    client = _get_client()
    if client is None:
        return {"ok": False, "error": _client_error, "content": ""}

    try:
        resp = client.chat.completions.create(
            model=chosen or config.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=config.OPENAI_MAX_TOKENS,
            temperature=0.2,
            timeout=_resolve_timeout(timeout),
        )
    except Exception as exc:  # noqa: BLE001 - surface any API error to caller
        return {"ok": False, "error": f"OpenAI API error: {exc}", "content": ""}

    choice = resp.choices[0].message.content or ""
    usage = getattr(resp, "usage", None)
    return {
        "ok": True,
        "content": choice.strip(),
        "backend": "api",
        "model": resp.model,
        "usage": {
            "prompt_tokens": getattr(usage, "prompt_tokens", None),
            "completion_tokens": getattr(usage, "completion_tokens", None),
            "total_tokens": getattr(usage, "total_tokens", None),
        } if usage else None,
    }


# --- Public sub-agent operations ------------------------------------------

def code(task: str, context: str = "", language: str = "", model: str = "",
         timeout: int = 0) -> dict:
    """Delegate a coding task; returns code (and brief notes) from ChatGPT."""
    lang = f" in {language}" if language else ""
    system = (
        "You are a focused coding sub-agent. Produce correct, idiomatic, "
        "self-contained code for the requested task. Prefer a single code "
        "block. Keep prose to a minimum — only essential usage notes."
    )
    user = f"Task{lang}:\n{task}"
    if context:
        user += f"\n\nRelevant context / constraints:\n{context}"
    return _chat(system, user, model=model or None, timeout=timeout or None)


def ask(prompt: str, model: str = "", timeout: int = 0) -> dict:
    """Delegate a general question (explanation, research, lookup)."""
    system = (
        "You are a concise technical assistant. Answer directly and "
        "accurately. Avoid filler."
    )
    return _chat(system, prompt, model=model or None, timeout=timeout or None)


def analyze_logs(logs: str, question: str = "", model: str = "",
                 timeout: int = 0) -> dict:
    """Delegate log reading & judgement to ChatGPT.

    Offloads the token-heavy work of scanning verbose logcat output: ChatGPT
    reads the logs and returns a compact verdict (severity, likely root cause,
    suggested next step), so only the conclusion flows back to Claude.
    """
    system = (
        "You are an Android logcat analysis expert. Read the provided log "
        "lines and judge them. Respond compactly with: (1) SEVERITY "
        "[ok | warning | error | crash], (2) a one-line summary, (3) the most "
        "likely root cause if any problem is present, (4) a concrete suggested "
        "next step. If a specific question is asked, answer it directly first. "
        "Do not echo the raw logs back."
    )
    user = ""
    if question:
        user += f"Question: {question}\n\n"
    user += f"Log lines:\n{logs}"
    return _chat(system, user, model=model or None, timeout=timeout or None)


def review(code_snippet: str, focus: str = "", model: str = "",
           timeout: int = 0) -> dict:
    """Delegate a code review / improvement pass.

    Defaults to gpt-5.6-terra (balanced tier) unless a model is given per call
    or set via set_model.
    """
    system = (
        "You are a senior code reviewer. Identify bugs, risks, and concrete "
        "improvements. Be specific and terse; show corrected snippets where "
        "helpful."
    )
    user = f"Review the following code"
    if focus:
        user += f" (focus: {focus})"
    user += f":\n\n{code_snippet}"
    return _chat(system, user, model=model or None, timeout=timeout or None,
                 default_model=config.CODEX_REVIEW_MODEL)
