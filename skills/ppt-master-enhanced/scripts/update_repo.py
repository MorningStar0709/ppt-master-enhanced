#!/usr/bin/env python3
"""Update the repository and sync Python dependencies when needed.

Usage:
    conda run -n ppt-master python skills/ppt-master-enhanced/scripts/update_repo.py
    conda run -n ppt-master python skills/ppt-master-enhanced/scripts/update_repo.py --skip-pip
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

try:
    from runtime_utils import configure_utf8_stdio, resolve_repo_root, safe_print
except ImportError:
    tools_dir = Path(__file__).resolve().parent
    if str(tools_dir) not in sys.path:
        sys.path.insert(0, str(tools_dir))
    from runtime_utils import configure_utf8_stdio, resolve_repo_root, safe_print  # type: ignore


TOOLS_DIR = Path(__file__).resolve().parent
SKILL_DIR = TOOLS_DIR.parent
REPO_ROOT = resolve_repo_root(__file__)
REQUIREMENTS_FILE = REPO_ROOT / "requirements.txt"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Pull the latest repository changes and sync Python dependencies "
            "only when requirements.txt changes."
        )
    )
    parser.add_argument(
        "--skip-pip",
        action="store_true",
        help="Skip Python dependency sync even if requirements.txt changed.",
    )
    return parser.parse_args()


def run_command(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=REPO_ROOT,
        check=check,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def file_digest(path: Path) -> str | None:
    if not path.exists():
        return None

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_git_available() -> None:
    if shutil.which("git") is None:
        raise RuntimeError("Missing executable: git")


def ensure_clean_tracked_worktree() -> None:
    status = run_command(["git", "status", "--porcelain", "--untracked-files=no"], check=False)
    if status.returncode != 0:
        details = (status.stderr or status.stdout or "").strip()
        raise RuntimeError(details or "Unable to inspect git status.")

    if status.stdout.strip():
        raise RuntimeError(
            "Tracked local changes detected. Please commit or stash them before running the update command."
        )


def get_head_revision() -> str:
    result = run_command(["git", "rev-parse", "HEAD"])
    return result.stdout.strip()


def sync_python_dependencies() -> None:
    if not REQUIREMENTS_FILE.exists():
        safe_print("requirements.txt not found; skipping Python dependency sync.")
        return

    safe_print("requirements.txt changed. Syncing Python dependencies...")
    result = run_command([sys.executable, "-m", "pip", "install", "-r", str(REQUIREMENTS_FILE)])
    if result.stdout.strip():
        safe_print(result.stdout.strip())
    if result.stderr.strip():
        safe_print(result.stderr.strip())


def main() -> int:
    configure_utf8_stdio()
    args = parse_args()

    try:
        ensure_git_available()
        ensure_clean_tracked_worktree()

        before_head = get_head_revision()
        before_requirements = file_digest(REQUIREMENTS_FILE)

        safe_print(f"Repository: {REPO_ROOT}")
        pull_result = run_command(["git", "pull", "--ff-only"])
        if pull_result.stdout.strip():
            safe_print(pull_result.stdout.strip())
        if pull_result.stderr.strip():
            safe_print(pull_result.stderr.strip())

        after_head = get_head_revision()
        after_requirements = file_digest(REQUIREMENTS_FILE)

        if before_head == after_head:
            safe_print("Repository is already up to date.")
        else:
            safe_print(f"Updated from {before_head[:7]} to {after_head[:7]}.")

        if args.skip_pip:
            safe_print("Skipped Python dependency sync (--skip-pip).")
        elif before_requirements != after_requirements:
            sync_python_dependencies()
        else:
            safe_print("requirements.txt unchanged. Skipping Python dependency sync.")

        safe_print("Note: system dependencies such as Node.js and Pandoc still need to be installed manually.")
        return 0
    except subprocess.CalledProcessError as exc:
        details = (exc.stderr or exc.stdout or "").strip()
        safe_print(details or "Command failed.", file=sys.stderr)
        return exc.returncode or 1
    except RuntimeError as exc:
        safe_print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

