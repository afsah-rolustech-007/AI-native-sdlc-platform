"""Section 04 demo: success, timeout, network-blocked — then docker ps leftover check."""

from common.sandbox import list_sandbox_container_ids, run_in_sandbox


def _show(label: str, result) -> None:
    leftovers = list_sandbox_container_ids()
    print(f"== {label} ==")
    print(f"  exit={result.exit_code} timed_out={result.timed_out} stdout={result.stdout.strip()!r}")
    print(f"  leftover sandbox containers={leftovers}")


def main() -> None:
    _show("success", run_in_sandbox("demo-sbx-ok", ["echo", "hello"], timeout_s=30))
    _show("timeout", run_in_sandbox("demo-sbx-hang", ["sleep", "30"], timeout_s=2))
    _show(
        "network-blocked",
        run_in_sandbox(
            "demo-sbx-net",
            ["wget", "-T", "3", "-q", "-O", "-", "http://example.com"],
            timeout_s=20,
        ),
    )


if __name__ == "__main__":
    main()
