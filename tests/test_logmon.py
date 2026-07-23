"""Tests for the real-time log monitor.

We avoid adb entirely by driving LogSession with a portable subprocess that
emits known lines, then verifying buffering, the read cursor, tail, and watch.
"""

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from subaiagents.logmon import LogSession  # noqa: E402


def _emitter_cmd(lines, delay=0.0):
    """A cross-platform command that prints `lines` then exits."""
    script = (
        "import sys,time\n"
        f"for i in range({lines}):\n"
        "    print('line %d' % i, flush=True)\n"
        f"    time.sleep({delay})\n"
    )
    return [sys.executable, "-u", "-c", script]


def _make_session(lines, delay=0.0):
    session = LogSession(_emitter_cmd(lines, delay), serial=None, filter_spec="")
    session.start()
    return session


def _wait_lines(session, n, timeout=5):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if len(session.tail(10_000)) >= n:
            return True
        time.sleep(0.02)
    return False


def test_buffer_captures_lines():
    s = _make_session(5)
    assert _wait_lines(s, 5), "expected 5 lines buffered"
    assert s.tail(10) == [f"line {i}" for i in range(5)]
    s.stop()


def test_read_cursor_advances():
    s = _make_session(4)
    assert _wait_lines(s, 4)
    first = s.read_new()
    assert first["count"] == 4
    assert first["new_lines"] == [f"line {i}" for i in range(4)]
    # Second read has nothing new.
    second = s.read_new()
    assert second["count"] == 0
    assert second["new_lines"] == []
    s.stop()


def test_tail_does_not_move_cursor():
    s = _make_session(3)
    assert _wait_lines(s, 3)
    _ = s.tail(3)  # peek
    read = s.read_new()
    assert read["count"] == 3  # tail did not consume
    s.stop()


def test_watch_matches_pattern():
    # Emit slowly so watch sees lines arrive over time.
    s = _make_session(6, delay=0.05)
    result = s.watch(pattern=r"line 3", timeout=5)
    assert result["ok"] and result["matched"]
    assert any("line 3" in m for m in result["matches"])
    s.stop()


def test_watch_times_out_without_match():
    s = _make_session(3)
    assert _wait_lines(s, 3)
    result = s.watch(pattern=r"NEVER_APPEARS", timeout=1)
    assert result["ok"] and result["matched"] is False
    s.stop()


def test_invalid_regex_reported():
    s = _make_session(1)
    result = s.watch(pattern="[unclosed", timeout=1)
    assert result["ok"] is False and "regex" in result["error"].lower()
    s.stop()
