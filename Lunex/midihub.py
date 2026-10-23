import os
import requests
from requests.adapters import HTTPAdapter
from PyQt6.QtCore import (
    Qt, pyqtSignal, QObject, QThread, QRunnable, QThreadPool,
    QByteArray, QUrl, QTimer
)
from PyQt6.QtGui import QPixmap, QPainter, QColor, QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QScrollArea, QFrame
)
from PyQt6.QtMultimedia import QSoundEffect

from themes import BLACK_THEME, WHITE_THEME


DEFAULT_MIDIHUB_BLACK = BLACK_THEME["midihub"]
DEFAULT_MIDIHUB_WHITE = WHITE_THEME["midihub"]

LOCAL_APPDATA = os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), "AppData", "Local")
LUNEX_APPDATA_DIR = os.path.abspath(os.path.join(LOCAL_APPDATA, "Lunex"))
DOWNLOADS_DIR = os.path.join(LUNEX_APPDATA_DIR, "midis")
os.makedirs(DOWNLOADS_DIR, exist_ok=True)


def _create_http_session() -> requests.Session:
    session = requests.Session()
    adapter = HTTPAdapter(pool_connections=8, pool_maxsize=8, max_retries=1)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({"Connection": "keep-alive"})
    return session


HTTP_SESSION = _create_http_session()


def is_safe_midi_path(midi_filename: str) -> tuple[bool, str]:
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
            resp = HTTP_SESSION.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list):
                data.reverse()
                self.loaded.emit(data)
            else:
                self.failed.emit("Invalid API response format")
        except Exception as e:
            self.failed.emit(str(e))


class ImageTaskSignals(QObject):
    image_ready = pyqtSignal(str, QByteArray)
    finished_task = pyqtSignal(str)


