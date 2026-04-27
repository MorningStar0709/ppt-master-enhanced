#!/usr/bin/env python3
"""PPT Master project management helpers.

Usage:
    conda run -n ppt-master python skills/ppt-master-enhanced/scripts/project_manager.py init <project_name> [--format ppt169] [--dir projects]
    conda run -n ppt-master python skills/ppt-master-enhanced/scripts/project_manager.py import-sources <project_path> <source1> [<source2> ...] [--move | --copy]
    conda run -n ppt-master python skills/ppt-master-enhanced/scripts/project_manager.py apply-template <project_path> <template_name> [--force]
    conda run -n ppt-master python skills/ppt-master-enhanced/scripts/project_manager.py validate <project_path>
    conda run -n ppt-master python skills/ppt-master-enhanced/scripts/project_manager.py info <project_path>
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import hashlib
import json
from typing import Any
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

try:
    from runtime_utils import (
        check_conda_env,
        configure_utf8_stdio,
        format_display_path,
        get_command_reports_dir,
        resolve_repo_root,
        safe_print,
        write_json_report,
    )
    from project_utils import (
        CANVAS_FORMATS,
        get_project_info as get_project_info_common,
        normalize_canvas_format,
        validate_project_structure,
        validate_svg_viewbox,
    )
    from review_utils import init_review_artifacts
    from error_helper import ErrorHelper
except ImportError:
    tools_dir = Path(__file__).resolve().parent
    if str(tools_dir) not in sys.path:
        sys.path.insert(0, str(tools_dir))
    from runtime_utils import (  # type: ignore
        configure_utf8_stdio,
        format_display_path,
        get_command_reports_dir,
        resolve_repo_root,
        safe_print,
        write_json_report,
    )
    from project_utils import (  # type: ignore
        CANVAS_FORMATS,
        get_project_info as get_project_info_common,
        normalize_canvas_format,
        validate_project_structure,
        validate_svg_viewbox,
    )
    from review_utils import init_review_artifacts  # type: ignore
    from error_helper import ErrorHelper  # type: ignore

TOOLS_DIR = Path(__file__).resolve().parent
SKILL_DIR = TOOLS_DIR.parent
REPO_ROOT = resolve_repo_root(__file__)
SOURCE_DIRNAME = "sources"
TEXT_SOURCE_SUFFIXES = {".md", ".markdown", ".txt"}
PDF_SUFFIXES = {".pdf"}
PRESENTATION_SUFFIXES = {".pptx", ".pptm", ".ppsx", ".ppsm", ".potx", ".potm"}
DOC_SUFFIXES = {
    ".docx", ".doc", ".odt", ".rtf",          # Office documents
    ".epub",                                    # eBooks
    ".html", ".htm",                            # Web pages
    ".tex", ".latex", ".rst", ".org",           # Academic / technical
    ".ipynb", ".typ",                           # Notebooks / Typst
}
WECHAT_HOST_KEYWORDS = ("mp.weixin.qq.com", "weixin.qq.com")
REPORTS_DIR = get_command_reports_dir(__file__)
TEMPLATE_LAYOUTS_DIR = SKILL_DIR / "templates" / "layouts"
TEMPLATE_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
TEMPLATE_MANIFEST_NAME = "template_manifest.json"
DEPRECATED_COMMAND_HINTS = {
    "copy-template": "Use 'apply-template <project_path> <template_name>' instead.",
}


def _curl_cffi_available() -> bool:
    """Return whether curl_cffi is importable (enables Python TLS impersonation)."""
    try:
        import curl_cffi  # noqa: F401
        return True
    except ImportError:
        return False


def is_url(value: str) -> bool:
    """Return whether a string looks like an HTTP(S) URL."""
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def sanitize_ascii_name(value: str, prefix: str = "item") -> str:
    """Return an ASCII-only filesystem token; fall back to a stable hashed token."""
    raw = value.strip()
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", raw)
    safe = re.sub(r"_+", "_", safe).strip("._")
    if safe:
        return safe[:120]
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:8]
    return f"{prefix}_{digest}"


def normalize_project_dir_token(project_name: str) -> str:
    """Normalize a project name into an ASCII-only directory token."""
    return sanitize_ascii_name(project_name, prefix="project")


def validate_english_project_slug(project_name: str) -> str:
    """Require a stable ASCII project slug instead of silently guessing one."""
    slug = project_name.strip()
    if not slug:
        raise ValueError("Project name is required")

    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,119}", slug):
        raise ValueError(
            "Project name must be an English-only slug using ASCII letters, digits, '.', '_', or '-'."
        )

    normalized = normalize_project_dir_token(slug)
    if normalized != slug:
        raise ValueError(
            "Project name must already be a stable English slug. "
            "Do not rely on automatic normalization."
        )

    return slug


def english_filename_for_path(source_path: Path, prefix: str = "source") -> str:
    """Build an ASCII-only filename while preserving the original extension."""
    suffix = source_path.suffix.lower()
    stem = sanitize_ascii_name(source_path.stem, prefix=prefix)
    return f"{stem}{suffix}"


def resolve_repo_relative_dir(path_str: str | Path) -> Path:
    """Resolve relative paths against the repository root, not the caller cwd."""
    path = Path(path_str)
    if path.is_absolute():
        return path
    return (REPO_ROOT / path).resolve()


def derive_url_basename(url: str) -> str:
    """Derive a stable base filename from a URL."""
    parsed = urlparse(url)
    parts = [sanitize_ascii_name(parsed.netloc, prefix="web")]
    if parsed.path and parsed.path != "/":
        path_part = sanitize_ascii_name(parsed.path.strip("/").replace("/", "_"), prefix="path")
        if path_part:
            parts.append(path_part)
    return "_".join(part for part in parts if part) or "web_source"


def is_within_path(path: Path, parent: Path) -> bool:
    """Return whether `path` resolves inside `parent`."""
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def to_display_path_text(path: Path | str) -> str:
    """Return a stable human-readable path for CLI output and JSON payloads."""
    return format_display_path(path, __file__)


def extract_common_cli_options(argv: list[str]) -> tuple[list[str], bool, Path | None]:
    """Extract shared options without forcing full argparse migration."""
    filtered = [argv[0]]
    json_output = False
    report_file: Path | None = None

    i = 1
    while i < len(argv):
        arg = argv[i]
        if arg == "--json":
            json_output = True
            i += 1
            continue
        if arg == "--report-file" and i + 1 < len(argv):
            report_file = Path(argv[i + 1])
            i += 2
            continue
        filtered.append(arg)
        i += 1

    return filtered, json_output, report_file


def default_report_path(command: str) -> Path:
    """Return the default report file for a command."""
    return REPORTS_DIR / f"project_manager_{command}_last.json"


def emit_command_result(
    command: str,
    payload: dict[str, Any],
    *,
    json_output: bool,
    report_file: Path | None,
) -> None:
    """Persist a structured command report and optionally print JSON."""
    target = report_file or default_report_path(command)
    payload["report_file"] = to_display_path_text(target)
    write_json_report(target, payload)
    if json_output:
        safe_print(json.dumps(payload, ensure_ascii=True, indent=2))
    else:
        safe_print(f"Report file: {payload['report_file']}")


class ProjectManager:
    """Create, inspect, validate, and populate project folders."""

    CANVAS_FORMATS = CANVAS_FORMATS

    def __init__(self, base_dir: str = "projects") -> None:
        self.base_dir = resolve_repo_relative_dir(base_dir)

    def init_project(
        self,
        project_name: str,
        canvas_format: str = "ppt169",
        base_dir: str | None = None,
    ) -> str:
        base_path = resolve_repo_relative_dir(base_dir) if base_dir else self.base_dir
        base_path.mkdir(parents=True, exist_ok=True)

        normalized_format = normalize_canvas_format(canvas_format)
        if normalized_format not in self.CANVAS_FORMATS:
            available = ", ".join(sorted(self.CANVAS_FORMATS.keys()))
            raise ValueError(
                f"Unsupported canvas format: {canvas_format} "
                f"(available: {available}; common alias: xhs -> xiaohongshu)"
            )

        display_project_name = validate_english_project_slug(project_name)
        project_dir_token = normalize_project_dir_token(display_project_name)
        date_str = datetime.now().strftime("%Y%m%d")
        project_dir_name = f"{project_dir_token}_{normalized_format}"
        project_path = base_path / project_dir_name

        if project_path.exists():
            raise FileExistsError(
                f"Project directory already exists: {project_path}. "
                "Reuse the existing project path or choose a different English project slug."
            )

        for rel_path in (
            "svg_output",
            "svg_final",
            "images",
            "notes",
            "review",
            "templates",
            SOURCE_DIRNAME,
            "exports",
        ):
            (project_path / rel_path).mkdir(parents=True, exist_ok=True)

        init_review_artifacts(project_path)

        canvas_info = self.CANVAS_FORMATS[normalized_format]
        readme_path = project_path / "README.md"
        readme_path.write_text(
            (
                f"# {display_project_name}\n\n"
                f"- Canvas format: {normalized_format}\n"
                f"- Created: {date_str}\n\n"
                "## Directories\n\n"
                "- `svg_output/`: raw SVG output\n"
                "- `svg_final/`: finalized SVG output\n"
                "- `images/`: presentation assets\n"
                "- `notes/`: speaker notes\n"
                "- `review/`: SVG review log, fix tasks, and export approval\n"
                "- `templates/`: project templates\n"
                "- `sources/`: source materials and normalized markdown\n"
                "- `exports/`: generated PPTX export snapshots (filenames include export timestamps)\n"
            ),
            encoding="utf-8",
        )

        safe_print(f"Project created: {project_path}")
        safe_print(f"Canvas: {canvas_info['name']} ({canvas_info['dimensions']})")
        return str(project_path)

    def _source_dir(self, project_path: Path) -> Path:
        sources_dir = project_path / SOURCE_DIRNAME
        sources_dir.mkdir(parents=True, exist_ok=True)
        return sources_dir

    def _ensure_unique_path(self, path: Path) -> Path:
        if not path.exists():
            return path

        suffix = path.suffix
        stem = path.stem
        counter = 2
        while True:
            candidate = path.with_name(f"{stem}_{counter}{suffix}")
            if not candidate.exists():
                return candidate
            counter += 1

    def _copy_or_move_file(self, source: Path, destination: Path, move: bool) -> Path:
        try:
            if source.resolve() == destination.resolve():
                return destination
        except FileNotFoundError:
            pass

        destination = self._ensure_unique_path(destination)
        if move:
            shutil.move(str(source), str(destination))
        else:
            shutil.copy2(source, destination)
        return destination

    def _copy_or_move_tree(self, source: Path, destination: Path, move: bool) -> Path:
        try:
            if source.resolve() == destination.resolve():
                return destination
        except FileNotFoundError:
            pass

        destination = self._ensure_unique_path(destination)
        if move:
            shutil.move(str(source), str(destination))
        else:
            shutil.copytree(source, destination)
        return destination

    def _run_tool(self, args: list[str]) -> None:
        try:
            result = subprocess.run(
                args,
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except FileNotFoundError as exc:
            err_msg = ErrorHelper.match_and_format_error(str(exc))
            raise RuntimeError(err_msg) from exc
        except subprocess.CalledProcessError as exc:
            details = (exc.stderr or exc.stdout or "").strip()
            err_msg = ErrorHelper.match_and_format_error(details)
            raise RuntimeError(err_msg) from exc

        if result.stdout.strip():
            safe_print(result.stdout.strip())

    def apply_template(self, project_path: str, template_name: str, force: bool = False) -> dict[str, list[Path] | str]:
        """Copy a library layout template into a project workspace."""
        project_path_obj = resolve_repo_relative_dir(project_path)
        template_dir = TEMPLATE_LAYOUTS_DIR / template_name

        if not project_path_obj.exists():
            raise FileNotFoundError(f"Project path does not exist: {project_path_obj}")
        if not template_dir.exists() or not template_dir.is_dir():
            raise FileNotFoundError(f"Template not found: {template_name}")

        target_templates_dir = project_path_obj / "templates"
        target_images_dir = project_path_obj / "images"
        manifest_path = target_templates_dir / TEMPLATE_MANIFEST_NAME
        target_templates_dir.mkdir(parents=True, exist_ok=True)
        target_images_dir.mkdir(parents=True, exist_ok=True)

        copied_templates: list[Path] = []
        copied_images: list[Path] = []

        for source in sorted(template_dir.iterdir()):
            if not source.is_file():
                continue

            suffix = source.suffix.lower()
            if suffix == ".svg" or source.name == "design_spec.md":
                destination_dir = target_templates_dir
            elif suffix in TEMPLATE_IMAGE_SUFFIXES:
                destination_dir = target_images_dir
            else:
                continue

            destination = destination_dir / source.name
            if destination.exists() and not force:
                raise FileExistsError(
                    f"Target file already exists: {destination}. "
                    "Pass --force to overwrite the existing project template files."
                )

            shutil.copy2(source, destination)
            if destination_dir == target_templates_dir:
                copied_templates.append(destination)
            else:
                copied_images.append(destination)

        if not copied_templates:
            raise RuntimeError(
                f"Template '{template_name}' does not contain any SVG files or design_spec.md to import."
            )

        manifest = {
            "template_name": template_name,
            "applied_at": datetime.now().isoformat(timespec="seconds"),
            "template_files": [path.name for path in copied_templates],
            "image_files": [path.name for path in copied_images],
        }
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

        return {
            "template_name": template_name,
            "project_path": project_path_obj,
            "templates": copied_templates,
            "images": copied_images,
            "manifest": manifest_path,
        }

    def _import_pdf(self, pdf_path: Path, markdown_path: Path) -> None:
        self._run_tool(
            [
                sys.executable,
                str(TOOLS_DIR / "source_to_md" / "pdf_to_md.py"),
                str(pdf_path),
                "-o",
                str(markdown_path),
            ]
        )

    def _import_doc(self, doc_path: Path, markdown_path: Path) -> None:
        self._run_tool(
            [
                sys.executable,
                str(TOOLS_DIR / "source_to_md" / "doc_to_md.py"),
                str(doc_path),
                "-o",
                str(markdown_path),
            ]
        )

    def _import_presentation(self, presentation_path: Path, markdown_path: Path) -> None:
        self._run_tool(
            [
                sys.executable,
                str(TOOLS_DIR / "source_to_md" / "ppt_to_md.py"),
                str(presentation_path),
                "-o",
                str(markdown_path),
            ]
        )

    def _import_url(self, url: str, markdown_path: Path) -> None:
        # Prefer web_to_md.py: it uses curl_cffi internally when available,
        # which handles WeChat and other TLS-fingerprint-blocked sites.
        # Fall back to the Node.js version only when the URL is known to
        # require TLS impersonation AND curl_cffi isn't installed.
        host = urlparse(url).netloc.lower()
        is_tls_sensitive = any(keyword in host for keyword in WECHAT_HOST_KEYWORDS)

        if is_tls_sensitive and not _curl_cffi_available() and shutil.which("node"):
            command = ["node", str(TOOLS_DIR / "source_to_md" / "web_to_md.cjs"),
                       url, "-o", str(markdown_path)]
        else:
            command = [
                sys.executable,
                str(TOOLS_DIR / "source_to_md" / "web_to_md.py"),
                url,
                "-o",
                str(markdown_path),
            ]
        self._run_tool(command)

    def _archive_url_record(self, sources_dir: Path, url: str) -> Path:
        file_path = self._ensure_unique_path(sources_dir / f"{derive_url_basename(url)}.url.txt")
        file_path.write_text(
            f"URL: {url}\nImported: {datetime.now().isoformat(timespec='seconds')}\n",
            encoding="utf-8",
        )
        return file_path

    def _normalize_text_source(self, source_path: Path, sources_dir: Path) -> Path:
        target = self._ensure_unique_path(sources_dir / f"{source_path.stem}.md")
        content = source_path.read_text(encoding="utf-8", errors="replace")
        target.write_text(content, encoding="utf-8")
        return target

    def _canonicalize_markdown_content(self, content: str) -> str:
        canonical = content.replace("\r\n", "\n")
        canonical = re.sub(r"(?m)^(\s*Crawled:\s+).*$", r"\1__IGNORED__", canonical)
        canonical = re.sub(r"(?m)^(\s*Imported:\s+).*$", r"\1__IGNORED__", canonical)
        canonical = re.sub(r"([^\s\]()/]+_files)/", "__ASSET_DIR__/", canonical)
        return canonical.strip()

    def _find_equivalent_markdown(self, source_path: Path, sources_dir: Path) -> Path | None:
        source_content = source_path.read_text(encoding="utf-8", errors="replace")
        canonical_source = self._canonicalize_markdown_content(source_content)

        for existing in sorted(sources_dir.iterdir()):
            if existing.suffix.lower() not in {".md", ".markdown"}:
                continue
            try:
                if existing.resolve() == source_path.resolve():
                    continue
            except FileNotFoundError:
                pass

            existing_content = existing.read_text(encoding="utf-8", errors="replace")
            if self._canonicalize_markdown_content(existing_content) == canonical_source:
                return existing

        return None

    def _companion_asset_dir(self, source_path: Path) -> Path | None:
        candidate = source_path.with_name(f"{source_path.stem}_files")
        if candidate.exists() and candidate.is_dir():
            return candidate
        return None

    def _rewrite_markdown_asset_refs(
        self,
        markdown_path: Path,
        original_asset_dirname: str,
        imported_asset_dirname: str,
    ) -> None:
        if original_asset_dirname == imported_asset_dirname:
            return

        content = markdown_path.read_text(encoding="utf-8", errors="replace")
        updated = content.replace(f"{original_asset_dirname}/", f"{imported_asset_dirname}/")
        if updated != content:
            markdown_path.write_text(updated, encoding="utf-8")

    def _import_markdown_with_assets(
        self,
        source_path: Path,
        sources_dir: Path,
        move: bool,
    ) -> tuple[Path, Path | None, str | None]:
        destination_name = english_filename_for_path(source_path, prefix="source")
        archived_markdown = self._copy_or_move_file(
            source_path,
            sources_dir / destination_name,
            move=move,
        )

        asset_dir = self._companion_asset_dir(source_path)
        if asset_dir is None:
            return archived_markdown, None, None

        imported_asset_dir = self._copy_or_move_tree(
            asset_dir,
            sources_dir / f"{archived_markdown.stem}_files",
            move=move,
        )
        self._rewrite_markdown_asset_refs(
            archived_markdown,
            original_asset_dirname=asset_dir.name,
            imported_asset_dirname=imported_asset_dir.name,
        )

        note = None
        if archived_markdown.name != source_path.name:
            note = (
                f"{source_path.name}: normalized to English filename {archived_markdown.name} "
                f"and rewrote asset references to {imported_asset_dir.name}/"
            )
        return archived_markdown, imported_asset_dir, note

    def import_sources(
        self,
        project_path: str,
        source_items: list[str],
        move: bool = False,
        copy: bool = False,
    ) -> dict[str, list[str]]:
        if move and copy:
            raise ValueError("--move and --copy are mutually exclusive")
        project_dir = Path(project_path)
        if not project_dir.exists() or not project_dir.is_dir():
            raise FileNotFoundError(f"Project directory not found: {project_dir}")
        if not source_items:
            raise ValueError("At least one source path or URL is required")

        sources_dir = self._source_dir(project_dir)
        summary: dict[str, list[str]] = {
            "archived": [],
            "markdown": [],
            "assets": [],
            "notes": [],
            "skipped": [],
        }
        explicit_markdown_stems = {
            Path(item).stem
            for item in source_items
            if not is_url(item)
            and Path(item).exists()
            and Path(item).is_file()
            and Path(item).suffix.lower() in {".md", ".markdown"}
        }

        for item in source_items:
            if is_url(item):
                archived = self._archive_url_record(sources_dir, item)
                markdown_path = self._ensure_unique_path(
                    sources_dir / f"{derive_url_basename(item)}.md"
                )
                try:
                    self._import_url(item, markdown_path)
                except Exception as exc:  # pragma: no cover - summary path
                    summary["skipped"].append(f"{item}: {exc}")
                    continue

                summary["archived"].append(str(archived))
                summary["markdown"].append(str(markdown_path))
                continue

            source_path = Path(item)
            if not source_path.exists():
                summary["skipped"].append(f"{item}: path not found")
                continue
            if source_path.is_dir():
                summary["skipped"].append(f"{item}: directories are not supported")
                continue

            if copy:
                effective_move = False
            elif move:
                effective_move = True
            elif is_within_path(source_path, REPO_ROOT):
                effective_move = True
                safe_print(
                    f"note: {source_path} is inside the ppt-master repo; moved "
                    f"(not copied) to avoid accidental commit. Pass --copy to override.",
                    file=sys.stderr,
                )
            else:
                effective_move = False
            suffix = source_path.suffix.lower()

            if suffix in {".md", ".markdown"}:
                duplicate_markdown = self._find_equivalent_markdown(source_path, sources_dir)
                if duplicate_markdown is not None:
                    summary["markdown"].append(str(duplicate_markdown))
                    summary["notes"].append(
                        f"{item}: skipped duplicate markdown import because equivalent content already exists as {duplicate_markdown.name}"
                    )
                    continue

                archived_markdown, asset_dir, note = self._import_markdown_with_assets(
                    source_path,
                    sources_dir,
                    move=effective_move,
                )
                summary["archived"].append(str(archived_markdown))
                summary["markdown"].append(str(archived_markdown))
                if asset_dir is not None:
                    summary["assets"].append(str(asset_dir))
                if note:
                    summary["notes"].append(note)
                continue

            archived_path = self._copy_or_move_file(
                source_path,
                sources_dir / english_filename_for_path(source_path, prefix="source"),
                move=effective_move,
            )
            summary["archived"].append(str(archived_path))
            if archived_path.name != source_path.name:
                summary["notes"].append(
                    f"{source_path.name}: normalized to English filename {archived_path.name}"
                )

            if suffix in PDF_SUFFIXES:
                canonical_markdown_path = sources_dir / f"{archived_path.stem}.md"
                if archived_path.stem in explicit_markdown_stems:
                    summary["notes"].append(
                        f"{item}: skipped PDF auto-conversion because a same-stem Markdown source was provided"
                    )
                    continue
                if canonical_markdown_path.exists():
                    summary["markdown"].append(str(canonical_markdown_path))
                    summary["notes"].append(
                        f"{item}: skipped PDF auto-conversion because {canonical_markdown_path.name} already exists"
                    )
                    continue
                markdown_path = canonical_markdown_path
                try:
                    self._import_pdf(archived_path, markdown_path)
                    summary["markdown"].append(str(markdown_path))
                except Exception as exc:  # pragma: no cover - summary path
                    summary["skipped"].append(f"{item}: PDF conversion failed ({exc})")
            elif suffix in PRESENTATION_SUFFIXES:
                canonical_markdown_path = sources_dir / f"{archived_path.stem}.md"
                if archived_path.stem in explicit_markdown_stems:
                    summary["notes"].append(
                        f"{item}: skipped presentation auto-conversion because a same-stem Markdown source was provided"
                    )
                    continue
                if canonical_markdown_path.exists():
                    summary["markdown"].append(str(canonical_markdown_path))
                    summary["notes"].append(
                        f"{item}: skipped presentation auto-conversion because {canonical_markdown_path.name} already exists"
                    )
                    continue
                markdown_path = canonical_markdown_path
                try:
                    self._import_presentation(archived_path, markdown_path)
                    summary["markdown"].append(str(markdown_path))
                except Exception as exc:  # pragma: no cover - summary path
                    summary["skipped"].append(f"{item}: presentation conversion failed ({exc})")
            elif suffix in DOC_SUFFIXES:
                canonical_markdown_path = sources_dir / f"{archived_path.stem}.md"
                if archived_path.stem in explicit_markdown_stems:
                    summary["notes"].append(
                        f"{item}: skipped document auto-conversion because a same-stem Markdown source was provided"
                    )
                    continue
                if canonical_markdown_path.exists():
                    summary["markdown"].append(str(canonical_markdown_path))
                    summary["notes"].append(
                        f"{item}: skipped document auto-conversion because {canonical_markdown_path.name} already exists"
                    )
                    continue
                markdown_path = canonical_markdown_path
                try:
                    self._import_doc(archived_path, markdown_path)
                    summary["markdown"].append(str(markdown_path))
                except Exception as exc:  # pragma: no cover - summary path
                    summary["skipped"].append(f"{item}: document conversion failed ({exc})")
            elif suffix == ".txt":
                markdown_path = self._normalize_text_source(archived_path, sources_dir)
                summary["markdown"].append(str(markdown_path))
            else:
                summary["notes"].append(f"{item}: archived only, no automatic conversion")

        return summary

    def validate_project(self, project_path: str) -> tuple[bool, list[str], list[str]]:
        project_path_obj = Path(project_path)
        is_valid, errors, warnings = validate_project_structure(str(project_path_obj))

        if project_path_obj.exists() and project_path_obj.is_dir():
            info = get_project_info_common(str(project_path_obj))
            if info.get("svg_files"):
                svg_files = [project_path_obj / "svg_output" / name for name in info["svg_files"]]
                expected_format = info.get("format")
                if expected_format == "unknown":
                    expected_format = None
                warnings.extend(validate_svg_viewbox(svg_files, expected_format))

        return is_valid, errors, warnings

    def get_project_info(self, project_path: str) -> dict[str, object]:
        shared = get_project_info_common(project_path)
        return {
            "name": shared.get("name", Path(project_path).name),
            "path": shared.get("path", str(project_path)),
            "exists": shared.get("exists", False),
            "svg_count": shared.get("svg_count", 0),
            "has_spec": shared.get("has_spec", False),
            "has_source": shared.get("has_source", False),
            "source_count": shared.get("source_count", 0),
            "canvas_format": shared.get("format_name", "Unknown"),
            "create_date": shared.get("date_formatted", "Unknown"),
        }


def print_usage() -> None:
    """Print CLI usage information from the module docstring."""
    safe_print(__doc__)


def parse_init_args(argv: list[str]) -> tuple[str, str, str]:
    """Parse arguments for the `init` subcommand."""
    if len(argv) < 3:
        raise ValueError("Project name is required")

    project_name = argv[2]
    canvas_format = "ppt169"
    base_dir = "projects"

    i = 3
    while i < len(argv):
        if argv[i] == "--format" and i + 1 < len(argv):
            canvas_format = argv[i + 1]
            i += 2
        elif argv[i] == "--dir" and i + 1 < len(argv):
            base_dir = argv[i + 1]
            i += 2
        else:
            i += 1

    return project_name, canvas_format, base_dir


def parse_import_args(argv: list[str]) -> tuple[str, list[str], bool, bool]:
    """Parse arguments for the `import-sources` subcommand."""
    if len(argv) < 4:
        raise ValueError("Project path and at least one source are required")

    project_path = argv[2]
    move = False
    copy = False
    sources: list[str] = []

    for arg in argv[3:]:
        if arg == "--move":
            move = True
        elif arg == "--copy":
            copy = True
        else:
            sources.append(arg)

    if move and copy:
        raise ValueError("--move and --copy are mutually exclusive")

    return project_path, sources, move, copy


def parse_apply_template_args(argv: list[str]) -> tuple[str, str, bool]:
    """Parse arguments for the `apply-template` subcommand."""
    if len(argv) < 4:
        raise ValueError("Project path and template name are required")

    project_path = argv[2]
    template_name = argv[3]
    force = "--force" in argv[4:]
    return project_path, template_name, force


def main() -> None:
    """Run the CLI entry point."""
    configure_utf8_stdio()
    if not check_conda_env():
        sys.exit(1)
    argv, json_output, report_file = extract_common_cli_options(sys.argv)
    if len(argv) < 2:
        print_usage()
        sys.exit(1)

    command = argv[1]
    if command in {"-h", "--help", "help"}:
        print_usage()
        return
    manager = ProjectManager()

    try:
        if command == "init":
            project_name, canvas_format, base_dir = parse_init_args(argv)
            project_path = manager.init_project(project_name, canvas_format, base_dir=base_dir)
            payload = {
                "ok": True,
                "command": "init",
                "project_name": project_name,
                "canvas_format": canvas_format,
                "base_dir": base_dir,
                "project_path": to_display_path_text(project_path),
                "next_steps": [
                    "Put source files into sources/ (or use import-sources)",
                    "Save your design spec to the project root",
                    "Use review/review_state.json as the machine review source and render Markdown reports from it",
                    "Generate SVG files into svg_output/",
                ],
            }
            safe_print(f"[OK] Project initialized: {project_path}")
            safe_print("Next:")
            safe_print("1. Put source files into sources/ (or use import-sources)")
            safe_print("2. Save your design spec to the project root")
            safe_print("3. Use review/review_state.json as the machine review source and render Markdown reports from it")
            safe_print("4. Generate SVG files into svg_output/")
            emit_command_result("init", payload, json_output=json_output, report_file=report_file)
            return

        if command == "import-sources":
            project_path, sources, move, copy = parse_import_args(argv)
            summary = manager.import_sources(project_path, sources, move=move, copy=copy)
            payload = {
                "ok": True,
                "command": "import-sources",
                "project_path": to_display_path_text(project_path),
                "sources": sources,
                "move": move,
                "copy": copy,
                "summary": {
                    key: [to_display_path_text(item) for item in value] if isinstance(value, list) else value
                    for key, value in summary.items()
                },
            }
            safe_print(f"[OK] Imported sources into: {project_path}")
            if summary["archived"]:
                safe_print("\nArchived originals / URL records:")
                for item in summary["archived"]:
                    safe_print(f"  - {item}")
            if summary["markdown"]:
                safe_print("\nNormalized markdown:")
                for item in summary["markdown"]:
                    safe_print(f"  - {item}")
            if summary["assets"]:
                safe_print("\nImported asset directories:")
                for item in summary["assets"]:
                    safe_print(f"  - {item}")
            if summary["notes"]:
                safe_print("\nNotes:")
                for item in summary["notes"]:
                    safe_print(f"  - {item}")
            if summary["skipped"]:
                safe_print("\nSkipped:")
                for item in summary["skipped"]:
                    safe_print(f"  - {item}")
            emit_command_result("import-sources", payload, json_output=json_output, report_file=report_file)
            return

        if command == "apply-template":
            project_path, template_name, force = parse_apply_template_args(argv)
            summary = manager.apply_template(project_path, template_name, force=force)
            payload = {
                "ok": True,
                "command": "apply-template",
                "project_path": to_display_path_text(project_path),
                "template_name": template_name,
                "force": force,
                "summary": {
                    "templates": [to_display_path_text(item) for item in summary["templates"]],
                    "images": [to_display_path_text(item) for item in summary["images"]],
                    "manifest": to_display_path_text(summary["manifest"]),
                },
            }
            safe_print(f"[OK] Applied template '{template_name}' to: {project_path}")
            safe_print("\nProject template files:")
            for item in summary["templates"]:
                safe_print(f"  - {item}")
            if summary["images"]:
                safe_print("\nImported template image assets:")
                for item in summary["images"]:
                    safe_print(f"  - {item}")
            safe_print(f"\nTemplate manifest: {summary['manifest']}")
            emit_command_result("apply-template", payload, json_output=json_output, report_file=report_file)
            return

        if command == "validate":
            if len(argv) < 3:
                raise ValueError("Project path is required")

            project_path = argv[2]
            is_valid, errors, warnings = manager.validate_project(project_path)
            payload = {
                "ok": is_valid,
                "command": "validate",
                "project_path": to_display_path_text(project_path),
                "errors": errors,
                "warnings": warnings,
            }

            safe_print(f"\nProject validation: {project_path}")
            safe_print("=" * 60)

            if errors:
                safe_print("\n[ERROR]")
                for error in errors:
                    safe_print(f"  - {error}")

            if warnings:
                safe_print("\n[WARN]")
                for warning in warnings:
                    safe_print(f"  - {warning}")

            if is_valid and not warnings:
                safe_print("\n[OK] Project structure is complete.")
            elif is_valid:
                safe_print("\n[OK] Project structure is valid, with warnings.")
            else:
                safe_print("\n[ERROR] Project structure is invalid.")
                emit_command_result("validate", payload, json_output=json_output, report_file=report_file)
                sys.exit(1)
            emit_command_result("validate", payload, json_output=json_output, report_file=report_file)
            return

        if command == "info":
            if len(argv) < 3:
                raise ValueError("Project path is required")

            project_path = argv[2]
            info = manager.get_project_info(project_path)
            payload = {
                "ok": bool(info.get("exists")),
                "command": "info",
                "project_path": to_display_path_text(project_path),
                "info": info,
            }

            safe_print(f"\nProject info: {info['name']}")
            safe_print("=" * 60)
            safe_print(f"Path: {info['path']}")
            safe_print(f"Exists: {'Yes' if info['exists'] else 'No'}")
            safe_print(f"SVG files: {info['svg_count']}")
            safe_print(f"Design spec: {'Yes' if info['has_spec'] else 'No'}")
            safe_print(f"Source materials: {'Yes' if info['has_source'] else 'No'}")
            safe_print(f"Source count: {info['source_count']}")
            safe_print(f"Template applied: {'Yes' if info.get('template_ready') else 'No'}")
            if info.get("template_name"):
                safe_print(f"Template name: {info['template_name']}")
            safe_print(f"Template SVG files: {info.get('template_svg_count', 0)}")
            safe_print(f"Canvas format: {info['canvas_format']}")
            safe_print(f"Created: {info['create_date']}")
            emit_command_result("info", payload, json_output=json_output, report_file=report_file)
            return

        raise ValueError(f"Unknown command: {command}")
    except Exception as exc:
        error_message = str(exc)
        report_file_override = report_file
        payload = {
            "ok": False,
            "command": command,
            "error": error_message,
        }
        if error_message.startswith("Unknown command:"):
            payload["invalid_command"] = command
            hint = DEPRECATED_COMMAND_HINTS.get(command)
            if hint:
                payload["hint"] = hint
                payload["error"] = f"{error_message} {hint}"
            if report_file_override is None:
                report_file_override = default_report_path("error")
            emit_command_result("error", payload, json_output=json_output, report_file=report_file_override)
        else:
            emit_command_result(command, payload, json_output=json_output, report_file=report_file_override)
        safe_print(f"[ERROR] {payload['error']}")
        print_usage()
        sys.exit(1)


if __name__ == "__main__":
    main()


