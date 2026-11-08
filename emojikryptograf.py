#!/usr/bin/env python3
"""
Emoji-Kryptograf & Dolmetscher (Emoji101 Desktop Companion) 🔮✨
Verwandelt Sätze in kreative Emoji-Ketten (Text ➔ Emoji)
und entschlüsselt geheime Chat-Bedeutungen & Doppeldeutigkeiten (Emoji ➔ Text)!
"""

import os
import sys
import time
import json
import random
import threading
from datetime import datetime

import requests

from deskimoni_core.qt import (
    Qt, QTimer, QPoint, QPointF, QRectF, QSize,
    QColor, QFont, QPainter, QPainterPath, QCursor, QIcon, QPen, QBrush,
    QLinearGradient, QAction, QActionGroup, QWidget, QApplication, QLineEdit,
    QPushButton, QMenu, QInputDialog, QMessageBox
)
from deskimoni_core.audio.sound_engine import RobotSoundEngine
from deskimoni_core.signals import WorkerSignals


EMOJI_CATEGORIES = [
    {
        "id": "slang",
        "name": "🔥 Slang",
        "items": ["🍆", "🍑", "💦", "🐱", "🌮", "🍯", "💨", "🍒", "👅", "🍭", "🥦", "🍃", "🌽", "🌶️", "🧢", "🗿", "💀", "🤡", "👀", "💅", "🐍", "🫵", "🫂", "🎭", "⌛", "🧎"]
    },
    {
        "id": "smileys",
        "name": "😀 Smileys",
        "items": ["😀", "😂", "🤣", "🥹", "😍", "🤩", "😎", "🥳", "🤔", "🫡", "🤫", "🫠", "🙃", "😏", "🙄", "😬", "😮‍💨", "😴", "🤯", "🥵", "🥶", "🥴", "😭", "😱", "😈", "💩", "🤖"]
    },
    {
        "id": "hands",
        "name": "🤌 Hände",
        "items": ["👋", "👌", "🤌", "🤏", "✌️", "🤞", "🫰", "🤟", "🤘", "🤙", "👈", "👉", "👆", "👇", "🖕", "🙏", "🤝", "👍", "👎", "👊", "👏", "🙌", "💪"]
    },
    {
        "id": "hearts",
        "name": "❤️ Herzen",
        "items": ["❤️", "🧡", "💛", "💚", "💙", "💜", "🖤", "🤍", "🤎", "💔", "❤️‍🔥", "❤️‍🩹", "❣️", "💕", "💞", "💓", "💗", "💖", "💘", "✨"]
    },
    {
        "id": "symbols",
        "name": "⚡ Chat",
        "items": ["✨", "🔥", "💥", "⚡", "💤", "💯", "💢", "🔞", "🆘", "❌", "✅", "⚠️", "🚫", "🧿", "🚩", "🎮", "🎰", "🎲"]
    },
    {
        "id": "food",
        "name": "☕ Food",
        "items": ["☕", "🍺", "🍻", "🥂", "🍷", "🍕", "🍔", "🍟", "🌮", "🍿", "🍩", "🍦", "🍰", "🍫", "🧋", "🍾", "🎉", "🎁"]
    }
]

TRANSLATION_STYLES = [
    {"id": "genz", "name": "🔥 Gen-Z & TikTok Slang", "desc": "Mit modernem Internet-Slang und ironischen Symbolen (💀, 🧢, 😭, 💅, 🗿)."},
    {"id": "precise", "name": "🎯 Präzise & Treffend", "desc": "Klare, elegante 1:1 Übersetzung des Inhalts in ausdrucksstarke Emojis."},
    {"id": "story", "name": "🍿 Mini-Bildergeschichte", "desc": "Erzählt den Ablauf wie einen kleinen Comic-Strip in 4 bis 7 Bildern."},
    {"id": "cryptic", "name": "🤫 Kryptischer Geheimcode", "desc": "Clever verschlüsselt wie ein Rätsel für Eingeweihte."}
]


