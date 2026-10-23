from PyQt6.QtCore import (
    Qt, QPoint, QRectF, QPropertyAnimation, QEasingCurve,
    pyqtProperty, QUrl, pyqtSignal
)
from PyQt6.QtGui import (
    QPainter, QColor, QFont, QKeySequence, QDesktopServices
)
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel,
    QPushButton, QAbstractButton, QDialog, QComboBox
)

from themes import BLACK_THEME, WHITE_THEME
from core_utils import SoundManager


class AutoRefreshComboBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.refresh_callback = None

    def showPopup(self):
        if self.refresh_callback:
            self.refresh_callback()
        super().showPopup()


class AnimatedToggle(QAbstractButton):
    def __init__(self, parent=None, width=38, height=20):
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedSize(width, height)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._bg_off = QColor("#222226")
        self._bg_on = QColor("#3b82f6")
        self._circle_color = QColor("#ffffff")

        self._padding = 2
        self._circle_radius = (height - self._padding * 2) / 2
        self._circle_x = float(self._padding)

        self._anim = QPropertyAnimation(self, b"circle_position", self)
        self._anim.setDuration(150)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutCubic)

        self.toggled.connect(self._handle_state_change)

    def hitButton(self, pos: QPoint) -> bool:
        return self.rect().contains(pos)

    @pyqtProperty(float)
    def circle_position(self):
        return self._circle_x

    @circle_position.setter
    def circle_position(self, pos):
        self._circle_x = pos
        self.update()

    def set_theme(self, theme: dict | bool):
        if isinstance(theme, dict):
            self._bg_off = QColor(theme.get("toggle_off_bg", "#222226"))
            self._bg_on = QColor(theme.get("toggle_on_bg", "#3b82f6"))
            self._circle_color = QColor(theme.get("toggle_circle", "#ffffff"))
        else:
            self._bg_off = QColor("#d1d5db") if theme else QColor("#222226")
            self._bg_on = QColor("#3b82f6")
            self._circle_color = QColor("#ffffff")
        self.update()

    def setCheckedSilently(self, checked: bool):
        self.blockSignals(True)
        self.setChecked(checked)
        end = self.width() - self._circle_radius * 2 - self._padding if checked else self._padding
        self._circle_x = float(end)
        self.update()
        self.blockSignals(False)

    def _handle_state_change(self, checked):
        SoundManager.play()
        start = self._circle_x
        end = self.width() - self._circle_radius * 2 - self._padding if checked else self._padding
        self._anim.stop()
        self._anim.setStartValue(start)
        self._anim.setEndValue(float(end))
        self._anim.start()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        bg_color = self._bg_on if self.isChecked() else self._bg_off
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(bg_color)
        p.drawRoundedRect(self.rect(), self.height() / 2, self.height() / 2)

        p.setBrush(self._circle_color)
        p.drawEllipse(
            QRectF(
                self._circle_x,
                self._padding,
                self._circle_radius * 2,
                self._circle_radius * 2
            )
        )


class SwitchRow(QWidget):
    def __init__(self, title: str, parent=None, theme_section: str = "midi_player"):
        super().__init__(parent)
        self.theme_section = theme_section
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 7, 12, 7)

        self.label = QLabel(title)
        self.toggle = AnimatedToggle()

        layout.addWidget(self.label)
        layout.addStretch()
        layout.addWidget(self.toggle)
        self.set_theme(BLACK_THEME.get(self.theme_section, BLACK_THEME["midi_player"]))

    def set_theme(self, theme: dict | bool):
        if isinstance(theme, bool):
            base = WHITE_THEME if theme else BLACK_THEME
            theme = base.get(self.theme_section, base["midi_player"])
        self.toggle.set_theme(theme)
        text_col = theme.get("switch_row_text", "#e1e1e6")
        bg_col = theme.get("switch_row_bg", "#16161a")
        border_col = theme.get("switch_row_border", "#23232a")
        hover_border_col = theme.get("switch_row_hover_border", "#32323d")

        self.label.setStyleSheet(f"color: {text_col}; font-size: 13px; font-weight: 500;")
        self.setStyleSheet(f"""
            SwitchRow {{
                background-color: {bg_col};
                border: 1px solid {border_col};
                border-radius: 6px;
            }}
            SwitchRow:hover {{
                border: 1px solid {hover_border_col};
            }}
        """)


