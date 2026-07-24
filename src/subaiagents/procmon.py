"""Generic background-command runner.

Lets Claude fire off a long-running command (adb or anything else), keep
working, and later poll its output, wait for it, or stop it — instead of
blocking a tool call for the whole duration.

  * bg_run   -> start a command in the background, return a job_id
  * bg_output-> return output captured since the last read (cursor advances)
  * bg_wait  -> block (bounded) until the job finishes
  * bg_list / bg_stop
"""

from __future__ import annotations

import collections
import itertools
import shlex
import subprocess
import threading
import time
import uuid
from typing import Optional

from . import config


class BackgroundJob:
    """A single background command with a combined stdout+stderr ring buffer."""

    def __init__(self, cmd, use_shell: bool, cwd: Optional[str]) -> None:
        self.id = uuid.uuid4().hex[:8]
        self.cmd = cmd
        self.use_shell = use_shell
        self.cwd = cwd
        self.started_at = time.time()
        self.finished_at: Optional[float] = None
        self.returncode: Optional[int] = None
        self.error: Optional[str] = None
        self.proc: Optional[subprocess.Popen] = None
        self._thread: Optional[threading.Thread] = None
        self._buffer: "collections.deque[tuple[int, str]]" = collections.deque(
            maxlen=config.BG_BUFFER_LINES
        )
        self._seq = itertools.count()
        self._last_read_seq = -1
        self._lock = threading.Lock()

    def start(self) -> None:
        try:
            self.proc = subprocess.Popen(
                self.cmd,
                shell=self.use_shell,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                text=True,
                bufsize=1,
                cwd=self.cwd or None,
            )
        except Exception as exc:  # noqa: BLE001
            self.error = f"Failed to start: {exc}"
            self.finished_at = time.time()
            return
        self._thread = threading.Thread(target=self._reader, daemon=True)
        self._thread.start()

    def _reader(self) -> None:
        assert self.proc is not None and self.proc.stdout is not None
        try:
            for line in self.proc.stdout:
                with self._lock:
                    self._buffer.append((next(self._seq), line.rstrip("\n")))
        except Exception as exc:  # noqa: BLE001
            self.error = f"Reader stopped: {exc}"
        finally:
            self.returncode = self.proc.wait()
            self.finished_at = time.time()

    @property
    def alive(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def read_new(self, max_lines: int = 500) -> dict:
        with self._lock:
            items = [it for it in self._buffer if it[0] > self._last_read_seq]
            if items:
                trimmed = items[-max_lines:] if len(items) > max_lines else items
                self._last_read_seq = self._buffer[-1][0]
            else:
                trimmed = []
        return {
            "ok": True,
            "job_id": self.id,
            "alive": self.alive,
            "returncode": self.returncode,
            "new_output": [l for _, l in trimmed],
            "count": len(trimmed),
            "error": self.error,
        }

    def tail(self, lines: int = 200) -> list:
        with self._lock:
            snap = list(self._buffer)
        return [l for _, l in snap[-lines:]]

    def wait(self, timeout: int) -> dict:
        timeout = max(1, min(timeout, config.BG_WAIT_MAX_TIMEOUT))
        deadline = time.time() + timeout
        while time.time() < deadline:
            if not self.alive:
                break
            time.sleep(0.2)
        return {
            "ok": True,
            "job_id": self.id,
            "finished": not self.alive,
            "returncode": self.returncode,
            "output_tail": self.tail(200),
            "error": self.error,
        }

    def stop(self) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:  # pragma: no cover - defensive
                self.proc.kill()


class JobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, BackgroundJob] = {}
        self._lock = threading.Lock()

    def run(self, command, use_shell: bool = False,
            cwd: Optional[str] = None) -> dict:
        if isinstance(command, str) and not use_shell:
            try:
                cmd = shlex.split(command, posix=(subprocess.os.name != "nt"))
            except ValueError as exc:
                return {"ok": False, "error": f"Could not parse command: {exc}"}
        else:
            cmd = command
        job = BackgroundJob(cmd, use_shell=use_shell, cwd=cwd)
        job.start()
        if job.error:
            return {"ok": False, "error": job.error}
        with self._lock:
            self._jobs[job.id] = job
        return {"ok": True, "job_id": job.id, "command": command,
                "note": "Poll with bg_output, block with bg_wait, stop with bg_stop."}

    def get(self, job_id: str) -> Optional[BackgroundJob]:
        with self._lock:
            return self._jobs.get(job_id)

    def stop(self, job_id: str) -> dict:
        job = self.get(job_id)
        if not job:
            return {"ok": False, "error": f"No such job: {job_id}"}
        job.stop()
        with self._lock:
            self._jobs.pop(job_id, None)
        return {"ok": True, "job_id": job_id, "stopped": True,
                "returncode": job.returncode}

    def list(self) -> dict:
        with self._lock:
            jobs = list(self._jobs.values())
        return {
            "ok": True,
            "count": len(jobs),
            "jobs": [
                {
                    "job_id": j.id,
                    "command": j.cmd,
                    "alive": j.alive,
                    "returncode": j.returncode,
                    "uptime_seconds": round(time.time() - j.started_at, 1),
                    "buffered_lines": len(j.tail(10_000)),
                    "error": j.error,
                }
                for j in jobs
            ],
        }


# Module-level singleton used by the MCP tools.
manager = JobManager()
