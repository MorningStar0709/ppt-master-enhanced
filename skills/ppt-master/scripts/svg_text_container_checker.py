#!/usr/bin/env python3
"""Check whether text content overflows its likely background container."""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

try:
    from runtime_utils import configure_utf8_stdio
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from runtime_utils import configure_utf8_stdio  # type: ignore


@dataclass
class RectBox:
    x: float
    y: float
    w: float
    h: float
    label: str
    area: float


class SVGTextContainerChecker:
    """Detect obvious text overflow relative to a local card/container rect."""

    MIN_CONTAINER_WIDTH = 120.0
    MIN_CONTAINER_HEIGHT = 48.0
    SAFE_MARGIN_X = 12.0
    SAFE_MARGIN_Y = 10.0
    HARD_OVERFLOW_TOLERANCE = 2.0
    CROWDING_TOLERANCE = 4.0
    MAX_BACKGROUND_WIDTH_RATIO = 0.96
    MAX_BACKGROUND_HEIGHT_RATIO = 0.85

    def __init__(self) -> None:
        self.results: list[dict] = []
        self.summary = {"total": 0, "passed": 0, "warnings": 0, "errors": 0}

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

    def check_file(self, svg_file: str) -> dict:
        path = Path(svg_file)
        result = {
            "file": path.name,
            "path": str(path),
            "errors": [],
            "warnings": [],
            "compact_issues": [],
            "info": {"containers_checked": 0},
            "passed": True,
        }

        try:
            root = ET.fromstring(path.read_text(encoding="utf-8"))
        except Exception as exc:
            self._add_issue(
                result,
                severity="error",
                issue_type="xml_parse_error",
                container="<file>",
                text=str(exc),
                message=f"Text/container check failed to parse XML: {exc}",
            )
            result["passed"] = False
            self._finalize(result)
            return result

        canvas_w, canvas_h = self._canvas_size(root)
        rects: list[RectBox] = []
        text_boxes: list[dict] = []
        self._collect_geometry(root, rects, text_boxes, tx=0.0, ty=0.0, canvas_w=canvas_w, canvas_h=canvas_h)
        result["info"]["containers_checked"] = self._assign_and_check(rects, text_boxes, result)
        result["passed"] = len(result["errors"]) == 0
        self._finalize(result)
        return result

    def summary_dict(self) -> dict:
        return {"summary": self.summary, "results": self.results}

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

    def _canvas_size(self, root) -> tuple[float, float]:
        viewbox = root.attrib.get("viewBox", "").strip().split()
        if len(viewbox) == 4:
            try:
                return float(viewbox[2]), float(viewbox[3])
            except ValueError:
                pass
        return (
            self._float(root.attrib.get("width"), 1280.0),
            self._float(root.attrib.get("height"), 720.0),
        )

    def _collect_geometry(
        self,
        element,
        rects: list[RectBox],
        text_boxes: list[dict],
        tx: float,
        ty: float,
        canvas_w: float,
        canvas_h: float,
    ) -> None:
        local_tx, local_ty = self._parse_translate(element.attrib.get("transform", ""))
        tx += local_tx
        ty += local_ty

        tag = self._local_name(element.tag)
        if tag == "rect":
            rect_box = self._rect_box_from_element(element, tx, ty, canvas_w, canvas_h)
            if rect_box is not None:
                rects.append(rect_box)
        elif tag == "text":
            text_boxes.extend(self._extract_text_boxes(element, tx, ty))

        for child in list(element):
            self._collect_geometry(child, rects, text_boxes, tx, ty, canvas_w, canvas_h)

    def _rect_box_from_element(self, element, tx: float, ty: float, canvas_w: float, canvas_h: float) -> RectBox | None:
        width = self._float(element.attrib.get("width"), 0.0)
        height = self._float(element.attrib.get("height"), 0.0)
        if width < self.MIN_CONTAINER_WIDTH or height < self.MIN_CONTAINER_HEIGHT:
            return None
        fill = element.attrib.get("fill", "").strip().lower()
        fill_opacity = self._float(element.attrib.get("fill-opacity"), 1.0)
        if fill in {"none", "transparent"} or fill_opacity <= 0.02:
            return None
        if width >= canvas_w * self.MAX_BACKGROUND_WIDTH_RATIO and height >= canvas_h * self.MAX_BACKGROUND_HEIGHT_RATIO:
            return None
        x = self._float(element.attrib.get("x"), 0.0) + tx
        y = self._float(element.attrib.get("y"), 0.0) + ty
        label = element.attrib.get("id") or "<container>"
        return RectBox(x=x, y=y, w=width, h=height, label=label, area=width * height)

    def _extract_text_boxes(self, element, tx: float, ty: float) -> list[dict]:
        tspans = [child for child in list(element) if self._local_name(child.tag) == "tspan"]
        if tspans:
            return self._extract_tspan_boxes(element, tspans, tx, ty)

        text = "".join(element.itertext()).strip()
        if not text:
            return []
        return [self._build_text_box(
            text=text,
            x=self._float(element.attrib.get("x"), 0.0) + tx,
            y=self._float(element.attrib.get("y"), 0.0) + ty,
            font_size=self._float(element.attrib.get("font-size"), 16.0),
            text_anchor=element.attrib.get("text-anchor", "start").strip(),
        )]

    def _extract_tspan_boxes(self, element, tspans, tx: float, ty: float) -> list[dict]:
        base_x = self._float(element.attrib.get("x"), 0.0) + tx
        current_y = self._float(element.attrib.get("y"), 0.0) + ty
        default_font_size = self._float(element.attrib.get("font-size"), 16.0)
        text_anchor = element.attrib.get("text-anchor", "start").strip()
        boxes: list[dict] = []

        for tspan in tspans:
            x = self._float(tspan.attrib.get("x"), base_x - tx) + tx if "x" in tspan.attrib else base_x
            if "y" in tspan.attrib:
                current_y = self._float(tspan.attrib.get("y"), 0.0) + ty

            font_size = self._float(tspan.attrib.get("font-size"), default_font_size)
            dy = tspan.attrib.get("dy")
            if dy not in (None, ""):
                current_y += self._relative_text_length(dy, font_size)

            text = "".join(tspan.itertext()).strip()
            if not text:
                continue
            boxes.append(self._build_text_box(
                text=text,
                x=x,
                y=current_y,
                font_size=font_size,
                text_anchor=text_anchor,
            ))

        return boxes

    def _build_text_box(self, text: str, x: float, y: float, font_size: float, text_anchor: str) -> dict:
        width = self._estimate_text_width(text, font_size)
        if text_anchor == "middle":
            x_min = x - width / 2.0
            x_max = x + width / 2.0
        elif text_anchor == "end":
            x_min = x - width
            x_max = x
        else:
            x_min = x
            x_max = x + width
        y_min = y - font_size
        y_max = y + font_size * 0.3
        return {
            "text": text,
            "x1": x_min,
            "y1": y_min,
            "x2": x_max,
            "y2": y_max,
            "x": x,
            "y": y,
            "font_size": font_size,
            "text_anchor": text_anchor,
        }

    def _assign_and_check(self, rects: list[RectBox], text_boxes: list[dict], result: dict) -> int:
        assigned: dict[int, list[dict]] = {}
        for text_box in text_boxes:
            rect_box = self._find_best_rect(rects, text_box)
            if rect_box is None:
                continue
            assigned.setdefault(id(rect_box), []).append(text_box)

        rect_map = {id(rect_box): rect_box for rect_box in rects}
        for rect_id, boxes in assigned.items():
            self._check_text_boxes_against_rect(rect_map[rect_id], boxes, result)
        return len(assigned)

    def _find_best_rect(self, rects: list[RectBox], text_box: dict) -> RectBox | None:
        center_x = (text_box["x1"] + text_box["x2"]) / 2.0
        center_y = (text_box["y1"] + text_box["y2"]) / 2.0
        containing = [
            rect_box
            for rect_box in rects
            if rect_box.x <= center_x <= rect_box.x + rect_box.w
            and rect_box.y <= center_y <= rect_box.y + rect_box.h
        ]
        if not containing:
            return None
        containing.sort(key=lambda rect_box: (rect_box.area, rect_box.y, rect_box.x))
        return containing[0]

    def _check_text_boxes_against_rect(self, rect_box: RectBox, text_boxes: list[dict], result: dict) -> None:
        left = rect_box.x
        top = rect_box.y
        right = rect_box.x + rect_box.w
        bottom = rect_box.y + rect_box.h

        for text_box in text_boxes:
            overflow = (
                text_box["x1"] < left - self.HARD_OVERFLOW_TOLERANCE
                or text_box["y1"] < top - self.HARD_OVERFLOW_TOLERANCE
                or text_box["x2"] > right + self.HARD_OVERFLOW_TOLERANCE
                or text_box["y2"] > bottom + self.HARD_OVERFLOW_TOLERANCE
            )
            if overflow:
                self._add_issue(
                    result,
                    severity="error",
                    issue_type="container_overflow",
                    container=rect_box.label,
                    text=text_box["text"],
                    message=f"{rect_box.label}: text exceeds container bounds ({text_box['text']})",
                )
                continue

            crowding = (
                text_box["x1"] < left + self.SAFE_MARGIN_X - self.CROWDING_TOLERANCE
                or text_box["y1"] < top + self.SAFE_MARGIN_Y - self.CROWDING_TOLERANCE
                or text_box["x2"] > right - self.SAFE_MARGIN_X + self.CROWDING_TOLERANCE
                or text_box["y2"] > bottom - self.SAFE_MARGIN_Y + self.CROWDING_TOLERANCE
            )
            if crowding:
                self._add_issue(
                    result,
                    severity="warning",
                    issue_type="edge_crowding",
                    container=rect_box.label,
                    text=text_box["text"],
                    message=f"{rect_box.label}: text is too close to container edge ({text_box['text']})",
                )
                continue

            if self._has_ppt_export_risk(rect_box, text_box):
                self._add_issue(
                    result,
                    severity="warning",
                    issue_type="ppt_export_risk",
                    container=rect_box.label,
                    text=text_box["text"],
                    message=f"{rect_box.label}: PPT export may widen this text beyond the container ({text_box['text']})",
                )

    def _add_issue(
        self,
        result: dict,
        severity: str,
        issue_type: str,
        container: str,
        text: str,
        message: str,
    ) -> None:
        if severity == "error":
            result["errors"].append(message)
        else:
            result["warnings"].append(message)
        result["compact_issues"].append({
            "severity": severity,
            "type": issue_type,
            "container": container,
            "text_excerpt": self._text_excerpt(text),
        })

    def _has_ppt_export_risk(self, rect_box: RectBox, text_box: dict) -> bool:
        font_size = float(text_box.get("font_size", 16.0))
        text_anchor = str(text_box.get("text_anchor", "start"))
        x = float(text_box.get("x", text_box["x1"]))

        ppt_text_width = self._estimate_text_width(text_box["text"], font_size) * 1.15
        padding = font_size * 0.1

        if text_anchor == "middle":
            x_min = x - ppt_text_width / 2.0 - padding
            x_max = x + ppt_text_width / 2.0 + padding
        elif text_anchor == "end":
            x_min = x - ppt_text_width - padding
            x_max = x + padding
        else:
            x_min = x - padding
            x_max = x + ppt_text_width + padding

        left = rect_box.x + self.SAFE_MARGIN_X
        right = rect_box.x + rect_box.w - self.SAFE_MARGIN_X
        return x_min < left or x_max > right

    def _estimate_text_width(self, text: str, font_size: float) -> float:
        width = 0.0
        for ch in text:
            if self._is_cjk_char(ch):
                width += font_size
            elif ch == " ":
                width += font_size * 0.3
            elif ch in "mMwWOQ":
                width += font_size * 0.75
            elif ch in "iIlj1!|":
                width += font_size * 0.3
            else:
                width += font_size * 0.55
        return max(width, font_size)

    def _is_cjk_char(self, ch: str) -> bool:
        cp = ord(ch)
        return (
            0x4E00 <= cp <= 0x9FFF
            or 0x3400 <= cp <= 0x4DBF
            or 0x2E80 <= cp <= 0x2EFF
            or 0x3000 <= cp <= 0x303F
            or 0xFF00 <= cp <= 0xFFEF
            or 0xF900 <= cp <= 0xFAFF
            or 0x20000 <= cp <= 0x2A6DF
        )

    def _text_excerpt(self, text: str, limit: int = 36) -> str:
        normalized = re.sub(r"\s+", " ", text).strip()
        if len(normalized) <= limit:
            return normalized
        return normalized[: limit - 1] + "…"

    def _print_result(self, result: dict) -> None:
        if result["errors"]:
            status = "[ERROR]"
        elif result["warnings"]:
            status = "[WARN]"
        else:
            status = "[OK]"
        print(f"{status} {result['file']}")
        for error in result["errors"][:6]:
            print(f"  [ERROR] {error}")
        for warning in result["warnings"][:6]:
            print(f"  [WARN] {warning}")
        if len(result["errors"]) > 6:
            print(f"  [ERROR] ... and {len(result['errors']) - 6} more")
        if len(result["warnings"]) > 6:
            print(f"  [WARN] ... and {len(result['warnings']) - 6} more")
        print()

    def _parse_translate(self, transform: str) -> tuple[float, float]:
        match = re.search(r"translate\(\s*([-\d.]+)(?:[\s,]+([-\d.]+))?\s*\)", transform)
        if not match:
            return 0.0, 0.0
        return self._float(match.group(1), 0.0), self._float(match.group(2), 0.0)

    def _float(self, value, default: float) -> float:
        if value in (None, ""):
            return default
        text = re.sub(r"[a-zA-Z%]+$", "", str(value).strip())
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
    parser = argparse.ArgumentParser(description="PPT Master - text/container overflow checker")
    parser.add_argument("target", help="SVG file or project directory")
    parser.add_argument("--summary-only", action="store_true", help="Only print summary")
    parser.add_argument("--json", action="store_true", help="Print JSON")
    args = parser.parse_args()

    checker = SVGTextContainerChecker()
    checker.check_directory(args.target, print_results=not args.summary_only and not args.json)

    if args.json:
        print(json.dumps(checker.summary_dict(), ensure_ascii=True, indent=2))
    else:
        summary = checker.summary
        print(
            "Text/container summary: "
            f"total={summary['total']} "
            f"passed={summary['passed']} "
            f"warnings={summary['warnings']} "
            f"errors={summary['errors']}"
        )

    sys.exit(1 if checker.summary["errors"] > 0 else 0)


if __name__ == "__main__":
    main()
