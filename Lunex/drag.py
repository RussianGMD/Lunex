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
        self._update_style(is_hovered=False)

    def set_theme(self, is_white: bool):
        self.is_white = is_white
        self._update_style(is_hovered=False)

    def _update_style(self, is_hovered: bool):
        if is_hovered:
            border_color = "#3b82f6"
        else:
            border_color = "#e4e4e7" if self.is_white else "#23232a"

        bg_color = "#ffffff" if self.is_white else "#16161a"

        self.setStyleSheet(f"""
            QWidget#midiCard {{
                background-color: {bg_color};
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