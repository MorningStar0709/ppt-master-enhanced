# Runtime Data

This directory stores skill-local runtime artifacts for `ppt-master`.

## Layout

- `command_reports/`
  - Machine-readable "last command" receipts written by helper CLIs such as `project_manager.py` and `asset_lookup.py`
  - Safe to regenerate
  - Not part of project deliverables

## Boundary

- Static skill assets live under `skills/ppt-master-enhanced/`
- Runtime receipts live under `skills/ppt-master-enhanced/.runtime/`
- Project-specific review and export state lives under `projects/<project>/`


