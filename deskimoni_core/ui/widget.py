#!/usr/bin/env python3
"""
Deskimoni v2 - DeskimonWidget
Haupt-Widget und Lebenszyklus: Verbindet alle Mixins (Rendering, Menüs, Speicher, KI, Voice, Content)
mit 60-FPS Physik, globalem Mauszeiger-Tracking und Ereignis-Schleifen.
"""

import os
import sys
import time
import math
import json
import shutil
import random
import subprocess
import threading
from datetime import datetime, timedelta

import psutil
from deskimoni_core.qt import (
    Qt, QTimer, QPoint, QPointF, QRectF, QSize,
    QColor, QFont, QPainter, QCursor, QIcon,
    QWidget, QApplication, QLineEdit, QPushButton,
    QInputDialog, QMessageBox, QStyle
)

from deskimoni_core.signals import WorkerSignals
from deskimoni_core.config import (
    SKINS, SKIN_NAMES, MODES, MODE_NAMES, EMOTIONS, EMOTION_NAMES,
    OLLAMA_MODELS, GEMINI_MODELS, LINUX_TIPS, TRANSLATIONS,
    DEFAULT_RSS_FEEDS, DEFAULT_RADIO_STATIONS,
    CHATTER_QUESTIONS, CHATTER_RELAX, CHATTER_JOKES, CHATTER_THOUGHTS, MOVIE_QUOTES,
    log_event
)
from deskimoni_core.audio.sound_engine import RobotSoundEngine
from deskimoni_core.platform.cursor import GlobalCursorTracker, CursorShaker
from deskimoni_core.services.ai import DeskimonAiMixin
from deskimoni_core.services.content import DeskimonContentMixin
from deskimoni_core.services.voice import DeskimonVoiceMixin
from deskimoni_core.services.worktime import DeskimonWorkTimeMixin
from deskimoni_core.ui.dialogs import DeskimonMemoryMixin
from deskimoni_core.ui.menus import DeskimonMenuMixin
from deskimoni_core.ui.renderer import DeskimonPaintMixin


