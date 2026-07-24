"""A thin, safe wrapper around the ``adb`` command-line tool.

Designed to run on Windows (adb.exe) as well as Linux/macOS. All public
functions return plain dicts so the MCP layer can serialize them directly.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import Optional

from . import config


class AdbError(RuntimeError):
    """Raised when adb cannot be located or a call fails hard."""


# Common Windows install locations checked when adb is not on PATH.
_WINDOWS_CANDIDATES = [
    r"C:\platform-tools\adb.exe",
    r"C:\adb\adb.exe",
    r"C:\Android\platform-tools\adb.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"),
    os.path.expandvars(r"%USERPROFILE%\AppData\Local\Android\Sdk\platform-tools\adb.exe"),
    os.path.expandvars(r"%APPDATA%\..\Local\Android\Sdk\platform-tools\adb.exe"),
    os.path.expandvars(r"%ANDROID_HOME%\platform-tools\adb.exe"),
    os.path.expandvars(r"%ANDROID_SDK_ROOT%\platform-tools\adb.exe"),
    os.path.expandvars(r"%ProgramFiles%\Android\platform-tools\adb.exe"),
    os.path.expandvars(r"%ProgramFiles(x86)%\Android\android-sdk\platform-tools\adb.exe"),
    os.path.expandvars(r"%USERPROFILE%\scoop\apps\adb\current\adb.exe"),
    os.path.expandvars(r"%ProgramData%\chocolatey\lib\adb\tools\platform-tools\adb.exe"),
    os.path.expandvars(r"%USERPROFILE%\Downloads\platform-tools\adb.exe"),
    # Linux/macOS common locations (harmless on Windows).
    "/usr/bin/adb",
    "/usr/local/bin/adb",
    os.path.expanduser("~/Android/Sdk/platform-tools/adb"),
    os.path.expanduser("~/Library/Android/sdk/platform-tools/adb"),
]


def find_adb() -> str:
    """Locate the adb executable.

    Order: explicit ADB_PATH env → PATH → common Windows locations.
    Raises AdbError with a helpful message if not found.
    """
    if config.ADB_PATH:
        if os.path.isfile(config.ADB_PATH):
            return config.ADB_PATH
        raise AdbError(
            f"ADB_PATH is set to '{config.ADB_PATH}' but no file exists there."
        )

    on_path = shutil.which("adb") or shutil.which("adb.exe")
    if on_path:
        return on_path

    for candidate in _WINDOWS_CANDIDATES:
        if candidate and os.path.isfile(candidate):
            return candidate

    raise AdbError(
        "Could not find adb. Install Android platform-tools and either add it "
        "to PATH or set the ADB_PATH environment variable "
        "(e.g. C:\\platform-tools\\adb.exe)."
    )


def _base_cmd(serial: Optional[str]) -> list[str]:
    cmd = [find_adb()]
    chosen = serial or config.ADB_DEFAULT_SERIAL
    if chosen:
        cmd += ["-s", chosen]
    return cmd


def _run(args: list[str], serial: Optional[str] = None,
         timeout: Optional[int] = None) -> dict:
    """Run an adb command and return a structured result dict."""
    cmd = _base_cmd(serial) + args
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout or config.ADB_TIMEOUT,
        )
    except FileNotFoundError as exc:  # pragma: no cover - defensive
        raise AdbError(f"adb executable not runnable: {exc}") from exc
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "command": " ".join(cmd),
            "returncode": None,
            "stdout": "",
            "stderr": f"Command timed out after {timeout or config.ADB_TIMEOUT}s",
        }

    return {
        "ok": proc.returncode == 0,
        "command": " ".join(cmd),
        "returncode": proc.returncode,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
    }


# --- Public operations -----------------------------------------------------

def devices() -> dict:
    """List connected devices with their state (device/offline/unauthorized)."""
    result = _run(["devices", "-l"])
    parsed = []
    if result["ok"]:
        for line in result["stdout"].splitlines()[1:]:  # skip header
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            entry = {"serial": parts[0], "state": parts[1] if len(parts) > 1 else "?"}
            for token in parts[2:]:
                if ":" in token:
                    k, v = token.split(":", 1)
                    entry[k] = v
            parsed.append(entry)
    result["devices"] = parsed
    return result


def shell(command: str, serial: Optional[str] = None) -> dict:
    """Run a shell command on the device."""
    # Pass the command as a single argument list to avoid host-side splitting.
    return _run(["shell", command], serial=serial)


def install(apk_path: str, serial: Optional[str] = None,
            replace: bool = True, grant_permissions: bool = False) -> dict:
    args = ["install"]
    if replace:
        args.append("-r")
    if grant_permissions:
        args.append("-g")
    args.append(apk_path)
    return _run(args, serial=serial, timeout=config.ADB_TIMEOUT * 3)


def uninstall(package: str, serial: Optional[str] = None,
              keep_data: bool = False) -> dict:
    args = ["uninstall"]
    if keep_data:
        args.append("-k")
    args.append(package)
    return _run(args, serial=serial)


def push(local: str, remote: str, serial: Optional[str] = None) -> dict:
    return _run(["push", local, remote], serial=serial,
                timeout=config.ADB_TIMEOUT * 3)


def pull(remote: str, local: str, serial: Optional[str] = None) -> dict:
    return _run(["pull", remote, local], serial=serial,
                timeout=config.ADB_TIMEOUT * 3)


def logcat(lines: int = 200, filter_spec: str = "",
           serial: Optional[str] = None) -> dict:
    """Grab a bounded snapshot of logcat (-d dumps and exits)."""
    args = ["logcat", "-d", "-t", str(lines)]
    if filter_spec:
        args += filter_spec.split()
    return _run(args, serial=serial)


def packages(filter_text: str = "", third_party_only: bool = False,
             serial: Optional[str] = None) -> dict:
    args = ["shell", "pm", "list", "packages"]
    if third_party_only:
        args.append("-3")
    result = _run(args, serial=serial)
    if result["ok"]:
        pkgs = [
            line.replace("package:", "").strip()
            for line in result["stdout"].splitlines()
            if line.strip()
        ]
        if filter_text:
            pkgs = [p for p in pkgs if filter_text.lower() in p.lower()]
        result["packages"] = pkgs
    return result


def current_app(serial: Optional[str] = None) -> dict:
    """Return the current foreground app/activity."""
    return _run(
        ["shell", "dumpsys activity activities | grep -E 'mResumedActivity|topResumedActivity'"],
        serial=serial,
    )


def screenshot(filename: str = "", serial: Optional[str] = None) -> dict:
    """Capture a screenshot and save it to the host screenshot directory."""
    import time

    os.makedirs(config.SCREENSHOT_DIR, exist_ok=True)
    if not filename:
        filename = f"screenshot_{int(time.time())}.png"
    local_path = os.path.join(config.SCREENSHOT_DIR, filename)
    remote_tmp = "/sdcard/__subai_shot.png"

    cap = _run(["shell", "screencap", "-p", remote_tmp], serial=serial)
    if not cap["ok"]:
        return cap
    result = pull(remote_tmp, local_path, serial=serial)
    _run(["shell", "rm", remote_tmp], serial=serial)  # best-effort cleanup
    result["saved_to"] = local_path if result["ok"] else None
    return result


def input_event(action: str, serial: Optional[str] = None, **params) -> dict:
    """UI input helper. action ∈ {tap, swipe, text, keyevent}."""
    action = action.lower()
    if action == "tap":
        args = ["shell", "input", "tap", str(params["x"]), str(params["y"])]
    elif action == "swipe":
        args = ["shell", "input", "swipe",
                str(params["x1"]), str(params["y1"]),
                str(params["x2"]), str(params["y2"]),
                str(params.get("duration_ms", 300))]
    elif action == "text":
        # Spaces must be escaped for `input text`.
        text = str(params["text"]).replace(" ", "%s")
        args = ["shell", "input", "text", text]
    elif action == "keyevent":
        args = ["shell", "input", "keyevent", str(params["keycode"])]
    else:
        raise AdbError(f"Unknown input action: {action}")
    return _run(args, serial=serial)


def reboot(mode: str = "", serial: Optional[str] = None) -> dict:
    """Reboot the device. mode ∈ {'', 'recovery', 'bootloader'}."""
    args = ["reboot"] + ([mode] if mode else [])
    return _run(args, serial=serial)


def connect(host_port: str) -> dict:
    """Connect to a device over TCP/IP (e.g. '192.168.0.10:5555')."""
    return _run(["connect", host_port])


def disconnect(host_port: str = "") -> dict:
    return _run(["disconnect"] + ([host_port] if host_port else []))


# --- Automation / repeated-execution helpers -------------------------------

def wait_for_device(timeout: int = 60, wait_for_boot: bool = False,
                    serial: Optional[str] = None) -> dict:
    """Block until the device is connected (and optionally fully booted).

    Handy in automation loops that reconnect after a reboot before continuing.
    """
    import time

    timeout = max(1, min(timeout, 600))
    result = _run(["wait-for-device"], serial=serial, timeout=timeout)
    if not result["ok"]:
        return result
    if wait_for_boot:
        deadline = time.time() + timeout
        while time.time() < deadline:
            boot = _run(["shell", "getprop", "sys.boot_completed"], serial=serial)
            if boot["ok"] and boot["stdout"].strip() == "1":
                result["boot_completed"] = True
                return result
            time.sleep(1)
        result["boot_completed"] = False
    return result


def start_app(package: str, activity: str = "", serial: Optional[str] = None) -> dict:
    """Launch an app. Uses the LAUNCHER intent when no activity is given."""
    if activity:
        component = activity if "/" in activity else f"{package}/{activity}"
        return _run(["shell", "am", "start", "-n", component], serial=serial)
    return _run(
        ["shell", "monkey", "-p", package,
         "-c", "android.intent.category.LAUNCHER", "1"],
        serial=serial,
    )


def stop_app(package: str, serial: Optional[str] = None) -> dict:
    """Force-stop an app."""
    return _run(["shell", "am", "force-stop", package], serial=serial)


def clear_app(package: str, serial: Optional[str] = None) -> dict:
    """Clear an app's data (factory-fresh state for repeated test runs)."""
    return _run(["shell", "pm", "clear", package], serial=serial)


