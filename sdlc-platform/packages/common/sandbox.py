"""Ephemeral Docker sandbox — `final_plan.md` §B.6.

Runtime is Docker (solo-dev default). Changing this later belongs in a decisions log.

Every run is labeled with `sdlc.task_id` so traces (Section 05) can correlate.
Containers are removed in a `finally` block *and* started with `--rm`, so a host
crash still does not leave leftovers in the common case.
"""

from __future__ import annotations

import re
import subprocess
import time
from dataclasses import dataclass
from typing import Literal
from uuid import uuid4

from common.config import get_settings
from common.telemetry import TelemetrySink

SANDBOX_LABEL = "sdlc.sandbox=1"
TASK_LABEL_KEY = "sdlc.task_id"


@dataclass(frozen=True)
class SandboxResult:
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: int
    timed_out: bool


def _container_name(task_id: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_.-]", "-", task_id)[:40].strip("-") or "task"
    return f"sdlc-sbx-{safe}-{uuid4().hex[:8]}"


def list_sandbox_container_ids(task_id: str | None = None) -> list[str]:
    """Ids of sandbox containers still present (`docker ps -aq` filtered by labels)."""
    args = ["docker", "ps", "-aq", "--filter", f"label={SANDBOX_LABEL}"]
    if task_id is not None:
        args.extend(["--filter", f"label={TASK_LABEL_KEY}={task_id}"])
    proc = subprocess.run(args, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        return []
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def _docker_rm(target: str) -> None:
    subprocess.run(["docker", "kill", target], capture_output=True, check=False)
    subprocess.run(["docker", "rm", "-f", target], capture_output=True, check=False)


def _teardown_sandbox(name: str, task_id: str, timeout_s: float = 8.0) -> None:
    """Remove this run's container and wait until Docker no longer lists it.

    `--rm` is not enough: if the `docker run` client is killed on timeout, the
    daemon can leave the container around for a moment. Explicit kill+rm plus
    a short poll closes that window.
    """
    _docker_rm(name)
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        leftover = list_sandbox_container_ids(task_id)
        if not leftover:
            return
        for cid in leftover:
            _docker_rm(cid)
        time.sleep(0.15)


def run_in_sandbox(
    task_id: str,
    command: list[str],
    timeout_s: int,
    network: bool = False,
    *,
    sink: TelemetrySink | None = None,
) -> SandboxResult:
    """Run `command` in a fresh container. Network is off unless `network=True`."""
    active_sink = sink if sink is not None else _default_sink()
    span_id = active_sink.start_span(
        kind="sandbox",
        name="run_in_sandbox",
        task_id=task_id,
        attributes={
            "model_id": None,
            "input_tokens": 0,
            "output_tokens": 0,
            "cost_usd": 0,
            "network": network,
        },
    )
    try:
        result = _run_container(task_id, command, timeout_s, network)
        status: Literal["ok", "error", "cancelled"] = (
            "error" if result.timed_out or result.exit_code != 0 else "ok"
        )
        active_sink.end_span(
            span_id,
            status=status,
            attributes={
                "latency_ms": result.duration_ms,
                "exit_code": result.exit_code,
                "timed_out": result.timed_out,
            },
        )
        return result
    except Exception as exc:
        active_sink.end_span(
            span_id,
            status="error",
            error_type=type(exc).__name__,
            error_message=str(exc),
        )
        raise


def _default_sink() -> TelemetrySink:
    from common.tracing import get_sink

    return get_sink()


def _run_container(
    task_id: str,
    command: list[str],
    timeout_s: int,
    network: bool,
) -> SandboxResult:
    settings = get_settings()
    name = _container_name(task_id)
    network_mode = "bridge" if network else "none"
    if network:
        # Opt-in only. Default-deny is the safety contract; log every exception.
        from common.tracing import get_logger

        get_logger().warning("sandbox_network_enabled", task_id=task_id, command=command)

    args = [
        "docker",
        "run",
        "--name",
        name,
        "--rm",
        "--label",
        SANDBOX_LABEL,
        "--label",
        f"{TASK_LABEL_KEY}={task_id}",
        "--memory",
        settings.sandbox_memory,
        "--cpus",
        settings.sandbox_cpus,
        "--network",
        network_mode,
        settings.sandbox_image,
        *command,
    ]
    started = time.perf_counter()
    timed_out = False
    exit_code = -1
    stdout = ""
    stderr = ""
    proc: subprocess.Popen[bytes] | None = None
    try:
        proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            stdout_b, stderr_b = proc.communicate(timeout=timeout_s)
            exit_code = proc.returncode if proc.returncode is not None else -1
            stdout = stdout_b.decode("utf-8", errors="replace")
            stderr = stderr_b.decode("utf-8", errors="replace")
        except subprocess.TimeoutExpired:
            timed_out = True
            # Stop the container first so `docker run --rm` can exit cleanly.
            # Killing only the CLI leaves an orphan that `--rm` never sees.
            _docker_rm(name)
            try:
                stdout_b, stderr_b = proc.communicate(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()
                stdout_b, stderr_b = proc.communicate()
            stdout = (stdout_b or b"").decode("utf-8", errors="replace")
            stderr = (stderr_b or b"").decode("utf-8", errors="replace")
            exit_code = proc.returncode if proc.returncode is not None else -1
    finally:
        if proc is not None and proc.poll() is None:
            proc.kill()
        _teardown_sandbox(name, task_id)

    duration_ms = int((time.perf_counter() - started) * 1000)
    return SandboxResult(
        stdout=stdout,
        stderr=stderr,
        exit_code=exit_code,
        duration_ms=duration_ms,
        timed_out=timed_out,
    )
