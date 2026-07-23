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


def claude_desktop_config_path() -> str:
    """Location of the Claude Desktop app's MCP config for this OS."""
    if os.name == "nt":
        return os.path.join(os.environ.get("APPDATA", ""), "Claude",
                            "claude_desktop_config.json")
    if sys.platform == "darwin":
        return os.path.expanduser(
            "~/Library/Application Support/Claude/claude_desktop_config.json")
    return os.path.expanduser("~/.config/Claude/claude_desktop_config.json")


def write_claude_desktop(server_config: dict) -> None:
    """Merge our server into the Claude Desktop app's config (keeps others)."""
    path = claude_desktop_config_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)

    data: dict = {}
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh) or {}
        except (json.JSONDecodeError, OSError) as exc:
            print(f"[warn] Existing config unreadable ({exc}); starting fresh. "
                  f"A backup is kept at {path}.bak")
            try:
                os.replace(path, path + ".bak")
            except OSError:
                pass
            data = {}

    servers = data.setdefault("mcpServers", {})
    servers["subaiagents"] = server_config
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
    print(f"[ok] Registered in Claude Desktop config: {path}")
    print("     -> FULLY quit Claude (system tray → Quit) and reopen it.")


def write_claude_code(server_config: dict) -> None:
    """Merge our server into the Claude Code user config (~/.claude.json).

    This is what the Claude Code desktop app / CLI reads for MCP servers. We
    only touch the top-level `mcpServers` key and leave everything else intact,
    keeping a timestamped backup first.
    """
    import time

    path = os.path.expanduser("~/.claude.json")
    data: dict = {}
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh) or {}
        except (json.JSONDecodeError, OSError) as exc:
            print(f"[warn] {path} unreadable ({exc}); not touching it. "
                  "Register the server through the app UI instead.")
            return
        # Back up before modifying an existing (possibly large) config.
        backup = f"{path}.bak.{int(time.time())}"
        try:
            with open(backup, "w", encoding="utf-8") as bf:
                json.dump(data, bf, ensure_ascii=False)
            print(f"[ok] Backed up existing config to {backup}")
        except OSError:
            pass

    servers = data.setdefault("mcpServers", {})
    servers["subaiagents"] = server_config
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
    print(f"[ok] Registered in Claude Code config: {path}")
    print("     -> Fully quit the Claude app (Task Manager if needed) and reopen,")
    print("        then use a LOCAL session (not a remote/cloud one) so it can")
    print("        reach your USB device.")


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
    parser.add_argument("--claude-desktop", action="store_true",
                        help="Also register into the Claude Desktop (chat) app config.")
    parser.add_argument("--claude-code", action="store_true",
                        help="Also register into the Claude Code config (~/.claude.json) "
                             "used by the Claude Code desktop app / CLI.")
    args = parser.parse_args()

    from subaiagents import chatgpt

    python_exe = os.path.abspath(sys.executable)
    adb_path = resolve_adb(args.adb_path)
    codex_path = chatgpt.find_codex()

    print("== Resolved paths ==")
    print(f"  python  : {python_exe}")
    print(f"  src     : {SRC}")
    print(f"  adb     : {adb_path or '(NOT FOUND — install platform-tools or pass --adb-path)'}")
    if codex_path:
        print(f"  codex   : {codex_path}  -> ChatGPT subscription, no API cost")
    else:
        print("  codex   : (not found — recommended: npm i -g @openai/codex && codex login)")
    print(f"  openai  : {'set (API fallback, billed)' if args.openai_key else '(not provided)'}")
    print()

    # Build env with all absolute paths. PYTHONPATH guarantees the package is
    # importable whether or not it was pip-installed → no PATH surprises.
    env: dict[str, str] = {"PYTHONPATH": SRC}
    if adb_path:
        env["ADB_PATH"] = adb_path
    # Sub-agent: prefer Codex CLI (subscription, no API cost); else API key.
    if codex_path:
        env["SUBAI_GPT_BACKEND"] = "codex"
        # Bake the absolute path so the server finds codex even when the app
        # launches it with a PATH that lacks the Codex install dir.
        env["SUBAI_CODEX_CMD"] = codex_path
    if args.openai_key:
        env["OPENAI_API_KEY"] = args.openai_key
        env["OPENAI_MODEL"] = args.openai_model
        if not codex_path:
            env["SUBAI_GPT_BACKEND"] = "api"

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
        print("[print-only] nothing written.")
    else:
        target = os.path.join(ROOT, ".mcp.json")
        with open(target, "w", encoding="utf-8") as fh:
            fh.write(pretty + "\n")
        print(f"[ok] Wrote {target}")
        if args.claude_desktop:
            write_claude_desktop(mcp_config["mcpServers"]["subaiagents"])
        if args.claude_code:
            write_claude_code(mcp_config["mcpServers"]["subaiagents"])

    if args.persist:
        if adb_path:
            persist_windows_env("ADB_PATH", adb_path)
        if args.openai_key:
            persist_windows_env("OPENAI_API_KEY", args.openai_key)

    print()
    if codex_path:
        print("NOTE: sub-agent uses the Codex CLI (your ChatGPT subscription, no "
              "API cost). Run `codex login` once if you haven't.")
    elif not args.openai_key:
        print("NOTE: no sub-agent backend yet. For no API cost, install Codex CLI "
              "(npm i -g @openai/codex && codex login) and re-run. "
              "ADB features work regardless.")
    print()
    if not adb_path:
        print("NEXT: install Android platform-tools, then re-run this script "
              "(or pass --adb-path).")
    else:
        print("NEXT: restart Claude Code, run /mcp, and confirm 'subaiagents' is connected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
