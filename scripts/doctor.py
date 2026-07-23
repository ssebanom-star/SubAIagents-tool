"""Environment diagnostics for subaiagents.

Run: python scripts/doctor.py
Checks adb discovery + device connectivity and the ChatGPT sub-agent config.
"""

from __future__ import annotations

import os
import sys

# Allow running from a source checkout without installing.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from subaiagents import adb, config  # noqa: E402


def check_adb() -> bool:
    print("== ADB ==")
    try:
        path = adb.find_adb()
        print(f"  [ok] adb found: {path}")
    except adb.AdbError as exc:
        print(f"  [FAIL] {exc}")
        return False

    result = adb.devices()
    if not result["ok"]:
        print(f"  [FAIL] `adb devices` failed: {result['stderr']}")
        return False

    devs = result["devices"]
    if not devs:
        print("  [warn] adb works but no devices connected.")
        print("         Connect a device with USB debugging enabled, then re-run.")
    else:
        for d in devs:
            print(f"  [ok] device: {d['serial']} ({d['state']})")
    return True


def check_chatgpt() -> bool:
    from subaiagents import chatgpt

    print("== Sub-agent backend (ChatGPT / Codex) ==")
    print(f"  [info] SUBAI_GPT_BACKEND = {config.GPT_BACKEND}")

    codex = chatgpt.find_codex()
    if codex:
        print(f"  [ok] Codex CLI found: {codex}")
        print("       -> uses your ChatGPT subscription (no per-token API cost).")
        print("       Make sure you've run `codex login` once.")
        return True

    print("  [warn] Codex CLI not found (recommended, no API cost).")
    print("         Install: npm install -g @openai/codex  then: codex login")

    if config.OPENAI_API_KEY:
        print("  [ok] OPENAI_API_KEY is set (API fallback available, billed per token).")
        try:
            import openai  # noqa: F401
            print("  [ok] openai package importable.")
            return True
        except ImportError:
            print("  [FAIL] openai package missing — run: pip install openai")
            return False

    print("  [warn] Neither Codex CLI nor OPENAI_API_KEY available — "
          "chatgpt_* tools will return an instructive error until configured.")
    return False


def main() -> int:
    adb_ok = check_adb()
    print()
    gpt_ok = check_chatgpt()
    print()
    if adb_ok and gpt_ok:
        print("All checks passed.")
        return 0
    print("Some checks need attention (see above).")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
