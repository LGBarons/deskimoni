#!/usr/bin/env python3
"""
Jo the Crow (jothecrow) - Slang- & Vibe-Übersetzerin als Desktop-Buddy! 🐦‍⬛✨
Eine 20-jährige Studentin aus Kiel im Jahr 2026, die deine Texte in 11 coole Vibes verwandelt:
- Jo the Crow Slang 2026 (Aura, Rizz, Digga, goated, no cap...)
- Corporate BS (Synergize, Leverage, Deep Dive...)
- König & Ritter (Fürwahr, Unsereins...)
- Pirat (Aye, beim Klabautermann!)
- Beamten-Modus (Bürokratendeutsch)
- Vallah Modus (Kiez-Deutsch)
- Peinlicher Chef
- Bundeswehr Soldat
- Woke & Gen-Z
- Hochdeutsch
- US Street Slang
"""

import os
import sys
import time
import json
import random
import threading
import subprocess
from datetime import datetime

import requests

from deskimoni_core.qt import (
    Qt, QTimer, QPoint, QPointF, QRectF, QSize,
    QColor, QFont, QPainter, QPainterPath, QCursor, QIcon, QPen, QBrush,
    QAction, QActionGroup, QWidget, QApplication, QLineEdit,
    QPushButton, QMenu, QInputDialog, QMessageBox, QSvgRenderer
)
from deskimoni_core.signals import WorkerSignals
from deskimoni_core.audio.sound_engine import RobotSoundEngine


# Die 11 Vibes aus Jo the Crows Repository
VIBES = [
    {
        "id": "JUGEND",
        "label": "Jo the Crow Slang",
        "icon": "🐦‍⬛",
        "desc": "Moderner Jugend-Slang 2026 (Aura, Rizz, Schere, Digga, gekocht, lowkey, fr, goated, no cap, Macher, Ehrenmann).",
    },
    {
        "id": "WOKE_GENZ",
        "label": "Woke & Gen-Z",
        "icon": "🏳️‍🌈",
        "desc": "Achtsam, inklusiv und modern (Slay, Sus, Cancel, Trigger Warning, No Cap, Valid, Vibe Check).",
    },
    {
        "id": "FIRMEN_JARGON",
        "label": "Corporate BS",
        "icon": "💼",
        "desc": "Deutsches Firmen-Jargon & Bullshit-Bingo (Synergize, Leverage, Needle Move, Deep Dive, Asynchron besprechen, Touchbase).",
    },
    {
        "id": "MITTELALTER",
        "label": "König & Ritter",
        "icon": "🏰",
        "desc": "Völlig überzogener Pluralis Majestatis, altertümlich, edel, ritterlich (Ihr, Unsereins, Fürwahr, Wohlan, Geselle).",
    },
    {
        "id": "PIRAT",
        "label": "Käpt'n Klabauter",
        "icon": "🏴‍☠️",
        "desc": "Rauer Seemanns-Slang (Aye, Landratten, beim Klabautermann, Klar Schiff machen, Volle Fahrt voraus!).",
    },
    {
        "id": "BEAMTER",
        "label": "Beamten-Modus",
        "icon": "📁",
        "desc": "Bürokratisches Amtsdeutsch, extrem lange Schachtelsätze, Passivkonstruktionen, Paragraphen, Aktenzeichen.",
    },
    {
        "id": "KIEZ",
        "label": "Vallah Modus",
        "icon": "🚬",
        "desc": "Kiez-Deutsch, Berliner/Hamburger Straße (Vallah, Habibi, Macher, Bruder, Chaya, Schwöre auf alles).",
    },
    {
        "id": "PEINLICHER_CHEF",
        "label": "Peinlicher Chef",
        "icon": "👔",
        "desc": "Versucht krampfhaft cool zu sein, nutzt Jugendslang oft völlig falsch, peinlich oder deplatziert.",
    },
    {
        "id": "HOCHDEUTSCH",
        "label": "Hochdeutsch",
        "icon": "🎓",
        "desc": "Korrektes, elegantes, höfliches und präzises Hochdeutsch ohne jeglichen Slang oder Umgangssprache.",
    },
    {
        "id": "SOLDAT",
        "label": "Bundeswehr Soldat",
        "icon": "🪖",
        "desc": "Militärischer Tonfall, kurz, zackig, Befehlsform, militärische Abkürzungen, Jawohl!",
    },
    {
        "id": "US_STREET",
        "label": "US Street Slang",
        "icon": "🇺🇸",
        "desc": "Cool American Street Slang (AAVE style, yo, fam, bet, finna, legit, straight up).",
    },
]

