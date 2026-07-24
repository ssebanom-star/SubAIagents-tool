"""Unit tests that exercise adb command assembly & parsing without a device.

We monkeypatch the subprocess boundary so tests run anywhere.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import subprocess  # noqa: E402

import pytest  # noqa: E402

from subaiagents import adb, config  # noqa: E402


class FakeCompleted:
    def __init__(self, stdout="", stderr="", returncode=0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


@pytest.fixture(autouse=True)
def _fake_adb(monkeypatch):
    # Pretend adb lives at a fixed path so find_adb() succeeds everywhere.
    monkeypatch.setattr(adb, "find_adb", lambda: "/usr/bin/adb")
    monkeypatch.setattr(config, "ADB_DEFAULT_SERIAL", "")


def _capture_cmd(monkeypatch, stdout="", returncode=0):
    captured = {}

    def fake_run(cmd, capture_output, text, timeout):
        captured["cmd"] = cmd
        return FakeCompleted(stdout=stdout, returncode=returncode)

    monkeypatch.setattr(subprocess, "run", fake_run)
    return captured


def test_devices_parsing(monkeypatch):
    out = (
        "List of devices attached\n"
        "ABC123   device product:sdk model:Pixel\n"
        "10.0.0.2:5555  offline\n"
    )
    _capture_cmd(monkeypatch, stdout=out)
    result = adb.devices()
    assert result["ok"]
    assert len(result["devices"]) == 2
    assert result["devices"][0]["serial"] == "ABC123"
    assert result["devices"][0]["state"] == "device"
    assert result["devices"][0]["model"] == "Pixel"
    assert result["devices"][1]["state"] == "offline"


def test_shell_command_assembly(monkeypatch):
    captured = _capture_cmd(monkeypatch, stdout="hello")
    adb.shell("echo hello", serial="ABC123")
    assert captured["cmd"] == ["/usr/bin/adb", "-s", "ABC123", "shell", "echo hello"]


def test_install_flags(monkeypatch):
    captured = _capture_cmd(monkeypatch)
    adb.install("/path/app.apk", replace=True, grant_permissions=True)
    assert captured["cmd"] == ["/usr/bin/adb", "install", "-r", "-g", "/path/app.apk"]


def test_input_tap_and_text(monkeypatch):
    captured = _capture_cmd(monkeypatch)
    adb.input_event("tap", x=10, y=20)
    assert captured["cmd"] == ["/usr/bin/adb", "shell", "input", "tap", "10", "20"]

    captured = _capture_cmd(monkeypatch)
    adb.input_event("text", text="hello world")
    # spaces escaped to %s for `input text`
    assert captured["cmd"][-1] == "hello%sworld"


def test_packages_filter(monkeypatch):
    out = "package:com.foo.app\npackage:com.bar.tool\npackage:com.foo.other\n"
    _capture_cmd(monkeypatch, stdout=out)
    result = adb.packages(filter_text="foo")
    assert result["packages"] == ["com.foo.app", "com.foo.other"]


def test_timeout_returns_structured(monkeypatch):
    def fake_run(cmd, capture_output, text, timeout):
        raise subprocess.TimeoutExpired(cmd, timeout)

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = adb.shell("sleep 999")
    assert result["ok"] is False
    assert "timed out" in result["stderr"].lower()


def test_default_serial_used(monkeypatch):
    monkeypatch.setattr(config, "ADB_DEFAULT_SERIAL", "DEFAULT1")
    captured = _capture_cmd(monkeypatch)
    adb.shell("ls")
    assert captured["cmd"][:3] == ["/usr/bin/adb", "-s", "DEFAULT1"]


def test_start_app_launcher(monkeypatch):
    captured = _capture_cmd(monkeypatch)
    adb.start_app("com.example.app")
    assert captured["cmd"] == [
        "/usr/bin/adb", "shell", "monkey", "-p", "com.example.app",
        "-c", "android.intent.category.LAUNCHER", "1"]


def test_start_app_with_activity(monkeypatch):
    # A bare ".Activity" is composed into "package/.Activity" for `am start -n`.
    captured = _capture_cmd(monkeypatch)
    adb.start_app("com.example.app", activity=".MainActivity")
    assert captured["cmd"] == [
        "/usr/bin/adb", "shell", "am", "start", "-n",
        "com.example.app/.MainActivity"]
    # A fully-qualified component is passed through unchanged.
    captured = _capture_cmd(monkeypatch)
    adb.start_app("com.example.app", activity="com.other/.Act")
    assert captured["cmd"][-1] == "com.other/.Act"


def test_stop_and_clear_app(monkeypatch):
    captured = _capture_cmd(monkeypatch)
    adb.stop_app("com.example.app")
    assert captured["cmd"][-3:] == ["am", "force-stop", "com.example.app"]
    captured = _capture_cmd(monkeypatch)
    adb.clear_app("com.example.app")
    assert captured["cmd"][-3:] == ["pm", "clear", "com.example.app"]


def test_repeat_shell_collects_runs(monkeypatch):
    _capture_cmd(monkeypatch, stdout="ok")
    result = adb.repeat_shell("echo ok", times=4, interval_sec=0)
    assert result["executed"] == 4
    assert result["succeeded"] == 4
    assert [r["iteration"] for r in result["runs"]] == [1, 2, 3, 4]


def test_repeat_shell_caps_times(monkeypatch):
    monkeypatch.setattr(config, "REPEAT_MAX_TIMES", 5)
    _capture_cmd(monkeypatch, stdout="x")
    result = adb.repeat_shell("echo x", times=1000, interval_sec=0)
    assert result["executed"] == 5
