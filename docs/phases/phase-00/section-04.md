# Section 04 — Execution Sandbox

## Objective

Build the ephemeral, network-restricted, task-scoped execution sandbox described in §B.6 — the mechanism every future code-executing agent (CodeGen, QA test runners, sandboxed bug reproduction) will run inside, built and proven now against trivial commands.

## Why It Exists

Once agents exist (Phase 06 onward), they will run generated code, install dependencies, and execute tests. If this happens inside the same process/host as the orchestrator, a bug in generated code (or a compromised dependency) is a security incident, not a test failure. Building the sandbox contract first — before there's any real code to execute — means every future "run this" call in the codebase has exactly one way to do it, and that way is safe by construction.

## Expected Architecture

`packages/common/sandbox.py` exposes `run_in_sandbox(task_id: str, command: list[str], timeout_s: int, network: bool = False) -> SandboxResult`. Implementation uses a container runtime (Docker, or a lighter-weight alternative like gVisor/Firecracker if available) to launch an ephemeral container: no network by default, mounted only the files it needs, destroyed on completion **regardless of outcome** (success, failure, or timeout — cleanup happens in a `finally`, not just on the happy path).

## Dependencies

Section 01 (task_id association for scoping/labeling containers).

## Atomic Implementation Tasks

1. Choose and document the container runtime (Docker is the pragmatic default for a solo engineer's dev machine; note in a decisions log if this changes later).
2. Implement `run_in_sandbox()`: launches a container with `--network=none` by default, a CPU/memory limit, and a hard wall-clock timeout.
3. Implement guaranteed teardown: wrap execution in try/finally (or equivalent) ensuring the container is removed even on timeout or exception in the orchestrator process itself (e.g., register cleanup via the container runtime's own auto-remove flag *and* an explicit teardown call, so a crash on the host side doesn't leak containers).
4. Implement `SandboxResult` (stdout, stderr, exit_code, duration_ms, timed_out: bool).
5. Add an opt-in `network=True` path used only by the sandbox contract itself (e.g., a QA agent that legitimately needs to hit a test dependency registry) — document that this is the exception, not the default, and log every use.
6. Unit/integration tests: a command that succeeds; a command that fails (non-zero exit); a command that hangs past timeout (confirm forced kill + container removal); confirm no container survives the test run (`docker ps -a` empty of test-tagged containers after suite completes).

## Manual Testing Procedure

1. Run `run_in_sandbox(task_id="demo", command=["echo", "hello"], timeout_s=5)` — confirm stdout captured correctly.
2. Run a command that sleeps longer than the timeout — confirm it's killed and `timed_out=True`.
3. Run `docker ps -a` immediately after each case — confirm zero leaked containers.
4. Attempt a network call (e.g., `curl example.com`) inside a `network=False` sandbox run — confirm it fails (proving network restriction is real, not just configured-but-unenforced).

## Expected Demo

Terminal output showing three sandbox runs (success, timeout, network-blocked) each followed by a `docker ps -a` check proving no residue.

## Acceptance Criteria

- [ ] Sandbox runs are network-restricted by default; the restriction is verified by an actual failed network call in a test, not just an absent flag inspection.
- [ ] Sandbox containers are destroyed after every run, verified by an automated post-test container-count assertion.
- [ ] Timeout is enforced and reported accurately in `SandboxResult`.
- [ ] Every sandbox invocation is tagged/labeled with `task_id` for later audit correlation with OTel traces (Section 05).

## Risks

- **Risk:** Container escape / sandbox misconfiguration. **Mitigation:** default-deny network, resource limits, and — as a process discipline — treat any change to sandbox defaults as requiring the same review rigor as a security-relevant change (per §N's "sandbox escape" risk row), even at this early, agent-less stage.
- **Risk:** Docker-in-Docker or nested-virtualization issues in some dev/CI environments. **Mitigation:** verify the sandbox works inside whatever CI runner is chosen (Section 06) early, not after other phases depend on it.

## Future Improvements

- Evaluate gVisor/Firecracker microVMs for stronger isolation once real (untrusted, LLM-generated) code is actually running inside (Phase 06) — Docker's default isolation is an acceptable starting point but is explicitly named as a risk area worth revisiting (§N).

## Research Opportunities

Compare container cold-start latency across runtimes once CodeGen agents are running many parallel sandboxed executions (Phase 06+) — this becomes a real cost/throughput question at that point, not now.