class KeybindButton(QPushButton):
    key_changed = pyqtSignal()

    def __init__(self, default_key: str, parent=None, theme_section: str = "midi_player"):
        super().__init__(parent)
        self.key_value = default_key
        self.is_listening = False
        self.theme_section = theme_section
        self.theme_data = BLACK_THEME.get(self.theme_section, BLACK_THEME["midi_player"])
        self.setFixedHeight(30)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_appearance()

    def set_theme(self, theme: dict | bool):
        if isinstance(theme, bool):
            base = WHITE_THEME if theme else BLACK_THEME
            self.theme_data = base.get(self.theme_section, base["midi_player"])
        else:
            self.theme_data = theme
        self._update_appearance()

    def set_key_silently(self, key_text: str):
        self.key_value = key_text.upper()
        self._update_appearance()

    def _update_appearance(self):
        t = self.theme_data
        if self.is_listening:
            listen_bg = t.get("keybind_listening_bg", "#182234")
            listen_text = t.get("keybind_listening_text", "#60a5fa")
            listen_border = t.get("keybind_listening_border", "#3b82f6")
            self.setText("...")
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: {listen_bg};
                    color: {listen_text};
                    border: 1px solid {listen_border};
                    border-radius: 5px;
                    font-size: 12px;
                    font-weight: 600;
                }}
            """)
        else:
            btn_bg = t.get("keybind_btn_bg", "#202026")
            btn_text = t.get("keybind_btn_text", "#e1e1e6")
            btn_border = t.get("keybind_btn_border", "#2c2c36")
            hover_bg = t.get("keybind_btn_hover_bg", "#2b2b34")
            hover_border = t.get("keybind_btn_hover_border", "#3d3d4a")
            self.setText(self.key_value)
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: {btn_bg};
                    color: {btn_text};
                    border: 1px solid {btn_border};
                    border-radius: 5px;
                    font-size: 12px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background-color: {hover_bg};
                    border: 1px solid {hover_border};
                }}
            """)

    def mousePressEvent(self, event):
        SoundManager.play()
        self.is_listening = True
        self._update_appearance()
        self.setFocus()
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if self.is_listening:
            key = event.key()
            if key in (Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt, Qt.Key.Key_Meta):
                event.accept()
                return

            key_text = QKeySequence(key).toString()
            if not key_text and event.text():
                key_text = event.text()

            if key_text:
                self.key_value = key_text.upper()
                self.key_changed.emit()

            self.is_listening = False
            self._update_appearance()
            self.clearFocus()
            SoundManager.play()
            event.accept()
        else:
            super().keyPressEvent(event)

    def focusOutEvent(self, event):
        if self.is_listening:
            self.is_listening = False
            self._update_appearance()
        super().focusOutEvent(event)


class KeybindSlot(QWidget):
    def __init__(self, title: str, default_key: str, parent=None, theme_section: str = "midi_player"):
        super().__init__(parent)
        self.theme_section = theme_section
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.label = QLabel(title)
        self.button = KeybindButton(default_key, theme_section=theme_section)

        layout.addWidget(self.label)
        layout.addWidget(self.button)
        self.set_theme(BLACK_THEME.get(self.theme_section, BLACK_THEME["midi_player"]))

    def set_theme(self, theme: dict | bool):
        if isinstance(theme, bool):
            base = WHITE_THEME if theme else BLACK_THEME
            theme = base.get(self.theme_section, base["midi_player"])
        lbl_col = theme.get("keybind_label_text", "#8f8f9d")
        self.label.setStyleSheet(f"color: {lbl_col}; font-size: 11px; font-weight: 500;")
        self.button.set_theme(theme)


