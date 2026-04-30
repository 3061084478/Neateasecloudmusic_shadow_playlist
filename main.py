from __future__ import annotations

import sys

from PySide6 import QtWidgets

from core.app_controller import AppController
from core.runtime_paths import resolve_runtime_paths
from ui.main_window import MainWindow
from ui.theme import apply_theme


def main() -> int:
    bundle_root, workspace_root, config_path = resolve_runtime_paths()
    app = QtWidgets.QApplication(sys.argv)
    controller = AppController(
        workspace_root=str(workspace_root),
        config_path=str(config_path),
        bundle_root=str(bundle_root),
    )
    apply_theme(app, controller.config_store.font_assets_dir, "default")
    window = MainWindow(controller)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
