"""Directly test the sub-agent (bypassing the app / MCP layer).

Run this in a shell where `codex` works and you're logged in (`codex login`).
It calls the Codex backend the same way the MCP server does, so it proves
whether a given model works end-to-end.

Examples:
    python scripts/try_model.py --model gpt-5.6-luna
    python scripts/try_model.py --model gpt-5.6-luna --task "write a quicksort in python"
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from subaiagents import chatgpt  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description="Test the sub-agent with a model.")
    p.add_argument("--model", default="", help="Model id, e.g. gpt-5.6-luna")
    p.add_argument("--language", default="python")
    p.add_argument(
        "--task",
        default=("Write a small Python function is_palindrome(s) that returns "
                 "True if s is a palindrome, ignoring case and non-alphanumeric "
                 "characters. Include a short example in a main block."),
    )
    args = p.parse_args()

    print("Backend / effective model:")
    print(json.dumps(chatgpt.get_model(), ensure_ascii=False, indent=2))
    print(f"\nDetected codex: {chatgpt.find_codex() or '(NOT FOUND)'}")
    print(f"\nRunning task with model={args.model or '(default)'} ...\n")

    result = chatgpt.code(args.task, language=args.language, model=args.model)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
