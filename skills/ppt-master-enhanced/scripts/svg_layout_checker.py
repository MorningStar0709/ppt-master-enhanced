#!/usr/bin/env python3
"""Check SVG layout geometry for obvious overflow and coordinate mistakes."""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

try:
    from runtime_utils import configure_utf8_stdio
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from runtime_utils import configure_utf8_stdio  # type: ignore


class SVGLayoutChecker:
    """Lightweight geometry checker for slide-sized SVG pages."""

    def __init__(self) -> None:
        self.results: list[dict] = []
        self.summary = {"total": 0, "passed": 0, "warnings": 0, "errors": 0}

    def check_file(self, svg_file: str) -> dict:
        path = Path(svg_file)
        result = {
            "file": path.name,
            "path": str(path),
            "errors": [],
            "warnings": [],
            "info": {},
            "passed": True,
        }

        try:
            root = ET.fromstring(path.read_text(encoding="utf-8"))
        except Exception as exc:
            result["errors"].append(f"Layout check failed to parse XML: {exc}")
            result["passed"] = False
            self._finalize(result)
            return result

        canvas = self._canvas_size(root)
        if canvas is None:
            result["errors"].append("Missing or invalid viewBox; cannot run layout geometry checks")
            result["passed"] = False
            self._finalize(result)
            return result

        canvas_w, canvas_h = canvas
        result["info"]["canvas"] = f"{int(canvas_w)}x{int(canvas_h)}"
        self._walk(root, result, canvas_w, canvas_h, tx=0.0, ty=0.0)
        self._check_translated_groups(root, result)

        result["passed"] = len(result["errors"]) == 0
        self._finalize(result)
        return result

    def check_directory(self, target: str, print_results: bool = True) -> list[dict]:
        path = Path(target)
        if path.is_file():
            svg_files = [path]
        else:
            svg_root = path / "svg_output" if (path / "svg_output").exists() else path
            svg_files = sorted(svg_root.glob("*.svg"))

        for svg_file in svg_files:
            result = self.check_file(str(svg_file))
            if print_results:
                self._print_result(result)
        return self.results

    def _finalize(self, result: dict) -> None:
        self.summary["total"] += 1
        if result["passed"]:
            if result["warnings"]:
                self.summary["warnings"] += 1
            else:
                self.summary["passed"] += 1
        else:
            self.summary["errors"] += 1
        self.results.append(result)

    def _canvas_size(self, root) -> tuple[float, float] | None:
        viewbox = root.attrib.get("viewBox", "").strip().split()
        if len(viewbox) != 4:
            return None
        try:
            return float(viewbox[2]), float(viewbox[3])
        except ValueError:
            return None

    def _walk(self, element, result: dict, canvas_w: float, canvas_h: float, tx: float, ty: float) -> None:
        local_tx, local_ty = self._parse_translate(element.attrib.get("transform", ""))
        tx += local_tx
        ty += local_ty

        tag = self._local_name(element.tag)
        if tag == "text":
            self._check_text_bounds(element, result, canvas_w, canvas_h, tx, ty)
        elif tag == "rect":
            self._check_rect_bounds(element, result, canvas_w, canvas_h, tx, ty)
        elif tag == "circle":
            self._check_circle_bounds(element, result, canvas_w, canvas_h, tx, ty)
        elif tag == "line":
            self._check_line_bounds(element, result, canvas_w, canvas_h, tx, ty)

        for child in list(element):
            self._walk(child, result, canvas_w, canvas_h, tx, ty)

    def _check_rect_bounds(self, element, result: dict, canvas_w: float, canvas_h: float, tx: float, ty: float) -> None:
        x = self._float(element.attrib.get("x"), 0.0) + tx
        y = self._float(element.attrib.get("y"), 0.0) + ty
        w = self._float(element.attrib.get("width"), 0.0)
        h = self._float(element.attrib.get("height"), 0.0)
        self._check_bbox(f"rect#{element.attrib.get('id', '')}".strip("#"), x, y, x + w, y + h, result, canvas_w, canvas_h)

    def _check_circle_bounds(self, element, result: dict, canvas_w: float, canvas_h: float, tx: float, ty: float) -> None:
        cx = self._float(element.attrib.get("cx"), 0.0) + tx
        cy = self._float(element.attrib.get("cy"), 0.0) + ty
        r = self._float(element.attrib.get("r"), 0.0)
        if self._is_allowed_decorative_bleed_circle(element, cx, cy, r, canvas_w, canvas_h):
            return
        self._check_bbox(f"circle#{element.attrib.get('id', '')}".strip("#"), cx - r, cy - r, cx + r, cy + r, result, canvas_w, canvas_h)

    def _check_line_bounds(self, element, result: dict, canvas_w: float, canvas_h: float, tx: float, ty: float) -> None:
        x1 = self._float(element.attrib.get("x1"), 0.0) + tx
        y1 = self._float(element.attrib.get("y1"), 0.0) + ty
        x2 = self._float(element.attrib.get("x2"), 0.0) + tx
        y2 = self._float(element.attrib.get("y2"), 0.0) + ty
        self._check_bbox(
            f"line#{element.attrib.get('id', '')}".strip("#"),
            min(x1, x2),
            min(y1, y2),
            max(x1, x2),
            max(y1, y2),
            result,
            canvas_w,
            canvas_h,
        )

    def _check_text_bounds(self, element, result: dict, canvas_w: float, canvas_h: float, tx: float, ty: float) -> None:
        tspans = [child for child in list(element) if self._local_name(child.tag) == "tspan"]
        if tspans:
            self._check_tspan_bounds(element, tspans, result, canvas_w, canvas_h, tx, ty)
            return

        x = self._float(element.attrib.get("x"), 0.0) + tx
        y = self._float(element.attrib.get("y"), 0.0) + ty
        font_size = self._float(element.attrib.get("font-size"), 16.0)
        text = "".join(element.itertext()).strip()
        text_anchor = element.attrib.get("text-anchor", "start").strip()
        self._check_text_line_bounds(
            text=text,
            x=x,
            y=y,
            font_size=font_size,
            text_anchor=text_anchor,
            result=result,
            canvas_w=canvas_w,
            canvas_h=canvas_h,
        )

    def _check_tspan_bounds(
        self,
        element,
        tspans,
        result: dict,
        canvas_w: float,
        canvas_h: float,
        tx: float,
        ty: float,
    ) -> None:
        base_x = self._float(element.attrib.get("x"), 0.0) + tx
        current_y = self._float(element.attrib.get("y"), 0.0) + ty
        default_font_size = self._float(element.attrib.get("font-size"), 16.0)
        text_anchor = element.attrib.get("text-anchor", "start").strip()

        for tspan in tspans:
            if "x" in tspan.attrib:
                x = self._float(tspan.attrib.get("x"), 0.0) + tx
            else:
                x = base_x

            if "y" in tspan.attrib:
                current_y = self._float(tspan.attrib.get("y"), 0.0) + ty

            font_size = self._float(tspan.attrib.get("font-size"), default_font_size)
            dy = tspan.attrib.get("dy")
            if dy not in (None, ""):
                current_y += self._relative_text_length(dy, font_size)

            text = "".join(tspan.itertext()).strip()
            self._check_text_line_bounds(
                text=text,
                x=x,
                y=current_y,
                font_size=font_size,
                text_anchor=text_anchor,
                result=result,
                canvas_w=canvas_w,
                canvas_h=canvas_h,
            )

    def _check_text_line_bounds(
        self,
        text: str,
        x: float,
        y: float,
        font_size: float,
        text_anchor: str,
        result: dict,
        canvas_w: float,
        canvas_h: float,
    ) -> None:
        est_width = max(font_size * max(len(text), 1) * 0.58, font_size)
        if text_anchor == "middle":
            x_min = x - est_width / 2
            x_max = x + est_width / 2
        elif text_anchor == "end":
            x_min = x - est_width
            x_max = x
        else:
            x_min = x
            x_max = x + est_width
        y_min = y - font_size
        y_max = y + font_size * 0.3
        self._check_bbox(f"text:{text[:20]}", x_min, y_min, x_max, y_max, result, canvas_w, canvas_h, text=text)

    def _check_bbox(
        self,
        label: str,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        result: dict,
        canvas_w: float,
        canvas_h: float,
        text: str | None = None,
    ) -> None:
        margin = 2.0
        if x2 < -margin or y2 < -margin or x1 > canvas_w + margin or y1 > canvas_h + margin:
            result["errors"].append(f"{label} is completely outside the canvas")
            return
        if x1 < -margin or y1 < -margin or x2 > canvas_w + margin or y2 > canvas_h + margin:
            msg = f"{label} exceeds the canvas bounds"
            if text:
                msg += f" ({text})"
            result["warnings"].append(msg)

    def _check_translated_groups(self, root, result: dict) -> None:
        for group in root.iter():
            if self._local_name(group.tag) != "g":
                continue
            transform = group.attrib.get("transform", "")
            if "translate" not in transform:
                continue
            rects = [child for child in list(group) if self._local_name(child.tag) == "rect"]
            if len(rects) != 1:
                continue
            rect = rects[0]
            rect_x = self._float(rect.attrib.get("x"), 0.0)
            rect_y = self._float(rect.attrib.get("y"), 0.0)
            rect_w = self._float(rect.attrib.get("width"), 0.0)
            rect_h = self._float(rect.attrib.get("height"), 0.0)
            if rect_w <= 0 or rect_h <= 0:
                continue
            # Ignore decorative bars and underlines; they are not container rects.
            if rect_w < 120 or rect_h < 24:
                continue
            for child in list(group):
                if self._local_name(child.tag) != "text":
                    continue
                x = self._float(child.attrib.get("x"), 0.0)
                y = self._float(child.attrib.get("y"), 0.0)
                if x > rect_x + rect_w + 40 or y > rect_y + rect_h + 20:
                    text = "".join(child.itertext()).strip()
                    result["warnings"].append(
                        f"Group {group.attrib.get('id', '<unnamed>')} uses translate() but child text looks like page-level coordinates: {text}"
                    )

    def _is_allowed_decorative_bleed_circle(
        self,
        element,
        cx: float,
        cy: float,
        r: float,
        canvas_w: float,
        canvas_h: float,
    ) -> bool:
        """Allow common background-decoration circles to bleed slightly outside the canvas."""
        fill_opacity = self._float(element.attrib.get("fill-opacity"), 1.0)
        opacity = self._float(element.attrib.get("opacity"), 1.0)
        stroke = element.attrib.get("stroke", "").strip().lower()
        if min(fill_opacity, opacity) > 0.08:
            return False
        if stroke and stroke not in {"none", "transparent"}:
            return False
        if cx < 0 or cy < 0 or cx > canvas_w or cy > canvas_h:
            return False
        overflow = max(
            0.0 - (cx - r),
            0.0 - (cy - r),
            (cx + r) - canvas_w,
            (cy + r) - canvas_h,
            0.0,
        )
        return overflow > 0

    def summary_dict(self) -> dict:
        return {"summary": self.summary, "results": self.results}

    def print_summary(self, compact: bool = False) -> None:
        if compact:
            print(
                "Layout summary: "
                f"total={self.summary['total']} "
                f"passed={self.summary['passed']} "
                f"warnings={self.summary['warnings']} "
                f"errors={self.summary['errors']}"
            )
            return
        print("Layout summary")
        print(json.dumps(self.summary, ensure_ascii=True, indent=2))

    def _print_result(self, result: dict) -> None:
        if result["errors"]:
            status = "[ERROR]"
        elif result["warnings"]:
            status = "[WARN]"
        else:
            status = "[OK]"
        print(f"{status} {result['file']}")
        for error in result["errors"]:
            print(f"  [ERROR] {error}")
        for warning in result["warnings"][:6]:
            print(f"  [WARN] {warning}")
        if len(result["warnings"]) > 6:
            print(f"  [WARN] ... and {len(result['warnings']) - 6} more")
        print()

    def _parse_translate(self, transform: str) -> tuple[float, float]:
        match = re.search(r"translate\(\s*([-\d.]+)(?:[\s,]+([-\d.]+))?\s*\)", transform)
        if not match:
            return 0.0, 0.0
        x = self._float(match.group(1), 0.0)
        y = self._float(match.group(2), 0.0)
        return x, y

    def _float(self, value, default: float) -> float:
        if value in (None, ""):
            return default
        text = str(value).strip()
        text = re.sub(r"[a-zA-Z%]+$", "", text)
        try:
            return float(text)
        except ValueError:
            return default

    def _relative_text_length(self, value, font_size: float) -> float:
        if value in (None, ""):
            return 0.0
        text = str(value).strip()
        if text.endswith("em"):
            return self._float(text[:-2], 0.0) * font_size
        return self._float(text, 0.0)

    def _local_name(self, tag: str) -> str:
        return tag.split("}", 1)[-1] if "}" in tag else tag


def main() -> None:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(description="PPT Master - SVG layout geometry checker")
    parser.add_argument("target", help="SVG file or project directory")
    parser.add_argument("--summary-only", action="store_true", help="Only print summary")
    parser.add_argument("--json", action="store_true", help="Print JSON")
    args = parser.parse_args()

    checker = SVGLayoutChecker()
    checker.check_directory(args.target, print_results=not args.summary_only and not args.json)

    if args.json:
        print(json.dumps(checker.summary_dict(), ensure_ascii=True, indent=2))
    else:
        checker.print_summary(compact=args.summary_only)

    sys.exit(1 if checker.summary["errors"] > 0 else 0)


if __name__ == "__main__":
    main()
