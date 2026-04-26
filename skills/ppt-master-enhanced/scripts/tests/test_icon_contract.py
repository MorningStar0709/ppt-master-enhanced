#!/usr/bin/env python3
"""Minimal regression tests for PPT Master icon contract enforcement."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from icon_reference_checker import IconReferenceChecker
from svg_quality_checker import SVGQualityChecker


def _write_svg(tmp_dir: Path, file_name: str, body: str) -> Path:
    path = tmp_dir / file_name
    path.write_text(body, encoding="utf-8")
    return path


class IconContractRegressionTests(unittest.TestCase):
    def test_external_icon_href_fails_quality_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            svg_path = _write_svg(
                Path(tmp),
                "bad_icon_href.svg",
                """<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
  <rect width="1280" height="720" fill="#FFFFFF"/>
  <use href="tabler-filled/ad.svg#icon" x="100" y="100" width="48" height="48" fill="#000000"/>
</svg>
""",
            )

            result = SVGQualityChecker(warn_on_icon_placeholders=False).check_file(str(svg_path))

            self.assertFalse(result["passed"])
            self.assertTrue(
                any("unsupported <use> href target" in error for error in result["errors"]),
                result["errors"],
            )

    def test_local_id_use_still_passes_quality_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            svg_path = _write_svg(
                Path(tmp),
                "local_use_ok.svg",
                """<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
  <defs>
    <g id="badge">
      <circle cx="12" cy="12" r="12" fill="#1A73E8"/>
    </g>
  </defs>
  <rect width="1280" height="720" fill="#FFFFFF"/>
  <use href="#badge" x="100" y="100"/>
</svg>
""",
            )

            result = SVGQualityChecker(warn_on_icon_placeholders=False).check_file(str(svg_path))

            self.assertTrue(result["passed"], result["errors"])

    def test_mixed_icon_libraries_fail_icon_reference_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            svg_path = _write_svg(
                Path(tmp),
                "mixed_libraries.svg",
                """<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
  <rect width="1280" height="720" fill="#FFFFFF"/>
  <use data-icon="chunk/a" x="100" y="100" width="48" height="48" fill="#000000"/>
  <use data-icon="tabler-filled/ad" x="200" y="100" width="48" height="48" fill="#000000"/>
</svg>
""",
            )

            result = IconReferenceChecker().check_file(str(svg_path))

            self.assertFalse(result["passed"])
            self.assertTrue(
                any("Mixed icon libraries detected" in error for error in result["errors"]),
                result["errors"],
            )

    def test_symbol_use_guidance_points_to_supported_patterns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            svg_path = _write_svg(
                Path(tmp),
                "symbol_use.svg",
                """<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
  <defs>
    <symbol id="iconSymbol">
      <circle cx="12" cy="12" r="12" fill="#1A73E8"/>
    </symbol>
  </defs>
  <use href="#iconSymbol" x="100" y="100"/>
</svg>
""",
            )

            result = SVGQualityChecker(warn_on_icon_placeholders=False).check_file(str(svg_path))

            self.assertFalse(result["passed"])
            self.assertTrue(
                any("<use data-icon=\"library/name\"/>" in error for error in result["errors"]),
                result["errors"],
            )
            self.assertTrue(
                any("<use href=\"#id\">" in error for error in result["errors"]),
                result["errors"],
            )


if __name__ == "__main__":
    unittest.main()
