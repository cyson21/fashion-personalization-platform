#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
import os
import tempfile
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    env = dict(os.environ)
    env["PYTHONPATH"] = str(root / "src")
    with tempfile.TemporaryDirectory(prefix="fashion-personalization-pycache-") as pycache_dir:
        env["PYTHONPYCACHEPREFIX"] = pycache_dir
        checks = [
            [sys.executable, "-m", "compileall", "-q", "src"],
            [sys.executable, "-m", "pytest", "-p", "no:cacheprovider"],
            [sys.executable, "-m", "fashion_personalization.cli"],
        ]
        for check in checks:
            print("$ " + " ".join(check), flush=True)
            completed = subprocess.run(check, cwd=root, env=env)
            if completed.returncode != 0:
                return completed.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
