"""How to invoke Zoekt for MVP: one-shot CLI, not a long-running search server.

Prefer host `zoekt-index` / `zoekt` on PATH. If those are missing, use a one-shot
`docker run` of the official image (equivalent packaged deployment). That is not
a compose service and is not the Phase 00 alpine sandbox (that image has no Zoekt).

Subprocess timeouts and, for Docker, memory/CPU/network-none match the sandbox
resource-bounded discipline without wrapping Zoekt inside alpine.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from common.config import get_settings
from repo_intel.exceptions import ZoektUnavailableError

ZOEKT_IMAGE = "ghcr.io/sourcegraph/zoekt"
INDEX_BIN = "zoekt-index"
SEARCH_BIN = "zoekt"


@dataclass(frozen=True)
class ZoektProcessResult:
    stdout: str
    stderr: str
    returncode: int
    timed_out: bool


class ZoektCommandRunner:
    """Runs index/search. Tests may substitute a fake."""

    mode: str = "host"

    def run_index(self, source_dir: Path, index_dir: Path, timeout_s: float) -> ZoektProcessResult:
        raise NotImplementedError

    def run_search(self, index_dir: Path, query: str, timeout_s: float) -> ZoektProcessResult:
        raise NotImplementedError


class HostZoektRunner(ZoektCommandRunner):
    mode = "host"

    def __init__(self, index_bin: str, search_bin: str) -> None:
        self.index_bin = index_bin
        self.search_bin = search_bin

    def run_index(self, source_dir: Path, index_dir: Path, timeout_s: float) -> ZoektProcessResult:
        return _run(
            [self.index_bin, "-index", str(index_dir), str(source_dir)],
            timeout_s,
        )

    def run_search(self, index_dir: Path, query: str, timeout_s: float) -> ZoektProcessResult:
        return _run(
            [self.search_bin, "-index_dir", str(index_dir), "-jsonl", query],
            timeout_s,
        )


class DockerZoektRunner(ZoektCommandRunner):
    """One-shot container. Not docker-compose; not the alpine sandbox image."""

    mode = "docker"

    def __init__(self, image: str = ZOEKT_IMAGE) -> None:
        self.image = image

    def run_index(self, source_dir: Path, index_dir: Path, timeout_s: float) -> ZoektProcessResult:
        return _run(
            _docker_argv(
                image=self.image,
                entrypoint=INDEX_BIN,
                extra_mounts=[(source_dir, "/data/src", True)],
                index_dir=index_dir,
                args=["-index", "/data/index", "/data/src"],
            ),
            timeout_s,
        )

    def run_search(self, index_dir: Path, query: str, timeout_s: float) -> ZoektProcessResult:
        return _run(
            _docker_argv(
                image=self.image,
                entrypoint=SEARCH_BIN,
                extra_mounts=[],
                index_dir=index_dir,
                args=["-index_dir", "/data/index", "-jsonl", query],
                index_readonly=True,
            ),
            timeout_s,
        )


def host_zoekt_bins() -> tuple[str, str] | None:
    index_bin = shutil.which(INDEX_BIN)
    search_bin = shutil.which(SEARCH_BIN)
    if index_bin and search_bin:
        return index_bin, search_bin
    return None


def docker_zoekt_image_present(image: str = ZOEKT_IMAGE) -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        probe = subprocess.run(
            ["docker", "image", "inspect", image],
            capture_output=True,
            check=False,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return probe.returncode == 0


def detect_zoekt_runner() -> ZoektCommandRunner:
    host = host_zoekt_bins()
    if host is not None:
        return HostZoektRunner(index_bin=host[0], search_bin=host[1])
    if docker_zoekt_image_present():
        return DockerZoektRunner()
    raise ZoektUnavailableError(
        "Zoekt is not installed. Install host binaries (`make zoekt-install`) "
        f"or pull the packaged image (`docker pull {ZOEKT_IMAGE}`) and retry. "
        "Search/index cannot proceed without Zoekt — this is not treated as zero hits."
    )


def zoekt_is_available() -> bool:
    try:
        detect_zoekt_runner()
    except ZoektUnavailableError:
        return False
    return True


def _docker_argv(
    *,
    image: str,
    entrypoint: str,
    extra_mounts: list[tuple[Path, str, bool]],
    index_dir: Path,
    args: list[str],
    index_readonly: bool = False,
) -> list[str]:
    settings = get_settings()
    index_opt = "ro" if index_readonly else "rw"
    argv = [
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "--memory",
        settings.sandbox_memory,
        "--cpus",
        settings.sandbox_cpus,
        "--user",
        f"{os.getuid()}:{os.getgid()}",
        "--entrypoint",
        entrypoint,
        "-v",
        f"{index_dir}:/data/index:{index_opt}",
    ]
    for host_path, container_path, readonly in extra_mounts:
        mode = "ro" if readonly else "rw"
        argv.extend(["-v", f"{host_path}:{container_path}:{mode}"])
    argv.append(image)
    argv.extend(args)
    return argv


def _run(argv: list[str], timeout_s: float) -> ZoektProcessResult:
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            check=False,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = _decode(exc.stdout)
        stderr = _decode(exc.stderr)
        return ZoektProcessResult(stdout=stdout, stderr=stderr, returncode=-1, timed_out=True)
    return ZoektProcessResult(
        stdout=_decode(proc.stdout),
        stderr=_decode(proc.stderr),
        returncode=proc.returncode,
        timed_out=False,
    )


def _decode(blob: bytes | None) -> str:
    if not blob:
        return ""
    return blob.decode("utf-8", errors="replace")