class DeskimonWidget(
    QWidget,
    DeskimonPaintMixin,
    DeskimonMenuMixin,
    DeskimonMemoryMixin,
    DeskimonAiMixin,
    DeskimonContentMixin,
    DeskimonVoiceMixin,
    DeskimonWorkTimeMixin,
):
    """Deskimoni Hauptfenster und interaktiver Desktop-Begleiter."""

    SKINS = SKINS
    SKIN_NAMES = SKIN_NAMES
    MODES = MODES
    MODE_NAMES = MODE_NAMES
    EMOTIONS = EMOTIONS
    EMOTION_NAMES = EMOTION_NAMES
    OLLAMA_MODELS = OLLAMA_MODELS
    GEMINI_MODELS = GEMINI_MODELS
    LINUX_TIPS = LINUX_TIPS
    TRANSLATIONS = TRANSLATIONS
    DEFAULT_RSS_FEEDS = DEFAULT_RSS_FEEDS
    DEFAULT_RADIO_STATIONS = DEFAULT_RADIO_STATIONS
    CHATTER_QUESTIONS = CHATTER_QUESTIONS
    CHATTER_RELAX = CHATTER_RELAX
    CHATTER_JOKES = CHATTER_JOKES
    CHATTER_THOUGHTS = CHATTER_THOUGHTS
    MOVIE_QUOTES = MOVIE_QUOTES

    def __init__(self):
        super().__init__()

        self.signals = WorkerSignals()
        self.signals.reply_ready.connect(self.on_ai_reply)
        self.signals.greeting_ready.connect(self.on_startup_greeting_ready)
        self.signals.speech_state.connect(self.on_speech_state)
        self.signals.mic_state.connect(self.on_mic_state)
        self.signals.mic_result.connect(self.on_mic_result)

        self.sound = RobotSoundEngine(self.signals)
        self.cursor_tracker = GlobalCursorTracker()
        self.cursor_shaker = CursorShaker()

        # Fenster-Dimensionen (oben Platz für Sprechblase, unten Platz für Chat-Leiste)
        self.always_on_top = True
        self.scale_factor = 1.0
        self.base_width = 270
        self.base_height = 370
        self.body_offset_x = 15
        self.body_offset_y = 68

        # Zustand & Skin
        self.app_language = "de"
        self.skin = "orbit"
        self.mode = "pet"
        self.saved_pos_x = None
        self.saved_pos_y = None
        self.is_walking_home = False
        self.forced_emotion = "auto"
        self.current_emotion = "normal"
        self.emotion_until = 0.0

        # Sprach- & KI-Zustand (Ollama lokal + Google Gemini Cloud-API)
        self.ollama_available = False
        self.installed_ollama_models = []
        self.ollama_model = "gemma3:4b"
        self.gemini_api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        self.gemini_model = "gemini-3.8-flash"
        self.ai_provider = "gemini" if self.gemini_api_key else "ollama"
        self.cursor_finder_enabled = True

        # RSS Feeds
        self.rss_feeds = list(self.DEFAULT_RSS_FEEDS)
        self.active_feed_idx = 0
        self.news_items = []
        self.news_idx = 0
        self.news_fetching = False
        self.last_news_fetch = 0.0
        self.news_auto_speak = False
        self.news_interval_mins = 30
        self.last_news_broadcast = time.time()

        # Health Reminders (Wasser & Bewegung)
        self.water_reminder_enabled = True
        self.water_reminder_mins = 35
        self.last_water_reminder = time.time()
        self.move_reminder_enabled = True
        self.move_reminder_mins = 50
        self.last_move_reminder = time.time()

        # Web-Radio & Streams
        self.radio_stations = list(self.DEFAULT_RADIO_STATIONS)
        self.active_radio_idx = 0
        self.radio_proc = None
        self.radio_playing = False

        # Plauder-Modus (Chatter)
        self.chatter_enabled = True
        self.chatter_interval_mins = 15
        self.next_chatter_time = time.time() + random.uniform(240.0, 600.0)

        # Gedächtnis & Identität
        self.bot_name = "Deskimoni"
        self.user_name = "Freund"
        self.user_facts = []
        self.load_memory()
        self.load_user_settings()
        self.detect_ollama_status()
        if self.gemini_api_key and (self.ai_provider == "gemini" or not self.ollama_available):
            self.ai_provider = "gemini"
        elif self.ollama_available:
            self.ai_provider = "ollama"

        # Chat-Zustand
        self.chat_history = []
        self.bubble_text = "Hallo! Doppelklicke auf meinen orangenen Knopf für Chat & Buttons!"
        self.bubble_until = time.time() + 8.0
        self.is_thinking = False
        self.is_speaking = False
        self.mic_status = "idle"
        self.mic_proc = None
        self.mic_wav_path = None

        # Animations-Variablen (60 FPS)
        self.tick_count = 0
        self.breath_phase = 0.0
        self.blink_state = 0.0
        self.is_blinking = False
        self.next_blink_time = time.time() + random.uniform(2.0, 5.0)

        # Tanz- & Headbang-Modus
        self.dance_enabled = True
        self.is_dancing = False
        self.dance_style = "none"
        self.dance_phase = 0.0
        self.forced_dance_until = 0.0
        self.forced_dance_style = "groove"
        self.ignored_dance_titles = set()

        # Spazier-Modus
        self.roaming_enabled = True
        self.roam_Mode = "local"
        self.walk_offset_x = 0.0
        self.walk_offset_y = 0.0
        self.walk_target_x = 0.0
        self.walk_target_y = 0.0
        self.win_target_x = None
        self.win_target_y = None
        self.walk_phase = 0.0
        self.is_stepping = False
        self.has_manual_walk_target = False
        self.next_walk_decision = time.time() + 10.0

        # Mauszeiger-Sucher
        self.cursor_idle_timeout = 180.0
        self.last_global_cursor_pos = self.cursor_tracker.get_pos()
        self.last_cursor_move_time = time.time()
        self.cursor_search_state = "idle"
        self.cursor_search_started_at = 0.0
        self.cursor_shake_ignore_until = 0.0
        self.last_cursor_hop_time = 0.0

        # Manuelles Ziehen mit der Maus
        self.is_dragging_pet = False
        self.drag_offset = QPointF(0, 0)
        self.norskmus_proc = None
        self.jothecrow_proc = None

        # Bauch-Button Timer (Einzelklick vs Doppelklick)
        self.belly_click_timer = QTimer(self)
        self.belly_click_timer.setSingleShot(True)
        self.belly_click_timer.timeout.connect(self._on_belly_single_click)

        # Augen-Ziel (Blickrichtung)
        self.look_x = 0.0
        self.look_y = 0.0
        self.target_look_x = 0.0
        self.target_look_y = 0.0
        self.last_random_look = time.time()

        # Interaktion & Physik
        self.setMouseTracking(True)
        self.pet_score = 0.0
        self.last_mouse_pos = None
        self.drag_history = []
        self.particles = []
        self.bounce_offset = 0.0
        self.bounce_velocity = 0.0

        # Pomodoro-Timer
        self.pomo_work_mins = 25
        self.pomo_short_break_mins = 5
        self.pomo_long_break_mins = 15
        self.pomo_sound_enabled = True
        self.pomo_phase = "work"
        self.pomo_duration = self.pomo_work_mins * 60
        self.pomo_remaining = self.pomo_duration
        self.pomo_running = False
        self.last_pomo_tick = time.time()

        # Wecker & Kurzzeit-Timer
        self.alarm_active = False
        self.alarm_time = None
        self.alarm_label = "Wecker"
        self.alarm_ringing = False

        # System-Metriken
        self.cpu_percent = 0.0
        self.ram_percent = 0.0
        self.cpu_temp = 45.0
        self.last_sys_check = 0.0

        # Live-Wetter
        self.weather_temp = "--°C"
        self.weather_desc = "Lade..."
        self.weather_city = ""
        self.weather_code = 113
        self.last_weather_check = 0.0
        self.weather_fetching = False

        # Musik & Media
        self.music_playing = False
        self.music_title = "Keine Musik aktiv"
        self.music_artist = "Starte Spotify / YouTube / VLC"
        self.music_service = ""
        self.last_music_check = 0.0
        self.linux_tip_idx = 0

        # Arbeitszeit- & Feierabend-Rechner initialisieren
        self.init_worktime()

        # UI & Tray Initialisierung
        self.setup_window_flags()
        self.ensure_kwin_keep_above_rule(self.always_on_top)
        self.setup_chat_ui()
        self.setup_tray()

        # Hintergrund-Dienste starten
        self.fetch_weather_async(speak_when_done=False)
        self.fetch_news_async(speak_when_done=False)

        # 60 FPS Animations-Schleife
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self.update_animation)
        self.anim_timer.start(16)

        # Persönliche Begrüßung beim Start
        QTimer.singleShot(800, self.greet_user_on_startup)

    # ==========================================
    # --- Einstellungen (JSON) ---
    # ==========================================
    def get_settings_path(self) -> str:
        return os.path.expanduser("~/.config/deskimoni/settings.json")

    def load_user_settings(self):
        path = self.get_settings_path()
        if not os.path.exists(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return
            need_save = False

            saved_key = data.get("gemini_api_key", "").strip()
            if saved_key:
                self.gemini_api_key = saved_key
            saved_gem_model = data.get("gemini_model", "").strip()
            valid_gemini_ids = [m[0] for m in self.GEMINI_MODELS]
            if saved_gem_model in valid_gemini_ids:
                self.gemini_model = saved_gem_model
            else:
                self.gemini_model = "gemini-3.8-flash"
                need_save = True

            saved_provider = data.get("ai_provider", "").strip()
            if saved_provider in ("ollama", "gemini"):
                self.ai_provider = saved_provider
            if self.gemini_api_key and (self.ai_provider == "gemini" or not self.installed_ollama_models):
                self.ai_provider = "gemini"
                need_save = True

            if "cursor_finder_enabled" in data:
                self.cursor_finder_enabled = bool(data["cursor_finder_enabled"])

            if "news_auto_speak" in data:
                self.news_auto_speak = bool(data["news_auto_speak"])
            if "news_interval_mins" in data:
                self.news_interval_mins = max(5, int(data["news_interval_mins"]))
            if "active_feed_idx" in data:
                self.active_feed_idx = max(0, int(data["active_feed_idx"]))
            if "rss_feeds" in data and isinstance(data["rss_feeds"], list) and data["rss_feeds"]:
                valid_f = [f for f in data["rss_feeds"] if isinstance(f, dict) and "name" in f and "url" in f]
                if valid_f:
                    self.rss_feeds = valid_f

            if "water_reminder_enabled" in data:
                self.water_reminder_enabled = bool(data["water_reminder_enabled"])
            if "water_reminder_mins" in data:
                self.water_reminder_mins = max(5, int(data["water_reminder_mins"]))
            if "move_reminder_enabled" in data:
                self.move_reminder_enabled = bool(data["move_reminder_enabled"])
            if "move_reminder_mins" in data:
                self.move_reminder_mins = max(5, int(data["move_reminder_mins"]))

            if "active_radio_idx" in data:
                self.active_radio_idx = max(0, int(data["active_radio_idx"]))
            if "radio_stations" in data and isinstance(data["radio_stations"], list) and data["radio_stations"]:
                valid_r = [s for s in data["radio_stations"] if isinstance(s, dict) and "name" in s and "url" in s]
                if valid_r:
                    self.radio_stations = valid_r

            if "chatter_enabled" in data:
                self.chatter_enabled = bool(data["chatter_enabled"])
            if "chatter_interval_mins" in data:
                self.chatter_interval_mins = max(3, int(data["chatter_interval_mins"]))

            if "pomo_work_mins" in data:
                self.pomo_work_mins = max(1, int(data["pomo_work_mins"]))
                if not self.pomo_running and self.pomo_phase == "work":
                    self.pomo_duration = self.pomo_work_mins * 60
                    self.pomo_remaining = self.pomo_duration
            if "pomo_short_break_mins" in data:
                self.pomo_short_break_mins = max(1, int(data["pomo_short_break_mins"]))
            if "pomo_long_break_mins" in data:
                self.pomo_long_break_mins = max(1, int(data["pomo_long_break_mins"]))
            if "pomo_sound_enabled" in data:
                self.pomo_sound_enabled = bool(data["pomo_sound_enabled"])

            if "dance_enabled" in data:
                self.dance_enabled = bool(data["dance_enabled"])

            if "app_language" in data and str(data["app_language"]).strip() in ("de", "en", "nb"):
                self.app_language = str(data["app_language"]).strip()

            if "bot_name" in data and str(data["bot_name"]).strip():
                self.bot_name = str(data["bot_name"]).strip()
            if "user_name" in data and str(data["user_name"]).strip():
                self.user_name = str(data["user_name"]).strip()

            if "skin" in data and str(data["skin"]).strip():
                saved_skin = str(data["skin"]).strip()
                valid_skin_ids = [s[0] for s in self.SKINS]
                if saved_skin in valid_skin_ids:
                    self.skin = saved_skin

            if "mode" in data and str(data["mode"]).strip():
                saved_mode = str(data["mode"]).strip()
                valid_mode_ids = [m[0] for m in self.MODES]
                if saved_mode in valid_mode_ids:
                    self.mode = saved_mode

            if "scale_factor" in data:
                try:
                    sf = float(data["scale_factor"])
                    if 0.5 <= sf <= 3.0:
                        self.scale_factor = sf
                except (ValueError, TypeError):
                    pass

            if "window_x" in data and "window_y" in data:
                try:
                    self.saved_pos_x = int(data["window_x"])
                    self.saved_pos_y = int(data["window_y"])
                except (ValueError, TypeError):
                    pass

            if need_save:
                self.save_user_settings()
        except Exception:
            pass

    def save_user_settings(self):
        path = self.get_settings_path()
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            cur_pos = self.pos()
            data = {
                "app_language": self.app_language,
                "skin": self.skin,
                "mode": self.mode,
                "scale_factor": self.scale_factor,
                "window_x": cur_pos.x(),
                "window_y": cur_pos.y(),
                "bot_name": self.bot_name,
                "user_name": self.user_name,
                "dance_enabled": self.dance_enabled,
                "gemini_api_key": self.gemini_api_key,
                "gemini_model": self.gemini_model,
                "ai_provider": self.ai_provider,
                "cursor_finder_enabled": self.cursor_finder_enabled,
                "news_auto_speak": self.news_auto_speak,
                "news_interval_mins": self.news_interval_mins,
                "active_feed_idx": self.active_feed_idx,
                "rss_feeds": self.rss_feeds,
                "water_reminder_enabled": self.water_reminder_enabled,
                "water_reminder_mins": self.water_reminder_mins,
                "move_reminder_enabled": self.move_reminder_enabled,
                "move_reminder_mins": self.move_reminder_mins,
                "active_radio_idx": self.active_radio_idx,
                "radio_stations": self.radio_stations,
                "chatter_enabled": self.chatter_enabled,
                "chatter_interval_mins": self.chatter_interval_mins,
                "pomo_work_mins": self.pomo_work_mins,
                "pomo_short_break_mins": self.pomo_short_break_mins,
                "pomo_long_break_mins": self.pomo_long_break_mins,
                "pomo_sound_enabled": self.pomo_sound_enabled,
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.chmod(path, 0o600)
        except Exception:
            pass

    # ==========================================
    # --- Fenster- und UI-Initialisierung ---
    # ==========================================
    def setup_window_flags(self):
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        if self.always_on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.resize(
            int(self.base_width * self.scale_factor),
            int(self.base_height * self.scale_factor),
        )
        self.setWindowTitle(self.bot_name)

    def setup_chat_ui(self):
        self.chat_input = QLineEdit(self)
        self.chat_input.setPlaceholderText("Frag Deskimoni etwas...")
        self.chat_input.returnPressed.connect(self.on_send_chat)
        self.chat_input.setStyleSheet(
            """
            QLineEdit {
                background-color: rgba(24, 25, 38, 235);
                color: #cdd6f4;
                border: 1.5px solid #89b4fa;
                border-radius: 13px;
                padding: 4px 10px;
                font-size: 12px;
            }
            QLineEdit:focus {
                border: 1.5px solid #f5c2e7;
                background-color: rgba(30, 30, 46, 250);
            }
            """
        )

        self.mic_btn = QPushButton(self)
        self.mic_btn.setIconSize(QSize(15, 15))
        self.mic_btn.setToolTip("Klicken zum Sprechen (Stoppt automatisch nach 4 Sek. oder bei erneutem Klick)")
        self.mic_btn.clicked.connect(self.toggle_microphone)
        self.update_mic_button_style()

        self.chat_toggle_btn = QPushButton(self)
        self.chat_toggle_btn.setIcon(self.get_app_icon("chat"))
        self.chat_toggle_btn.setIconSize(QSize(15, 15))
        self.chat_toggle_btn.setToolTip("Chat-Eingabefeld ein-/ausblenden")
        self.chat_toggle_btn.clicked.connect(self.toggle_chat_bar)
        self.chat_toggle_btn.setStyleSheet(
            """
            QPushButton {
                background-color: rgba(30, 30, 46, 220);
                border: 1.5px solid #45475a;
                border-radius: 13px;
                padding: 0px;
            }
            QPushButton:hover {
                border-color: #89b4fa;
                background-color: rgba(49, 50, 68, 240);
            }
            """
        )

        self.model_btn = QPushButton(self)
        self.model_btn.setIconSize(QSize(15, 15))
        self.model_btn.clicked.connect(self.cycle_ollama_model)
        self.update_model_button_ui()

        self.voice_btn = QPushButton(self)
        self.voice_btn.setIconSize(QSize(15, 15))
        self.voice_btn.clicked.connect(self.cycle_voice_profile)
        self.update_voice_button_ui()

        self.walk_btn = QPushButton(self)
        self.walk_btn.setIconSize(QSize(15, 15))
        self.walk_btn.clicked.connect(self.toggle_roaming)
        self.update_walk_button_ui()

        self.controls_visible = False
        self.chat_bar_visible = True
        self.layout_chat_ui()

    def update_mic_button_style(self):
        if self.mic_status == "recording":
            self.mic_btn.setIcon(self.get_app_icon("mic_stop"))
            self.mic_btn.setStyleSheet(
                """
                QPushButton {
                    background-color: #f38ba8;
                    border: 2px solid #ffffff;
                    border-radius: 13px;
                    padding: 0px;
                }
                """
            )
        elif self.mic_status == "recognizing":
            self.mic_btn.setIcon(self.get_app_icon("voice"))
            self.mic_btn.setStyleSheet(
                """
                QPushButton {
                    background-color: #f9e2af;
                    border: 1.5px solid #fab387;
                    border-radius: 13px;
                    padding: 0px;
                }
                """
            )
        else:
            self.mic_btn.setIcon(self.get_app_icon("mic"))
            self.mic_btn.setStyleSheet(
                """
                QPushButton {
                    background-color: rgba(30, 30, 46, 220);
                    border: 1.5px solid #45475a;
                    border-radius: 13px;
                    padding: 0px;
                }
                QPushButton:hover {
                    border-color: #a6e3a1;
                    background-color: rgba(49, 50, 68, 240);
                }
                """
            )

    def update_model_button_ui(self):
        if self.ai_provider == "gemini" and self.gemini_api_key:
            self.model_btn.setIcon(self.get_app_icon("cloud"))
            self.model_btn.setToolTip(
                f"☁️ Google Gemini Cloud-KI aktiv!\nAktives Modell: {self.gemini_model}\n"
                "Klicken zum Umschalten zwischen Modellen!"
            )
            border_col = "#89b4fa"
        elif self.ollama_available:
            self.model_btn.setIcon(self.get_app_icon("brain"))
            self.model_btn.setToolTip(
                f"🟢 Ollama (Lokal) verbunden!\nAktives KI-Modell: {self.ollama_model}\n"
                f"Installierte Modelle: {', '.join(self.installed_ollama_models) or 'Standard'}\n"
                "Klicken zum schnellen Umschalten!"
            )
            border_col = "#cba6f7"
        else:
            self.model_btn.setIcon(self.get_app_icon("key"))
            self.model_btn.setToolTip(
                "🟠 Weder Ollama noch Gemini API-Key aktiv (Offline-Modus)!\n"
                "Klicken, um deinen Google Gemini API-Key einzugeben!"
            )
            border_col = "#fab387"

        self.model_btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: rgba(30, 30, 46, 220);
                border: 1.5px solid {border_col};
                border-radius: 13px;
                padding: 0px;
            }}
            QPushButton:hover {{
                border-color: #89b4fa;
                background-color: rgba(49, 50, 68, 240);
            }}
            """
        )

    def cycle_ollama_model(self):
        self.detect_ollama_status()
        if not self.ollama_available and not self.gemini_api_key:
            self.prompt_gemini_api_key()
            return

        options = []
        if self.ollama_available:
            ollama_ids = (
                self.installed_ollama_models
                if self.installed_ollama_models
                else [m[0] for m in self.OLLAMA_MODELS]
            )
            for mid in ollama_ids:
                options.append(("ollama", mid))
        if self.gemini_api_key:
            for mid, *_ in self.GEMINI_MODELS:
                options.append(("gemini", mid))

        if not options:
            return

        current_pair = (
            ("gemini", self.gemini_model)
            if self.ai_provider == "gemini"
            else ("ollama", self.ollama_model)
        )
        try:
            idx = (options.index(current_pair) + 1) % len(options)
        except ValueError:
            idx = 0

        next_prov, next_model = options[idx]
        if next_prov == "gemini":
            self.set_gemini_model(next_model)
        else:
            self.set_ollama_model(next_model)

    def update_voice_button_ui(self):
        current_label = self.sound.voice_id
        for vid, label, *_ in RobotSoundEngine.VOICE_PROFILES:
            if vid == self.sound.voice_id:
                current_label = label
                break
        self.voice_btn.setIcon(self.get_app_icon("voice"))
        self.voice_btn.setToolTip(
            f"Aktive Stimme: {current_label}\nKlicken zum Stimmen-Wechseln & Probehören!"
        )
        self.voice_btn.setStyleSheet(
            """
            QPushButton {
                background-color: rgba(30, 30, 46, 220);
                border: 1.5px solid #45475a;
                border-radius: 13px;
                padding: 0px;
            }
            QPushButton:hover {
                border-color: #f9e2af;
                background-color: rgba(49, 50, 68, 240);
            }
            """
        )

    def cycle_voice_profile(self):
        v_ids = [v[0] for v in RobotSoundEngine.VOICE_PROFILES]
        try:
            idx = (v_ids.index(self.sound.voice_id) + 1) % len(v_ids)
        except ValueError:
            idx = 0
        self.set_voice_profile(v_ids[idx])

    def set_voice_profile(self, profile_id: str):
        self.sound.set_voice_profile(profile_id)
        self.update_voice_button_ui()
        label = profile_id
        for vid, lbl, *_ in RobotSoundEngine.VOICE_PROFILES:
            if vid == profile_id:
                label = lbl
                break
        self.show_bubble(f"🗣️ Neue Stimme aktiv:\n{label}", 4.5)
        self.sound.speak("Hallo! So klinge ich jetzt!", "happy")

    def update_walk_button_ui(self):
        self.walk_btn.setIcon(self.get_app_icon("paw"))
        if self.roaming_enabled:
            self.walk_btn.setToolTip("Spaziergang aktiv! (Klicken zum Stehenbleiben)")
            self.walk_btn.setStyleSheet(
                """
                QPushButton {
                    background-color: #a6e3a1;
                    border: 1.5px solid #ffffff;
                    border-radius: 13px;
                    padding: 0px;
                }
                """
            )
        else:
            self.walk_btn.setToolTip("Spaziergang starten (Deskimoni watschelt umher)")
            self.walk_btn.setStyleSheet(
                """
                QPushButton {
                    background-color: rgba(30, 30, 46, 220);
                    border: 1.5px solid #45475a;
                    border-radius: 13px;
                    padding: 0px;
                }
                QPushButton:hover {
                    border-color: #a6e3a1;
                    background-color: rgba(49, 50, 68, 240);
                }
                """
            )

    def toggle_roaming(self):
        self.roaming_enabled = not self.roaming_enabled
        self.update_walk_button_ui()
        self.sound.play_chirp("happy" if self.roaming_enabled else "curious")

        if self.roaming_enabled:
            self.next_walk_decision = time.time() + 1.0
            self.show_bubble("🐾 Juhu! Wenn mir langweilig ist, watschel ich gemütlich herum!", 4.0)
        else:
            self.walk_target_x = 0.0
            self.walk_target_y = 0.0
            self.win_target_x = None
            self.win_target_y = None
            self.has_manual_walk_target = True
            self.show_bubble("⏸ Okay, ich bleibe brav an meinem Platz stehen!", 3.5)

        self.layout_chat_ui()
        self.update()

    def layout_chat_ui(self):
        s = self.scale_factor
        cx_shift = int((self.body_offset_x - 15 + self.walk_offset_x) * s)
        y_pos = int((self.body_offset_y + 264 + self.walk_offset_y) * s)
        h = int(28 * s)
        btn_w = int(26 * s)

        self.chat_toggle_btn.setGeometry(cx_shift + int(4 * s), y_pos, btn_w, h)
        self.model_btn.setGeometry(cx_shift + int(32 * s), y_pos, btn_w, h)
        self.voice_btn.setGeometry(cx_shift + int(60 * s), y_pos, btn_w, h)
        self.walk_btn.setGeometry(cx_shift + int(88 * s), y_pos, btn_w, h)
        self.mic_btn.setGeometry(cx_shift + int(238 * s), y_pos, btn_w, h)
        self.chat_input.setGeometry(cx_shift + int(116 * s), y_pos, int(119 * s), h)

        if not getattr(self, "controls_visible", False):
            self.chat_toggle_btn.hide()
            self.model_btn.hide()
            self.voice_btn.hide()
            self.walk_btn.hide()
            self.mic_btn.hide()
            self.chat_input.hide()
        else:
            self.chat_toggle_btn.show()
            self.model_btn.show()
            self.voice_btn.show()
            self.walk_btn.show()
            self.mic_btn.show()
            if self.chat_bar_visible:
                self.chat_input.show()
            else:
                self.chat_input.hide()

    def toggle_controls_visibility(self):
        self.controls_visible = not self.controls_visible
        if self.controls_visible:
            self.chat_bar_visible = True
        self.layout_chat_ui()
        self.trigger_bounce(6.0)
        self.sound.play_chirp("happy" if self.controls_visible else "curious")
        if self.controls_visible:
            self.chat_input.setFocus()
            self.show_bubble("🎛️ Buttons & Chat eingeblendet! (Doppelklick auf meinen Bauch zum Verstecken)", 4.5)
        else:
            self.show_bubble("✨ Buttons & Chat wieder versteckt!", 3.0)
        self.update()

    def _on_belly_single_click(self):
        mode_ids = [m[0] for m in self.MODES]
        idx = (mode_ids.index(self.mode) + 1) % len(mode_ids)
        self.set_mode(mode_ids[idx])

    def toggle_chat_bar(self):
        self.chat_bar_visible = not self.chat_bar_visible
        self.layout_chat_ui()
        if self.chat_bar_visible:
            self.chat_input.setFocus()

    # ==========================================
    # --- Mauszeiger-Sucher & Hilfs-Tools ---
    # ==========================================
    def is_norskmus_running(self) -> bool:
        return self.norskmus_proc is not None and self.norskmus_proc.poll() is None

    def toggle_norskmus(self):
        if self.is_norskmus_running():
            try:
                self.norskmus_proc.terminate()
                self.norskmus_proc = None
            except Exception:
                pass
            self.show_bubble("🐭 NorskMus macht ein Nickerchen! Ha det bra!", 3.0)
            self.sound.play_chirp("happy")
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            script_sh = os.path.join(base_dir, "run_mouse.sh")
            script_py = os.path.join(base_dir, "norskmus.py")
            try:
                if sys.platform.startswith("win"):
                    self.norskmus_proc = subprocess.Popen([sys.executable, script_py])
                elif os.path.exists(script_sh) and os.access(script_sh, os.X_OK):
                    self.norskmus_proc = subprocess.Popen([script_sh])
                else:
                    self.norskmus_proc = subprocess.Popen([sys.executable, script_py])
                self.show_bubble("🐭 NorskMus ist da! Vær så god! 🇳🇴", 3.5)
                self.sound.play_chirp("love")
            except Exception as e:
                self.show_bubble(f"⚠️ Konnte NorskMus nicht starten: {e}", 4.0)

    def is_jothecrow_running(self) -> bool:
        return self.jothecrow_proc is not None and self.jothecrow_proc.poll() is None

    def toggle_jothecrow(self):
        if self.is_jothecrow_running():
            try:
                self.jothecrow_proc.terminate()
                self.jothecrow_proc = None
            except Exception:
                pass
            self.show_bubble("🐦‍⬛ Jo the Crow macht Pause! Ciao Digga!", 3.0)
            self.sound.play_chirp("happy")
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            script_sh = os.path.join(base_dir, "run_crow.sh")
            script_bat = os.path.join(base_dir, "start_crow_windows.bat")
            script_py = os.path.join(base_dir, "jothecrow.py")
            try:
                if sys.platform.startswith("win") and os.path.exists(script_bat):
                    self.jothecrow_proc = subprocess.Popen([script_bat], shell=True)
                elif os.path.exists(script_sh) and os.access(script_sh, os.X_OK):
                    self.jothecrow_proc = subprocess.Popen([script_sh])
                else:
                    self.jothecrow_proc = subprocess.Popen([sys.executable, script_py])
                self.show_bubble("🐦‍⬛ Jo the Crow ist gelandet! Sheesh! ✨", 3.5)
                self.sound.play_chirp("love")
            except Exception as e:
                self.show_bubble(f"⚠️ Konnte Jo the Crow nicht starten: {e}", 4.0)

    def toggle_cursor_finder(self):
        self.cursor_finder_enabled = not self.cursor_finder_enabled
        self.cursor_search_state = "idle"
        self.last_cursor_move_time = time.time()
        self.save_user_settings()
        state_str = "aktiviert (nach 3 Min.)" if self.cursor_finder_enabled else "deaktiviert"
        self.show_bubble(f"🧭 Mauszeiger-Sucher: {state_str}", 4.0)

    def shake_mouse_cursor(self):
        self.cursor_shake_ignore_until = time.time() + 1.4
        self.cursor_shaker.shake()

    def start_cursor_search_now(self):
        self.cursor_search_state = "found"
        self.cursor_search_started_at = time.time()
        self.last_cursor_hop_time = time.time()
        self.sound.play_chirp("curious")
        self.current_emotion = "excited"
        self.emotion_until = time.time() + 6.0
        self.trigger_bounce(8.0)
        self.spawn_particle("star")

        self.show_bubble("🧭 Ich schüttle deinen Mauszeiger, damit er groß wird! ✨", 5.5)
        self.shake_mouse_cursor()

    def get_autostart_path(self) -> str:
        if sys.platform == "win32":
            appdata = os.environ.get("APPDATA", "")
            return os.path.join(appdata, r"Microsoft\Windows\Start Menu\Programs\Startup\deskimoni.bat")
        return os.path.expanduser("~/.config/autostart/deskimoni.desktop")

    def is_autostart_enabled(self) -> bool:
        return os.path.exists(self.get_autostart_path())

    def toggle_autostart(self):
        autostart_file = self.get_autostart_path()
        if os.path.exists(autostart_file):
            try:
                os.remove(autostart_file)
                self.show_bubble("Autostart beim Login deaktiviert.", 4.0)
            except OSError:
                pass
        else:
            try:
                os.makedirs(os.path.dirname(autostart_file), exist_ok=True)
                if sys.platform == "win32":
                    with open(autostart_file, "w", encoding="utf-8") as f:
                        f.write(f'@echo off\nstart "" "{sys.executable}" deskimoni.py\n')
                else:
                    desktop_src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "deskimoni.desktop")
                    if os.path.exists(desktop_src):
                        shutil.copyfile(desktop_src, autostart_file)
                self.show_bubble("🚀 Super! Ich starte jetzt immer automatisch beim Login!", 4.5)
                self.sound.play_chirp("happy")
            except OSError:
                pass

    def toggle_voice(self):
        self.sound.voice_enabled = not self.sound.voice_enabled

    def toggle_chirps(self):
        self.sound.chirps_enabled = not self.sound.chirps_enabled

    def set_ollama_model(self, model_name: str):
        self.ollama_model = model_name
        self.ai_provider = "ollama"
        self.save_user_settings()
        self.update_model_button_ui()
        self.sound.play_chirp("curious")
        self.show_bubble(f"🧠 Lokales KI-Gehirn gewechselt auf:\n{model_name}", 4.5)

    def show_bubble(self, text: str, duration: float = 8.0):
        self.bubble_text = text
        self.bubble_until = time.time() + duration
        self.update()

    def on_speech_state(self, speaking: bool):
        self.is_speaking = speaking
        self.update()

    def on_send_chat(self):
        user_text = self.chat_input.text().strip()
        if not user_text or self.is_thinking:
            return
        self.chat_input.clear()
        self.ask_deskimoni(user_text)

    def reset_thinking_state(self):
        if getattr(self, "is_thinking", False):
            self.is_thinking = False
            self.current_emotion = "normal"
            self.update()

    def on_ai_reply(self, reply_text: str, emotion: str):
        self.is_thinking = False
        self.current_emotion = emotion
        self.emotion_until = time.time() + 7.5
        self.trigger_bounce(7.5)
        if emotion in ("love", "happy", "excited"):
            self.spawn_particle("heart" if emotion == "love" else "star")

        duration = max(7.0, min(16.0, len(reply_text) * 0.12))
        self.show_bubble(reply_text, duration)
        self.sound.speak(reply_text, emotion)

    # ==========================================
    # --- Setter & Aktionen ---
    # ==========================================
    def set_skin(self, skin_id):
        self.skin = skin_id
        self.trigger_bounce(8.0)
        self.sound.play_chirp("happy")
        self.save_user_settings()
        self.update()

    def set_mode(self, mode_id):
        self.mode = mode_id
        self.trigger_bounce(5.0)
        self.sound.play_chirp("curious")
        if mode_id == "weather" and time.time() - self.last_weather_check > 600:
            self.fetch_weather_async(speak_when_done=False)
        elif mode_id == "music":
            self.update_mpris_metadata()
        self.save_user_settings()
        self.update()

    def set_forced_emotion(self, emo_id):
        self.forced_emotion = emo_id
        if emo_id != "auto":
            self.current_emotion = emo_id
        self.update()

    def toggle_pomodoro(self):
        self.mode = "pomodoro"
        self.pomo_running = not self.pomo_running
        self.last_pomo_tick = time.time()
        self.trigger_bounce(6.0)
        self.sound.play_chirp("happy")
        status = "fortgesetzt" if self.pomo_running else "pausiert"
        self.show_bubble(f"🍅 Pomodoro {status}! ({self.pomo_remaining // 60} Min verbleibend)", 3.0)

    def reset_pomodoro(self):
        self.pomo_running = False
        self.pomo_phase = "work"
        self.pomo_duration = self.pomo_work_mins * 60
        self.pomo_remaining = self.pomo_duration
        self.show_bubble(f"🔄 Pomodoro auf {self.pomo_work_mins}:00 zurückgesetzt!", 3.0)
        self.update()

    def start_pomodoro_phase(self, phase: str = "work"):
        self.mode = "pomodoro"
        self.pomo_phase = phase
        if phase == "work":
            mins = self.pomo_work_mins
            desc = "Fokus-Zeit"
        elif phase == "short_break":
            mins = self.pomo_short_break_mins
            desc = "Kurze Pause"
        elif phase == "long_break":
            mins = self.pomo_long_break_mins
            desc = "Lange Pause"
        else:
            mins = self.pomo_work_mins
            desc = "Fokus-Zeit"
        self.pomo_duration = mins * 60
        self.pomo_remaining = self.pomo_duration
        self.pomo_running = True
        self.last_pomo_tick = time.time()
        self.trigger_bounce(6.5)
        self.sound.play_chirp("happy")
        self.show_bubble(f"⏱️ {desc} ({mins} Min) gestartet!", 3.5)

    def set_pomodoro_minutes(self, mins, phase="work"):
        self.mode = "pomodoro"
        self.pomo_phase = phase
        self.pomo_duration = mins * 60
        self.pomo_remaining = self.pomo_duration
        self.pomo_running = True
        self.last_pomo_tick = time.time()
        self.show_bubble(f"⏱️ Pomodoro ({mins} Min) gestartet!", 3.5)

    def prompt_pomodoro_work_dialog(self):
        val, ok = QInputDialog.getInt(
            self, "🍅 Pomodoro-Arbeitszeit", "Fokus-Zeit in Minuten:", self.pomo_work_mins, 5, 120, 5
        )
        if ok:
            self.pomo_work_mins = val
            if not self.pomo_running and self.pomo_phase == "work":
                self.pomo_duration = val * 60
                self.pomo_remaining = self.pomo_duration
            self.save_user_settings()
            self.show_bubble(f"🍅 Pomodoro-Arbeitszeit auf {val} Min. gesetzt!", 3.5)

    def prompt_pomodoro_breaks_dialog(self):
        val_s, ok_s = QInputDialog.getInt(
            self, "☕ Kurze Pause", "Dauer der kurzen Pause in Minuten:", self.pomo_short_break_mins, 1, 30, 1
        )
        if not ok_s:
            return
        val_l, ok_l = QInputDialog.getInt(
            self, "🛋️ Lange Pause", "Dauer der langen Pause in Minuten:", self.pomo_long_break_mins, 5, 60, 5
        )
        if not ok_l:
            return
        self.pomo_short_break_mins = val_s
        self.pomo_long_break_mins = val_l
        self.save_user_settings()
        self.show_bubble(f"☕ Pausen gesetzt: Kurz {val_s} Min, Lang {val_l} Min!", 4.0)

    def prompt_alarm_countdown_dialog(self):
        mins, ok = QInputDialog.getInt(
            self, "⏰ Schnell-Wecker / Timer", "In wie vielen Minuten soll der Wecker klingeln?", 10, 1, 360, 1
        )
        if ok:
            self.set_alarm_countdown(mins)

    def prompt_alarm_time_dialog(self):
        import re
        default_time = (datetime.now() + timedelta(minutes=30)).strftime("%H:%M")
        txt, ok = QInputDialog.getText(
            self, "⏰ Wecker auf feste Uhrzeit", "Gib die gewünschte Uhrzeit ein (HH:MM):", text=default_time
        )
        if ok and txt.strip():
            m = re.search(r"(\d{1,2})[:\.](\d{2})", txt.strip())
            if m:
                h = int(m.group(1))
                mi = int(m.group(2))
                if 0 <= h <= 23 and 0 <= mi <= 59:
                    self.set_alarm_at_time(h, mi)
                    return
            self.show_bubble("⚠️ Ungültiges Zeitformat! Bitte z. B. '14:30' eingeben.", 3.5)

    def set_alarm_countdown(self, mins: int, label: str = "Wecker"):
        self.alarm_time = time.time() + (mins * 60)
        self.alarm_label = label
        self.alarm_active = True
        self.alarm_ringing = False
        target_str = datetime.fromtimestamp(self.alarm_time).strftime("%H:%M")
        msg = f"⏰ Wecker auf {mins} Min. gestellt (klingelt um {target_str})!"
        self.show_bubble(msg, 5.0)
        self.sound.speak(f"Ich habe einen Wecker auf {mins} Minuten gestellt. Er klingelt um {target_str} Uhr.", "happy")
        self.set_mode("clock")

    def set_alarm_at_time(self, hour: int, minute: int, label: str = "Wecker"):
        now_dt = datetime.now()
        target_dt = now_dt.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target_dt <= now_dt:
            target_dt += timedelta(days=1)
        self.alarm_time = target_dt.timestamp()
        self.alarm_label = label
        self.alarm_active = True
        self.alarm_ringing = False
        diff_mins = max(1, int(round((self.alarm_time - time.time()) / 60.0)))
        time_str = f"{hour:02d}:{minute:02d}"
        msg = f"⏰ Wecker gestellt auf {time_str} Uhr (in ca. {diff_mins} Min.)!"
        self.show_bubble(msg, 5.0)
        self.sound.speak(f"Dein Wecker ist auf {time_str} Uhr gestellt.", "happy")
        self.set_mode("clock")

    def cancel_alarm(self):
        if self.alarm_active:
            self.alarm_active = False
            self.alarm_time = None
            self.alarm_ringing = False
            self.show_bubble("🛑 Wecker ausgeschaltet.", 3.0)
            self.sound.speak("Der Wecker wurde ausgeschaltet.", "neutral")
        else:
            self.show_bubble("Aktuell ist kein Wecker aktiv.", 3.0)

    def trigger_alarm_ring(self):
        self.alarm_ringing = True
        self.alarm_active = False
        lbl = self.alarm_label or "Wecker"
        self.trigger_bounce(12.0)
        for _ in range(8):
            self.spawn_particle("star")
        self.sound.play_chirp("alarm")
        msg = f"⏰🔔 Ring-Ring! Die Zeit ist um: {lbl}!"
        self.show_bubble(msg, 10.0)
        self.sound.speak(f"Achtung, die Zeit ist um! Dein Wecker für {lbl} klingelt!", "excited")

    def start_forced_dance(self, style: str = "dance", duration: float = 25.0):
        self.forced_dance_style = "headbang" if style == "headbang" else "groove"
        self.forced_dance_until = time.time() + duration
        self.is_dancing = True
        self.dance_style = self.forced_dance_style
        self.trigger_bounce(9.0)
        self.sound.play_chirp("excited" if self.dance_style == "headbang" else "happy")
        if self.dance_style == "headbang":
            self.show_bubble(f"🤘 Let's Rock! {self.bot_name} headbangt ab! ⚡", 4.0)
        else:
            self.show_bubble(f"🕺 Shake it! {self.bot_name} tanzt zum Beat! ✨", 4.0)

    def stop_forced_dance(self):
        self.forced_dance_until = 0.0
        self.is_dancing = False
        self.dance_style = "none"
        self.show_bubble("🛑 Tanzpause eingelegt!", 3.0)
        self.update()

    def mark_current_not_music(self):
        """Merkt sich den aktuellen Titel als 'Keine Musik' und stoppt sofort das Tanzen."""
        cur_title = getattr(self, "music_title", "").strip().lower()
        if cur_title:
            self.ignored_dance_titles.add(cur_title)
        self.stop_forced_dance()
        self.is_dancing = False
        self.dance_style = "none"
        self.trigger_bounce(5.0)
        self.sound.play_chirp("curious")
        self.show_bubble("🤫 Ups, verstanden! Das ist keine Musik – ich sitze brav still!", 4.5)
        self.sound.speak("Verstanden! Bei diesem Video sitze ich still.", "neutral")
        self.update()

    def is_playback_real_music(self) -> bool:
        """Prüft, ob die aktuelle Medienwiedergabe echte Musik ist und keine normalen Sprachvideos/Podcasts."""
        if getattr(self, "radio_playing", False):
            return True

        if not getattr(self, "music_playing", False):
            return False

        track_title = str(getattr(self, "music_title", "")).lower().strip()
        track_artist = str(getattr(self, "music_artist", "")).lower().strip()
        service = str(getattr(self, "music_service", "")).lower().strip()
        combined = f"{track_title} {track_artist}".strip()

        # 1. Wurde dieser Titel vom Nutzer explizit als 'Keine Musik' markiert?
        if track_title in self.ignored_dance_titles or combined in self.ignored_dance_titles:
            return False

        # 2. Reine Sprach- & Video-Schlüsselwörter ausschließen
        speech_keywords = (
            "podcast", "talk", "nachrichten", "news", "review", "tutorial",
            "let's play", "lets play", "gameplay", "doku", "dokumentation",
            "interview", "vlog", "guide", "erklärung", "stream", "reaction",
            "reaktion", "hörbuch", "audiobook", "lecture", "vortrag", "debatt",
            "comedy", "stand-up", "unboxing", "tagesschau", "folge", "episode",
            "video essay", "analyse", "kommentar", "erklärt", "vorstellung",
            "testbericht", "wissen", "reportage", "wetter"
        )
        if any(sk in combined for sk in speech_keywords):
            return False

        # 3. Dedizierte Musik-Player (Spotify, VLC, Clementine, Rhythmbox, Deezer, Tidal, Apple Music etc.)
        music_services = ("spotify", "clementine", "rhythmbox", "audacious", "vlc", "deezer", "tidal", "apple")
        if any(ms in service for ms in music_services):
            return True

        # 4. Wenn es aus dem Browser kommt (z.B. YouTube):
        # Nur tanzen, wenn es typische Musik-Merkmale hat oder Rock/Metal ist
        music_indicators = (
            "music", "musik", "song", "feat.", "ft.", "remix", "official video",
            "official audio", "lyric", "lyrics", "soundtrack", "ost", "theme",
            "beat", "cover", "album", "live in concert", "orchestra", "instrumental",
            "dj", "bass", "synth", "lofi", "chillhop", "rap", "hip hop", "pop"
        )
        rock_words = (
            "rock", "metal", "punk", "ac/dc", "acdc", "metallica", "rammstein",
            "maiden", "slipknot", "linkin", "nirvana", "foo fighters", "guitar",
            "heavy", "disturbed", "sabaton", "korn", "motörhead", "motorhead",
            "judas", "greenday", "green day", "sum 41", "system of a down", "soad"
        )
        if any(mi in combined for mi in music_indicators) or any(rw in combined for rw in rock_words):
            return True

        return False

    def set_scale(self, scale):
        self.scale_factor = scale
        self.resize(
            int(self.base_width * self.scale_factor),
            int(self.base_height * self.scale_factor),
        )
        self.layout_chat_ui()
        self.save_user_settings()
        self.update()

    def toggle_always_on_top(self):
        self.always_on_top = not self.always_on_top
        pos = self.pos()
        self.setup_window_flags()
        self.move(pos)
        self.show()
        self.ensure_kwin_keep_above_rule(self.always_on_top)
        state_txt = "aktiviert (Immer im Vordergrund)" if self.always_on_top else "deaktiviert"
        self.show_bubble(f"📌 Vordergrund-Modus: {state_txt}", 4.0)

    def ensure_kwin_keep_above_rule(self, keep_above: bool = True):
        if not sys.platform.startswith("linux") or not shutil.which("kwriteconfig6"):
            return
        if not os.environ.get("WAYLAND_DISPLAY") and not os.environ.get("DISPLAY"):
            return
        try:
            res = subprocess.run(
                ["kreadconfig6", "--file", "kwinrulesrc", "--group", "General", "--key", "rules"],
                capture_output=True, text=True, timeout=1.0
            )
            existing_rules = res.stdout.strip()
            rule_list = [r for r in existing_rules.split(",") if r]
            if "deskimoni-rule" not in rule_list:
                rule_list.append("deskimoni-rule")
                subprocess.run(
                    ["kwriteconfig6", "--file", "kwinrulesrc", "--group", "General", "--key", "rules", ",".join(rule_list)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1.0
                )
                subprocess.run(
                    ["kwriteconfig6", "--file", "kwinrulesrc", "--group", "General", "--key", "count", str(len(rule_list))],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1.0
                )

            for key, val in [
                ("Description", "Deskimoni Immer im Vordergrund"),
                ("title", "Deskimoni"),
                ("titlematch", "1"),
                ("above", "true" if keep_above else "false"),
                ("aboverule", "2" if keep_above else "0"),
                ("minimizerule", "2"),
                ("minimize", "false"),
                ("skiptaskbar", "true"),
                ("skiptaskbarrule", "2"),
                ("skippager", "true"),
                ("skippagerrule", "2"),
            ]:
                subprocess.run(
                    ["kwriteconfig6", "--file", "kwinrulesrc", "--group", "deskimoni-rule", "--key", key, val],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1.0
                )

            subprocess.run(
                ["qdbus-qt6", "org.kde.KWin", "/KWin", "reconfigure"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1.0
            )
        except Exception:
            pass

    def trigger_bounce(self, strength=7.0):
        self.bounce_velocity = -strength

    def trigger_love_burst(self):
        self.current_emotion = "love"
        self.emotion_until = time.time() + 4.0
        self.trigger_bounce(9.0)
        self.sound.play_chirp("love")
        for _ in range(6):
            self.spawn_particle("heart")

    def spawn_particle(self, p_type="heart"):
        self.particles.append(
            {
                "type": p_type,
                "x": random.uniform(60, 180),
                "y": random.uniform(45, 95),
                "vx": random.uniform(-0.8, 0.8),
                "vy": random.uniform(-2.0, -0.9),
                "life": 1.0,
                "size": random.uniform(12, 20),
            }
        )

    # ==========================================
    # --- 60 FPS Animations-Schleife ---
    # ==========================================
    def update_animation(self):
        now = time.time()
        self.tick_count += 1
        self.breath_phase += 0.05

        # Tanz- & Headbang-Erkennung (nur bei echter Musik oder Web-Radio, nicht bei normalen Sprachvideos!)
        real_music_active = self.is_playback_real_music()
        forced_active = now < self.forced_dance_until

        is_dancing = False
        current_style = "none"

        if forced_active:
            is_dancing = True
            current_style = self.forced_dance_style
        elif getattr(self, "dance_enabled", True) and real_music_active:
            is_dancing = True
            is_rock = False
            if self.radio_playing and self.radio_stations:
                st_name = self.radio_stations[self.active_radio_idx % len(self.radio_stations)].get("name", "").lower()
                if any(w in st_name for w in ("rock", "def con", "metal", "punk")):
                    is_rock = True
            if getattr(self, "music_playing", False):
                track_info = f"{getattr(self, 'music_title', '')} {getattr(self, 'music_artist', '')}".lower()
                rock_words = (
                    "rock", "metal", "punk", "ac/dc", "acdc", "metallica", "rammstein",
                    "maiden", "slipknot", "linkin", "nirvana", "foo fighters", "guitar",
                    "heavy", "disturbed", "sabaton", "korn", "motörhead", "motorhead",
                    "judas", "greenday", "green day", "sum 41", "system of a down", "soad"
                )
                if any(rw in track_info for rw in rock_words):
                    is_rock = True

            current_style = "headbang" if is_rock else "groove"

        self.is_dancing = is_dancing
        self.dance_style = current_style

        if is_dancing:
            if current_style == "headbang":
                self.dance_phase += 0.28
                if random.random() < 0.045:
                    self.spawn_particle(random.choice(["star", "note"]))
            else:
                self.dance_phase += 0.13
                if random.random() < 0.035:
                    self.spawn_particle("note")

        # Feder-Physik
        self.bounce_offset += self.bounce_velocity
        self.bounce_velocity += 0.65
        if self.bounce_offset > 0:
            self.bounce_offset = 0
            self.bounce_velocity *= -0.35
            if abs(self.bounce_velocity) < 0.5:
                self.bounce_velocity = 0.0

        # Globale Mausposition abrufen (Plattformunabhängig via GlobalCursorTracker!)
        global_cursor = self.cursor_tracker.get_pos()
        cursor_moved_dist = math.hypot(
            global_cursor.x() - self.last_global_cursor_pos.x(),
            global_cursor.y() - self.last_global_cursor_pos.y(),
        )
        if self.cursor_shaker.is_shaking() or now < self.cursor_shake_ignore_until:
            self.last_global_cursor_pos = global_cursor
        elif cursor_moved_dist > 8.0:
            self.last_global_cursor_pos = global_cursor
            self.last_cursor_move_time = now
            if self.cursor_search_state in ("seeking", "found") and (now - self.cursor_search_started_at) > 1.2:
                self.cursor_search_state = "idle"
                self.sound.play_chirp("happy")
                self.trigger_bounce(6.0)
                self.show_bubble("🎉 Da bist du ja wieder! Mauszeiger erfolgreich gefunden!", 3.5)
        elif (
            self.cursor_finder_enabled
            and self.cursor_search_state == "idle"
            and (now - self.last_cursor_move_time) >= self.cursor_idle_timeout
        ):
            self.start_cursor_search_now()

        if self.cursor_search_state in ("seeking", "found") and (now - self.cursor_search_started_at) > 4.5:
            self.cursor_search_state = "idle"

        if self.is_dragging_pet and not (QApplication.mouseButtons() & Qt.MouseButton.LeftButton):
            self.is_dragging_pet = False
            self.save_user_settings()
            self._check_multimonitor_dropped()

        # Spazieren & Watscheln
        if (self.roaming_enabled or self.has_manual_walk_target) and not self.is_dragging_pet:
            cur_screen = self.get_current_screen()
            primary_screen = QApplication.primaryScreen()

            if self.is_walking_home and primary_screen is not None:
                p_geom = primary_screen.availableGeometry()
                center_pt = self.geometry().center()
                if p_geom.contains(center_pt):
                    self.is_walking_home = False
                    self.has_manual_walk_target = False
                    self.win_target_x = None
                    self.win_target_y = None
                    self._walk_float_x = None
                    self._walk_float_y = None
                    self.sound.stop_gohome_music()
                    self.trigger_arrived_home_reaction()

            if self.roaming_enabled and not self.has_manual_walk_target and not self.is_walking_home and now >= self.next_walk_decision:
                if random.random() < 0.65 and cur_screen is not None:
                    geom = cur_screen.availableGeometry()
                    tx = self.x() + random.randint(-140, 140)
                    ty = self.y() + random.randint(-60, 60)
                    self.win_target_x = max(geom.left() + 25, min(geom.right() - self.width() - 25, tx))
                    self.win_target_y = max(geom.top() + 25, min(geom.bottom() - self.height() - 25, ty))
                    self.walk_target_x = random.uniform(-10.0, 10.0)
                    self.walk_target_y = random.uniform(-4.0, 4.0)
                    self.next_walk_decision = now + random.uniform(7.0, 14.0)
                else:
                    self.win_target_x = None
                    self.win_target_y = None
                    self.walk_target_x = 0.0
                    self.walk_target_y = 0.0
                    self.next_walk_decision = now + random.uniform(5.0, 10.0)

            dx_w = self.walk_target_x - self.walk_offset_x
            dy_w = self.walk_target_y - self.walk_offset_y
            dist_w = math.hypot(dx_w, dy_w)
            if dist_w > 0.8:
                self.walk_offset_x += (dx_w / dist_w) * min(dist_w, 0.45)
                self.walk_offset_y += (dy_w / dist_w) * min(dist_w, 0.35)
                self.layout_chat_ui()

            if self.win_target_x is not None and self.win_target_y is not None:
                dx_win = self.win_target_x - self.x()
                dy_win = self.win_target_y - self.y()
                dist_win = math.hypot(dx_win, dy_win)
                if dist_win > 3.0:
                    self.is_stepping = True
                    if not hasattr(self, "_walk_float_x") or self._walk_float_x is None:
                        self._walk_float_x = float(self.x())
                        self._walk_float_y = float(self.y())

                    if self.is_walking_home:
                        win_speed = 0.85
                        self.walk_phase += 0.13
                    elif self.has_manual_walk_target:
                        win_speed = 2.5
                        self.walk_phase += 0.22
                    else:
                        win_speed = 1.15
                        self.walk_phase += 0.18

                    step_x = (dx_win / dist_win) * min(dist_win, win_speed)
                    step_y = (dy_win / dist_win) * min(dist_win, win_speed)
                    self._walk_float_x += step_x
                    self._walk_float_y += step_y
                    self.move(int(round(self._walk_float_x)), int(round(self._walk_float_y)))
                    self.target_look_x = (dx_win / dist_win) * 8.0
                else:
                    self.is_stepping = False
                    self.has_manual_walk_target = False
                    self.win_target_x = None
                    self.win_target_y = None
                    self._walk_float_x = None
                    self._walk_float_y = None
                    if self.is_walking_home:
                        self.is_walking_home = False
                        self.sound.stop_gohome_music()
                        self.trigger_arrived_home_reaction()
            else:
                self.is_stepping = False
                self.has_manual_walk_target = False
                self._walk_float_x = None
                self._walk_float_y = None
        else:
            self.is_stepping = False

        # Blinzeln
        if not self.is_blinking and now >= self.next_blink_time:
            self.is_blinking = True
        if self.is_blinking:
            self.blink_state += 0.28
            if self.blink_state >= 1.5:
                self.blink_state = 0.0
                self.is_blinking = False
                self.next_blink_time = now + random.uniform(2.2, 5.5)

        # Augen-Fokus (Folgt dem Cursor in Echtzeit über alle Monitore)
        if self.is_stepping and self.win_target_x is not None:
            pass
        elif (now - self.last_cursor_move_time) < 1.8:
            center_global_x = self.x() + (self.body_offset_x + self.walk_offset_x + 120.0) * self.scale_factor
            center_global_y = self.y() + (self.body_offset_y + self.walk_offset_y + 126.0) * self.scale_factor
            dx_g = global_cursor.x() - center_global_x
            dy_g = global_cursor.y() - center_global_y
            dist_g = math.hypot(dx_g, dy_g)

            if dist_g > 15.0:
                norm_factor = max(180.0, min(700.0, dist_g * 0.45))
                self.target_look_x = max(-1.0, min(1.0, dx_g / norm_factor)) * 11.0
                self.target_look_y = max(-1.0, min(1.0, dy_g / norm_factor)) * 8.0
            else:
                self.target_look_x = 0.0
                self.target_look_y = 0.0
        else:
            if now - self.last_random_look > 3.0:
                self.last_random_look = now
                if random.random() < 0.60:
                    self.target_look_x = 0.0
                    self.target_look_y = 0.0
                else:
                    self.target_look_x = random.uniform(-6.0, 6.0)
                    self.target_look_y = random.uniform(-3.5, 3.5)

        self.look_x += (self.target_look_x - self.look_x) * 0.14
        self.look_y += (self.target_look_y - self.look_y) * 0.14

        self.pet_score = max(0.0, self.pet_score - 0.35)

        # Periodische Systemprüfungen (alle 2.5 Sekunden)
        if now - self.last_sys_check > 2.5:
            self.last_sys_check = now
            self.cpu_percent = psutil.cpu_percent(interval=None)
            self.ram_percent = psutil.virtual_memory().percent
            try:
                temps = psutil.sensors_temperatures()
                for name in ("k10temp", "coretemp", "acpitz", "amdgpu"):
                    if name in temps and temps[name]:
                        self.cpu_temp = temps[name][0].current
                        break
            except Exception:
                pass
            self.update_mpris_metadata()

        # Wenn er tanzt, steigen ab und zu Musiknoten auf!
        if getattr(self, "is_dancing", False) and random.random() < 0.035:
            self.spawn_particle("note")

        if self.radio_proc and self.radio_proc.poll() is not None:
            self.radio_playing = False
            self.radio_proc = None

        if now - self.last_weather_check > 1200:
            self.fetch_weather_async(speak_when_done=False)

        if now - self.last_news_fetch > 1500:
            self.fetch_news_async(speak_when_done=False)

        if self.news_auto_speak and (now - self.last_news_broadcast) > (self.news_interval_mins * 60):
            self.last_news_broadcast = now
            self.broadcast_latest_news()

        if self.water_reminder_enabled and (now - self.last_water_reminder) > (self.water_reminder_mins * 60):
            self.last_water_reminder = now
            self.trigger_water_reminder()

        if self.move_reminder_enabled and (now - self.last_move_reminder) > (self.move_reminder_mins * 60):
            self.last_move_reminder = now
            self.trigger_move_reminder()

        if (
            self.chatter_enabled
            and (now >= self.next_chatter_time)
            and not self.is_speaking
            and not self.is_thinking
            and not self.pomo_running
            and not self.is_dragging_pet
        ):
            self.trigger_random_chatter()
            jitter = random.uniform(0.75, 1.25)
            self.next_chatter_time = now + (self.chatter_interval_mins * 60 * jitter)

        # Arbeitszeit-Prüfung (§ 4 ArbZG Pausen & Feierabend)
        self.check_worktime_alerts(now)

        if self.alarm_active and self.alarm_time and now >= self.alarm_time:
            self.trigger_alarm_ring()

        if self.pomo_running:
            elapsed = now - self.last_pomo_tick
            if elapsed >= 1.0:
                self.pomo_remaining = max(0, self.pomo_remaining - int(elapsed))
                self.last_pomo_tick = now
                if self.pomo_remaining == 0:
                    self.pomo_running = False
                    self.trigger_love_burst()
                    if self.pomo_phase == "work":
                        msg = f"🍅 Pomodoro geschafft ({self.pomo_work_mins} Min Fokus)! Zeit für eine Pause!"
                        voice_msg = f"Super Fokus! Deine {self.pomo_work_mins} Minuten Arbeitszeit sind geschafft. Zeit für eine Pause!"
                        self.pomo_phase = "short_break"
                        self.pomo_duration = self.pomo_short_break_mins * 60
                        self.pomo_remaining = self.pomo_duration
                    else:
                        msg = "☕ Pause beendet! Bereit für den nächsten Fokus-Block?"
                        voice_msg = "Deine Pause ist vorbei. Auf geht's in die nächste produktive Runde!"
                        self.pomo_phase = "work"
                        self.pomo_duration = self.pomo_work_mins * 60
                        self.pomo_remaining = self.pomo_duration
                    self.show_bubble(msg, 9.0)
                    if self.pomo_sound_enabled:
                        self.sound.speak(voice_msg, "love")

        if self.forced_emotion != "auto":
            self.current_emotion = self.forced_emotion
        elif now < self.emotion_until:
            pass
        else:
            hour = datetime.now().hour
            if hour >= 23 or hour < 6:
                self.current_emotion = "sleepy"
                if random.random() < 0.02:
                    self.spawn_particle("zzz")
            elif self.cpu_percent > 85.0:
                self.current_emotion = "dizzy"
            else:
                self.current_emotion = "normal"

        alive_particles = []
        for p in self.particles:
            p["x"] += p["vx"]
            p["y"] += p["vy"]
            p["life"] -= 0.022
            if p["life"] > 0:
                alive_particles.append(p)
        self.particles = alive_particles

        self.update()

    # ==========================================
    # --- Maus- & Touch-Ereignisse ---
    # ==========================================
    def enterEvent(self, event):
        super().enterEvent(event)
        # Sofortige Kalibrierung bei Maus-Berührung (Linux Wayland & Multi-Monitor)
        pos = QCursor.pos()
        self.cursor_tracker.calibrate(pos)
        self.last_global_cursor_pos = pos
        self.last_cursor_move_time = time.time()

    def mousePressEvent(self, event):
        self.cursor_tracker.calibrate(event.globalPosition().toPoint())
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position()
            bx = pos.x() / self.scale_factor - (self.body_offset_x + self.walk_offset_x)
            by = pos.y() / self.scale_factor - (self.body_offset_y + self.walk_offset_y)

            # Kleiner orangener Action-Button am Bauch
            btn_rect = QRectF(92, 206, 56, 24)
            if btn_rect.contains(QPointF(bx, by)):
                self.belly_click_timer.start(230)
                return

            # Display-Klick-Aktionen
            screen_rect = QRectF(52, 72, 136, 122)
            if screen_rect.contains(QPointF(bx, by)):
                if self.mode == "work":
                    self.toggle_work_pause()
                    return
                elif self.mode == "pomodoro":
                    self.toggle_pomodoro()
                    return
                elif self.mode == "music":
                    if bx < 92:
                        self.mpris_command("Previous")
                    elif bx > 148:
                        self.mpris_command("Next")
                    else:
                        self.mpris_command("PlayPause")
                    self.trigger_bounce(5.0)
                    QTimer.singleShot(300, self.update_mpris_metadata)
                    return
                elif self.mode == "news":
                    if bx < 92:
                        self.prev_news_item()
                    elif bx > 148:
                        self.next_news_item()
                    else:
                        self.speak_current_news()
                    self.trigger_bounce(5.0)
                    return
                elif self.mode == "radio":
                    if bx < 92:
                        self.prev_radio_station()
                    elif bx > 148:
                        self.next_radio_station()
                    else:
                        self.toggle_radio()
                    self.trigger_bounce(5.0)
                    return
                elif self.mode == "weather":
                    self.fetch_weather_async(speak_when_done=True)
                    return
                elif self.mode == "linux":
                    self.show_linux_tip()
                    return

            self.trigger_bounce(6.5)
            self.sound.play_chirp("happy")
            if self.current_emotion != "dizzy":
                self.current_emotion = random.choice(["happy", "excited"])
                self.emotion_until = time.time() + 2.2
                self.spawn_particle("star")

            self.sound.stop_kwai_whistle()
            self.is_dragging_pet = True
            self.is_walking_home = False
            self._walk_float_x = None
            self._walk_float_y = None
            self.drag_offset = event.globalPosition() - QPointF(self.pos())
            win = self.windowHandle()
            if win is not None:
                win.startSystemMove()

        elif event.button() == Qt.MouseButton.RightButton:
            menu = self.build_context_menu()
            menu.exec(event.globalPosition().toPoint())

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.is_dragging_pet:
                self.is_dragging_pet = False
                self.save_user_settings()
                self._check_multimonitor_dropped()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position()
            bx = pos.x() / self.scale_factor - (self.body_offset_x + self.walk_offset_x)
            by = pos.y() / self.scale_factor - (self.body_offset_y + self.walk_offset_y)
            btn_rect = QRectF(92, 206, 56, 24)
            if btn_rect.contains(QPointF(bx, by)):
                self.belly_click_timer.stop()
                self.toggle_controls_visibility()
                return
            self.trigger_love_burst()

    def mouseMoveEvent(self, event):
        self.cursor_tracker.calibrate(event.globalPosition().toPoint())
        if self.is_dragging_pet and (event.buttons() & Qt.MouseButton.LeftButton):
            new_pos = event.globalPosition() - self.drag_offset
            self.move(int(new_pos.x()), int(new_pos.y()))
            return

        pos = event.position()
        now = time.time()
        bx = pos.x() / self.scale_factor - (self.body_offset_x + self.walk_offset_x)
        by = pos.y() / self.scale_factor - (self.body_offset_y + self.walk_offset_y)

        # Kopf-Region zum Streicheln
        head_rect = QRectF(45, 15, 150, 68)
        if self.last_mouse_pos is not None:
            move_dist = math.hypot(
                pos.x() - self.last_mouse_pos.x(), pos.y() - self.last_mouse_pos.y()
            )
            if head_rect.contains(QPointF(bx, by)) and move_dist > 2.0:
                self.pet_score += move_dist * 0.45
                if self.pet_score > 38.0:
                    if self.current_emotion != "love":
                        self.sound.play_chirp("love")
                    self.current_emotion = "love"
                    self.emotion_until = now + 3.0
                    if random.random() < 0.25:
                        self.spawn_particle("heart")

            self.drag_history.append((now, pos.x()))
            self.drag_history = [(t, x) for t, x in self.drag_history if now - t < 0.6]
            if len(self.drag_history) > 12:
                xs = [x for _, x in self.drag_history]
                if max(xs) - min(xs) > 130 * self.scale_factor:
                    if self.current_emotion != "dizzy":
                        self.sound.play_chirp("dizzy")
                    self.current_emotion = "dizzy"
                    self.emotion_until = now + 3.0
                    self.drag_history.clear()

        self.last_mouse_pos = pos

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        mode_ids = [m[0] for m in self.MODES]
        idx = mode_ids.index(self.mode)
        if delta > 0:
            idx = (idx - 1) % len(mode_ids)
        else:
            idx = (idx + 1) % len(mode_ids)
        self.set_mode(mode_ids[idx])
