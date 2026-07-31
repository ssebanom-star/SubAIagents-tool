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
from .logmon import monitor as _monitor
from .procmon import manager as _jobs

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
# ADB automation / repeated-execution tools
# --------------------------------------------------------------------------

@mcp.tool()
def adb_wait_for_device(timeout: int = 60, wait_for_boot: bool = False,
                        serial: Optional[str] = None) -> dict:
    """Block until the device is connected (and optionally fully booted).

    Use in automation flows that continue after a reboot/reconnect.
    """
    return _adb.wait_for_device(timeout=timeout, wait_for_boot=wait_for_boot,
                                serial=serial)


@mcp.tool()
def adb_start_app(package: str, activity: str = "",
                  serial: Optional[str] = None) -> dict:
    """Launch an app by package (LAUNCHER intent), or a specific activity."""
    return _adb.start_app(package, activity=activity, serial=serial)


@mcp.tool()
def adb_stop_app(package: str, serial: Optional[str] = None) -> dict:
    """Force-stop an app."""
    return _adb.stop_app(package, serial=serial)


@mcp.tool()
def adb_clear_app(package: str, serial: Optional[str] = None) -> dict:
    """Clear an app's data (fresh state between repeated test runs)."""
    return _adb.clear_app(package, serial=serial)


@mcp.tool()
def adb_getprop(prop: str = "", serial: Optional[str] = None) -> dict:
    """Read a system property (all properties if `prop` omitted)."""
    return _adb.getprop(prop=prop, serial=serial)


@mcp.tool()
def adb_repeat_shell(command: str, times: int = 3, interval_sec: float = 1.0,
                     stop_on_error: bool = False,
                     serial: Optional[str] = None) -> dict:
    """Run a shell command repeatedly, collecting each run's output.

    Good for polling, monitoring, or flakiness checks. `times` is capped by
    SUBAI_REPEAT_MAX_TIMES.
    """
    return _adb.repeat_shell(command, times=times, interval_sec=interval_sec,
                             stop_on_error=stop_on_error, serial=serial)


@mcp.tool()
def adb_screenrecord(seconds: int = 10, filename: str = "",
                     serial: Optional[str] = None) -> dict:
    """Record the screen for `seconds` and pull the mp4 to the host.

    Blocks for ~`seconds` (max 180). For long unattended captures, run
    `adb shell screenrecord ...` through bg_run instead.
    """
    return _adb.screenrecord(seconds=seconds, filename=filename, serial=serial)


# --------------------------------------------------------------------------
# Background command tools (offload long-running commands)
# --------------------------------------------------------------------------

@mcp.tool()
def bg_run(command: str, use_shell: bool = False, cwd: str = "") -> dict:
    """Start a command in the background; returns a job_id.

    Fire-and-continue for anything long-running (adb screenrecord, a build,
    `adb shell top`, etc.). Poll it with bg_output, block with bg_wait, and
    stop it with bg_stop.

    Args:
        command: Command line (split like a shell unless use_shell=True).
        use_shell: Run through the OS shell (enables pipes/redirection).
        cwd: Optional working directory.
    """
    return _jobs.run(command, use_shell=use_shell, cwd=cwd or None)


@mcp.tool()
def bg_output(job_id: str, max_lines: int = 500) -> dict:
    """Return output captured since the last read (cursor advances)."""
    job = _jobs.get(job_id)
    if not job:
        return {"ok": False, "error": f"No such job: {job_id}"}
    return job.read_new(max_lines=max_lines)


@mcp.tool()
def bg_wait(job_id: str, timeout: int = 30) -> dict:
    """Block until the job finishes or timeout (bounded by SUBAI_BG_WAIT_MAX_TIMEOUT)."""
    job = _jobs.get(job_id)
    if not job:
        return {"ok": False, "error": f"No such job: {job_id}"}
    return job.wait(timeout=timeout)


@mcp.tool()
def bg_list() -> dict:
    """List active/known background jobs."""
    return _jobs.list()


@mcp.tool()
def bg_stop(job_id: str) -> dict:
    """Stop and remove a background job."""
    return _jobs.stop(job_id)


# --------------------------------------------------------------------------
# Real-time log monitoring tools
# --------------------------------------------------------------------------

@mcp.tool()
def adb_logcat_start(filter_spec: str = "", serial: Optional[str] = None,
                     clear_first: bool = True) -> dict:
    """Start a background real-time logcat session; returns a session_id.

    The session keeps capturing logs in the background. Poll it with
    adb_logcat_read, wait for a pattern with adb_logcat_watch, or have GPT
    judge it with adb_logcat_analyze.

    Args:
        filter_spec: Optional logcat filter, e.g. "MyTag:D *:S" or "*:E".
        serial: Optional device serial.
        clear_first: Clear the log buffer before starting (fresh capture).
    """
    return _monitor.start(filter_spec=filter_spec, serial=serial,
                          clear_first=clear_first)


@mcp.tool()
def adb_logcat_read(session_id: str, max_lines: int = 500) -> dict:
    """Return only the log lines captured since the previous read (cursor advances)."""
    session = _monitor.get(session_id)
    if not session:
        return {"ok": False, "error": f"No such session: {session_id}"}
    return session.read_new(max_lines=max_lines)


