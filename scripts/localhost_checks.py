#!/usr/bin/env python
"""
Localhost environment checks for setup/start workflows.
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import subprocess
import sys
from pathlib import Path


MIN_PYTHON = (3, 10)
MIN_NODE_MAJOR = 18


def _ok(message: str) -> None:
    print(f"[OK] {message}")


def _fail(message: str) -> None:
    print(f"[FAIL] {message}")


def _info(message: str) -> None:
    print(f"[INFO] {message}")


def _parse_semver(text: str) -> tuple[int, int, int] | None:
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", text)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def _command_output(command: list[str]) -> str | None:
    try:
        completed = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
        return (completed.stdout or completed.stderr).strip()
    except Exception:
        return None


def _run_command(command: list[str], cwd: Path | None = None) -> bool:
    try:
        subprocess.run(command, check=True, cwd=cwd)
        return True
    except FileNotFoundError:
        _fail(f"Command not found: {command[0]}")
    except subprocess.CalledProcessError as exc:
        _fail(f"Command failed (exit {exc.returncode}): {' '.join(command)}")
    return False


def _npm_command() -> str:
    if sys.platform.startswith("win"):
        return "npm.cmd"
    return "npm"


def check_uv() -> bool:
    uv_raw = _command_output(["uv", "--version"])
    if not uv_raw:
        _fail("UV is not available on PATH")
        _info("Install UV from https://docs.astral.sh/uv/getting-started/installation/")
        return False
    _ok(uv_raw)
    return True


def check_python() -> bool:
    if sys.version_info < MIN_PYTHON:
        _fail(
            f"Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ required "
            f"(found {sys.version_info.major}.{sys.version_info.minor})"
        )
        return False
    _ok(f"Python {sys.version.split()[0]}")
    return True


def check_node() -> bool:
    node_raw = _command_output(["node", "--version"])
    npm_raw = _command_output(["npm", "--version"])
    if not npm_raw and sys.platform.startswith("win"):
        npm_raw = _command_output(["npm.cmd", "--version"])
    if not node_raw:
        _fail("Node.js is not available on PATH")
        return False
    node_ver = _parse_semver(node_raw)
    if not node_ver:
        _fail(f"Unable to parse Node.js version output: {node_raw}")
        return False
    if node_ver[0] < MIN_NODE_MAJOR:
        _fail(f"Node.js {MIN_NODE_MAJOR}+ required (found {node_raw})")
        return False
    _ok(f"Node.js {node_raw.lstrip('v')}")

    if not npm_raw:
        _fail("npm is not available on PATH")
        return False
    _ok(f"npm {npm_raw}")
    return True


def check_python_dependencies() -> bool:
    required_imports = {
        "aiofiles": "aiofiles",
        "fastapi": "fastapi",
        "httpx": "httpx",
        "pydantic": "pydantic",
        "python-dotenv": "dotenv",
        "python-multipart": "multipart",
        "requests": "requests",
        "selenium": "selenium",
        "tqdm": "tqdm",
        "uvicorn": "uvicorn",
        "webdriver-manager": "webdriver_manager",
        "websockets": "websockets",
    }
    missing = [
        package
        for package, import_name in required_imports.items()
        if importlib.util.find_spec(import_name) is None
    ]
    if missing:
        _fail(f"Missing Python packages: {', '.join(missing)}")
        _info("Run `uv sync` from the repository root to install Python dependencies.")
        return False
    _ok("Required Python packages are installed")
    return True


def install_node_dependencies(root: Path) -> bool:
    npm_cmd = _npm_command()
    ok = True
    frontend_dir = root / "frontend"
    if frontend_dir.exists():
        _info("Installing frontend dependencies (`npm install` in `frontend`)")
        ok = _run_command([npm_cmd, "install"], cwd=frontend_dir) and ok
    else:
        _fail(f"Missing frontend directory: {frontend_dir}")
        ok = False

    _info("Installing root dependencies (`npm install` in repository root)")
    ok = _run_command([npm_cmd, "install"], cwd=root) and ok
    return ok


def check_node_dependencies(root: Path) -> bool:
    frontend_modules = root / "frontend" / "node_modules"
    root_modules = root / "node_modules"
    ok = True
    if not frontend_modules.exists():
        _fail("frontend/node_modules missing (run `npm --prefix frontend install`)")
        ok = False
    else:
        _ok("frontend/node_modules present")

    if not root_modules.exists():
        _fail("node_modules missing (run `npm install`)")
        ok = False
    else:
        _ok("node_modules present")
    return ok


def ensure_python_dependencies(root: Path, install_missing: bool) -> bool:
    if check_python_dependencies():
        return True
    if install_missing:
        _info("Python dependencies are managed by UV; automatic package installs are disabled here.")
    return False


def ensure_node_dependencies(root: Path, install_missing: bool) -> bool:
    if check_node_dependencies(root):
        return True
    if not install_missing:
        return False
    if not install_node_dependencies(root):
        return False
    return check_node_dependencies(root)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run localhost environment checks")
    parser.add_argument(
        "--mode",
        choices=["env", "setup", "start"],
        default="env",
        help="Check profile to run",
    )
    parser.add_argument(
        "--install-missing",
        action="store_true",
        help="Install missing dependencies automatically",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    all_ok = True

    all_ok = check_uv() and all_ok
    all_ok = check_python() and all_ok
    all_ok = check_node() and all_ok

    if args.mode in {"setup", "start"}:
        all_ok = ensure_python_dependencies(root, args.install_missing) and all_ok
        all_ok = ensure_node_dependencies(root, args.install_missing) and all_ok

    if all_ok:
        _ok(f"All {args.mode} checks passed")
        return 0
    _fail(f"{args.mode} checks failed")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
