"""Subprocess helpers for crash-recovery trials."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "run_graph_task.py"


def spawn_worker(
    task_id: str,
    *,
    database_url: str,
    hook_dir: Path | None = None,
    resume: str | None = None,
    checkpointer: str = "postgres",
) -> subprocess.Popen[str]:
    env = os.environ.copy()
    env["DATABASE_URL"] = database_url
    env["ENVIRONMENT"] = "test"
    env["PYTHONPATH"] = f"{ROOT / 'packages'}:{ROOT / 'apps'}:{ROOT}"
    if hook_dir is not None:
        env["SDLC_CHAOS_HOOK_DIR"] = str(hook_dir)
    args = [sys.executable, str(SCRIPT), "--task-id", task_id, "--checkpointer", checkpointer]
    if resume:
        args.extend(["--resume", resume])
    return subprocess.Popen(
        args,
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def wait_ready(hook_dir: Path, phase: str, timeout_s: float = 30.0) -> None:
    ready = hook_dir / f"{phase}.ready"
    deadline = time.time() + timeout_s
    while not ready.exists():
        if time.time() > deadline:
            raise TimeoutError(f"timed out waiting for {phase}.ready")
        time.sleep(0.02)


def send_go(hook_dir: Path, phase: str) -> None:
    (hook_dir / f"{phase}.go").write_text("1", encoding="utf-8")


def sigkill(proc: subprocess.Popen[str]) -> None:
    if proc.poll() is not None:
        return
    proc.send_signal(signal.SIGKILL)
    proc.wait(timeout=10)


def wait_exit(proc: subprocess.Popen[str], timeout_s: float = 60.0) -> int:
    try:
        return proc.wait(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        sigkill(proc)
        raise