class EmojiKryptografWidget(QWidget):
    def __init__(self):
        super().__init__()

        self.scale_factor = 1.0
        self.base_width = 380
        self.base_height = 430

        # Modus: "ENCODE" (Text ➔ Emoji) oder "DECODE" (Emoji ➔ Text)
        self.mode = "ENCODE"
        self.active_style = "genz"
        self.active_category_idx = 0

        # Sound & Sprache
        self.signals = WorkerSignals()
        self.sound = RobotSoundEngine(self.signals)
        self.sound.set_voice_profile("cute_bot")

        # Status & Animation
        self.bounce_offset = 0.0
        self.bounce_velocity = 0.0
        self.is_thinking = False
        self.is_dragging = False
        self.drag_offset = QPointF(0, 0)
        self.glow_phase = 0.0

        # Text & Blase
        self.bubble_title = "🔮 Emoji-Kryptograf"
        self.bubble_text = "Hau einen Satz rein – ich verwandle ihn in Emojis! ✨"
        self.last_emojis = ""
        self.bubble_until = time.time() + 15.0

        # API-Key aus Deskimoni-Konfiguration laden
        self.gemini_api_key = self.load_gemini_key()

        self.setup_ui()

        # 60 FPS Render & Animation Timer
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self.update_animation)
        self.anim_timer.start(16)

        # Start-Begrüßung
        QTimer.singleShot(600, lambda: self.sound.play_chirp("happy"))

    def load_gemini_key(self) -> str:
        key = os.environ.get("GEMINI_API_KEY", "").strip()
        if key:
            return key
        config_path = os.path.expanduser("~/.config/deskimoni/settings.json")
        try:
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("gemini_api_key", "").strip()
        except Exception:
            pass
        return ""

    def save_gemini_key(self, key: str):
        self.gemini_api_key = key.strip()
        config_path = os.path.expanduser("~/.config/deskimoni/settings.json")
        try:
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            data = {}
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            data["gemini_api_key"] = self.gemini_api_key
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[EmojiKryptograf] Fehler beim Speichern des API-Keys: {e}")

    def setup_ui(self):
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.resize(self.base_width, self.base_height)
        self.setWindowTitle("Emoji-Kryptograf & Dolmetscher 🔮")

        # Modus-Umschalt Button (Text ➔ Emoji vs. Emoji ➔ Text)
        self.mode_btn = QPushButton(self)
        self.mode_btn.clicked.connect(self.toggle_mode)
        self.mode_btn.setStyleSheet(
            """
            QPushButton {
                background-color: rgba(30, 41, 59, 235);
                color: #38bdf8;
                border: 1.5px solid #38bdf8;
                border-radius: 12px;
                font-size: 11px;
                font-weight: bold;
                padding: 4px 8px;
            }
            QPushButton:hover {
                background-color: rgba(56, 189, 248, 0.2);
                border-color: #7dd3fc;
                color: #ffffff;
            }
            """
        )

        # Kopieren Button (kopiert die zuletzt generierten Emojis)
        self.copy_btn = QPushButton("📋 Kopieren", self)
        self.copy_btn.clicked.connect(self.copy_last_emojis)
        self.copy_btn.setStyleSheet(
            """
            QPushButton {
                background-color: rgba(30, 41, 59, 210);
                color: #cbd5e1;
                border: 1px solid #475569;
                border-radius: 10px;
                font-size: 10px;
                padding: 3px 6px;
            }
            QPushButton:hover {
                background-color: rgba(51, 65, 85, 240);
                color: #f8fafc;
                border-color: #94a3b8;
            }
            """
        )

        # Emoji-Kategorie Pills (Schnell-Auswahl)
        self.cat_buttons = []
        for idx, cat in enumerate(EMOJI_CATEGORIES):
            btn = QPushButton(cat["name"], self)
            btn.clicked.connect(lambda checked, i=idx: self.switch_category(i))
            self.cat_buttons.append(btn)

        # Schnellauswahl Emoji Buttons (horizontales Band mit 9 beliebten Emojis der aktiven Kategorie)
        self.emoji_pick_btns = []
        for i in range(8):
            ebtn = QPushButton(self)
            ebtn.clicked.connect(lambda checked, idx=i: self.on_emoji_clicked(idx))
            ebtn.setStyleSheet(
                """
                QPushButton {
                    background-color: rgba(15, 23, 42, 220);
                    border: 1px solid rgba(51, 65, 85, 0.7);
                    border-radius: 8px;
                    font-size: 16px;
                    padding: 0px;
                }
                QPushButton:hover {
                    background-color: rgba(30, 58, 138, 0.6);
                    border-color: #38bdf8;
                    transform: scale(1.1);
                }
                """
            )
            self.emoji_pick_btns.append(ebtn)

        # Eingabefeld unten
        self.input_field = QLineEdit(self)
        self.input_field.returnPressed.connect(self.on_submit)
        self.input_field.setStyleSheet(
            """
            QLineEdit {
                background-color: rgba(15, 23, 42, 245);
                color: #f8fafc;
                border: 1.5px solid #38bdf8;
                border-radius: 14px;
                padding: 6px 12px;
                font-size: 12px;
            }
            QLineEdit:focus {
                border-color: #818cf8;
                background-color: rgba(15, 23, 42, 255);
            }
            """
        )

        # Clear Button
        self.clear_btn = QPushButton("✖", self)
        self.clear_btn.clicked.connect(self.input_field.clear)
        self.clear_btn.setStyleSheet(
            """
            QPushButton {
                background: transparent;
                color: #64748b;
                border: none;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                color: #f43f5e;
            }
            """
        )

        # Senden Button
        self.submit_btn = QPushButton("🚀", self)
        self.submit_btn.clicked.connect(self.on_submit)
        self.submit_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #2563eb;
                color: #ffffff;
                border: none;
                border-radius: 14px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #3b82f6;
            }
            QPushButton:pressed {
                background-color: #1d4ed8;
            }
            """
        )

        self.update_mode_ui()
        self.update_category_ui()
        self.layout_ui()

    def update_mode_ui(self):
        if self.mode == "ENCODE":
            self.mode_btn.setText("🔀 Satz ➔ Emojis (Kryptograf)")
            self.input_field.setPlaceholderText("Satz eingeben (z.B. 'Ich brauche Urlaub')...")
        else:
            self.mode_btn.setText("🔍 Emojis ➔ Bedeutung (Dolmetscher)")
            self.input_field.setPlaceholderText("Emojis wählen oder tippen (z.B. 🍑🍆👀)...")

    def update_category_ui(self):
        for idx, btn in enumerate(self.cat_buttons):
            if idx == self.active_category_idx:
                btn.setStyleSheet(
                    """
                    QPushButton {
                        background-color: #2563eb;
                        color: #ffffff;
                        border: 1px solid #38bdf8;
                        border-radius: 8px;
                        font-size: 10px;
                        font-weight: bold;
                        padding: 2px 6px;
                    }
                    """
                )
            else:
                btn.setStyleSheet(
                    """
                    QPushButton {
                        background-color: rgba(30, 41, 59, 180);
                        color: #94a3b8;
                        border: 1px solid #334155;
                        border-radius: 8px;
                        font-size: 10px;
                        padding: 2px 6px;
                    }
                    QPushButton:hover {
                        background-color: rgba(51, 65, 85, 230);
                        color: #f1f5f9;
                    }
                    """
                )

        cat = EMOJI_CATEGORIES[self.active_category_idx]
        items = cat["items"]
        for i, ebtn in enumerate(self.emoji_pick_btns):
            if i < len(items):
                ebtn.setText(items[i])
                ebtn.setVisible(True)
            else:
                ebtn.setVisible(False)

    def switch_category(self, idx: int):
        self.active_category_idx = idx % len(EMOJI_CATEGORIES)
        self.update_category_ui()
        self.sound.play_chirp("curious")

    def on_emoji_clicked(self, idx: int):
        cat = EMOJI_CATEGORIES[self.active_category_idx]
        if idx < len(cat["items"]):
            emoji = cat["items"][idx]
            current = self.input_field.text()
            self.input_field.setText(current + emoji)
            self.trigger_bounce(4.0)
            self.sound.play_chirp("happy")

    def toggle_mode(self):
        self.mode = "DECODE" if self.mode == "ENCODE" else "ENCODE"
        self.update_mode_ui()
        self.trigger_bounce(6.0)
        self.sound.play_chirp("curious")
        if self.mode == "ENCODE":
            self.show_bubble("Modus gewechselt:\nSatz ➔ Emoji-Kryptograf 🔮", 4.0, "🔮 Kryptograf")
        else:
            self.show_bubble("Modus gewechselt:\nEmojis ➔ Bedeutung Dolmetschen 🔍", 4.0, "🔍 Dolmetscher")

    def copy_last_emojis(self):
        text_to_copy = self.last_emojis or self.input_field.text()
        if text_to_copy:
            clipboard = QApplication.clipboard()
            if clipboard:
                clipboard.setText(text_to_copy)
            self.trigger_bounce(5.0)
            self.sound.play_chirp("love")
            self.show_bubble(f"In Zwischenablage kopiert! ✨\n{text_to_copy}", 3.5, "📋 Kopiert!")
        else:
            self.show_bubble("Noch keine Emojis zum Kopieren vorhanden!", 3.0, "⚠️ Hinweis")

    def layout_ui(self):
        w = self.width()
        h = self.height()

        # Obere Steuerzeile: Modus-Umschalter links, Kopieren rechts
        self.mode_btn.setGeometry(16, 12, int(w * 0.64), 28)
        self.copy_btn.setGeometry(int(w * 0.64) + 24, 12, int(w * 0.28), 28)

        # Kategorie-Tabs (unterhalb der Blase, y ~ 285)
        cat_y = h - 116
        tab_w = int((w - 32) / len(self.cat_buttons))
        for i, btn in enumerate(self.cat_buttons):
            btn.setGeometry(16 + i * tab_w, cat_y, tab_w - 3, 22)

        # Schnellauswahl Emoji Buttons (y ~ 315)
        pick_y = h - 86
        btn_w = int((w - 32) / len(self.emoji_pick_btns))
        for i, ebtn in enumerate(self.emoji_pick_btns):
            ebtn.setGeometry(16 + i * btn_w, pick_y, btn_w - 4, 30)

        # Unterste Zeile: Eingabefeld, Clear, Senden (y ~ 355)
        input_y = h - 48
        submit_w = 40
        self.input_field.setGeometry(16, input_y, w - 32 - submit_w - 8, 36)
        self.clear_btn.setGeometry(w - 32 - submit_w - 32, input_y + 4, 28, 28)
        self.submit_btn.setGeometry(w - 16 - submit_w, input_y, submit_w, 36)

    def trigger_bounce(self, strength: float = 6.0):
        self.bounce_velocity = -strength

    def show_bubble(self, text: str, duration: float = 8.0, title: str = "🔮 Emoji-Kryptograf"):
        self.bubble_title = title
        self.bubble_text = text
        self.bubble_until = time.time() + duration
        self.update()

    def on_submit(self):
        text = self.input_field.text().strip()
        if not text or self.is_thinking:
            return
        self.is_thinking = True
        self.trigger_bounce(6.0)
        self.sound.play_chirp("curious")

        if self.mode == "ENCODE":
            self.show_bubble("Verschlüssele Satz in Emoji-Kette... 🔮✨", 10.0, "🔮 Kryptograf")
        else:
            self.show_bubble("Analysiere geheime Chat-Bedeutung... 🔍🧐", 10.0, "🔍 Dolmetscher")

        threading.Thread(target=self._worker, args=(text, self.mode), daemon=True).start()

    def _worker(self, user_text: str, current_mode: str):
        style = next((s for s in TRANSLATION_STYLES if s["id"] == self.active_style), TRANSLATION_STYLES[0])

        if current_mode == "ENCODE":
            # Text ➔ Emoji
            system_prompt = (
                f"Du bist der geniale 'Emoji-Kryptograf'.\n"
                f"Auftrag: Übersetze den folgenden Text/Gedanken in eine ausdrucksstarke, treffende Kette von Emojis.\n"
                f"STIL: {style['name']} ({style['desc']})\n\n"
                f"REGELN:\n"
                f"1. Gib als erste Zeile NUR die Emoji-Kette aus (3 bis 8 Emojis).\n"
                f"2. Gib als zweite Zeile eine kurze, witzige Erklärung (maximal 1 kurzer Satz auf Deutsch), warum diese Emojis passen.\n"
                f"FORMAT:\n"
                f"EMOJIS: <Kette>\n"
                f"INFO: <Erklärung>"
            )
            user_prompt = f"Übersetze in Emojis:\n{user_text}"
        else:
            # Emoji ➔ Text
            system_prompt = (
                "Du bist der clevere 'Emoji-Dolmetscher & Kultur-Detektiv'.\n"
                "Auftrag: Analysiere die folgende Emoji-Kombination. Was bedeutet sie im heutigen Chat-Alltag (WhatsApp, TikTok, Instagram)?\n"
                "Achte besonders auf Doppeldeutigkeiten, Slang (z.B. 🍑 für Po, 🍆 für Intimes, 🥦 für Weed, 🧢 für Cap/Lüge, 💀 für Totlachen etc.) und Nuancen.\n\n"
                "REGELN:\n"
                "1. Gib als erste Zeile einen kurzen Titel (2-4 Worte).\n"
                "2. Gib als zweite Zeile die Bedeutung & Nuancen in 1 bis maximal 2 lockeren Sätzen auf Deutsch an.\n"
                "FORMAT:\n"
                "TITEL: <Titel>\n"
                "BEDEUTUNG: <Erklärung>"
            )
            user_prompt = f"Analysiere diese Emoji-Kombination:\n{user_text}"

        reply = ""
        # 1. Google Gemini API (Standard: gemini-3.8-flash)
        if self.gemini_api_key:
            models_to_try = ["gemini-3.8-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
            session = requests.Session()
            session.trust_env = False
            try:
                import certifi
                session.verify = certifi.where()
            except Exception:
                pass

            headers = {
                "x-goog-api-key": self.gemini_api_key,
                "Content-Type": "application/json"
            }
            payload = {
                "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
                "system_instruction": {"parts": [{"text": system_prompt}]},
                "generationConfig": {"temperature": 0.7, "maxOutputTokens": 200},
            }
            for model_name in models_to_try:
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
                    res = session.post(url, json=payload, headers=headers, timeout=12.0)
                    if res.status_code == 200:
                        data = res.json()
                        candidates = data.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            if parts:
                                reply = "".join(p.get("text", "") for p in parts).strip()
                                if reply:
                                    break
                    else:
                        print(f"[EmojiKryptograf] Gemini ({model_name}) HTTP {res.status_code}: {res.text[:120]}")
                except Exception as e:
                    print(f"[EmojiKryptograf] Gemini ({model_name}) Exception: {e}")

        # 2. Lokales Ollama
        if not reply:
            try:
                res = requests.post(
                    "http://127.0.0.1:11434/api/generate",
                    json={
                        "model": "gemma3:4b",
                        "prompt": f"{system_prompt}\n\n{user_prompt}",
                        "stream": False,
                    },
                    timeout=8.0,
                )
                if res.status_code == 200:
                    reply = res.json().get("response", "").strip()
            except Exception:
                reply = ""

        # 3. Offline Intelligenter Fallback
        if not reply:
            reply = self._offline_fallback(user_text, current_mode)

        QTimer.singleShot(0, self, lambda: self._on_result_ready(reply, current_mode, user_text))

    def _offline_fallback(self, text: str, mode: str) -> str:
        low = text.lower()
        if mode == "ENCODE":
            emojis = []
            if any(w in low for w in ("kaffee", "coffee", "wach")):
                emojis.append("☕")
            if any(w in low for w in ("bier", "feiern", "party", "prost")):
                emojis.append("🍻")
            if any(w in low for w in ("arbeit", "job", "arbeiten", "büro")):
                emojis.append("💻")
            if any(w in low for w in ("feierabend", "nach hause", "heim")):
                emojis.append("🚀")
            if any(w in low for w in ("müde", "schlafen", "bett")):
                emojis.append("🥱")
            if any(w in low for w in ("essen", "hunger", "pizza", "burger")):
                emojis.append("🍕")
            if any(w in low for w in ("liebe", "herz", "toll", "schön")):
                emojis.append("❤️")
            if any(w in low for w in ("lustig", "witzig", "lachen")):
                emojis.append("😂")
            if not emojis:
                emojis = ["✨", "🔮", "💬", "🔥"]
            chain = "".join(emojis)
            return f"EMOJIS: {chain}\nINFO: Offline-Übersetzung nach Schlüsselwörtern!"
        else:
            if "🍑" in text or "🍆" in text or "💦" in text:
                return "TITEL: Flirt & Zweideutig!\nBEDEUTUNG: Klassischer WhatsApp-Flirt mit eindeutigen zweideutigen Symbolen."
            elif "💀" in text:
                return "TITEL: Totgelacht (Gen-Z)!\nBEDEUTUNG: 'Ich sterbe vor Lachen' im modernen Internet-Slang."
            elif "🧢" in text:
                return "TITEL: Cap / Lüge!\nBEDEUTUNG: Das Cap-Symbol steht für 'Glaub ich nicht' oder 'reine Erfindung'."
            return f"TITEL: Emoji-Mischung\nBEDEUTUNG: Drückt eine bunte Gefühlswelt im Chat aus."

    def _on_result_ready(self, raw_reply: str, mode: str, original_input: str):
        self.is_thinking = False
        self.trigger_bounce(8.0)
        self.sound.play_chirp("happy")

        title = "🔮 Emoji-Kryptograf" if mode == "ENCODE" else "🔍 Emoji-Dolmetscher"
        emojis_found = ""
        speech_text = ""
        display_lines = []

        for line in raw_reply.splitlines():
            line_str = line.strip()
            if not line_str:
                continue
            if line_str.startswith("EMOJIS:"):
                emojis_found = line_str.replace("EMOJIS:", "").strip()
                display_lines.append(f"<span style='font-size: 24px;'>{emojis_found}</span>")
            elif line_str.startswith("INFO:"):
                info = line_str.replace("INFO:", "").strip()
                display_lines.append(info)
                speech_text = info
            elif line_str.startswith("TITEL:"):
                title = line_str.replace("TITEL:", "").strip()
            elif line_str.startswith("BEDEUTUNG:"):
                bedeutung = line_str.replace("BEDEUTUNG:", "").strip()
                display_lines.append(bedeutung)
                speech_text = bedeutung
            else:
                display_lines.append(line_str)

        if emojis_found:
            self.last_emojis = emojis_found

        full_display = "\n\n".join(display_lines) if display_lines else raw_reply
        self.show_bubble(full_display, 12.0, title)

        if speech_text:
            self.sound.speak(speech_text, "happy")
        elif emojis_found and mode == "ENCODE":
            self.sound.speak(f"Hier ist deine Emoji-Kette: {emojis_found}", "happy")

    # ==========================================
    # --- 60 FPS Animation & Rendering ---
    # ==========================================
    def update_animation(self):
        self.bounce_offset += self.bounce_velocity
        self.bounce_velocity += 0.65
        if self.bounce_offset > 0:
            self.bounce_offset = 0
            self.bounce_velocity *= -0.35
            if abs(self.bounce_velocity) < 0.5:
                self.bounce_velocity = 0.0

        self.glow_phase = (self.glow_phase + 0.05) % (2 * 3.14159)

        if self.is_dragging and not (QApplication.mouseButtons() & Qt.MouseButton.LeftButton):
            self.is_dragging = False

        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        now = time.time()
        # Sprechblase / Display zeichnen
        self.draw_bubble(painter)

        # Emoji-Kryptograf Bot zeichnen (schwebende goldene Cyber-Kugel mit Brille)
        self.draw_kryptograf_bot(painter)

    def draw_bubble(self, painter: QPainter):
        w = self.width()
        bubble_rect = QRectF(16, 48, w - 32, 175)

        # Subtiler Cyber-Glow & abgerundeter Hintergrund
        painter.setPen(QPen(QColor("#38bdf8"), 1.5))
        painter.setBrush(QColor(15, 23, 42, 245))
        painter.drawRoundedRect(bubble_rect, 16, 16)

        # Titel-Balken
        title_rect = QRectF(bubble_rect.left() + 12, bubble_rect.top() + 8, bubble_rect.width() - 24, 20)
        painter.setPen(QColor("#38bdf8"))
        painter.setFont(QFont("SansSerif", 9, QFont.Weight.Bold))
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.bubble_title)

        # Trennlinie
        painter.setPen(QPen(QColor(51, 65, 85, 180), 1))
        line_y = bubble_rect.top() + 30
        painter.drawLine(int(bubble_rect.left() + 10), int(line_y), int(bubble_rect.right() - 10), int(line_y))

        # Inhaltstext
        painter.setPen(QColor("#f1f5f9"))
        painter.setFont(QFont("SansSerif", 10))
        text_rect = QRectF(bubble_rect.left() + 12, line_y + 8, bubble_rect.width() - 24, bubble_rect.height() - 42)
        
        # HTML Rendering für große Emojis wenn vorhanden
        clean_text = self.bubble_text.replace("<span style='font-size: 24px;'>", "").replace("</span>", "")
        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
            clean_text,
        )

        # Sprechblasen-Spitze nach unten zum Bot
        tip = QPainterPath()
        tip_x = bubble_rect.center().x() - 40
        tip.moveTo(tip_x - 10, bubble_rect.bottom())
        tip.lineTo(tip_x + 10, bubble_rect.bottom())
        tip.lineTo(tip_x, bubble_rect.bottom() + 12)
        tip.closeSubpath()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(15, 23, 42, 245))
        painter.drawPath(tip)

    def draw_kryptograf_bot(self, painter: QPainter):
        # Position des schwebenden Bots (rechts unterhalb der Blase)
        cx = self.width() / 2.0 - 40
        cy = 250 + self.bounce_offset

        # Leuchtende Aura / Hologramm-Ring
        glow_alpha = int(40 + 20 * (1.0 + random.uniform(-0.1, 0.1)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(56, 189, 248, glow_alpha))
        painter.drawEllipse(QPointF(cx, cy), 32, 32)

        # Goldener Smiley-Körper
        grad = QLinearGradient(cx - 24, cy - 24, cx + 24, cy + 24)
        grad.setColorAt(0.0, QColor("#fbbf24"))
        grad.setColorAt(1.0, QColor("#f59e0b"))
        painter.setBrush(grad)
        painter.setPen(QPen(QColor("#d97706"), 2))
        painter.drawEllipse(QPointF(cx, cy), 24, 24)

        # Cyber-Sonnenbrille 🕶️
        painter.setBrush(QColor("#0f172a"))
        painter.setPen(QPen(QColor("#38bdf8"), 1.5))
        
        # Linkes & rechtes Glas
        painter.drawRoundedRect(QRectF(cx - 20, cy - 8, 18, 12), 4, 4)
        painter.drawRoundedRect(QRectF(cx + 2, cy - 8, 18, 12), 4, 4)
        # Steg
        painter.drawLine(int(cx - 2), int(cy - 2), int(cx + 2), int(cy - 2))

        # Cyan-Reflexion in der Brille
        painter.setPen(QPen(QColor("#7dd3fc"), 1))
        painter.drawLine(int(cx - 16), int(cy - 5), int(cx - 6), int(cy - 5))
        painter.drawLine(int(cx + 6), int(cy - 5), int(cx + 16), int(cy - 5))

        # Cooles Lächeln
        painter.setPen(QPen(QColor("#78350f"), 2))
        mouth = QPainterPath()
        mouth.moveTo(cx - 10, cy + 10)
        mouth.quadTo(cx, cy + 16, cx + 10, cy + 10)
        painter.drawPath(mouth)

        # Kleine Antenne / Kristall oben
        painter.setPen(QPen(QColor("#38bdf8"), 2))
        painter.drawLine(int(cx), int(cy - 24), int(cx), int(cy - 32))
        painter.setBrush(QColor("#38bdf8"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(cx, cy - 34), 3, 3)

    # ==========================================
    # --- Maus- & Kontext-Events ---
    # ==========================================
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position()
            # Klick auf den Bot oder oberen Bereich -> Witziger Spruch & Bounce
            if pos.y() < self.height() - 120:
                self.trigger_bounce(8.0)
                self.sound.play_chirp("happy")
                spruch = random.choice([
                    "Emoji-Kryptografie aktiv! Was soll ich verwandeln? 🔮",
                    "Aura +1000! Emojis sind die Weltsprache von morgen! ✨",
                    "Schick mir einen Satz oder Emojis zum Entschlüsseln! 🕵️",
                    "Peach, Eggplant & Skull... ich kenne alle Codes! 😎"
                ])
                self.show_bubble(spruch, 5.0, "🔮 Bereit!")

                self.is_dragging = True
                self.drag_offset = event.globalPosition() - QPointF(self.pos())
                win = self.windowHandle()
                if win is not None:
                    win.startSystemMove()

        elif event.button() == Qt.MouseButton.RightButton:
            self.show_context_menu(event.globalPosition().toPoint())

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging = False

    def mouseMoveEvent(self, event):
        if self.is_dragging and (event.buttons() & Qt.MouseButton.LeftButton):
            new_pos = event.globalPosition() - self.drag_offset
            self.move(int(new_pos.x()), int(new_pos.y()))

    def show_context_menu(self, pos):
        menu = QMenu(self)
        menu.setStyleSheet(
            """
            QMenu {
                background-color: #0f172a;
                color: #f8fafc;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 6px;
                font-size: 13px;
            }
            QMenu::item:selected {
                background-color: #38bdf8;
                color: #0f172a;
            }
            """
        )

        act_mode = QAction("🔄 Modus wechseln (Satz ➔ Emoji / Emoji ➔ Satz)", self)
        act_mode.triggered.connect(self.toggle_mode)
        menu.addAction(act_mode)

        style_sub = menu.addMenu("🎨 Übersetzungs-Stil")
        style_grp = QActionGroup(self)
        for st in TRANSLATION_STYLES:
            act_s = QAction(st["name"], self, checkable=True)
            act_s.setChecked(self.active_style == st["id"])
            act_s.triggered.connect(lambda checked, sid=st["id"]: setattr(self, "active_style", sid) or self.show_bubble(f"Stil gewählt: {sid}!", 3.0))
            style_grp.addAction(act_s)
            style_sub.addAction(act_s)

        menu.addSeparator()
        act_copy = QAction("📋 Emojis in Zwischenablage kopieren", self)
        act_copy.triggered.connect(self.copy_last_emojis)
        menu.addAction(act_copy)

        act_clear = QAction("🧹 Eingabe leeren", self)
        act_clear.triggered.connect(self.input_field.clear)
        menu.addAction(act_clear)

        menu.addSeparator()
        act_key = QAction("🔑 Gemini API-Key prüfen / ändern...", self)
        def _set_key():
            k, ok = QInputDialog.getText(self, "API-Key", "Google Gemini API-Key:", text=self.gemini_api_key)
            if ok:
                self.save_gemini_key(k)
                self.show_bubble("API-Key gespeichert & aktiv! ✨", 3.5)
                self.sound.play_chirp("happy")
        act_key.triggered.connect(_set_key)
        menu.addAction(act_key)

        menu.addSeparator()
        act_close = QAction("❌ Emoji-Kryptograf schlafen legen", self)
        act_close.triggered.connect(self.close)
        menu.addAction(act_close)

        menu.exec(pos)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("EmojiKryptograf")
    widget = EmojiKryptografWidget()
    widget.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
