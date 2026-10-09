import os
import requests
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QSize, QByteArray, QUrl, QTimer
from PyQt6.QtGui import QPixmap, QPainter, QColor, QFont, QIcon
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QLineEdit, QComboBox, QScrollArea, QFrame, QSizePolicy
)
from PyQt6.QtMultimedia import QSoundEffect

DOWNLOADS_DIR = os.path.abspath("midis")
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

def is_safe_midi_path(midi_filename: str) -> tuple[bool, str]:
    """
    Checking Security:
    1. Only .mid.
    2. File only saves on folder midis (DOWNLOADS_DIR).
    """
    if not midi_filename or not isinstance(midi_filename, str):
        return False, "Fail!"
    
    clean_fn = midi_filename.strip()
    
    
    if not clean_fn.lower().endswith(".mid") or clean_fn.lower() == ".mid":
        return False, "Fail!"
    
    
    downloads_dir_norm = os.path.normcase(os.path.abspath(DOWNLOADS_DIR))
    target_path_norm = os.path.normcase(os.path.abspath(os.path.join(DOWNLOADS_DIR, clean_fn)))
    target_dir_norm = os.path.dirname(target_path_norm)
    
    
    if target_dir_norm != downloads_dir_norm:
        return False, "Fail!"
        
    return True, ""

class HubSound:
    effect = None

    @classmethod
    def init(cls):
        path = os.path.abspath("sounds/click.wav")
        if os.path.exists(path):
            cls.effect = QSoundEffect()
            cls.effect.setSource(QUrl.fromLocalFile(path))
            cls.effect.setVolume(0.6)

    @classmethod
    def play(cls):
        if cls.effect:
            cls.effect.play()

class DataLoaderThread(QThread):
    loaded = pyqtSignal(list)
    failed = pyqtSignal(str)

    def run(self):
        url = "https://api.nanomidi.net/api/midiData"
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list):
                data.reverse()
                self.loaded.emit(data)
            else:
                self.failed.emit("Invalid API response format")
        except Exception as e:
            self.failed.emit(str(e))

class ImageLoaderThread(QThread):
    image_ready = pyqtSignal(str, QByteArray)

    def __init__(self, filename: str, parent=None):
        super().__init__(parent)
        self.filename = filename

    def run(self):
        url = f"https://api.nanomidi.net/api/v2/images/{self.filename}?size=100x100"
        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                self.image_ready.emit(self.filename, QByteArray(resp.content))
        except Exception:
            pass

class FileDownloadThread(QThread):
    download_finished = pyqtSignal(str)
    download_failed = pyqtSignal(str)

    def __init__(self, midi_filename: str, parent=None):
        super().__init__(parent)
        self.midi_filename = midi_filename

    def run(self):
        
        is_safe, err_msg = is_safe_midi_path(self.midi_filename)
        if not is_safe:
            self.download_failed.emit(err_msg)
            return

        url = f"https://api.nanomidi.net/api/midis/{self.midi_filename}"
        local_path = os.path.abspath(os.path.join(DOWNLOADS_DIR, self.midi_filename))
        try:
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            with open(local_path, "wb") as f:
                f.write(resp.content)
            self.download_finished.emit(local_path)
        except Exception:
            self.download_failed.emit("Fail!")

