#!/usr/bin/env python3
"""
Deskimoni v2.1 - Meeting-Planer & Büro-Bingo (Bullshit-Bingo) 🎯📅
Modul für nervige Pflicht-Besprechungen & Telcos:
- Private Terminverwaltung in ~/.config/deskimoni/meetings.json (nicht im Git-Repository!)
- Wiederkehrende Termine:
    * Mittwochs 13:00 Uhr: Fakultätsbesprechung ("Die große Laberstunde")
    * Dienstags 09:30 Uhr: X3-Runde ("Mega nervig")
    * Jeden 1. Dienstag im Monat: Große X3-Runde ("Totaler Schwachsinn")
    * Jour Fixe, Morgenlage etc.
- Sarkastische Vorwarnung (5 Min. vorher) & Start-Gong
- Interaktives 4x4 Büro- & Telco-Bullshit-Bingo mit leiser Bingo-Ansage!
"""

import os
import sys
import time
import json
import random
from datetime import datetime, date, timedelta

from deskimoni_core.qt import (
    Qt, QTimer, QPoint, QPointF, QRectF, QSize,
    QColor, QFont, QPainter, QCursor, QIcon, QPen, QBrush,
    QAction, QActionGroup, QWidget, QApplication, QLineEdit,
    QPushButton, QMenu, QInputDialog, QMessageBox,
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QCheckBox, QFrame
)


BUZZWORDS = [
    "Könnt ihr meinen Bildschirm sehen?",
    "Lass uns das mal asynchron besprechen",
    "Da bin ich ganz bei dir",
    "Du bist noch stummgeschaltet!",
    "Das hätte auch eine E-Mail sein können",
    "Wer schreibt das Protokoll?",
    "Lass uns da einen Deep Dive machen",
    "Können wir das offline vertiefen?",
    "Synergien heben / Low hanging fruits",
    "Ich muss gleich in den nächsten Call springen",
    "Kurzes Meinungsbild einholen",
    "Wir müssen die PS auf die Straße bringen",
    "Die Stakeholder abholen",
    "Da ist noch ein Blocker",
    "Ich sehe da noch Optimierungsbedarf",
    "Können alle die Folien sehen?",
    "Ich übergebe das Wort an...",
    "Kurzes Update von meiner Seite",
    "Ich höre dich gerade abgehackt",
    "Da machen wir einen Haken dran",
    "Jemand vergisst sich zu muten (Kauen/Atmen)",
    "Am Ende des Tages...",
    "Köpfe kurz zusammenstecken",
    "Wir drehen uns im Kreis",
    "Lass uns das mitnehmen ins nächste Meeting",
    "Das ist ein valider Punkt",
    "Könnt ihr mich alle hören?",
    "Da gehe ich voll mit",
    "Einfach mal eine Lanze brechen"
]

