#!/usr/bin/env python3
"""PPT Master - SVG to PPTX Tool (thin wrapper).

Delegates to the svg_to_pptx package. Kept for CLI backward compatibility:
    conda run -n ppt-master python scripts/svg_to_pptx.py <project_path> -s final
"""

import sys
from pathlib import Path

# Ensure the scripts directory is on sys.path so the package can be found
sys.path.insert(0, str(Path(__file__).resolve().parent))

from runtime_utils import configure_utf8_stdio
from svg_to_pptx import main

configure_utf8_stdio()

if __name__ == '__main__':
    main()