class MidiHubCard(QWidget):
    action_requested = pyqtSignal(dict, str)

    def __init__(self, midi_info: dict, parent=None):
        super().__init__(parent)
        self.midi_info = midi_info
        self.setObjectName("midiHubCard")
        self.setFixedHeight(86)
        self.is_white = False
        self.has_custom_cover = False
        self._setup_ui()
        self.update_button_state()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 14, 10)
        layout.setSpacing(14)

        self.cover_label = QLabel()
        self.cover_label.setFixedSize(66, 66)
        self.cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.set_placeholder_image()
        layout.addWidget(self.cover_label)

        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        info_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        name = self.midi_info.get("name", "Unknown Track")
        self.title_lbl = QLabel(name)

        artist = self.midi_info.get("artists") or "Unknown Artist"
        arranger = self.midi_info.get("arranger")
        uploader = self.midi_info.get("uploader") or "Unknown"

        meta_parts = [artist]
        if arranger:
            meta_parts.append(f"Arr: {arranger}")
        meta_parts.append(f"By: {uploader}")
        self.meta_lbl = QLabel("   ".join(meta_parts))

        dls = self.midi_info.get("downloads", 0)
        views = self.midi_info.get("views", 0)
        self.stats_lbl = QLabel(f"↓ {dls:,}     👁 {views:,}")

        info_layout.addWidget(self.title_lbl)
        info_layout.addWidget(self.meta_lbl)
        info_layout.addWidget(self.stats_lbl)
        layout.addLayout(info_layout, stretch=1)

        self.action_btn = QPushButton()
        self.action_btn.setFixedSize(120, 30)
        self.action_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.action_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.action_btn.clicked.connect(self._on_action_clicked)
        layout.addWidget(self.action_btn)

        self.set_theme(False)

    def set_theme(self, is_white: bool):
        self.is_white = is_white
        if not self.has_custom_cover:
            self.set_placeholder_image()

        if is_white:
            self.setStyleSheet("""
                QWidget#midiHubCard {
                    background-color: #ffffff;
                    border: 1px solid #e4e4e7;
                    border-radius: 7px;
                }
                QWidget#midiHubCard:hover {
                    border: 1px solid #cbd5e1;
                }
            """)
            self.title_lbl.setStyleSheet("color: #18181b; font-size: 13px; font-weight: 600;")
            self.meta_lbl.setStyleSheet("color: #71717a; font-size: 11px;")
            self.stats_lbl.setStyleSheet("color: #a1a1aa; font-size: 10px; font-weight: bold;")
        else:
            self.setStyleSheet("""
                QWidget#midiHubCard {
                    background-color: #16161a;
                    border: 1px solid #23232a;
                    border-radius: 7px;
                }
                QWidget#midiHubCard:hover {
                    border: 1px solid #2f2f3a;
                }
            """)
            self.title_lbl.setStyleSheet("color: #ffffff; font-size: 13px; font-weight: 600;")
            self.meta_lbl.setStyleSheet("color: #8f8f9d; font-size: 11px;")
            self.stats_lbl.setStyleSheet("color: #555562; font-size: 10px; font-weight: bold;")

        self.update_button_state()

    def set_placeholder_image(self):
        pix = QPixmap(66, 66)
        bg_col = QColor("#f4f4f7") if self.is_white else QColor("#181820")
        pen_col = QColor("#a1a1aa") if self.is_white else QColor("#454555")
        pix.fill(bg_col)
        p = QPainter(pix)
        p.setPen(pen_col)
        p.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        p.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, "♪")
        p.end()
        border_col = "#e4e4e7" if self.is_white else "#101014"
        self.cover_label.setStyleSheet(f"background-color: {bg_col.name()}; border: 1px solid {border_col}; border-radius: 5px;")
        self.cover_label.setPixmap(pix)

    def set_cover_pixmap(self, pix: QPixmap):
        self.has_custom_cover = True
        scaled = pix.scaled(
            66, 66, 
            Qt.AspectRatioMode.KeepAspectRatioByExpanding, 
            Qt.TransformationMode.SmoothTransformation
        )
        self.cover_label.setStyleSheet("border-radius: 5px; border: none;")
        self.cover_label.setPixmap(scaled)

    def update_button_state(self):
        midi_fn = self.midi_info.get("midiFilename", "")
        is_safe, _ = is_safe_midi_path(midi_fn)
        if not is_safe:
            self.action_btn.setText("Download")
            self._apply_standard_btn_style()
            return

        local_path = os.path.join(DOWNLOADS_DIR, midi_fn)
        if os.path.isfile(local_path):
            self.action_btn.setText("Load in Lunex")
            if self.is_white:
                self.action_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #dbeafe;
                        color: #1d4ed8;
                        border: 1px solid #93c5fd;
                        border-radius: 5px;
                        font-size: 11px;
                        font-weight: 600;
                    }
                    QPushButton:hover {
                        background-color: #bfdbfe;
                        border: 1px solid #3b82f6;
                    }
                """)
            else:
                self.action_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #1d3354;
                        color: #60a5fa;
                        border: 1px solid #2d4f82;
                        border-radius: 5px;
                        font-size: 11px;
                        font-weight: 600;
                    }
                    QPushButton:hover {
                        background-color: #264472;
                        border: 1px solid #3b82f6;
                        color: #ffffff;
                    }
                """)
        else:
            self.action_btn.setText("Download")
            self._apply_standard_btn_style()

    def _apply_standard_btn_style(self):
        if self.is_white:
            self.action_btn.setStyleSheet("""
                QPushButton {
                    background-color: #f4f4f7;
                    color: #18181b;
                    border: 1px solid #d4d4d8;
                    border-radius: 5px;
                    font-size: 11px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background-color: #e4e4e7;
                    border: 1px solid #a1a1aa;
                }
            """)
        else:
            self.action_btn.setStyleSheet("""
                QPushButton {
                    background-color: #202026;
                    color: #ffffff;
                    border: 1px solid #2c2c36;
                    border-radius: 5px;
                    font-size: 11px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background-color: #2b2b34;
                    border: 1px solid #3d3d4a;
                }
            """)

    def set_downloading_state(self):
        self.action_btn.setEnabled(False)
        self.action_btn.setText("Downloading...")
        if self.is_white:
            self.action_btn.setStyleSheet("""
                QPushButton {
                    background-color: #e4e4e7;
                    color: #71717a;
                    border: 1px solid #d4d4d8;
                    border-radius: 5px;
                    font-size: 11px;
                }
            """)
        else:
            self.action_btn.setStyleSheet("""
                QPushButton {
                    background-color: #16161a;
                    color: #8f8f9d;
                    border: 1px solid #23232a;
                    border-radius: 5px;
                    font-size: 11px;
                }
            """)

    def set_failed_state(self, text: str = "Fail!"):
        self.action_btn.setEnabled(False)
        self.action_btn.setText(text)
        if self.is_white:
            self.action_btn.setStyleSheet("""
                QPushButton {
                    background-color: #fee2e2;
                    color: #ef4444;
                    border: 1px solid #f87171;
                    border-radius: 5px;
                    font-size: 11px;
                    font-weight: 600;
                }
            """)
        else:
            self.action_btn.setStyleSheet("""
                QPushButton {
                    background-color: #2b1717;
                    color: #ef4444;
                    border: 1px solid #7f1d1d;
                    border-radius: 5px;
                    font-size: 11px;
                    font-weight: 600;
                }
            """)
        QTimer.singleShot(2500, self._restore_after_fail)

    def _restore_after_fail(self):
        self.action_btn.setEnabled(True)
        self.update_button_state()

    def _on_action_clicked(self):
        HubSound.play()
        midi_fn = self.midi_info.get("midiFilename", "")
        
        
        is_safe, err_msg = is_safe_midi_path(midi_fn)
        if not is_safe:
            self.set_failed_state("Fail!")
            return

        local_path = os.path.join(DOWNLOADS_DIR, midi_fn)
        if os.path.isfile(local_path):
            self.action_requested.emit(self.midi_info, "load")
        else:
            self.action_requested.emit(self.midi_info, "download")

