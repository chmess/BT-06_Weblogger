#!/usr/bin/env python3
"""Inspect the held flock, and signal only its verified owner via pidfd."""
import argparse
import fcntl
import json
import os
import signal
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["status", "stop", "require-stopped"])
    args = parser.parse_args()
    lock = ROOT / "runtime/app.lock"
    if not lock.exists():
        print("BT-06 Weblogger ist beendet.")
        return
    with lock.open() as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            if args.command == "require-stopped":
                print("Programm vor dem Update beenden.", file=sys.stderr)
                sys.exit(1)
            record = json.load(stream)
            pid = int(record["pid"])
            # pidfd avoids signalling a recycled PID. Verify arguments after opening it.
            fd = os.pidfd_open(pid)
            try:
                cmd = (Path("/proc") / str(pid) / "cmdline").read_bytes().split(b"\0")
                cwd = (Path("/proc") / str(pid) / "cwd").resolve()
                expected = str(ROOT / "app.py").encode()
                if not ((b"app.py" in cmd and cwd == ROOT) or expected in cmd):
                    raise RuntimeError("Prozessidentität stimmt nicht. Kein Signal gesendet.")
                print(f"BT-06 Weblogger aktiv (PID {pid}).")
                if args.command == "stop":
                    signal.pidfd_send_signal(fd, signal.SIGTERM)
                    import select
                    poll = select.poll()
                    poll.register(fd, select.POLLIN)
                    if not poll.poll(10000):
                        raise RuntimeError("Beenden noch nicht abgeschlossen; keine erzwungene Terminierung.")
                    print("Programm geordnet beendet.")
            finally:
                os.close(fd)
        else:
            print("BT-06 Weblogger ist beendet.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Statusprüfung fehlgeschlagen: {exc}", file=sys.stderr)
        sys.exit(1)