DEFAULT_MEETINGS = [
    {
        "id": "x3_gross",
        "title": "Große X3-Runde",
        "day_of_week": 1,           # Dienstag
        "time": "09:30",
        "monthly_nth": 1,           # Nur am 1. Dienstag im Monat!
        "duration_mins": 90,
        "subtext": "Totaler Schwachsinn – die extra lange XL-Version!",
        "enabled": True,
        "sarcasm_pre": [
            "🚨 Alarmstufe Rot: In 5 Minuten startet die GROSSE X3-Runde! Erster Dienstag im Monat... das wird zäh!",
            "Große X3-Runde naht. Warum gibt es dafür eigentlich keinen gesetzlichen Schmerzensgeld-Anspruch?"
        ],
        "sarcasm_start": [
            "Große X3-Runde startet jetzt! Höchste Zeit für Meeting-Bingo. Möge die Geduld mit dir sein!",
            "Große X3-Runde ist live. Nicken, lächeln und im Kopf schon Feierabend planen!"
        ]
    },
    {
        "id": "x3_runde",
        "title": "X3-Runde",
        "day_of_week": 1,           # Dienstag
        "time": "09:30",
        "monthly_nth": None,        # Jeder Dienstag (falls nicht 1. Di oder als Fallback)
        "duration_mins": 45,
        "subtext": "Mega nervig – könnte locker eine E-Mail sein!",
        "enabled": True,
        "sarcasm_pre": [
            "In 5 Minuten startet die X3-Runde! Mega nervig... Hol dir schnell noch einen starken Kaffee!",
            "Achtung: X3-Runde in 5 Minuten voraus. Zeit fürs Pokerface!"
        ],
        "sarcasm_start": [
            "Die X3-Runde fängt jetzt an. Bullshit-Bingo bereit? Stark bleiben!",
            "X3-Runde läuft! Das hätte definitiv eine E-Mail sein können."
        ]
    },
    {
        "id": "fakultaet",
        "title": "Fakultätsbesprechung",
        "day_of_week": 2,           # Mittwoch
        "time": "13:00",
        "monthly_nth": None,
        "duration_mins": 60,
        "subtext": "Die große Laberstunde – Scheuklappen aufsetzen!",
        "enabled": True,
        "sarcasm_pre": [
            "Mittwoch 13 Uhr naht: In 5 Minuten beginnt die Fakultätsbesprechung! Die große Laberstunde...",
            "Fakultätsbesprechung in Kürze! Bereithalten zum Stummschalten und Scheuklappen aufsetzen!"
        ],
        "sarcasm_start": [
            "Fakultätsbesprechung fängt an. Das hätte zu 100% eine E-Mail sein können!",
            "Die große Laberstunde läuft! Ich zähle schon mal die Floskeln für dein Büro-Bingo mit."
        ]
    },
    {
        "id": "jour_fixe",
        "title": "Jour Fixe",
        "day_of_week": 0,           # Montag
        "time": "10:00",
        "monthly_nth": None,
        "duration_mins": 45,
        "subtext": "Der klassische Montags-Kaffeeklatsch",
        "enabled": False,           # Standardmäßig inaktiv, kann aktiviert werden
        "sarcasm_pre": [
            "In 5 Minuten Jour Fixe. Wir schaffen den Montag!",
            "Gleich Jour Fixe... einmal tief durchatmen!"
        ],
        "sarcasm_start": [
            "Jour Fixe gestartet. Denk an deine Bullshit-Bingo-Kacheln!",
            "Jour Fixe läuft! Einfach freundlich schauen."
        ]
    },
    {
        "id": "morgenlage",
        "title": "Morgenlage / Standup",
        "day_of_week": [0, 1, 2, 3, 4], # Montag bis Freitag
        "time": "08:30",
        "monthly_nth": None,
        "duration_mins": 15,
        "subtext": "Tägliches Standup-Gequatsche",
        "enabled": False,           # Standardmäßig inaktiv
        "sarcasm_pre": [
            "Gleich Morgenlage... einmal kurz wach aussehen!",
            "In 5 Minuten Morgenlage. Kaffee auffüllen!"
        ],
        "sarcasm_start": [
            "Morgenlage läuft. Sag einfach 'Blocker gibt es keine' und gut ist!",
            "Morgenlage aktiv. Kurz, schmerzlos, abhacken!"
        ]
    }
]


