from __future__ import annotations

from pathlib import Path

from PySide6 import QtGui, QtWidgets


def load_brand_fonts(font_assets_dir: str) -> None:
    font_dir = Path(font_assets_dir)
    if not font_dir.exists():
        return
    for filename in (
        "Inter-Regular.ttf",
        "Inter-Medium.ttf",
        "Inter-SemiBold.ttf",
        "Outfit-Regular.ttf",
        "Outfit-Bold.ttf",
    ):
        path = font_dir / filename
        if path.exists():
            QtGui.QFontDatabase.addApplicationFont(str(path))


def build_stylesheet() -> str:
    return """
    QWidget {
        color: #f6f7fb;
        font-family: "Inter", "Outfit", "Microsoft YaHei UI", sans-serif;
        font-size: 14px;
    }
    QMainWindow {
        background: #07080a;
    }
    #windowRoot {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
            stop:0 #07080a,
            stop:0.58 #0b1016,
            stop:1 #10161b);
    }
    #startupSurface {
        background: rgba(16, 17, 17, 0.96);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 26px;
    }
    #card {
        background: rgba(16, 17, 17, 0.94);
        border: 1px solid rgba(255, 255, 255, 0.07);
        border-radius: 20px;
    }
    #pageTitle {
        font-size: 30px;
        font-weight: 700;
        color: #ffffff;
    }
    #sectionTitle {
        font-size: 18px;
        font-weight: 700;
        color: #ffffff;
    }
    #mutedText {
        color: rgba(206, 206, 206, 0.86);
        line-height: 1.45em;
    }
    #primaryButton, #secondaryButton, #ghostButton {
        min-height: 42px;
        padding: 0 18px;
        font-size: 14px;
        font-weight: 600;
        border-radius: 999px;
    }
    #primaryButton {
        color: #18191a;
        background: rgba(255, 255, 255, 0.88);
        border: 1px solid rgba(255, 255, 255, 0.18);
    }
    #primaryButton:hover {
        background: #ffffff;
    }
    #secondaryButton {
        color: #f9f9f9;
        background: rgba(255, 255, 255, 0.04);
        border: 1px solid rgba(255, 255, 255, 0.10);
    }
    #secondaryButton:hover {
        background: rgba(255, 255, 255, 0.08);
        border-color: rgba(255, 255, 255, 0.16);
    }
    #ghostButton {
        color: rgba(206, 206, 206, 0.84);
        background: transparent;
        border: 1px solid transparent;
    }
    #ghostButton:hover {
        color: #ffffff;
        background: rgba(255, 255, 255, 0.05);
    }
    QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDateEdit {
        background: rgba(255, 255, 255, 0.03);
        color: #f9f9f9;
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 14px;
        padding: 10px 12px;
        selection-background-color: rgba(85, 179, 255, 0.35);
    }
    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus, QDateEdit:focus {
        border: 1px solid rgba(85, 179, 255, 0.55);
    }
    QPlainTextEdit {
        border-radius: 18px;
    }
    QScrollArea, QScrollArea > QWidget > QWidget {
        background: transparent;
        border: 0;
    }
    QScrollBar:vertical {
        width: 8px;
        background: transparent;
        margin: 6px 2px;
    }
    QScrollBar::handle:vertical {
        background: rgba(255, 255, 255, 0.14);
        border-radius: 4px;
        min-height: 40px;
    }
    QScrollBar::handle:vertical:hover {
        background: rgba(255, 255, 255, 0.22);
    }
    QScrollBar:horizontal {
        height: 8px;
        background: transparent;
        margin: 2px 6px;
    }
    QScrollBar::handle:horizontal {
        background: rgba(255, 255, 255, 0.14);
        border-radius: 4px;
        min-width: 40px;
    }
    QScrollBar::add-line, QScrollBar::sub-line {
        width: 0;
        height: 0;
        border: 0;
        background: transparent;
    }
    """


def apply_theme(app: QtWidgets.QApplication, font_assets_dir: str, theme_key: str = "default") -> None:
    del theme_key
    load_brand_fonts(font_assets_dir)
    app.setStyleSheet(build_stylesheet())