class MidiHubView(QWidget):
    midi_loaded = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        HubSound.init()
        self.all_midis = []
        self.filtered_midis = []
        self.image_cache = {}
        self.active_threads = []
        self.is_white = False
        self.current_page = 1
        self.page_size = 10
        self.total_pages = 1
        self._setup_ui()
        self.fetch_data()

    def _setup_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(18, 16, 18, 10)
        root_layout.setSpacing(10)

        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 0)
        top_bar.setSpacing(10)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search tracks or artists...")
        self.search_input.setFixedHeight(30)
        self.search_input.textChanged.connect(self._on_search_changed)
        top_bar.addWidget(self.search_input, stretch=1)

        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["Newest", "Oldest", "Downloads", "Views"])
        self.sort_combo.setFixedHeight(30)
        self.sort_combo.setFixedWidth(120)
        self.sort_combo.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.sort_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sort_combo.currentIndexChanged.connect(self._on_sort_changed)
        top_bar.addWidget(self.sort_combo)

        root_layout.addLayout(top_bar)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)

        self.cards_container = QWidget()
        self.cards_container.setStyleSheet("background: transparent;")
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setContentsMargins(0, 0, 4, 0)
        self.cards_layout.setSpacing(8)
        self.cards_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.scroll.setWidget(self.cards_container)
        root_layout.addWidget(self.scroll, stretch=1)

        footer_layout = QHBoxLayout()
        footer_layout.setContentsMargins(0, 4, 0, 0)

        self.btn_prev = QPushButton("Previous")
        self.btn_next = QPushButton("Next")
        self.btn_prev.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_next.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_prev.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_next.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.btn_prev.clicked.connect(self._prev_page)
        self.btn_next.clicked.connect(self._next_page)

        self.page_label = QLabel("Page 1 / 1")

        footer_layout.addWidget(self.btn_prev)
        footer_layout.addStretch()
        footer_layout.addWidget(self.page_label)
        footer_layout.addStretch()
        footer_layout.addWidget(self.btn_next)

        root_layout.addLayout(footer_layout)

        self.powered_lbl = QLabel("Powered by nanoMIDI")
        self.powered_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root_layout.addWidget(self.powered_lbl)

        self.set_theme(False)

    def set_theme(self, is_white: bool):
        self.is_white = is_white
        if is_white:
            self.search_input.setStyleSheet("""
                QLineEdit {
                    background-color: #ffffff;
                    color: #18181b;
                    border: 1px solid #d4d4d8;
                    border-radius: 5px;
                    padding: 0 10px;
                    font-size: 12px;
                }
                QLineEdit:focus { border: 1px solid #3b82f6; }
            """)
            self.sort_combo.setStyleSheet("""
                QComboBox {
                    background-color: #ffffff;
                    color: #18181b;
                    border: 1px solid #d4d4d8;
                    border-radius: 5px;
                    padding-left: 10px;
                    font-size: 11px;
                    font-weight: 500;
                }
                QComboBox:hover { border: 1px solid #3b82f6; }
                QComboBox::drop-down { border: none; width: 0px; }
                QComboBox QAbstractItemView {
                    background-color: #ffffff;
                    color: #18181b;
                    selection-background-color: #e0e7ff;
                    selection-color: #1d4ed8;
                    border: 1px solid #d4d4d8;
                    border-radius: 5px;
                    padding: 4px;
                    outline: none;
                }
            """)
            self.scroll.setStyleSheet("""
                QScrollArea { border: none; background-color: transparent; }
                QScrollBar:vertical {
                    border: none;
                    background: #f4f4f7;
                    width: 6px;
                    border-radius: 3px;
                    margin: 0px;
                }
                QScrollBar::handle:vertical {
                    background: #d4d4d8;
                    min-height: 25px;
                    border-radius: 3px;
                }
                QScrollBar::handle:vertical:hover { background: #3b82f6; }
                QScrollBar::sub-line:vertical, QScrollBar::add-line:vertical { border: none; background: none; height: 0px; }
                QScrollBar::up-arrow:vertical, QScrollBar::down-arrow:vertical { background: none; }
                QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
            """)
            btn_page_style = """
                QPushButton {
                    background-color: #ffffff;
                    color: #18181b;
                    border: 1px solid #d4d4d8;
                    border-radius: 5px;
                    font-size: 12px;
                    font-weight: 600;
                    height: 28px;
                    padding: 0 16px;
                }
                QPushButton:hover { background-color: #f4f4f7; border: 1px solid #3b82f6; }
                QPushButton:disabled {
                    background-color: rgba(228, 228, 231, 0.4);
                    color: rgba(24, 24, 27, 0.25);
                    border: 1px solid rgba(212, 212, 216, 0.4);
                }
            """
            self.page_label.setStyleSheet("color: #71717a; font-size: 11px; font-weight: 600;")
            self.powered_lbl.setStyleSheet("""
                color: #a1a1aa;
                font-size: 10px;
                font-weight: 500;
                letter-spacing: 0.4px;
                margin-top: 2px;
            """)
        else:
            self.search_input.setStyleSheet("""
                QLineEdit {
                    background-color: #16161a;
                    color: #ffffff;
                    border: 1px solid #23232a;
                    border-radius: 5px;
                    padding: 0 10px;
                    font-size: 12px;
                }
                QLineEdit:focus { border: 1px solid #3b82f6; }
            """)
            self.sort_combo.setStyleSheet("""
                QComboBox {
                    background-color: #16161a;
                    color: #c9c9d4;
                    border: 1px solid #23232a;
                    border-radius: 5px;
                    padding-left: 10px;
                    font-size: 11px;
                    font-weight: 500;
                }
                QComboBox:hover { border: 1px solid #3b82f6; color: #ffffff; }
                QComboBox::drop-down { border: none; width: 0px; }
                QComboBox QAbstractItemView {
                    background-color: #16161a;
                    color: #e1e1e6;
                    selection-background-color: #26334d;
                    selection-color: #60a5fa;
                    border: 1px solid #2c2c38;
                    border-radius: 5px;
                    padding: 4px;
                    outline: none;
                }
            """)
            self.scroll.setStyleSheet("""
                QScrollArea { border: none; background-color: transparent; }
                QScrollBar:vertical {
                    border: none;
                    background: #101014;
                    width: 6px;
                    border-radius: 3px;
                    margin: 0px;
                }
                QScrollBar::handle:vertical {
                    background: #23232c;
                    min-height: 25px;
                    border-radius: 3px;
                }
                QScrollBar::handle:vertical:hover { background: #3b82f6; }
                QScrollBar::sub-line:vertical, QScrollBar::add-line:vertical { border: none; background: none; height: 0px; }
                QScrollBar::up-arrow:vertical, QScrollBar::down-arrow:vertical { background: none; }
                QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
            """)
            btn_page_style = """
                QPushButton {
                    background-color: #16161a;
                    color: #ffffff;
                    border: 1px solid #23232a;
                    border-radius: 5px;
                    font-size: 12px;
                    font-weight: 600;
                    height: 28px;
                    padding: 0 16px;
                }
                QPushButton:hover { background-color: #202026; border: 1px solid #3b82f6; }
                QPushButton:disabled {
                    background-color: rgba(22, 22, 26, 0.25);
                    color: rgba(255, 255, 255, 0.2);
                    border: 1px solid rgba(35, 35, 42, 0.25);
                }
            """
            self.page_label.setStyleSheet("color: #8f8f9d; font-size: 11px; font-weight: 600;")
            self.powered_lbl.setStyleSheet("""
                color: rgba(255, 255, 255, 0.18);
                font-size: 10px;
                font-weight: 500;
                letter-spacing: 0.4px;
                margin-top: 2px;
            """)

        self.btn_prev.setStyleSheet(btn_page_style)
        self.btn_next.setStyleSheet(btn_page_style)

        for i in range(self.cards_layout.count()):
            item = self.cards_layout.itemAt(i)
            if item and item.widget() and isinstance(item.widget(), MidiHubCard):
                item.widget().set_theme(is_white)

    def fetch_data(self):
        self._clear_cards()
        color_status = "#71717a" if self.is_white else "#8f8f9d"
        status_lbl = QLabel("Fetching tracks from nanomidi.net...")
        status_lbl.setStyleSheet(f"color: {color_status}; font-size: 13px; font-weight: 500; margin-top: 50px;")
        status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cards_layout.addWidget(status_lbl)

        self.loader_thread = DataLoaderThread(self)
        self.loader_thread.loaded.connect(self._on_data_loaded)
        self.loader_thread.failed.connect(self._on_data_failed)
        self.loader_thread.start()

    def _on_data_loaded(self, data: list):
        self.all_midis = data
        self._apply_filters()

    def _on_data_failed(self, error: str):
        self._clear_cards()
        self.btn_prev.setEnabled(False)
        self.btn_next.setEnabled(False)
        self.page_label.setText("Page 0 / 0")

        error_container = QWidget()
        error_layout = QVBoxLayout(error_container)
        error_layout.setContentsMargins(0, 60, 0, 0)
        error_layout.setSpacing(10)
        error_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title_lbl = QLabel("Failed Connection to nanoMIDI!")
        title_lbl.setStyleSheet("color: #ff5f56; font-size: 16px; font-weight: bold;")
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        body_text = (
            "Please, try again, check your connection\n"
            "or check the status of nanoMIDI\n"
            "(status.nanomidi.net)"
        )
        body_lbl = QLabel(body_text)
        body_color = "#71717a" if self.is_white else "#8f8f9d"
        body_lbl.setStyleSheet(f"color: {body_color}; font-size: 12px; font-weight: 500;")
        body_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        error_layout.addWidget(title_lbl)
        error_layout.addWidget(body_lbl)
        self.cards_layout.addWidget(error_container)

    def _apply_filters(self):
        query = self.search_input.text().strip().lower()
        if query:
            self.filtered_midis = [
                m for m in self.all_midis 
                if query in m.get("name", "").lower() or query in m.get("artists", "").lower()
            ]
        else:
            self.filtered_midis = list(self.all_midis)

        sort_mode = self.sort_combo.currentText()
        if sort_mode == "Newest":
            self.filtered_midis.sort(key=lambda m: m.get("id", 0), reverse=True)
        elif sort_mode == "Oldest":
            self.filtered_midis.sort(key=lambda m: m.get("id", 0))
        elif sort_mode == "Downloads":
            self.filtered_midis.sort(key=lambda m: m.get("downloads", 0), reverse=True)
        elif sort_mode == "Views":
            self.filtered_midis.sort(key=lambda m: m.get("views", 0), reverse=True)

        self.current_page = 1
        self._render_page()

    def _render_page(self):
        self._clear_cards()
        total = len(self.filtered_midis)
        self.total_pages = max(1, (total + self.page_size - 1) // self.page_size)
        self.page_label.setText(f"Page {self.current_page} / {self.total_pages}")

        self.btn_prev.setEnabled(self.current_page > 1)
        self.btn_next.setEnabled(self.current_page < self.total_pages)

        if not self.filtered_midis:
            empty_lbl = QLabel("No MIDI files found")
            empty_color = "#71717a" if self.is_white else "#7b7b8a"
            empty_lbl.setStyleSheet(f"color: {empty_color}; font-size: 13px; margin-top: 40px;")
            empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.cards_layout.addWidget(empty_lbl)
            return

        start_idx = (self.current_page - 1) * self.page_size
        end_idx = min(start_idx + self.page_size, total)
        page_items = self.filtered_midis[start_idx:end_idx]

        for item in page_items:
            card = MidiHubCard(item)
            card.set_theme(self.is_white)
            card.action_requested.connect(self._handle_card_action)
            self.cards_layout.addWidget(card)

            img_fn = item.get("imageFilename")
            if img_fn:
                if img_fn in self.image_cache:
                    card.set_cover_pixmap(self.image_cache[img_fn])
                else:
                    t = ImageLoaderThread(img_fn, self)
                    t.image_ready.connect(self._on_image_downloaded)
                    self.active_threads.append(t)
                    t.start()

        self.scroll.verticalScrollBar().setValue(0)

    def _on_image_downloaded(self, filename: str, data: QByteArray):
        pix = QPixmap()
        if pix.loadFromData(data):
            self.image_cache[filename] = pix
            for i in range(self.cards_layout.count()):
                w = self.cards_layout.itemAt(i).widget()
                if isinstance(w, MidiHubCard) and w.midi_info.get("imageFilename") == filename:
                    w.set_cover_pixmap(pix)

    def _handle_card_action(self, midi_info: dict, action: str):
        midi_fn = midi_info.get("midiFilename", "")
        sender_card = self.sender()

        
        is_safe, err_msg = is_safe_midi_path(midi_fn)
        if not is_safe:
            if isinstance(sender_card, MidiHubCard):
                sender_card.set_failed_state("Fail!")
            return

        local_path = os.path.abspath(os.path.join(DOWNLOADS_DIR, midi_fn))
        if action == "load":
            self.midi_loaded.emit(local_path)
        elif action == "download":
            if isinstance(sender_card, MidiHubCard):
                sender_card.set_downloading_state()
            downloader = FileDownloadThread(midi_fn, self)
            downloader.download_finished.connect(lambda path: self._on_download_success(path, sender_card))
            downloader.download_failed.connect(lambda err: self._on_download_failed(err, sender_card))
            self.active_threads.append(downloader)
            downloader.start()

    def _on_download_success(self, path: str, card: MidiHubCard):
        if card:
            card.update_button_state()
            card.action_btn.setEnabled(True)
        self.midi_loaded.emit(path)

    def _on_download_failed(self, err: str, card: MidiHubCard):
        if card:
            card.set_failed_state("Fail!")

    def _prev_page(self):
        HubSound.play()
        if self.current_page > 1:
            self.current_page -= 1
            self._render_page()

    def _next_page(self):
        HubSound.play()
        if self.current_page < self.total_pages:
            self.current_page += 1
            self._render_page()

    def _on_search_changed(self):
        self._apply_filters()

    def _on_sort_changed(self):
        HubSound.play()
        self._apply_filters()

    def _clear_cards(self):
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()