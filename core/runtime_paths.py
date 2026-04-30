from __future__ import annotations

import sys
from pathlib import Path
from typing import Tuple


def resolve_runtime_paths() -> Tuple[Path, Path, Path]:
    if getattr(sys, "frozen", False):
        bundle_root = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent)).resolve()
        workspace_root = Path(sys.executable).resolve().parent
    else:
        bundle_root = Path(__file__).resolve().parents[1]
        workspace_root = bundle_root

    workspace_root.mkdir(parents=True, exist_ok=True)
    config_path = workspace_root / "config.json"
    return bundle_root, workspace_root, config_path