SLANG_GREETINGS = [
    "Yo Digga! Was geht ab? Drop mal nen Text zum Übersetzen! 🐦‍⬛",
    "Jo the Crow am Start! Welchen Vibe brauchst du heute? ✨",
    "Servus! Lass mal deinen Text übelst transformieren, no cap! 🚀",
    "Aura auf Maximum! Schreib mir was und ich mach Slang draus! 😎",
    "Moin aus Kiel! Jo the Crow ist bereit zum Kochen! 🐦‍⬛🔥",
]


class JoTheCrowWidget(QWidget):
    """Jo the Crow – Slang- & Vibe-Übersetzer Desktop-Begleiterin."""

    def __init__(self):
        super().__init__()

        self.signals = WorkerSignals()
        self.signals.reply_ready.connect(self._on_translation_ready)
        self.sound = RobotSoundEngine(self.signals)
        self.sound.set_voice_profile("katja_warm")  # Junge, sympathische Frauenstimme für Jo

        # Fenster-Eigenschaften
        self.scale_factor = 1.0
        self.base_width = 240
        self.base_height = 320
        self.active_vibe = "JUGEND"
        self.intensity = 75  # 25, 50, 75, 100

        # Chat & Sprechblase
        self.bubble_text = random.choice(SLANG_GREETINGS)
        self.bubble_until = time.time() + 8.0
        self.is_thinking = False

        # Physik & Animation
        self.bounce_offset = 0.0
        self.bounce_velocity = 0.0
        self.is_dragging = False
        self.drag_offset = QPointF(0, 0)

        # SVG Renderer für Jo the Crow laden
        self.svg_renderer = None
        base_dir = os.path.dirname(os.path.abspath(__file__))
        svg_path = os.path.join(base_dir, "assets", "crow", "jothecrow1.svg")
        if os.path.exists(svg_path) and QSvgRenderer is not None:
            self.svg_renderer = QSvgRenderer(svg_path)

        # Gemini API Key laden (aus Deskimoni Settings)
        self.gemini_api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        self.load_gemini_key_from_settings()

        self.setup_ui()

        # 60 FPS Loop
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self.update_animation)
        self.anim_timer.start(16)

    def load_gemini_key_from_settings(self):
        settings_path = os.path.expanduser("~/.config/deskimoni/settings.json")
        try:
            if os.path.exists(settings_path):
                with open(settings_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                key = data.get("gemini_api_key", "").strip()
                if key:
                    self.gemini_api_key = key
        except Exception:
            pass

    def save_gemini_key_to_settings(self, key: str):
        self.gemini_api_key = key.strip()
        settings_path = os.path.expanduser("~/.config/deskimoni/settings.json")
        try:
            os.makedirs(os.path.dirname(settings_path), exist_ok=True)
            data = {}
            if os.path.exists(settings_path):
                with open(settings_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            data["gemini_api_key"] = self.gemini_api_key
            with open(settings_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[JoTheCrow] Fehler beim Speichern des API-Keys: {e}")

    def setup_ui(self):
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.resize(self.base_width, self.base_height)
        self.setWindowTitle("Jo the Crow – Slang Übersetzerin")

        # Eingabefeld unten
        self.input_field = QLineEdit(self)
        self.input_field.setPlaceholderText("Text eingeben & Enter drücken...")
        self.input_field.returnPressed.connect(self.on_translate_requested)
        self.input_field.setStyleSheet(
            """
            QLineEdit {
                background-color: rgba(24, 25, 38, 240);
                color: #cdd6f4;
                border: 1.5px solid #cba6f7;
                border-radius: 12px;
                padding: 4px 10px;
                font-size: 11px;
            }
            QLineEdit:focus {
                border-color: #f5c2e7;
                background-color: rgba(30, 30, 46, 255);
            }
            """
        )

        # Vibe-Umschalter Button
        self.vibe_btn = QPushButton(self)
        self.update_vibe_btn()
        self.vibe_btn.clicked.connect(self.cycle_vibe)
        self.vibe_btn.setStyleSheet(
            """
            QPushButton {
                background-color: rgba(30, 30, 46, 230);
                color: #cdd6f4;
                border: 1.5px solid #45475a;
                border-radius: 12px;
                font-size: 13px;
                padding: 0px;
            }
            QPushButton:hover {
                border-color: #cba6f7;
                background-color: rgba(49, 50, 68, 250);
            }
            """
        )

        self.layout_ui()

    def update_vibe_btn(self):
        v = next((x for x in VIBES if x["id"] == self.active_vibe), VIBES[0])
        self.vibe_btn.setText(v["icon"])
        self.vibe_btn.setToolTip(f"Aktiver Vibe: {v['label']}\nKlicken zum Wechseln!")

    def layout_ui(self):
        s = self.scale_factor
        y_pos = int(self.height() - 36 * s)
        btn_w = int(32 * s)
        h = int(28 * s)
        input_w = int(self.width() - btn_w - 18 * s)

        self.vibe_btn.setGeometry(int(8 * s), y_pos, btn_w, h)
        self.input_field.setGeometry(int(44 * s), y_pos, input_w, h)

    def cycle_vibe(self):
        v_ids = [v["id"] for v in VIBES]
        idx = (v_ids.index(self.active_vibe) + 1) % len(v_ids)
        self.active_vibe = v_ids[idx]
        self.update_vibe_btn()
        v = next(x for x in VIBES if x["id"] == self.active_vibe)
        self.trigger_bounce(5.0)
        self.sound.play_chirp("curious")
        self.show_bubble(f"Neuer Vibe gewählt:\n{v['icon']} {v['label']}!", 3.5)

    def set_vibe(self, vibe_id: str):
        if any(v["id"] == vibe_id for v in VIBES):
            self.active_vibe = vibe_id
            self.update_vibe_btn()
            v = next(x for x in VIBES if x["id"] == self.active_vibe)
            self.show_bubble(f"Vibe: {v['icon']} {v['label']}", 3.0)

    def show_bubble(self, text: str, duration: float = 6.0):
        self.bubble_text = text
        self.bubble_until = time.time() + duration
        self.update()

    def trigger_bounce(self, strength: float = 6.0):
        self.bounce_velocity = -strength

    def on_translate_requested(self):
        text = self.input_field.text().strip()
        if not text or self.is_thinking:
            return
        self.input_field.clear()
        self.is_thinking = True
        self.trigger_bounce(5.0)
        self.sound.play_chirp("curious")
        self.show_bubble("Ich koche kurz die Übersetzung... 🐦‍⬛🔥", 10.0)

        threading.Thread(target=self._translate_worker, args=(text,), daemon=True).start()

    def _translate_worker(self, user_text: str):
        target_vibe = next((v for v in VIBES if v["id"] == self.active_vibe), VIBES[0])

        if self.intensity < 25:
            intensity_desc = "Dezent: Nur leichte Nuancen."
        elif self.intensity < 60:
            intensity_desc = "Spürbar: Deutliche Merkmale des Stils."
        elif self.intensity < 85:
            intensity_desc = "Stark: Den Stil voll ausleben."
        else:
            intensity_desc = "Extrem: Maximale Übertreibung, fast schon eine Karikatur."

        system_prompt = (
            f"Du bist Jo the Crow, eine coole 20-jährige Studentin aus Kiel im Jahr 2026.\n"
            f"Dein Auftrag: Transformiere den folgenden Text in den Vibe '{target_vibe['label']}'.\n"
            f"VIBE-BESCHREIBUNG: {target_vibe['desc']}\n"
            f"INTENSITÄT: {intensity_desc}\n\n"
            f"WICHTIG:\n"
            f"- Antworte NUR direkt mit dem transformierten Text (maximal 1 bis 2 Sätze)!\n"
            f"- Keine Einleitungen wie 'Hier ist die Übersetzung' oder Anführungszeichen.\n"
            f"- Behalte die Kernaussage bei."
        )

        reply = ""
        # 1. Google Gemini API versuchen
        if self.gemini_api_key:
            models_to_try = ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-3.8-flash"]
            session = requests.Session()
            session.trust_env = False
            headers = {
                "x-goog-api-key": self.gemini_api_key,
                "Content-Type": "application/json"
            }
            payload = {
                "contents": [{"parts": [{"text": f"Transformiere diesen Text in den Vibe '{target_vibe['label']}':\n\n{user_text}"}]}],
                "systemInstruction": {"parts": [{"text": system_prompt}]},
                "generationConfig": {"temperature": 0.8, "maxOutputTokens": 200},
            }
            for model_name in models_to_try:
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
                    res = session.post(url, json=payload, headers=headers, timeout=9.0)
                    if res.status_code == 200:
                        data = res.json()
                        candidates = data.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            if parts:
                                reply = parts[0].get("text", "").strip()
                                if reply:
                                    break
                    else:
                        print(f"[JoTheCrow] Gemini ({model_name}) HTTP {res.status_code}: {res.text[:100]}")
                except Exception as e:
                    print(f"[JoTheCrow] Gemini ({model_name}) Exception: {e}")

        # 2. Lokales Ollama als Fallback
        if not reply:
            try:
                res = requests.post(
                    "http://127.0.0.1:11434/api/generate",
                    json={
                        "model": "gemma3:4b",
                        "prompt": f"{system_prompt}\n\nText:\n{user_text}",
                        "stream": False,
                    },
                    timeout=8.0,
                )
                if res.status_code == 200:
                    reply = res.json().get("response", "").strip()
            except Exception:
                reply = ""

        # 3. Witziger Offline-Fallback, falls weder Gemini noch Ollama aktiv ist
        if not reply:
            if target_vibe["id"] == "JUGEND":
                reply = f"Bro, ohne Internet bin ich lost! Aber '{user_text}' ist lowkey übelst goated, no cap! 🐦‍⬛"
            elif target_vibe["id"] == "FIRMEN_JARGON":
                reply = f"Lassen Sie uns bezüglich '{user_text}' asynchron ein alignment herstellen und die Synergien hebeln!"
            elif target_vibe["id"] == "PIRAT":
                reply = f"Beim Klabautermann! '{user_text}', sagst du? Setzt die Segel, ihr Landratten!"
            elif target_vibe["id"] == "MITTELALTER":
                reply = f"Fürwahr! Welch edle Kunde vernehmet Unser Gehör: {user_text}!"
            else:
                reply = f"Yo! {user_text} (im {target_vibe['label']}-Vibe)!"

        # Thread-sichere UI- & Sprach-Aktualisierung via Qt-Signal
        self.signals.reply_ready.emit(reply, target_vibe["icon"])

    def _on_translation_ready(self, reply: str, icon: str):
        self.is_thinking = False
        self.trigger_bounce(8.0)
        self.sound.play_chirp("happy")
        display_text = f"{icon} {reply}"
        duration = max(6.0, min(14.0, len(reply) * 0.12))
        self.show_bubble(display_text, duration)
        self.sound.speak(reply, "happy")

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

        if self.is_dragging and not (QApplication.mouseButtons() & Qt.MouseButton.LeftButton):
            self.is_dragging = False

        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        # Sprechblase zeichnen
        now = time.time()
        if self.bubble_text and now < self.bubble_until:
            self.draw_bubble(painter)

        # Jo the Crow Körper (SVG oder dynamische Vektor-Krähe)
        crow_rect = QRectF(30, 80 + self.bounce_offset, 180, 190)

        if self.svg_renderer is not None and self.svg_renderer.isValid():
            self.svg_renderer.render(painter, crow_rect)
        else:
            # Schöne Vektor-Krähe als Fallback
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#1e1e2e"))
            painter.drawEllipse(crow_rect)
            painter.setBrush(QColor("#fab387"))
            beak = QPainterPath()
            beak.moveTo(crow_rect.right() - 20, crow_rect.center().y())
            beak.lineTo(crow_rect.right() + 15, crow_rect.center().y() + 5)
            beak.lineTo(crow_rect.right() - 20, crow_rect.center().y() + 15)
            painter.drawPath(beak)
            painter.setBrush(QColor("#ffffff"))
            painter.drawEllipse(QPointF(crow_rect.center().x() + 25, crow_rect.center().y() - 15), 10, 10)
            painter.setBrush(QColor("#11111b"))
            painter.drawEllipse(QPointF(crow_rect.center().x() + 28, crow_rect.center().y() - 15), 5, 5)

    def draw_bubble(self, painter: QPainter):
        bubble_rect = QRectF(10, 8, self.width() - 20, 68)

        painter.setPen(QPen(QColor("#cba6f7"), 1.5))
        painter.setBrush(QColor(24, 25, 38, 245))
        painter.drawRoundedRect(bubble_rect, 14, 14)

        tip = QPainterPath()
        tip.moveTo(bubble_rect.center().x() - 8, bubble_rect.bottom())
        tip.lineTo(bubble_rect.center().x() + 8, bubble_rect.bottom())
        tip.lineTo(bubble_rect.center().x(), bubble_rect.bottom() + 9)
        tip.closeSubpath()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(24, 25, 38, 245))
        painter.drawPath(tip)

        painter.setPen(QColor("#cdd6f4"))
        font = QFont("SansSerif", 9)
        painter.setFont(font)
        text_rect = bubble_rect.adjusted(8, 6, -8, -6)
        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
            self.bubble_text,
        )

    # ==========================================
    # --- Maus- & Kontext-Events ---
    # ==========================================
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position()
            # Wenn auf die Krähe geklickt wird -> hüpfen & Spruch
            if pos.y() < self.height() - 40:
                self.trigger_bounce(8.0)
                self.sound.play_chirp("happy")
                v = next((x for x in VIBES if x["id"] == self.active_vibe), VIBES[0])
                msg = random.choice([
                    f"Yo! Aktiver Vibe: {v['icon']} {v['label']}! Hau mir nen Satz rein!",
                    "Aura +1000! Schick mir Text zum Kochen! 🐦‍⬛🔥",
                    "Jo the Crow am Start! Welchen Text soll ich umwandeln?",
                ])
                self.show_bubble(msg, 5.0)

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
                background-color: #1e1e2e;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 8px;
                padding: 6px;
                font-size: 13px;
            }
            QMenu::item:selected {
                background-color: #cba6f7;
                color: #11111b;
            }
            """
        )

        vibe_sub = menu.addMenu("🎭 Vibe auswählen")
        vibe_grp = QActionGroup(self)
        for v in VIBES:
            act = QAction(f"{v['icon']} {v['label']}", self, checkable=True)
            act.setChecked(self.active_vibe == v["id"])
            act.triggered.connect(lambda checked, vid=v["id"]: self.set_vibe(vid))
            vibe_grp.addAction(act)
            vibe_sub.addAction(act)

        int_sub = menu.addMenu("⚡ Intensität")
        int_grp = QActionGroup(self)
        for val, lbl in [(25, "Dezent (25%)"), (50, "Spürbar (50%)"), (75, "Stark (75%)"), (100, "Extrem (100%)")]:
            act_i = QAction(lbl, self, checkable=True)
            act_i.setChecked(self.intensity == val)
            act_i.triggered.connect(lambda checked, v=val: setattr(self, "intensity", v))
            int_grp.addAction(act_i)
            int_sub.addAction(act_i)

        menu.addSeparator()
        act_key = QAction("🔑 Google Gemini API-Key prüfen / eingeben...", self)
        def _set_key():
            k, ok = QInputDialog.getText(self, "API-Key", "Google Gemini API-Key:", text=self.gemini_api_key)
            if ok:
                self.save_gemini_key_to_settings(k)
                self.show_bubble("API-Key gespeichert & aktiv! ✨", 3.5)
                self.sound.play_chirp("happy")
        act_key.triggered.connect(_set_key)
        menu.addAction(act_key)

        menu.addSeparator()
        act_quit = QAction("❌ Jo the Crow schlafen legen", self)
        act_quit.triggered.connect(self.close)
        menu.addAction(act_quit)

        menu.exec(pos)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("JoTheCrow")
    crow = JoTheCrowWidget()
    crow.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
