"""Real-time logcat monitoring.

MCP tools are request/response, so continuous streaming can't be pushed to
the client. Instead we run ``adb logcat`` as a background process per session,
buffer its lines in a ring buffer, and expose poll / watch / analyze tools:

  * start   -> spawn a background logcat, return a session id
  * read    -> return only lines new since the last read (cursor advances)
  * tail    -> peek the last N lines without moving the cursor
  * watch   -> block (bounded) until a regex matches in incoming lines
  * analyze -> hand recent lines to the ChatGPT sub-agent for a verdict
  * stop / list / clear
"""

from __future__ import annotations

import collections
import itertools
import re
import subprocess
import threading
import time
import uuid
from typing import Optional

from . import adb, config


class LogSession:
    """A single background ``adb logcat`` capture."""

    def __init__(self, cmd: list[str], serial: Optional[str],
                 filter_spec: str) -> None:
        self.id = uuid.uuid4().hex[:8]
        self.cmd = cmd
        self.serial = serial
        self.filter_spec = filter_spec
        self.started_at = time.time()
        self.proc: Optional[subprocess.Popen] = None
        self._thread: Optional[threading.Thread] = None
        self._buffer: "collections.deque[tuple[int, str]]" = collections.deque(
            maxlen=config.LOG_BUFFER_LINES
        )
        self._seq = itertools.count()
        self._last_read_seq = -1
        self._lock = threading.Lock()
        self.error: Optional[str] = None

    # -- lifecycle ---------------------------------------------------------

    def start(self) -> None:
        try:
            self.proc = subprocess.Popen(
                self.cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except Exception as exc:  # noqa: BLE001
            self.error = f"Failed to start logcat: {exc}"
            return
        self._thread = threading.Thread(target=self._reader, daemon=True)
        self._thread.start()

    def _reader(self) -> None:
        assert self.proc is not None and self.proc.stdout is not None
        try:
            for line in self.proc.stdout:
                with self._lock:
                    self._buffer.append((next(self._seq), line.rstrip("\n")))
        except Exception as exc:  # noqa: BLE001 - reader thread must not crash silently
            self.error = f"Reader stopped: {exc}"

    @property
    def alive(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def stop(self) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:  # pragma: no cover - defensive
                self.proc.kill()

    # -- data access -------------------------------------------------------

    def _snapshot(self) -> list[tuple[int, str]]:
        with self._lock:
            return list(self._buffer)

    def read_new(self, max_lines: int = 500) -> dict:
        """Return lines captured since the previous read; advance the cursor."""
        with self._lock:
            items = [it for it in self._buffer if it[0] > self._last_read_seq]
            dropped = 0
            if self._buffer:
                oldest = self._buffer[0][0]
                if oldest > self._last_read_seq + 1 and self._last_read_seq >= 0:
                    dropped = oldest - (self._last_read_seq + 1)
            if items:
                trimmed = items[-max_lines:] if len(items) > max_lines else items
                self._last_read_seq = self._buffer[-1][0]
            else:
                trimmed = []
        return {
            "session_id": self.id,
            "alive": self.alive,
            "new_lines": [l for _, l in trimmed],
            "count": len(trimmed),
            "dropped": dropped,
            "error": self.error,
        }

    def tail(self, lines: int = 100) -> list[str]:
        snap = self._snapshot()
        return [l for _, l in snap[-lines:]]

    def watch(self, pattern: str, timeout: int) -> dict:
        """Block until `pattern` (regex) appears in new lines or timeout."""
        timeout = max(1, min(timeout, config.LOG_WATCH_MAX_TIMEOUT))
        try:
            rx = re.compile(pattern)
        except re.error as exc:
            return {"ok": False, "error": f"Invalid regex: {exc}"}

        deadline = time.time() + timeout
        # Start scanning from the current cursor without consuming it wholesale.
        with self._lock:
            scan_from = self._last_read_seq

        matched: list[str] = []
        while time.time() < deadline:
            with self._lock:
                new = [it for it in self._buffer if it[0] > scan_from]
                if new:
                    scan_from = new[-1][0]
            for _, line in new:
                if rx.search(line):
                    matched.append(line)
            if matched:
                with self._lock:
                    self._last_read_seq = max(self._last_read_seq, scan_from)
                return {
                    "ok": True,
                    "matched": True,
                    "session_id": self.id,
                    "matches": matched[:50],
                    "match_count": len(matched),
                }
            if not self.alive:
                break
            time.sleep(0.3)

        return {
            "ok": True,
            "matched": False,
            "session_id": self.id,
            "alive": self.alive,
            "waited_seconds": timeout,
        }


class LogMonitor:
    """Registry of active log sessions."""

    def __init__(self) -> None:
        self._sessions: dict[str, LogSession] = {}
        self._lock = threading.Lock()

    def start(self, filter_spec: str = "", serial: Optional[str] = None,
              clear_first: bool = True) -> dict:
        chosen = serial or config.ADB_DEFAULT_SERIAL or None
        try:
            base = [adb.find_adb()]
        except adb.AdbError as exc:
            return {"ok": False, "error": str(exc)}
        if chosen:
            base += ["-s", chosen]

        if clear_first:
            subprocess.run(base + ["logcat", "-c"], capture_output=True,
                           text=True, timeout=config.ADB_TIMEOUT)

        cmd = base + ["logcat", "-v", "threadtime"]
        if filter_spec:
            cmd += filter_spec.split()

        session = LogSession(cmd, chosen, filter_spec)
        session.start()
        if session.error:
            return {"ok": False, "error": session.error}
        with self._lock:
            self._sessions[session.id] = session
        return {
            "ok": True,
            "session_id": session.id,
            "serial": chosen,
            "filter_spec": filter_spec,
            "note": "Use adb_logcat_read to poll new lines, adb_logcat_watch to "
                    "wait for a pattern, or adb_logcat_analyze to have GPT judge.",
        }

    def get(self, session_id: str) -> Optional[LogSession]:
        with self._lock:
            return self._sessions.get(session_id)

    def stop(self, session_id: str) -> dict:
        session = self.get(session_id)
        if not session:
            return {"ok": False, "error": f"No such session: {session_id}"}
        session.stop()
        with self._lock:
            self._sessions.pop(session_id, None)
        return {"ok": True, "session_id": session_id, "stopped": True}

    def list(self) -> dict:
        with self._lock:
            sessions = list(self._sessions.values())
        return {
            "ok": True,
            "count": len(sessions),
            "sessions": [
                {
                    "session_id": s.id,
                    "serial": s.serial,
                    "filter_spec": s.filter_spec,
                    "alive": s.alive,
                    "buffered_lines": len(s._snapshot()),
                    "uptime_seconds": round(time.time() - s.started_at, 1),
                    "error": s.error,
                }
                for s in sessions
            ],
        }


# Module-level singleton used by the MCP tools.
monitor = LogMonitor()
