"""One command from a fresh clone: python scripts/start.py [--dev] [--port 8000]."""
import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description="Install and run the curriculum backend")
    parser.add_argument("--dev", action="store_true", help="Install test dependencies and enable reload")
    parser.add_argument("--install-only", action="store_true")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    if sys.version_info < (3, 13):
        parser.error("Python 3.13 or newer is required; Python 3.13 is the tested version")
    env = ROOT / ".venv"
    python = env / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.exists():
        venv.create(env, with_pip=True)
    requirement = "requirements-dev.txt" if args.dev else "requirements.txt"
    digest = hashlib.sha256((ROOT / "requirements.txt").read_bytes() +
                            ((ROOT / "requirements-dev.txt").read_bytes() if args.dev else b"")).hexdigest()
    marker = env / ("installed-dev.sha256" if args.dev else "installed.sha256")
    if not marker.exists() or marker.read_text().strip() != digest:
        subprocess.run([str(python), "-m", "pip", "install", "-r", requirement], cwd=ROOT, check=True)
        marker.write_text(digest, encoding="ascii")
    if args.install_only:
        return
    print(f"Swagger: http://{args.host}:{args.port}/docs", flush=True)
    command = [str(python), "-m", "uvicorn", "backend.app.main:app", "--host", args.host, "--port", str(args.port)]
    if args.dev:
        command.append("--reload")
    try:
        raise SystemExit(subprocess.call(command, cwd=ROOT))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
