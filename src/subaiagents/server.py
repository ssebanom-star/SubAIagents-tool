"""subaiagents MCP server.

Exposes two tool groups to Claude Code over stdio:
  * adb_*      — control connected Android devices via adb.
  * chatgpt_*  — delegate auxiliary coding/lookups to ChatGPT to save tokens.

Run: python -m subaiagents.server
"""

from __future__ import annotations

from typing import Optional

from mcp.server.fastmcp import FastMCP

from . import adb as _adb
from . import chatgpt as _chatgpt

mcp = FastMCP("subaiagents")


# --------------------------------------------------------------------------
# ADB tools
# --------------------------------------------------------------------------

@mcp.tool()
def adb_devices() -> dict:
    """List connected Android devices and their states."""
    return _adb.devices()


@mcp.tool()
def adb_shell(command: str, serial: Optional[str] = None) -> dict:
    """Run a shell command on a connected device.

    Args:
        command: The shell command line to execute on the device.
        serial: Optional device serial (uses default device if omitted).
    """
    return _adb.shell(command, serial=serial)


@mcp.tool()
def adb_install(apk_path: str, serial: Optional[str] = None,
                replace: bool = True, grant_permissions: bool = False) -> dict:
    """Install an APK onto a device."""
    return _adb.install(apk_path, serial=serial, replace=replace,
                        grant_permissions=grant_permissions)


@mcp.tool()
def adb_uninstall(package: str, serial: Optional[str] = None,
                  keep_data: bool = False) -> dict:
    """Uninstall a package from a device."""
    return _adb.uninstall(package, serial=serial, keep_data=keep_data)


@mcp.tool()
def adb_push(local: str, remote: str, serial: Optional[str] = None) -> dict:
    """Copy a file from the host to the device."""
    return _adb.push(local, remote, serial=serial)


@mcp.tool()
def adb_pull(remote: str, local: str, serial: Optional[str] = None) -> dict:
    """Copy a file from the device to the host."""
    return _adb.pull(remote, local, serial=serial)


@mcp.tool()
def adb_logcat(lines: int = 200, filter_spec: str = "",
               serial: Optional[str] = None) -> dict:
    """Fetch a bounded snapshot of logcat.

    Args:
        lines: Number of trailing lines to return.
        filter_spec: Optional logcat filter, e.g. "MyTag:D *:S".
        serial: Optional device serial.
    """
    return _adb.logcat(lines=lines, filter_spec=filter_spec, serial=serial)


@mcp.tool()
def adb_packages(filter_text: str = "", third_party_only: bool = False,
                 serial: Optional[str] = None) -> dict:
    """List installed packages (optionally filtered)."""
    return _adb.packages(filter_text=filter_text,
                        third_party_only=third_party_only, serial=serial)


@mcp.tool()
def adb_current_app(serial: Optional[str] = None) -> dict:
    """Report the current foreground app/activity."""
    return _adb.current_app(serial=serial)


@mcp.tool()
def adb_screenshot(filename: str = "", serial: Optional[str] = None) -> dict:
    """Capture a screenshot and save it on the host."""
    return _adb.screenshot(filename=filename, serial=serial)


@mcp.tool()
def adb_tap(x: int, y: int, serial: Optional[str] = None) -> dict:
    """Tap the screen at (x, y)."""
    return _adb.input_event("tap", serial=serial, x=x, y=y)


@mcp.tool()
def adb_swipe(x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300,
             serial: Optional[str] = None) -> dict:
    """Swipe from (x1, y1) to (x2, y2)."""
    return _adb.input_event("swipe", serial=serial, x1=x1, y1=y1, x2=x2, y2=y2,
                           duration_ms=duration_ms)


@mcp.tool()
def adb_input_text(text: str, serial: Optional[str] = None) -> dict:
    """Type text into the focused field."""
    return _adb.input_event("text", serial=serial, text=text)


@mcp.tool()
def adb_keyevent(keycode: int, serial: Optional[str] = None) -> dict:
    """Send a key event (e.g. 4 = BACK, 3 = HOME, 26 = POWER)."""
    return _adb.input_event("keyevent", serial=serial, keycode=keycode)


@mcp.tool()
def adb_reboot(mode: str = "", serial: Optional[str] = None) -> dict:
    """Reboot the device. mode: '' | 'recovery' | 'bootloader'."""
    return _adb.reboot(mode=mode, serial=serial)


@mcp.tool()
def adb_connect(host_port: str) -> dict:
    """Connect to a device over TCP/IP, e.g. '192.168.0.10:5555'."""
    return _adb.connect(host_port)


@mcp.tool()
def adb_disconnect(host_port: str = "") -> dict:
    """Disconnect a TCP/IP device (all if host_port omitted)."""
    return _adb.disconnect(host_port)


# --------------------------------------------------------------------------
# ChatGPT sub-agent tools
# --------------------------------------------------------------------------

@mcp.tool()
def chatgpt_code(task: str, context: str = "", language: str = "",
                 model: str = "") -> dict:
    """Delegate an auxiliary coding task to ChatGPT to save Claude tokens.

    Use for boilerplate, scaffolding, or self-contained helpers where Claude
    only needs the finished code back rather than generating it itself.

    Args:
        task: What to build.
        context: Constraints, signatures, or surrounding code to respect.
        language: Target language (e.g. "python", "kotlin").
        model: Optional model override (defaults to the configured model).
    """
    return _chatgpt.code(task, context=context, language=language, model=model)


@mcp.tool()
def chatgpt_ask(prompt: str, model: str = "") -> dict:
    """Delegate a general question/lookup to ChatGPT to save Claude tokens."""
    return _chatgpt.ask(prompt, model=model)


@mcp.tool()
def chatgpt_review(code_snippet: str, focus: str = "", model: str = "") -> dict:
    """Delegate a code review pass to ChatGPT."""
    return _chatgpt.review(code_snippet, focus=focus, model=model)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
