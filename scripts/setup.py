"""One-command setup: resolve every path and write a working MCP config.

Run this ON YOUR MACHINE (Windows/macOS/Linux). It auto-discovers the Python
executable, the adb binary, and the project source path, then writes a
ready-to-use `.mcp.json` with all absolute paths filled in — so you never edit
paths by hand.

Usage:
    python scripts/setup.py
    python scripts/setup.py --openai-key sk-...            # add ChatGPT key
    python scripts/setup.py --adb-path C:\\tools\\adb.exe   # force adb path
    python scripts/setup.py --persist                       # also setx env vars (Windows)
    python scripts/setup.py --print-only                    # don't write, just show

After it runs, restart Claude Code and check `/mcp`.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

# Make the package importable so we can reuse adb discovery.
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

from subaiagents import adb, config  # noqa: E402


def resolve_adb(override: str) -> str | None:
    if override:
        if os.path.isfile(override):
            return os.path.abspath(override)
        print(f"[warn] --adb-path '{override}' not found; falling back to auto-discovery.")
    # Temporarily honor override via config, else auto-discover.
    try:
        return adb.find_adb()
    except adb.AdbError:
        return None


def persist_windows_env(name: str, value: str) -> None:
    """Persist a user env var on Windows via setx (best effort)."""
    if os.name != "nt":
        print(f"[skip] --persist only applies on Windows (would set {name}).")
        return
    try:
        subprocess.run(["setx", name, value], check=True,
                       capture_output=True, text=True)
        print(f"[ok] Persisted {name} for your user (new terminals will see it).")
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] Could not setx {name}: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Auto-configure subaiagents MCP paths.")
    parser.add_argument("--openai-key", default=os.environ.get("OPENAI_API_KEY", ""),
                        help="OpenAI API key for the ChatGPT sub-agent.")
    parser.add_argument("--openai-model", default=config.OPENAI_MODEL,
                        help="Model for the ChatGPT sub-agent.")
    parser.add_argument("--adb-path", default="", help="Force a specific adb path.")
    parser.add_argument("--persist", action="store_true",
                        help="Also persist env vars via setx (Windows only).")
    parser.add_argument("--print-only", action="store_true",
                        help="Print the config/command without writing .mcp.json.")
    args = parser.parse_args()

    python_exe = os.path.abspath(sys.executable)
    adb_path = resolve_adb(args.adb_path)

    print("== Resolved paths ==")
    print(f"  python : {python_exe}")
    print(f"  src    : {SRC}")
    print(f"  adb    : {adb_path or '(NOT FOUND — install platform-tools or pass --adb-path)'}")
    print(f"  model  : {args.openai_model}")
    print(f"  openai : {'set' if args.openai_key else '(not provided — ADB still works)'}")
    print()

    # Build env with all absolute paths. PYTHONPATH guarantees the package is
    # importable whether or not it was pip-installed → no PATH surprises.
    env: dict[str, str] = {"PYTHONPATH": SRC, "OPENAI_MODEL": args.openai_model}
    if adb_path:
        env["ADB_PATH"] = adb_path
    if args.openai_key:
        env["OPENAI_API_KEY"] = args.openai_key

    mcp_config = {
        "mcpServers": {
            "subaiagents": {
                "command": python_exe,
                "args": ["-m", "subaiagents.server"],
                "env": env,
            }
        }
    }

    pretty = json.dumps(mcp_config, indent=2, ensure_ascii=False)
    print("== .mcp.json ==")
    print(pretty)
    print()

    # Equivalent `claude mcp add` one-liner.
    env_flags = " ".join(f"--env {k}={v}" for k, v in env.items())
    print("== Equivalent CLI ==")
    print(f'  claude mcp add subaiagents {env_flags} -- "{python_exe}" -m subaiagents.server')
    print()

    if args.print_only:
        print("[print-only] .mcp.json not written.")
    else:
        target = os.path.join(ROOT, ".mcp.json")
        with open(target, "w", encoding="utf-8") as fh:
            fh.write(pretty + "\n")
        print(f"[ok] Wrote {target}")

    if args.persist:
        if adb_path:
            persist_windows_env("ADB_PATH", adb_path)
        if args.openai_key:
            persist_windows_env("OPENAI_API_KEY", args.openai_key)

    print()
    if not adb_path:
        print("NEXT: install Android platform-tools, then re-run this script "
              "(or pass --adb-path).")
    else:
        print("NEXT: restart Claude Code, run /mcp, and confirm 'subaiagents' is connected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