@mcp.tool()
def adb_logcat_tail(session_id: str, lines: int = 100) -> dict:
    """Peek the last N buffered lines without moving the read cursor."""
    session = _monitor.get(session_id)
    if not session:
        return {"ok": False, "error": f"No such session: {session_id}"}
    return {"ok": True, "session_id": session_id, "alive": session.alive,
            "lines": session.tail(lines)}


@mcp.tool()
def adb_logcat_watch(session_id: str, pattern: str, timeout: int = 30) -> dict:
    """Block until a regex pattern appears in incoming logs, or timeout.

    Useful for "wait until a crash / specific event happens". Bounded by
    SUBAI_LOG_WATCH_MAX_TIMEOUT.
    """
    session = _monitor.get(session_id)
    if not session:
        return {"ok": False, "error": f"No such session: {session_id}"}
    return session.watch(pattern=pattern, timeout=timeout)


@mcp.tool()
def adb_logcat_analyze(session_id: str, question: str = "", lines: int = 300,
                       model: str = "", timeout: int = 0) -> dict:
    """Hand recent logs to the ChatGPT sub-agent to read and judge.

    Reads the last `lines` from the session and asks ChatGPT for a verdict
    (severity, summary, likely root cause, next step). This offloads the
    token-heavy log scanning from Claude — only the conclusion comes back.

    Args:
        session_id: The logcat session to analyze.
        question: Optional specific question (e.g. "왜 앱이 죽었어?").
        lines: How many recent lines to feed to GPT.
        model: Optional model override.
        timeout: Seconds to allow (0 = default); raise for large log dumps.
    """
    session = _monitor.get(session_id)
    if not session:
        return {"ok": False, "error": f"No such session: {session_id}"}
    tail = session.tail(lines)
    if not tail:
        return {"ok": True, "session_id": session_id,
                "note": "No log lines captured yet.", "content": ""}
    result = _chatgpt.analyze_logs("\n".join(tail), question=question,
                                   model=model, timeout=timeout)
    result["session_id"] = session_id
    result["lines_analyzed"] = len(tail)
    return result


@mcp.tool()
def adb_logcat_stop(session_id: str) -> dict:
    """Stop and remove a background logcat session."""
    return _monitor.stop(session_id)


@mcp.tool()
def adb_logcat_list() -> dict:
    """List active background logcat sessions."""
    return _monitor.list()


# --------------------------------------------------------------------------
# ChatGPT sub-agent tools
# --------------------------------------------------------------------------

@mcp.tool()
def chatgpt_code(task: str, context: str = "", language: str = "",
                 model: str = "", timeout: int = 0) -> dict:
    """Delegate an auxiliary coding task to ChatGPT to save Claude tokens.

    Use for boilerplate, scaffolding, or self-contained helpers where Claude
    only needs the finished code back rather than generating it itself.

    Args:
        task: What to build.
        context: Constraints, signatures, or surrounding code to respect.
        language: Target language (e.g. "python", "kotlin").
        model: Optional model override (defaults to the configured model).
        timeout: Seconds to allow (0 = default). Set higher for big/complex
            tasks that need more time; capped by SUBAI_CODEX_MAX_TIMEOUT.
    """
    return _chatgpt.code(task, context=context, language=language, model=model,
                         timeout=timeout)


@mcp.tool()
def chatgpt_ask(prompt: str, model: str = "", timeout: int = 0) -> dict:
    """Delegate a general question/lookup to ChatGPT to save Claude tokens.

    `timeout` (seconds, 0 = default) lets you allow more time for a hard query.
    """
    return _chatgpt.ask(prompt, model=model, timeout=timeout)


@mcp.tool()
def chatgpt_review(code_snippet: str, focus: str = "", model: str = "",
                   timeout: int = 0) -> dict:
    """Delegate a code review pass to ChatGPT (`timeout` seconds, 0 = default)."""
    return _chatgpt.review(code_snippet, focus=focus, model=model,
                           timeout=timeout)


@mcp.tool()
def chatgpt_set_model(model: str) -> dict:
    """Set the default model the sub-agent uses for later calls.

    Applies to both backends: for Codex it maps to `codex -m <model>`
    (e.g. "gpt-5-codex"), for the API it's the OpenAI model id (e.g. "gpt-4o").
    Pass an empty string to clear the override and use the configured default.
    Per-call `model=` arguments still take precedence over this.
    """
    return _chatgpt.set_model(model)


@mcp.tool()
def chatgpt_get_model() -> dict:
    """Show the active sub-agent backend and its effective default model."""
    return _chatgpt.get_model()


@mcp.tool()
def chatgpt_analyze_logs(logs: str, question: str = "", model: str = "",
                         timeout: int = 0) -> dict:
    """Have ChatGPT read & judge arbitrary log text (not tied to a session).

    Use when you already have log lines (from adb_logcat, a file, etc.) and
    want GPT to do the reading/judging to save Claude tokens. `timeout` seconds
    (0 = default) can be raised for large log dumps.
    """
    return _chatgpt.analyze_logs(logs, question=question, model=model,
                                 timeout=timeout)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
