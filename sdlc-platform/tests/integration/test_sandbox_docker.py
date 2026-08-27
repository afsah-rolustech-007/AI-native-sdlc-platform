"""Docker sandbox integration tests."""

from __future__ import annotations

import shutil
import subprocess
from uuid import uuid4

import pytest

from common.sandbox import list_sandbox_container_ids, run_in_sandbox
from common.telemetry import RecordingTelemetrySink

docker_ok = shutil.which("docker") is not None
if docker_ok:
    probe = subprocess.run(["docker", "info"], capture_output=True, check=False, timeout=20)
    docker_ok = probe.returncode == 0

pytestmark = pytest.mark.skipif(not docker_ok, reason="Docker is required for sandbox tests")


def test_sandbox_success_captures_stdout() -> None:
    sink = RecordingTelemetrySink()
    task_id = f"sbx-ok-{uuid4().hex[:8]}"
    result = run_in_sandbox(task_id, ["echo", "hello"], timeout_s=30, sink=sink)
    assert result.timed_out is False
    assert result.exit_code == 0
    assert "hello" in result.stdout
    assert list_sandbox_container_ids(task_id) == []
    assert sink.started[0]["kind"] == "sandbox"
    assert sink.started[0]["task_id"] == task_id


def test_sandbox_nonzero_exit() -> None:
    task_id = f"sbx-fail-{uuid4().hex[:8]}"
    result = run_in_sandbox(task_id, ["sh", "-c", "exit 7"], timeout_s=30)
    assert result.timed_out is False
    assert result.exit_code == 7
    assert list_sandbox_container_ids(task_id) == []


def test_sandbox_timeout_kills_and_removes_container() -> None:
    task_id = f"sbx-hang-{uuid4().hex[:8]}"
    result = run_in_sandbox(task_id, ["sleep", "30"], timeout_s=2)
    assert result.timed_out is True
    assert list_sandbox_container_ids(task_id) == []


def test_sandbox_default_network_blocks_egress() -> None:
    task_id = f"sbx-net-{uuid4().hex[:8]}"
    result = run_in_sandbox(
        task_id,
        ["wget", "-T", "3", "-q", "-O", "-", "http://example.com"],
        timeout_s=20,
        network=False,
    )
    assert result.exit_code != 0
    assert result.timed_out is False
    assert list_sandbox_container_ids(task_id) == []
