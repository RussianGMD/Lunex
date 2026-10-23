import os
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QWidget


class MidiDropCard(QWidget):
    file_dropped = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("midiCard")
        self.setAcceptDrops(True)
        self.is_white = False
        self._bg_color = "#16161a"
        self._border_color = "#23232a"
        self._hover_border_color = "#3b82f6"
        self._update_style(is_hovered=False)

    def set_theme(self, theme_or_is_white: dict | bool):
        if isinstance(theme_or_is_white, dict):
            self.is_white = bool(theme_or_is_white.get("is_white", False))
            self._bg_color = theme_or_is_white.get("card_bg", "#16161a")
            self._border_color = theme_or_is_white.get("card_border", "#23232a")
            self._hover_border_color = theme_or_is_white.get("card_hover_border", "#3b82f6")
        else:
            self.is_white = bool(theme_or_is_white)
            self._bg_color = "#ffffff" if self.is_white else "#16161a"
            self._border_color = "#e4e4e7" if self.is_white else "#23232a"
            self._hover_border_color = "#3b82f6"
        self._update_style(is_hovered=False)

    def _update_style(self, is_hovered: bool):
        border_color = self._hover_border_color if is_hovered else self._border_color
        self.setStyleSheet(f"""
            QWidget#midiCard {{
                background-color: {self._bg_color};
                border: 1px solid {border_color};
                border-radius: 7px;
            }}
        """)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                path = url.toLocalFile()
                if path.lower().endswith((".mid", ".midi")):
                    event.acceptProposedAction()
                    self._update_style(is_hovered=True)
                    return
        event.ignore()

    def dragLeaveEvent(self, event):
        self._update_style(is_hovered=False)
        event.accept()

    def dropEvent(self, event):
        self._update_style(is_hovered=False)
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                path = url.toLocalFile()
                if path.lower().endswith((".mid", ".midi")):
                    event.acceptProposedAction()
                    self.file_dropped.emit(path)
                    return
        event.ignore()