class UpdateDialog(QDialog):
    def __init__(self, parent=None, theme_data: dict | None = None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(380, 180)
        self.theme_data = theme_data or BLACK_THEME["update_dialog"]
        self.old_pos = None
        self._setup_ui()

    def _setup_ui(self):
        container = QWidget(self)
        container.setObjectName("updateDialogContainer")
        container.setFixedSize(380, 180)

        root_layout = QVBoxLayout(container)
        root_layout.setContentsMargins(16, 12, 16, 16)
        root_layout.setSpacing(10)

        header_bar = QHBoxLayout()
        header_bar.setContentsMargins(0, 0, 0, 0)

        title_lbl = QLabel("Update Available")
        title_lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))

        btn_close = QPushButton()
        btn_close.setFixedSize(11, 11)
        btn_close.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #ff5f56;
                border: 1px solid #e0443e;
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #ff7b73; }
        """)
        btn_close.clicked.connect(self.close)

        header_bar.addWidget(title_lbl)
        header_bar.addStretch()
        header_bar.addWidget(btn_close)
        root_layout.addLayout(header_bar)

        content_layout = QVBoxLayout()
        content_layout.setSpacing(6)

        msg_lbl = QLabel("Please, update the Lunex to new version.")
        msg_lbl.setFont(QFont("Segoe UI", 11, QFont.Weight.DemiBold))
        msg_lbl.setWordWrap(True)

        link_lbl = QLabel(
            'Download here: <a href="https://lunexsoftworksllc.netlify.app" '
            'style="color: #3b82f6; text-decoration: none; font-weight: 600;">lunexsoftworksllc.netlify.app</a>'
        )
        link_lbl.setFont(QFont("Segoe UI", 10))
        link_lbl.setOpenExternalLinks(True)

        content_layout.addWidget(msg_lbl)
        content_layout.addWidget(link_lbl)
        root_layout.addLayout(content_layout)
        root_layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        btn_download = QPushButton("Open Link")
        btn_download.setFixedHeight(28)
        btn_download.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_download.clicked.connect(self._open_site)

        btn_ok = QPushButton("OK")
        btn_ok.setFixedHeight(28)
        btn_ok.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_ok.clicked.connect(self.close)

        btn_layout.addStretch()
        btn_layout.addWidget(btn_download)
        btn_layout.addWidget(btn_ok)
        root_layout.addLayout(btn_layout)

        t = self.theme_data
        bg = t.get("bg", "#16161a")
        border = t.get("border", "#2c2c36")
        title_col = t.get("title_text", "#8f8f9d")
        msg_col = t.get("msg_text", "#ffffff")
        link_col = t.get("link_text", "#a1a1aa")
        btn_bg = t.get("btn_bg", "#202026")
        btn_text = t.get("btn_text", "#ffffff")
        btn_border = t.get("btn_border", "#2c2c36")
        btn_hover_bg = t.get("btn_hover_bg", "#2b2b34")
        btn_hover_border = t.get("btn_hover_border", "#3b82f6")

        container.setStyleSheet(f"""
            QWidget#updateDialogContainer {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 10px;
            }}
        """)
        title_lbl.setStyleSheet(f"color: {title_col};")
        msg_lbl.setStyleSheet(f"color: {msg_col};")
        link_lbl.setStyleSheet(f"color: {link_col};")

        btn_style = f"""
            QPushButton {{
                background-color: {btn_bg};
                color: {btn_text};
                border: 1px solid {btn_border};
                border-radius: 5px;
                font-size: 11px;
                font-weight: 600;
                padding: 0 14px;
            }}
            QPushButton:hover {{
                background-color: {btn_hover_bg};
                border: 1px solid {btn_hover_border};
            }}
        """
        btn_download.setStyleSheet(btn_style)
        btn_ok.setStyleSheet(btn_style)

    def _open_site(self):
        SoundManager.play()
        QDesktopServices.openUrl(QUrl("https://lunexsoftworksllc.netlify.app"))
        self.close()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and event.position().y() <= 36:
            self.old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self.old_pos is not None:
            delta = QPoint(event.globalPosition().toPoint() - self.old_pos)
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self.old_pos = None