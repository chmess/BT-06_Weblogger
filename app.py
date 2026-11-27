#!/usr/bin/env python3
"""Portable Linux entry point."""
import argparse
import json
import signal
import sys
import threading
from pathlib import Path

from backend import VERSION
from backend.common.simulation import generate, load_profiles
from backend.linux.runtime import InstanceLock

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description="BT-06 Weblogger · Linux · offline")
    parser.add_argument("--version", action="version", version=VERSION)
    parser.add_argument("--root", type=Path, default=ROOT, help="Separates Daten-/Konfigurationsverzeichnis")
    commands = parser.add_subparsers(dest="command", required=True)
    serve = commands.add_parser("serve")
    serve.add_argument("--root",type=Path,default=argparse.SUPPRESS,help="Separates Daten-/Konfigurationsverzeichnis")
    serve.add_argument("--port", type=int, default=8766)
    serve.add_argument("--base-path", default="")
    serve.add_argument("--public-origin", action="append", help="Explizite Origin des authentifizierenden Reverse Proxy; für mehrere Zugangsadressen wiederholen")
    demo = commands.add_parser("generate")
    demo.add_argument("--root",type=Path,default=argparse.SUPPRESS,help="Separates Daten-/Konfigurationsverzeichnis")
    demo.add_argument("--days", type=int, default=7)
    demo.add_argument("--interval-minutes", type=int, default=5)
    demo.add_argument("--seed", type=int, default=42)
    demo.add_argument("--scenario", choices=["daily", "humidity", "ventilation", "gaps"], default="humidity")
    demo.add_argument("--end", help="Festes Ende mit UTC-Offset für reproduzierbare Läufe")
    args = parser.parse_args()
    try:
        args.root=args.root.resolve()
        with InstanceLock(args.root / "runtime/app.lock",metadata={"command":args.command,"code_root":str(ROOT),"data_root":str(args.root)}):
            if args.command == "generate":
                options = {k: getattr(args, k) for k in ("days", "interval_minutes", "seed", "scenario")}
                if args.end:
                    options["end"] = args.end
                print(json.dumps(generate(args.root / "simulation", options, load_profiles(args.root / "private/profiles.json")), ensure_ascii=False, indent=2))
                return
            from backend.server import Application, make_server
            app = Application(args.root, args.base_path, args.public_origin)
            server = make_server(app, args.port)
            # shutdown must run outside the serving thread.
            def stop(signum, frame):
                threading.Thread(target=server.shutdown, daemon=True).start()
            signal.signal(signal.SIGTERM, stop)
            signal.signal(signal.SIGINT, stop)
            print(f"BT-06 Weblogger {VERSION}: http://127.0.0.1:{server.server_port}{app.base_path}/", flush=True)
            try:
                app.resume()
                server.serve_forever(poll_interval=.25)
            finally:
                app.close()
                server.server_close()
    except (ValueError, OSError, RuntimeError) as exc:
        print(f"Start fehlgeschlagen: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
