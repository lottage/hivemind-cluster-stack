"""
Test runner with a hard unit/live split.

    python tests/run_tests.py          # unit: tests/test_*.py with every non-localhost connection blocked
    python tests/run_tests.py live     # live: tests/live/test_*.py against the real homelab (read-only checks)

Unit tests must never reach the LAN: several harness modules (Valkey A-MEM, the MCP bridge,
edge-fleet OTA) connect to live services by default, and a unit run on the LAN used to write
test cards into Courage's live Valkey. The guard below turns any such connection into an
OSError so modules fall back to their offline paths, and lists every attempt at the end.
"""

import os
import socket
import sys
import unittest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(TESTS_DIR)
sys.path.insert(0, REPO_ROOT)  # same import root as `python -m unittest` from the repo root
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
blocked_attempts = []


def _is_local(host) -> bool:
    host = str(host)
    return host in LOCAL_HOSTS or host.startswith("127.")


def install_network_guard():
    orig_connect = socket.socket.connect
    orig_create = socket.create_connection

    def guarded_connect(self, addr):
        host = addr[0] if isinstance(addr, tuple) else addr
        if not _is_local(host):
            blocked_attempts.append(addr)
            raise OSError(f"unit tests may not open network connections (blocked {addr})")
        return orig_connect(self, addr)

    def guarded_create(address, *args, **kwargs):
        if not _is_local(address[0]):
            blocked_attempts.append(address)
            raise OSError(f"unit tests may not open network connections (blocked {address})")
        return orig_create(address, *args, **kwargs)

    socket.socket.connect = guarded_connect
    socket.create_connection = guarded_create


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "unit"
    if mode == "unit":
        os.environ.setdefault("STONESAGE_OFFLINE", "1")
        install_network_guard()
        suite = unittest.defaultTestLoader.discover(TESTS_DIR, pattern="test_*.py", top_level_dir=TESTS_DIR)
    elif mode == "live":
        suite = unittest.defaultTestLoader.discover(os.path.join(TESTS_DIR, "live"), pattern="test_*.py")
    else:
        print(f"unknown mode {mode!r}; use 'unit' or 'live'")
        return 2

    result = unittest.TextTestRunner(verbosity=1).run(suite)
    if blocked_attempts:
        uniq = sorted({f"{a[0]}:{a[1]}" if isinstance(a, tuple) else str(a) for a in blocked_attempts})
        print(f"\nNetwork guard blocked {len(blocked_attempts)} connection attempt(s) to: {', '.join(uniq)}")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
