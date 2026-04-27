#!/usr/bin/env python3
"""Runtime helpers for Windows/UTF-8 safe CLI execution."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def configure_utf8_stdio() -> None:
    """Best-effort UTF-8 stdio configuration for Windows/Trae terminals."""
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None:
            continue
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def check_conda_env() -> bool:
    """
    Verify if the current Python environment is the expected 'ppt-master' conda environment.
    Returns True if valid, False if not.
    """
    prefix = sys.prefix
    is_valid = "ppt-master" in prefix or "PPTMaster" in prefix
    if not is_valid:
        safe_print("\n" + "!" * 60)
        safe_print("🚨 ENVIRONMENT MISMATCH DETECTED")
        safe_print("-" * 60)
        safe_print(f"Current Python: {sys.executable}")
        safe_print(f"Current Prefix: {prefix}")
        safe_print("\nThis script MUST run in the 'ppt-master' conda environment.")
        safe_print("\n[REQUIRED COMMAND FORM]")
        safe_print("  conda run -n ppt-master python <script_name>.py ...")
        safe_print("!" * 60 + "\n")
    return is_valid


def safe_print(*args, **kwargs) -> None:
    """Print with a final fallback that replaces unencodable characters."""
    kwargs.setdefault("flush", True)
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        sep = kwargs.get("sep", " ")
        end = kwargs.get("end", "\n")
        text = sep.join(str(arg) for arg in args)
        stream = kwargs.get("file", sys.stdout)
        encoding = getattr(stream, "encoding", None) or "utf-8"
        try:
            stream.write(text.encode(encoding, errors="replace").decode(encoding, errors="replace") + end)
        except Exception:
            print(text.encode("ascii", errors="replace").decode("ascii") + end, end="")


def write_json_report(path: Path, payload: dict) -> Path:
    """Write a JSON report atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    temp_path.replace(path)
    return path


def resolve_skill_dir(anchor: str | Path) -> Path:
    """Return the ppt-master skill root for a file or directory inside the skill."""
    anchor_path = Path(anchor).resolve()
    current = anchor_path if anchor_path.is_dir() else anchor_path.parent
    for candidate in (current, *current.parents):
        if (candidate / "SKILL.md").exists() and (candidate / "scripts").exists():
            return candidate
    raise RuntimeError(f"Unable to locate ppt-master skill root from: {anchor_path}")


def resolve_repo_root(anchor: str | Path) -> Path:
    """Return the repository root, preferring explicit configuration over fixed parent depth."""
    env_value = os.environ.get("PPT_MASTER_REPO_ROOT", "").strip()
    if env_value:
        return Path(env_value).resolve()

    skill_dir = resolve_skill_dir(anchor)
    for candidate in (skill_dir, *skill_dir.parents):
        if (candidate / "skills" / "ppt-master-enhanced" / "SKILL.md").exists():
            return candidate
        skill_marker = candidate / ".trae" / "skills" / "ppt-master-enhanced" / "SKILL.md"
        if skill_marker.exists():
            return candidate

    for candidate in (skill_dir, *skill_dir.parents):
        if (candidate / "projects").exists() and (
            (candidate / "skills" / "ppt-master-enhanced" / "SKILL.md").exists()
            or (candidate / ".trae").exists()
        ):
            return candidate

    return skill_dir.parents[2] if len(skill_dir.parents) >= 3 else skill_dir


def get_command_reports_dir(anchor: str | Path) -> Path:
    """Return the skill-local runtime directory for machine-readable command reports."""
    env_value = os.environ.get("PPT_MASTER_COMMAND_REPORTS_DIR", "").strip()
    if env_value:
        return Path(env_value).resolve()
    return resolve_skill_dir(anchor) / ".runtime" / "command_reports"


def format_display_path(path: str | Path, anchor: str | Path) -> str:
    """Render a stable slash-separated path relative to repo root when possible."""
    resolved = Path(path).resolve()
    try:
        repo_root = resolve_repo_root(anchor).resolve()
        return resolved.relative_to(repo_root).as_posix()
    except Exception:
        pass

    try:
        skill_dir = resolve_skill_dir(anchor).resolve()
        return resolved.relative_to(skill_dir).as_posix()
    except Exception:
        return str(resolved).replace("\\", "/")