class ImageLoaderTask(QRunnable):
    def __init__(self, filename: str, generation: int, get_generation_fn):
        super().__init__()
        self.setAutoDelete(True)
        self.filename = filename
        self.generation = generation
        self._get_generation = get_generation_fn
        self.signals = ImageTaskSignals()

    def run(self):
        try:
            if self._get_generation() != self.generation:
                return
            url = f"https://api.nanomidi.net/api/v2/images/{self.filename}?size=100x100"
            resp = HTTP_SESSION.get(url, timeout=5)
            if resp.status_code == 200 and resp.content:
                self.signals.image_ready.emit(self.filename, QByteArray(resp.content))
        except Exception:
            pass
        finally:
            try:
                self.signals.finished_task.emit(self.filename)
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
            os.makedirs(DOWNLOADS_DIR, exist_ok=True)
            resp = HTTP_SESSION.get(url, timeout=15)
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
        self.theme_data = dict(DEFAULT_MIDIHUB_BLACK)
        self.has_custom_cover = False
        self._btn_state = "normal"
        self._fail_text = "Fail!"
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

        self.meta_lbl = QLabel(" \u2022 ".join(meta_parts))

        dls = self.midi_info.get("downloads", 0)
        views = self.midi_info.get("views", 0)
        self.stats_lbl = QLabel(f"\u2b07 {dls:,}   \U0001f441 {views:,}")

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

        self.set_theme(DEFAULT_MIDIHUB_BLACK)

    def set_theme(self, theme_or_is_white: dict | bool):
        if isinstance(theme_or_is_white, dict):
            self.is_white = bool(theme_or_is_white.get("is_white", False))
            base = DEFAULT_MIDIHUB_WHITE if self.is_white else DEFAULT_MIDIHUB_BLACK
            merged = dict(base)
            merged.update(theme_or_is_white)
            self.theme_data = merged
        else:
            self.is_white = bool(theme_or_is_white)
            self.theme_data = dict(DEFAULT_MIDIHUB_WHITE if self.is_white else DEFAULT_MIDIHUB_BLACK)

        t = self.theme_data
        if not self.has_custom_cover:
            self.set_placeholder_image()

        self.setStyleSheet(f"""
            QWidget#midiHubCard {{
                background-color: {t.get("card_bg", "#16161a")};
                border: 1px solid {t.get("card_border", "#23232a")};
                border-radius: 7px;
            }}
            QWidget#midiHubCard:hover {{
                border: 1px solid {t.get("card_hover_border", "#2f2f3a")};
            }}
        """)
        self.title_lbl.setStyleSheet(f"color: {t.get('card_title_text', '#ffffff')}; font-size: 13px; font-weight: 600;")
        self.meta_lbl.setStyleSheet(f"color: {t.get('card_meta_text', '#8f8f9d')}; font-size: 11px;")
        self.stats_lbl.setStyleSheet(f"color: {t.get('card_stats_text', '#555562')}; font-size: 10px; font-weight: bold;")

        if self._btn_state == "downloading":
            self._apply_downloading_btn_style()
        elif self._btn_state == "failed":
            self._apply_failed_btn_style()
        else:
            self.update_button_state()

    def set_placeholder_image(self):
        t = self.theme_data
        pix = QPixmap(66, 66)
        bg_col = QColor(t.get("placeholder_bg", "#181820"))
        pen_col = QColor(t.get("placeholder_text", "#454555"))
        border_col = t.get("placeholder_border", "#101014")

        pix.fill(bg_col)
        p = QPainter(pix)
        p.setPen(pen_col)
        p.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        p.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, "\u266a")
        p.end()

        self.cover_label.setStyleSheet(
            f"background-color: {bg_col.name()}; border: 1px solid {border_col}; border-radius: 5px;"
        )
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
        self._btn_state = "normal"
        midi_fn = self.midi_info.get("midiFilename", "")
        is_safe, _ = is_safe_midi_path(midi_fn)
        if not is_safe:
            self.action_btn.setText("Download")
            self._apply_standard_btn_style()
            return

        local_path = os.path.join(DOWNLOADS_DIR, midi_fn)
        if os.path.isfile(local_path):
            t = self.theme_data
            self.action_btn.setText("Load in Lunex")
            self.action_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {t.get("load_btn_bg", "#1d3354")};
                    color: {t.get("load_btn_text", "#60a5fa")};
                    border: 1px solid {t.get("load_btn_border", "#2d4f82")};
                    border-radius: 5px;
                    font-size: 11px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background-color: {t.get("load_btn_hover_bg", "#264472")};
                    border: 1px solid {t.get("load_btn_hover_border", "#3b82f6")};
                    color: {t.get("load_btn_hover_text", "#ffffff")};
                }}
            """)
        else:
            self.action_btn.setText("Download")
            self._apply_standard_btn_style()

    def _apply_standard_btn_style(self):
        t = self.theme_data
        self.action_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {t.get("download_btn_bg", "#202026")};
                color: {t.get("download_btn_text", "#ffffff")};
                border: 1px solid {t.get("download_btn_border", "#2c2c36")};
                border-radius: 5px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {t.get("download_btn_hover_bg", "#2b2b34")};
                border: 1px solid {t.get("download_btn_hover_border", "#3d3d4a")};
            }}
        """)

    def _apply_downloading_btn_style(self):
        t = self.theme_data
        self.action_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {t.get("downloading_btn_bg", "#16161a")};
                color: {t.get("downloading_btn_text", "#8f8f9d")};
                border: 1px solid {t.get("downloading_btn_border", "#23232a")};
                border-radius: 5px;
                font-size: 11px;
            }}
        """)

    def _apply_failed_btn_style(self):
        t = self.theme_data
        self.action_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {t.get("fail_btn_bg", "#2b1717")};
                color: {t.get("fail_btn_text", "#ef4444")};
                border: 1px solid {t.get("fail_btn_border", "#7f1d1d")};
                border-radius: 5px;
                font-size: 11px;
                font-weight: 600;
            }}
        """)

    def set_downloading_state(self):
        self._btn_state = "downloading"
        self.action_btn.setEnabled(False)
        self.action_btn.setText("Downloading...")
        self._apply_downloading_btn_style()

    def set_failed_state(self, text: str = "Fail!"):
        self._btn_state = "failed"
        self._fail_text = text
        self.action_btn.setEnabled(False)
        self.action_btn.setText(text)
        self._apply_failed_btn_style()
        QTimer.singleShot(2500, self._restore_after_fail)

    def _restore_after_fail(self):
        self._btn_state = "normal"
        self.action_btn.setEnabled(True)
        self.update_button_state()

    def _on_action_clicked(self):
        HubSound.play()
        midi_fn = self.midi_info.get("midiFilename", "")
        is_safe, _ = is_safe_midi_path(midi_fn)
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
        self._pending_images: set[str] = set()
        self._page_generation = 0
        self.is_white = False
        self.theme_data = dict(DEFAULT_MIDIHUB_BLACK)

        self.is_loading_data = False
        self.has_connection_error = False
        self.retry_btn: QPushButton | None = None
        self.error_title_lbl: QLabel | None = None
        self.error_body_lbl: QLabel | None = None
        self.status_lbl: QLabel | None = None
        self.empty_lbl: QLabel | None = None

        self.retry_timer = QTimer(self)
        self.retry_timer.setSingleShot(True)
        self.retry_timer.setInterval(5000)
        self.retry_timer.timeout.connect(self._show_retry_button)

        self.image_pool = QThreadPool(self)
        self.image_pool.setMaxThreadCount(4)

        self.current_page = 1
        self.page_size = 10
        self.total_pages = 1

        self._setup_ui()
        self.fetch_data()

    def _get_page_generation(self) -> int:
        return self._page_generation

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

        self.set_theme(DEFAULT_MIDIHUB_BLACK)

    def _get_retry_btn_style(self) -> str:
        t = self.theme_data
        return f"""
            QPushButton {{
                background-color: {t.get("retry_btn_bg", "#16161a")};
                color: {t.get("retry_btn_text", "#ffffff")};
                border: 1px solid {t.get("retry_btn_border", "#23232a")};
                border-radius: 5px;
                font-size: 12px;
                font-weight: 600;
                height: 30px;
                padding: 0 18px;
            }}
            QPushButton:hover {{
                background-color: {t.get("retry_btn_hover_bg", "#202026")};
                border: 1px solid {t.get("retry_btn_hover_border", "#3b82f6")};
            }}
        """

    def set_theme(self, theme_or_is_white: dict | bool):
        if isinstance(theme_or_is_white, dict):
            self.is_white = bool(theme_or_is_white.get("is_white", False))
            base = DEFAULT_MIDIHUB_WHITE if self.is_white else DEFAULT_MIDIHUB_BLACK
            merged = dict(base)
            merged.update(theme_or_is_white)
            self.theme_data = merged
        else:
            self.is_white = bool(theme_or_is_white)
            self.theme_data = dict(DEFAULT_MIDIHUB_WHITE if self.is_white else DEFAULT_MIDIHUB_BLACK)

        t = self.theme_data

        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {t.get("search_bg", "#16161a")};
                color: {t.get("search_text", "#ffffff")};
                border: 1px solid {t.get("search_border", "#23232a")};
                border-radius: 5px;
                padding: 0 10px;
                font-size: 12px;
            }}
            QLineEdit:focus {{
                border: 1px solid {t.get("search_focus_border", "#3b82f6")};
            }}
        """)

        self.sort_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {t.get("combo_bg", "#16161a")};
                color: {t.get("combo_text", "#c9c9d4")};
                border: 1px solid {t.get("combo_border", "#23232a")};
                border-radius: 5px;
                padding-left: 10px;
                font-size: 11px;
                font-weight: 500;
            }}
            QComboBox:hover {{
                border: 1px solid {t.get("combo_hover_border", "#3b82f6")};
                color: {t.get("combo_hover_text", "#ffffff")};
            }}
            QComboBox::drop-down {{ border: none; width: 0px; }}
            QComboBox QAbstractItemView {{
                background-color: {t.get("combo_popup_bg", "#16161a")};
                color: {t.get("combo_popup_text", "#e1e1e6")};
                selection-background-color: {t.get("combo_selection_bg", "#26334d")};
                selection-color: {t.get("combo_selection_text", "#60a5fa")};
                border: 1px solid {t.get("combo_popup_border", "#2c2c38")};
                border-radius: 5px;
                padding: 4px;
                outline: none;
            }}
        """)

        self.scroll.setStyleSheet(f"""
            QScrollArea {{ border: none; background-color: transparent; }}
            QScrollBar:vertical {{
                border: none;
                background: {t.get("scrollbar_bg", "#101014")};
                width: 6px;
                border-radius: 3px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background: {t.get("scrollbar_handle_bg", "#23232c")};
                min-height: 25px;
                border-radius: 3px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {t.get("scrollbar_handle_hover_bg", "#3b82f6")};
            }}
            QScrollBar::sub-line:vertical, QScrollBar::add-line:vertical {{
                border: none; background: none; height: 0px;
            }}
            QScrollBar::up-arrow:vertical, QScrollBar::down-arrow:vertical {{ background: none; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
        """)

        btn_page_style = f"""
            QPushButton {{
                background-color: {t.get("page_btn_bg", "#16161a")};
                color: {t.get("page_btn_text", "#ffffff")};
                border: 1px solid {t.get("page_btn_border", "#23232a")};
                border-radius: 5px;
                font-size: 12px;
                font-weight: 600;
                height: 28px;
                padding: 0 16px;
            }}
            QPushButton:hover {{
                background-color: {t.get("page_btn_hover_bg", "#202026")};
                border: 1px solid {t.get("page_btn_hover_border", "#3b82f6")};
            }}
            QPushButton:disabled {{
                background-color: {t.get("page_btn_disabled_bg", "rgba(22, 22, 26, 0.25)")};
                color: {t.get("page_btn_disabled_text", "rgba(255, 255, 255, 0.2)")};
                border: 1px solid {t.get("page_btn_disabled_border", "rgba(35, 35, 42, 0.25)")};
            }}
        """
        self.btn_prev.setStyleSheet(btn_page_style)
        self.btn_next.setStyleSheet(btn_page_style)

        self.page_label.setStyleSheet(
            f"color: {t.get('page_label_text', '#8f8f9d')}; font-size: 11px; font-weight: 600;"
        )
        self.powered_lbl.setStyleSheet(f"""
            color: {t.get("powered_text", "rgba(255, 255, 255, 0.18)")};
            font-size: 10px;
            font-weight: 500;
            letter-spacing: 0.4px;
            margin-top: 2px;
        """)

        if self.status_lbl is not None:
            self.status_lbl.setStyleSheet(
                f"color: {t.get('status_text', '#8f8f9d')}; font-size: 13px; font-weight: 500; margin-top: 50px;"
            )
        if self.empty_lbl is not None:
            self.empty_lbl.setStyleSheet(
                f"color: {t.get('empty_text', '#7b7b8a')}; font-size: 13px; margin-top: 40px;"
            )
        if self.error_title_lbl is not None:
            self.error_title_lbl.setStyleSheet(
                f"color: {t.get('error_title_text', '#ff5f56')}; font-size: 16px; font-weight: bold;"
            )
        if self.error_body_lbl is not None:
            self.error_body_lbl.setStyleSheet(
                f"color: {t.get('error_body_text', '#8f8f9d')}; font-size: 12px; font-weight: 500;"
            )
        if self.retry_btn is not None:
            self.retry_btn.setStyleSheet(self._get_retry_btn_style())

        for i in range(self.cards_layout.count()):
            item = self.cards_layout.itemAt(i)
            if item and item.widget() and isinstance(item.widget(), MidiHubCard):
                item.widget().set_theme(t)

    def fetch_data(self):
        if self.is_loading_data:
            return
        if self.retry_timer.isActive():
            self.retry_timer.stop()

        self.is_loading_data = True
        self.has_connection_error = False
        self._clear_cards()

        self.btn_prev.setEnabled(False)
        self.btn_next.setEnabled(False)
        self.page_label.setText("Page 1 / 1")

        color_status = self.theme_data.get("status_text", "#8f8f9d")
        self.status_lbl = QLabel("Fetching tracks from nanomidi.net...")
        self.status_lbl.setStyleSheet(f"color: {color_status}; font-size: 13px; font-weight: 500; margin-top: 50px;")
        self.status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cards_layout.addWidget(self.status_lbl)

        self.loader_thread = DataLoaderThread(self)
        self.loader_thread.loaded.connect(self._on_data_loaded)
        self.loader_thread.failed.connect(self._on_data_failed)
        self.loader_thread.finished.connect(self.loader_thread.deleteLater)
        self.loader_thread.start()

    def _on_data_loaded(self, data: list):
        self.is_loading_data = False
        self.has_connection_error = False
        if self.retry_timer.isActive():
            self.retry_timer.stop()
        self.all_midis = data
        self._apply_filters()

    def _on_data_failed(self, error: str):
        self.is_loading_data = False
        self.has_connection_error = True
        self._clear_cards()

        self.btn_prev.setEnabled(False)
        self.btn_next.setEnabled(False)
        self.page_label.setText("Page 0 / 0")

        error_container = QWidget()
        error_layout = QVBoxLayout(error_container)
        error_layout.setContentsMargins(0, 60, 0, 0)
        error_layout.setSpacing(10)
        error_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        t = self.theme_data
        self.error_title_lbl = QLabel("Failed Connection to nanoMIDI!")
        self.error_title_lbl.setStyleSheet(
            f"color: {t.get('error_title_text', '#ff5f56')}; font-size: 16px; font-weight: bold;"
        )
        self.error_title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        body_text = (
            "Please, try again, check your connection\n"
            "or check the status of nanoMIDI\n"
            "(status.nanomidi.net)"
        )
        self.error_body_lbl = QLabel(body_text)
        self.error_body_lbl.setStyleSheet(
            f"color: {t.get('error_body_text', '#8f8f9d')}; font-size: 12px; font-weight: 500;"
        )
        self.error_body_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.retry_btn = QPushButton("Try Again")
        self.retry_btn.setFixedSize(120, 30)
        self.retry_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.retry_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.retry_btn.setStyleSheet(self._get_retry_btn_style())
        self.retry_btn.clicked.connect(self._on_retry_clicked)
        self.retry_btn.setVisible(False)

        error_layout.addWidget(self.error_title_lbl)
        error_layout.addWidget(self.error_body_lbl)
        error_layout.addWidget(self.retry_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        self.cards_layout.addWidget(error_container)
        self.retry_timer.start(5000)

    def _show_retry_button(self):
        if self.has_connection_error and self.retry_btn is not None:
            self.retry_btn.setVisible(True)

    def _on_retry_clicked(self):
        HubSound.play()
        self.fetch_data()

    def _apply_filters(self):
        if self.is_loading_data or self.has_connection_error:
            return

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
        if self.is_loading_data or self.has_connection_error:
            return

        self._page_generation += 1
        self.image_pool.clear()
        self._pending_images.clear()
        self._clear_cards()

        total = len(self.filtered_midis)
        self.total_pages = max(1, (total + self.page_size - 1) // self.page_size)

        self.page_label.setText(f"Page {self.current_page} / {self.total_pages}")
        self.btn_prev.setEnabled(self.current_page > 1)
        self.btn_next.setEnabled(self.current_page < self.total_pages)

        if not self.filtered_midis:
            self.empty_lbl = QLabel("No MIDI files found")
            empty_color = self.theme_data.get("empty_text", "#7b7b8a")
            self.empty_lbl.setStyleSheet(f"color: {empty_color}; font-size: 13px; margin-top: 40px;")
            self.empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.cards_layout.addWidget(self.empty_lbl)
            return

        start_idx = (self.current_page - 1) * self.page_size
        end_idx = min(start_idx + self.page_size, total)
        page_items = self.filtered_midis[start_idx:end_idx]
        current_gen = self._page_generation

        for item in page_items:
            card = MidiHubCard(item)
            card.set_theme(self.theme_data)
            card.action_requested.connect(self._handle_card_action)
            self.cards_layout.addWidget(card)

            img_fn = item.get("imageFilename")
            if img_fn:
                if img_fn in self.image_cache:
                    card.set_cover_pixmap(self.image_cache[img_fn])
                elif img_fn not in self._pending_images:
                    self._pending_images.add(img_fn)
                    task = ImageLoaderTask(img_fn, current_gen, self._get_page_generation)
                    task.signals.image_ready.connect(self._on_image_downloaded)
                    task.signals.finished_task.connect(self._on_image_task_finished)
                    self.image_pool.start(task)

        self.scroll.verticalScrollBar().setValue(0)

    def _on_image_task_finished(self, filename: str):
        self._pending_images.discard(filename)

    def _on_image_downloaded(self, filename: str, data: QByteArray):
        pix = QPixmap()
        if pix.loadFromData(data):
            self.image_cache[filename] = pix
            for i in range(self.cards_layout.count()):
                w = self.cards_layout.itemAt(i).widget()
                if isinstance(w, MidiHubCard) and w.midi_info.get("imageFilename") == filename:
                    w.set_cover_pixmap(pix)

    def _cleanup_download_thread(self, thread: QThread):
        if thread in self.active_threads:
            self.active_threads.remove(thread)
        thread.deleteLater()

    def _handle_card_action(self, midi_info: dict, action: str):
        midi_fn = midi_info.get("midiFilename", "")
        sender_card = self.sender()

        is_safe, _ = is_safe_midi_path(midi_fn)
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
            downloader.download_finished.connect(lambda path, c=sender_card: self._on_download_success(path, c))
            downloader.download_failed.connect(lambda err, c=sender_card: self._on_download_failed(err, c))
            downloader.finished.connect(lambda d=downloader: self._cleanup_download_thread(d))
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
        self.retry_btn = None
        self.error_title_lbl = None
        self.error_body_lbl = None
        self.status_lbl = None
        self.empty_lbl = None
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()