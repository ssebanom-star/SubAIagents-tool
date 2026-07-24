"""Tests for the generic background job manager (no adb/device needed)."""

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from subaiagents.procmon import JobManager  # noqa: E402


def _py(code: str) -> list:
    return [sys.executable, "-u", "-c", code]


def test_bg_run_captures_and_finishes():
    mgr = JobManager()
    res = mgr.run(_py("print('hello'); print('world')"))
    assert res["ok"]
    job = mgr.get(res["job_id"])
    done = job.wait(timeout=5)
    assert done["finished"] and job.returncode == 0
    assert "hello" in job.tail(10) and "world" in job.tail(10)


def test_bg_output_cursor_advances():
    mgr = JobManager()
    res = mgr.run(_py("import time\nfor i in range(3):\n print(i, flush=True)\n time.sleep(0.05)"))
    job = mgr.get(res["job_id"])
    job.wait(timeout=5)
    first = job.read_new()
    assert first["count"] == 3
    second = job.read_new()
    assert second["count"] == 0


def test_bg_stop_kills_long_job():
    mgr = JobManager()
    res = mgr.run(_py("import time\nwhile True:\n time.sleep(0.1)"))
    job = mgr.get(res["job_id"])
    time.sleep(0.2)
    assert job.alive
    out = mgr.stop(res["job_id"])
    assert out["ok"] and out["stopped"]
    assert not job.alive


def test_bg_list_reports_jobs():
    mgr = JobManager()
    r = mgr.run(_py("print('x')"))
    mgr.get(r["job_id"]).wait(timeout=5)
    listing = mgr.list()
    assert listing["count"] >= 1
    assert any(j["job_id"] == r["job_id"] for j in listing["jobs"])


def test_bad_command_returns_error():
    mgr = JobManager()
    res = mgr.run("this_command_should_not_exist_12345 --nope")
    # Either fails to start (ok False) or starts and exits nonzero quickly.
    if res["ok"]:
        job = mgr.get(res["job_id"])
        job.wait(timeout=5)
        assert job.returncode not in (0, None)
    else:
        assert "error" in res