def getprop(prop: str = "", serial: Optional[str] = None) -> dict:
    """Read a system property (or all properties if `prop` is empty)."""
    args = ["shell", "getprop"] + ([prop] if prop else [])
    return _run(args, serial=serial)


def repeat_shell(command: str, times: int = 3, interval_sec: float = 1.0,
                 serial: Optional[str] = None,
                 stop_on_error: bool = False) -> dict:
    """Run a shell command repeatedly, collecting each run's output.

    Suited to polling/monitoring or flakiness checks. `times` is capped by
    SUBAI_REPEAT_MAX_TIMES.
    """
    import time

    times = max(1, min(times, config.REPEAT_MAX_TIMES))
    interval_sec = max(0.0, min(interval_sec, 3600))
    runs = []
    for i in range(times):
        res = shell(command, serial=serial)
        runs.append({
            "iteration": i + 1,
            "ok": res["ok"],
            "returncode": res["returncode"],
            "stdout": res["stdout"],
            "stderr": res["stderr"],
        })
        if stop_on_error and not res["ok"]:
            break
        if i < times - 1:
            time.sleep(interval_sec)
    ok_count = sum(1 for r in runs if r["ok"])
    return {
        "ok": True,
        "command": command,
        "requested": times,
        "executed": len(runs),
        "succeeded": ok_count,
        "failed": len(runs) - ok_count,
        "runs": runs,
    }


def screenrecord(seconds: int = 10, filename: str = "",
                 serial: Optional[str] = None) -> dict:
    """Record the screen for `seconds`, then pull the mp4 to the host.

    Blocks for roughly `seconds`. For unattended long recordings, drive
    `adb shell screenrecord` via the background job tools instead.
    """
    import os
    import time

    seconds = max(1, min(seconds, 180))  # screenrecord hard limit is 180s
    os.makedirs(config.SCREENSHOT_DIR, exist_ok=True)
    if not filename:
        filename = f"screenrecord_{int(time.time())}.mp4"
    local_path = os.path.join(config.SCREENSHOT_DIR, filename)
    remote_tmp = "/sdcard/__subai_rec.mp4"

    rec = _run(
        ["shell", "screenrecord", "--time-limit", str(seconds), remote_tmp],
        serial=serial, timeout=seconds + 30,
    )
    if not rec["ok"]:
        return rec
    result = pull(remote_tmp, local_path, serial=serial)
    _run(["shell", "rm", remote_tmp], serial=serial)  # best-effort cleanup
    result["saved_to"] = local_path if result["ok"] else None
    return result