class OfficeBingoDialog(QDialog):
    """Interaktives 4x4 Büro- & Telco-Bullshit-Bingo Fenster."""

    def __init__(self, parent=None, sound_engine=None):
        super().__init__(parent)
        self.sound = sound_engine
        self.setWindowTitle("🎯 Meeting- & Büro-Bingo (Bullshit-Bingo)")
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        self.resize(520, 560)
        self.setStyleSheet(
            """
            QDialog {
                background-color: #0b111e;
                color: #f1f5f9;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QLabel {
                color: #f1f5f9;
            }
            """
        )

        self.bingo_tiles = []
        self.checked_state = [False] * 16
        self.bingo_achieved = False
        self.quiet_mode = False

        self.setup_ui()
        self.generate_new_card()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header
        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("🎯 Büro- & Meeting-Bingo")
        title.setStyleSheet("font-size: 17px; font-weight: bold; color: #38bdf8;")
        sub = QLabel("Hake die typischen Floskeln in deiner Telco ab – wer 4 in einer Reihe hat, gewinnt!")
        sub.setStyleSheet("font-size: 11px; color: #94a3b8;")
        title_box.addWidget(title)
        title_box.addWidget(sub)
        header.addLayout(title_box)

        # Mute / Leiser Modus Checkbox
        self.mute_cb = QCheckBox("🤫 Leiser Modus (Kein lauter Ruf)")
        self.mute_cb.setToolTip("Falls dein Mikrofon im Call an ist, flüstert Deskimoni nicht laut in den Raum!")
        self.mute_cb.setStyleSheet("color: #cbd5e1; font-size: 11px;")
        self.mute_cb.toggled.connect(lambda c: setattr(self, "quiet_mode", c))
        header.addWidget(self.mute_cb)

        layout.addLayout(header)

        # Status / Bingo Banner
        self.status_banner = QLabel("Tippe auf eine Floskel, sobald jemand sie im Call ausspricht:")
        self.status_banner.setStyleSheet("font-size: 12px; color: #cbd5e1; padding: 4px 0px;")
        layout.addWidget(self.status_banner)

        # 4x4 Gitter
        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(8)

        self.buttons = []
        for row in range(4):
            for col in range(4):
                idx = row * 4 + col
                btn = QPushButton()
                btn.setCheckable(True)
                btn.setSizePolicy(btn.sizePolicy().horizontalPolicy(), btn.sizePolicy().verticalPolicy())
                btn.setMinimumHeight(76)
                btn.setStyleSheet(self._get_btn_style(False))
                btn.clicked.connect(lambda checked, i=idx: self.on_tile_clicked(i))
                self.grid_layout.addWidget(btn, row, col)
                self.buttons.append(btn)

        layout.addLayout(self.grid_layout)

        # Buttons unten: Neu Mischen, Zurücksetzen, Schließen
        btn_bar = QHBoxLayout()
        self.shuffle_btn = QPushButton("🔄 Neue Bingo-Karte mischen")
        self.shuffle_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #1e293b;
                color: #38bdf8;
                border: 1px solid #38bdf8;
                border-radius: 8px;
                padding: 8px 14px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #38bdf8;
                color: #0b111e;
            }
            """
        )
        self.shuffle_btn.clicked.connect(self.generate_new_card)
        btn_bar.addWidget(self.shuffle_btn)

        self.reset_btn = QPushButton("🧹 Häkchen zurücksetzen")
        self.reset_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #1e293b;
                color: #94a3b8;
                border: 1px solid #475569;
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #334155;
                color: #f1f5f9;
            }
            """
        )
        self.reset_btn.clicked.connect(self.reset_checks)
        btn_bar.addWidget(self.reset_btn)

        btn_bar.addStretch()

        close_btn = QPushButton("Schließen")
        close_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #334155;
                color: #f1f5f9;
                border: none;
                border-radius: 8px;
                padding: 8px 16px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #475569;
            }
            """
        )
        close_btn.clicked.connect(self.accept)
        btn_bar.addWidget(close_btn)

        layout.addLayout(btn_bar)

    def _get_btn_style(self, checked: bool) -> str:
        if checked:
            return """
            QPushButton {
                background-color: #065f46;
                color: #ecfdf5;
                border: 2px solid #10b981;
                border-radius: 10px;
                padding: 6px;
                font-size: 11px;
                font-weight: bold;
                text-align: center;
            }
            QPushButton:hover {
                background-color: #047857;
            }
            """
        else:
            return """
            QPushButton {
                background-color: #1e293b;
                color: #e2e8f0;
                border: 1.5px solid #334155;
                border-radius: 10px;
                padding: 6px;
                font-size: 11px;
                text-align: center;
            }
            QPushButton:hover {
                background-color: #334155;
                border-color: #38bdf8;
                color: #ffffff;
            }
            """

    def generate_new_card(self):
        pool = list(BUZZWORDS)
        random.shuffle(pool)
        self.bingo_tiles = pool[:16]
        self.checked_state = [False] * 16
        self.bingo_achieved = False

        for i, text in enumerate(self.bingo_tiles):
            btn = self.buttons[i]
            btn.setChecked(False)
            btn.setText(text)
            btn.setStyleSheet(self._get_btn_style(False))

        self.status_banner.setText("🎯 Neue Bingo-Karte gemischt! Hör gut zu im Call...")
        self.status_banner.setStyleSheet("font-size: 12px; color: #38bdf8; padding: 4px 0px;")
        if self.sound:
            self.sound.play_chirp("curious")

    def reset_checks(self):
        self.checked_state = [False] * 16
        self.bingo_achieved = False
        for btn in self.buttons:
            btn.setChecked(False)
            btn.setStyleSheet(self._get_btn_style(False))
        self.status_banner.setText("Häkchen zurückgesetzt. Auf ein Neues!")
        self.status_banner.setStyleSheet("font-size: 12px; color: #cbd5e1; padding: 4px 0px;")

    def on_tile_clicked(self, idx: int):
        is_checked = self.buttons[idx].isChecked()
        self.checked_state[idx] = is_checked
        self.buttons[idx].setStyleSheet(self._get_btn_style(is_checked))

        if is_checked and self.sound:
            self.sound.play_chirp("happy")

        self.check_bingo()

    def check_bingo(self):
        lines = [
            # Reihen
            [0, 1, 2, 3], [4, 5, 6, 7], [8, 9, 10, 11], [12, 13, 14, 15],
            # Spalten
            [0, 4, 8, 12], [1, 5, 9, 13], [2, 6, 10, 14], [3, 7, 11, 15],
            # Diagonalen
            [0, 5, 10, 15], [3, 6, 9, 12]
        ]

        has_bingo = any(all(self.checked_state[i] for i in line) for line in lines)
        if has_bingo and not self.bingo_achieved:
            self.bingo_achieved = True
            self.status_banner.setText("🎉🎉🎉 BIIINGO! Du hast 4 in einer Reihe! Telco gewonnen! 🎉🎉🎉")
            self.status_banner.setStyleSheet("font-size: 13px; font-weight: bold; color: #facc15; padding: 4px 0px;")

            if self.sound:
                self.sound.play_chirp("love")
                if not self.quiet_mode:
                    self.sound.speak("Biiiingo! Vier in einer Reihe! Du hast die Telco offiziell gewonnen!", "happy")

    def mark_floskel_by_keyword(self, keyword: str) -> bool:
        low = keyword.lower().strip()
        for idx, text in enumerate(self.bingo_tiles):
            if low in text.lower():
                self.buttons[idx].setChecked(True)
                self.on_tile_clicked(idx)
                return True
        return False


class ManageMeetingsDialog(QDialog):
    """Verwaltungsfenster für private Termine & Besprechungen."""

    def __init__(self, mixin_parent):
        super().__init__(mixin_parent)
        self.mixin = mixin_parent
        self.setWindowTitle("📅 Meine Besprechungen & Termine")
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        self.resize(560, 460)
        self.setStyleSheet(
            """
            QDialog {
                background-color: #0b111e;
                color: #f1f5f9;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QLabel {
                color: #f1f5f9;
            }
            """
        )
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        # Header
        title = QLabel("📅 Regelmäßige Besprechungen & Termine")
        title.setStyleSheet("font-size: 17px; font-weight: bold; color: #38bdf8;")
        sub = QLabel("Hier sind deine wiederkehrenden Telcos & Meetings gespeichert (lokal in ~/.config/deskimoni/meetings.json).")
        sub.setStyleSheet("font-size: 11px; color: #94a3b8;")
        layout.addWidget(title)
        layout.addWidget(sub)

        # Liste der Meetings
        self.items_layout = QVBoxLayout()
        self.items_layout.setSpacing(8)

        scroll_widget = QWidget()
        scroll_widget.setLayout(self.items_layout)
        scroll_widget.setStyleSheet("background: transparent;")

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(scroll_widget)
        scroll_area.setStyleSheet("QScrollArea { border: 1px solid #1e293b; border-radius: 8px; background-color: #0f172a; }")
        layout.addWidget(scroll_area)

        self.refresh_list()

        # Buttons
        btn_bar = QHBoxLayout()
        add_btn = QPushButton("➕ Neuen Termin hinzufügen...")
        add_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #2563eb;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 8px 14px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #3b82f6;
            }
            """
        )
        add_btn.clicked.connect(self.on_add_clicked)
        btn_bar.addWidget(add_btn)

        btn_bar.addStretch()

        close_btn = QPushButton("Fertig")
        close_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #334155;
                color: #f1f5f9;
                border: none;
                border-radius: 8px;
                padding: 8px 16px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #475569;
            }
            """
        )
        close_btn.clicked.connect(self.accept)
        btn_bar.addWidget(close_btn)

        layout.addLayout(btn_bar)

    def refresh_list(self):
        # Alle vorhandenen Widgets in items_layout entfernen
        while self.items_layout.count():
            item = self.items_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        days_de = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]

        for m in self.mixin.meetings:
            card = QFrame()
            card.setStyleSheet(
                """
                QFrame {
                    background-color: #1e293b;
                    border: 1px solid #334155;
                    border-radius: 8px;
                    padding: 8px;
                }
                """
            )
            h = QHBoxLayout(card)
            h.setContentsMargins(8, 8, 8, 8)

            # Checkbox für Aktiv / Inaktiv
            cb = QCheckBox()
            cb.setChecked(m.get("enabled", True))
            cb.toggled.connect(lambda checked, mid=m["id"]: self.on_toggle_enabled(mid, checked))
            h.addWidget(cb)

            # Details
            info_layout = QVBoxLayout()
            t_str = m.get("time", "??:??")
            dow = m.get("day_of_week")
            if isinstance(dow, list):
                day_name = "Mo-Fr"
            elif isinstance(dow, int) and 0 <= dow < 7:
                day_name = days_de[dow]
            else:
                day_name = "Täglich"

            nth = m.get("monthly_nth")
            nth_str = f" (jeden {nth}. {day_name} im Monat)" if nth else ""

            lbl_title = QLabel(f"<b>{m.get('title')}</b> – {day_name}{nth_str} um {t_str} Uhr ({m.get('duration_mins', 45)} Min.)")
            lbl_title.setStyleSheet("font-size: 13px; color: #f8fafc;")
            lbl_sub = QLabel(m.get("subtext", ""))
            lbl_sub.setStyleSheet("font-size: 11px; color: #94a3b8;")

            info_layout.addWidget(lbl_title)
            info_layout.addWidget(lbl_sub)
            h.addLayout(info_layout, stretch=1)

            # Löschen Button (für benutzerdefinierte)
            if m.get("id") not in ("x3_runde", "x3_gross", "fakultaet"):
                del_btn = QPushButton("🗑️")
                del_btn.setToolTip("Termin löschen")
                del_btn.setStyleSheet("background: transparent; border: none; font-size: 14px;")
                del_btn.clicked.connect(lambda _, mid=m["id"]: self.on_delete(mid))
                h.addWidget(del_btn)

            self.items_layout.addWidget(card)

        self.items_layout.addStretch()

    def on_toggle_enabled(self, mid: str, checked: bool):
        for m in self.mixin.meetings:
            if m["id"] == mid:
                m["enabled"] = checked
                break
        self.mixin.save_meetings_data()

    def on_delete(self, mid: str):
        self.mixin.meetings = [m for m in self.mixin.meetings if m["id"] != mid]
        self.mixin.save_meetings_data()
        self.refresh_list()

    def on_add_clicked(self):
        title, ok = QInputDialog.getText(self, "Neuer Termin", "Titel des Meetings (z. B. Jour Fixe):")
        if not ok or not title.strip():
            return

        time_str, ok2 = QInputDialog.getText(self, "Uhrzeit", "Uhrzeit (HH:MM, z. B. 10:00):", text="10:00")
        if not ok2 or not time_str.strip():
            return

        days = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Mo-Fr (Täglich)"]
        day_chosen, ok3 = QInputDialog.getItem(self, "Wochentag", "Wann findet das Meeting statt?", days, 0, False)
        if not ok3:
            return

        dow = days.index(day_chosen)
        if dow == 5:
            dow = [0, 1, 2, 3, 4]

        new_entry = {
            "id": f"custom_{int(time.time())}",
            "title": title.strip(),
            "day_of_week": dow,
            "time": time_str.strip(),
            "monthly_nth": None,
            "duration_mins": 45,
            "subtext": "Eigenes Meeting",
            "enabled": True,
            "sarcasm_pre": [f"Gleich {title.strip()}! Kaffee bereithalten."],
            "sarcasm_start": [f"{title.strip()} läuft jetzt. Durchhalten!"]
        }
        self.mixin.meetings.append(new_entry)
        self.mixin.save_meetings_data()
        self.refresh_list()


class DeskimonMeetingBingoMixin:
    """Mixin für private Termine, Erinnerungen mit Sarkasmus & Telco-Bullshit-Bingo."""

    def init_meeting_bingo(self):
        self.meetings_file = os.path.expanduser("~/.config/deskimoni/meetings.json")
        self.meetings = []
        self.bingo_dialog = None
        self.meetings_last_check = 0.0
        self.meetings_fired_alerts = set()  # (date_str, meeting_id, 'pre'/'start')

        self.load_meetings_data()

    def load_meetings_data(self):
        """Lädt Meetings aus ~/.config/deskimoni/meetings.json oder legt Standard an."""
        try:
            if os.path.exists(self.meetings_file):
                with open(self.meetings_file, "r", encoding="utf-8") as f:
                    self.meetings = json.load(f)
            else:
                self.meetings = list(DEFAULT_MEETINGS)
                self.save_meetings_data()
        except Exception:
            self.meetings = list(DEFAULT_MEETINGS)

    def save_meetings_data(self):
        try:
            os.makedirs(os.path.dirname(self.meetings_file), exist_ok=True)
            with open(self.meetings_file, "w", encoding="utf-8") as f:
                json.dump(self.meetings, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ==========================================
    # --- 🎯 Büro-Bingo Steuerung ---
    # ==========================================
    def open_office_bingo(self):
        if self.bingo_dialog is None:
            self.bingo_dialog = OfficeBingoDialog(self, sound_engine=self.sound)
        self.bingo_dialog.show()
        self.bingo_dialog.raise_()
        self.bingo_dialog.activateWindow()
        self.sound.play_chirp("curious")
        self.show_bubble("🎯 Büro-Bingo geöffnet! Hör gut zu in deiner Telco!", 3.5)

    def open_manage_meetings(self):
        dialog = ManageMeetingsDialog(self)
        dialog.exec()

    # ==========================================
    # --- 60 FPS Check: Meeting Alerts ---
    # ==========================================
    def check_meeting_alerts(self, now: float):
        # Alle 15 Sekunden prüfen
        if now - self.meetings_last_check < 15.0:
            return
        self.meetings_last_check = now

        today = date.today()
        today_str = today.isoformat()
        now_dt = datetime.fromtimestamp(now)
        current_dow = today.weekday() # 0 = Montag, 1 = Dienstag, ...
        # Berechnen ob heute der N-te Wochentag im Monat ist (z. B. 1. Dienstag)
        day_of_month = today.day
        nth_weekday = (day_of_month - 1) // 7 + 1

        for m in self.meetings:
            if not m.get("enabled", True):
                continue

            dow = m.get("day_of_week")
            # Prüfen ob Wochentag passt
            match_dow = False
            if isinstance(dow, list) and current_dow in dow:
                match_dow = True
            elif isinstance(dow, int) and current_dow == dow:
                match_dow = True

            if not match_dow:
                continue

            # Prüfen auf monatlichen N-ten Tag (z. B. 1. Dienstag)
            nth = m.get("monthly_nth")
            if nth is not None and nth != nth_weekday:
                continue

            # Bei Überschneidung Große X3 vs normale X3: am 1. Dienstag nur die große X3 feuern
            if m["id"] == "x3_runde" and nth_weekday == 1:
                # Am 1. Dienstag läuft die große X3 Runde
                continue

            time_parts = m.get("time", "").split(":")
            if len(time_parts) != 2:
                continue

            m_hour = int(time_parts[0])
            m_minute = int(time_parts[1])

            meet_dt = now_dt.replace(hour=m_hour, minute=m_minute, second=0, microsecond=0)
            diff_secs = (meet_dt - now_dt).total_seconds()

            # 1. Vorwarnung: 5 Minuten vorher (zwischen 4 und 6 Minuten)
            pre_key = (today_str, m["id"], "pre")
            if 0 < diff_secs <= 330 and pre_key not in self.meetings_fired_alerts:
                self.meetings_fired_alerts.add(pre_key)
                self._trigger_meeting_alert(m, is_start=False)

            # 2. Start-Gong: Pünktlich zur Startzeit (zwischen -60s und +60s)
            start_key = (today_str, m["id"], "start")
            if -60 <= diff_secs <= 60 and start_key not in self.meetings_fired_alerts:
                self.meetings_fired_alerts.add(start_key)
                self._trigger_meeting_alert(m, is_start=True)

    def _trigger_meeting_alert(self, m: dict, is_start: bool):
        self.trigger_bounce(9.0)
        self.sound.play_chirp("curious")

        if is_start:
            pool = m.get("sarcasm_start", [f"{m.get('title')} startet jetzt!"])
            msg = random.choice(pool)
            self.show_bubble(f"🚨 {m.get('title')} beginnt JETZT!\n{msg}", 9.0)
            self.sound.speak(msg, "excited")
        else:
            pool = m.get("sarcasm_pre", [f"In 5 Minuten startet {m.get('title')}!"])
            msg = random.choice(pool)
            self.show_bubble(f"⏰ In 5 Minuten: {m.get('title')}\n{msg}", 8.0)
            self.sound.speak(msg, "happy")

    # ==========================================
    # --- Nächsten Termin ansagen ---
    # ==========================================
    def speak_next_meeting(self):
        next_m, diff_s = self.get_next_meeting()
        if not next_m:
            msg = "Du hast aktuell keine anstehenden Besprechungen eingetragen. Herrliche Ruhe!"
            self.show_bubble(f"📅 {msg}", 4.5)
            self.sound.speak(msg, "happy")
            return

        mins = int(diff_s // 60)
        hours = mins // 60
        rem_mins = mins % 60

        if hours > 24:
            days = hours // 24
            time_txt = f"in {days} Tagen"
        elif hours > 0:
            time_txt = f"in {hours} Stunden und {rem_mins} Minuten"
        else:
            time_txt = f"in {mins} Minuten"

        sub = next_m.get("subtext", "")
        reply = f"Dein nächster Termin ist '{next_m['title']}' ({time_txt}, um {next_m['time']} Uhr). {sub}"
        self.trigger_bounce(6.0)
        self.sound.play_chirp("happy")
        self.show_bubble(f"📅 Nächster Termin:\n{next_m['title']} um {next_m['time']} Uhr ({time_txt})\n{sub}", 7.0)
        self.sound.speak(reply, "happy")

    def get_next_meeting(self) -> tuple:
        """Ermittelt den zeitlich nächsten aktiven Termin."""
        now_dt = datetime.now()
        candidates = []

        for m in self.meetings:
            if not m.get("enabled", True):
                continue
            time_parts = m.get("time", "").split(":")
            if len(time_parts) != 2:
                continue
            th, tm = int(time_parts[0]), int(time_parts[1])
            dow_list = m.get("day_of_week")
            if isinstance(dow_list, int):
                dow_list = [dow_list]
            elif not isinstance(dow_list, list):
                dow_list = [0, 1, 2, 3, 4]

            # In den nächsten 14 Tagen suchen
            for d_offset in range(14):
                chk_date = (now_dt + timedelta(days=d_offset)).date()
                if chk_date.weekday() in dow_list:
                    nth = m.get("monthly_nth")
                    if nth is not None:
                        nth_cur = (chk_date.day - 1) // 7 + 1
                        if nth != nth_cur:
                            continue
                    cand_dt = datetime(chk_date.year, chk_date.month, chk_date.day, th, tm)
                    diff = (cand_dt - now_dt).total_seconds()
                    if diff > 0:
                        candidates.append((diff, m, cand_dt))
                        break

        if not candidates:
            return None, 0.0

        candidates.sort(key=lambda x: x[0])
        best = candidates[0]
        return best[1], best[0]
