"""ChatGPT sub-agent.

Delegates auxiliary / boilerplate coding and lookups to the OpenAI API so
that the primary Claude Code agent spends fewer tokens: Claude decides *what*
to delegate, ChatGPT produces the bulk output, and only the result flows back.
"""

from __future__ import annotations

from typing import Optional

from . import config

_client = None
_client_error: Optional[str] = None


def _get_client():
    """Lazily build the OpenAI client so a missing key never crashes startup."""
    global _client, _client_error
    if _client is not None or _client_error is not None:
        return _client

    if not config.OPENAI_API_KEY:
        _client_error = (
            "OPENAI_API_KEY is not set. Set it in the MCP server env to enable "
            "the ChatGPT sub-agent."
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


def _chat(system: str, user: str, model: Optional[str] = None) -> dict:
    client = _get_client()
    if client is None:
        return {"ok": False, "error": _client_error, "content": ""}

    try:
        resp = client.chat.completions.create(
            model=model or config.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=config.OPENAI_MAX_TOKENS,
            temperature=0.2,
        )
    except Exception as exc:  # noqa: BLE001 - surface any API error to caller
        return {"ok": False, "error": f"OpenAI API error: {exc}", "content": ""}

    choice = resp.choices[0].message.content or ""
    usage = getattr(resp, "usage", None)
    return {
        "ok": True,
        "content": choice.strip(),
        "model": resp.model,
        "usage": {
            "prompt_tokens": getattr(usage, "prompt_tokens", None),
            "completion_tokens": getattr(usage, "completion_tokens", None),
            "total_tokens": getattr(usage, "total_tokens", None),
        } if usage else None,
    }


# --- Public sub-agent operations ------------------------------------------

def code(task: str, context: str = "", language: str = "", model: str = "") -> dict:
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
    return _chat(system, user, model=model or None)


def ask(prompt: str, model: str = "") -> dict:
    """Delegate a general question (explanation, research, lookup)."""
    system = (
        "You are a concise technical assistant. Answer directly and "
        "accurately. Avoid filler."
    )
    return _chat(system, prompt, model=model or None)


def review(code_snippet: str, focus: str = "", model: str = "") -> dict:
    """Delegate a code review / improvement pass."""
    system = (
        "You are a senior code reviewer. Identify bugs, risks, and concrete "
        "improvements. Be specific and terse; show corrected snippets where "
        "helpful."
    )
    user = f"Review the following code"
    if focus:
        user += f" (focus: {focus})"
    user += f":\n\n{code_snippet}"
    return _chat(system, user, model=model or None)
