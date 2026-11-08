#!/usr/bin/env python3
"""
Deskimoni v2.1 - Quick-Launcher für eigene Apps, AppImages & Webseiten 🚀🎨
Verwaltet persönliche Programme, AppImages (z.B. Proggibe Bildbearbeitung) und eigene Webseiten:
- 100% private Speicherung in ~/.config/deskimoni/quicklaunch.json (nicht im Git-Repository!)
- Direktstart per Kontextmenü
- Sprachsteuerung ("Starte Proggibe", "Öffne Bildbearbeitung", "Öffne LGB Solutions")
- Verwaltung & Dateiauswahl über hübsches Qt-Fenster
"""

import os
import sys
import shutil
import json
import subprocess
from typing import List, Dict, Optional

from deskimoni_core.qt import (
    Qt, QTimer, QPoint, QPointF, QRectF, QSize,
    QColor, QFont, QPainter, QCursor, QIcon, QPen, QBrush,
    QAction, QWidget, QApplication, QLineEdit,
    QPushButton, QMenu, QInputDialog, QMessageBox,
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox,
    QScrollArea, QFrame, QFileDialog
)


DEFAULT_QUICKLAUNCH = [
    {
        "id": "proggibe",
        "name": "Proggibe",
        "type": "app",
        "target": "proggibe",
        "subtext": "Schnelle Bildbearbeitung (AppImage / Tool)",
        "keywords": ["proggibe", "bildbearbeitung", "bild bearbeiten", "fotos bearbeiten", "grafik"],
        "icon": "🎨"
    },
    {
        "id": "lgb_solutions",
        "name": "LGB-Solutions",
        "type": "web",
        "target": "https://lgb-solutions.icu",
        "subtext": "Freie, datensparsame Weblösungen",
        "keywords": ["lgb", "lgb solutions", "meine webseite", "lgb website"],
        "icon": "🌐"
    }
]


class AddQuickLaunchDialog(QDialog):
    """Dialog zum Hinzufügen oder Bearbeiten eines Programms / einer Webseite."""

    def __init__(self, parent=None, item: Optional[Dict] = None):
        super().__init__(parent)
        self.item = item or {}
        self.setWindowTitle("➕ Programm oder Webseite hinzufügen")
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        self.resize(460, 340)
        self.setStyleSheet(
            """
            QDialog {
                background-color: #0b111e;
                color: #f1f5f9;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QLabel {
                color: #f1f5f9;
                font-size: 12px;
            }
            QLineEdit {
                background-color: #1e293b;
                color: #f8fafc;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 6px 10px;
                font-size: 12px;
            }
            QLineEdit:focus {
                border-color: #38bdf8;
            }
            """
        )
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(18, 18, 18, 18)

        # Name
        layout.addWidget(QLabel("Name (z. B. Proggibe Bildbearbeitung):"))
        self.name_edit = QLineEdit(self.item.get("name", ""))
        layout.addWidget(self.name_edit)

        # Typ (App oder Web)
        layout.addWidget(QLabel("Typ:"))
        type_box = QHBoxLayout()
        self.btn_type_app = QPushButton("💻 Programm / AppImage / Skript")
        self.btn_type_web = QPushButton("🌐 Webseite / Webapp")
        for b in (self.btn_type_app, self.btn_type_web):
            b.setCheckable(True)
            b.setStyleSheet(
                """
                QPushButton {
                    background-color: #1e293b;
                    color: #cbd5e1;
                    border: 1px solid #334155;
                    border-radius: 8px;
                    padding: 6px 12px;
                    font-size: 11px;
                }
                QPushButton:checked {
                    background-color: #2563eb;
                    color: #ffffff;
                    border-color: #38bdf8;
                    font-weight: bold;
                }
                """
            )
        self.btn_type_app.clicked.connect(lambda: self._set_type("app"))
        self.btn_type_web.clicked.connect(lambda: self._set_type("web"))
        type_box.addWidget(self.btn_type_app)
        type_box.addWidget(self.btn_type_web)
        layout.addLayout(type_box)

        cur_type = self.item.get("type", "app")
        self._set_type(cur_type)

        # Ziel / Pfad / URL
        self.lbl_target = QLabel("Pfad zum Programm / AppImage oder Befehl:")
        layout.addWidget(self.lbl_target)

        target_box = QHBoxLayout()
        self.target_edit = QLineEdit(self.item.get("target", ""))
        target_box.addWidget(self.target_edit, stretch=1)

        self.browse_btn = QPushButton("📁 Durchsuchen...")
        self.browse_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #334155;
                color: #f1f5f9;
                border: none;
                border-radius: 8px;
                padding: 6px 12px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #475569;
            }
            """
        )
        self.browse_btn.clicked.connect(self.on_browse)
        target_box.addWidget(self.browse_btn)
        layout.addLayout(target_box)

        # Sprach-Stichworte
        layout.addWidget(QLabel("Sprach-Befehle (durch Komma getrennt, z. B. 'proggibe, bildbearbeitung'):"))
        kws = ", ".join(self.item.get("keywords", []))
        self.kws_edit = QLineEdit(kws)
        layout.addWidget(self.kws_edit)

        # Emoji / Icon
        layout.addWidget(QLabel("Icon / Emoji (z. B. 🎨, 🌐, 📸, 🚀):"))
        self.icon_edit = QLineEdit(self.item.get("icon", "🚀"))
        self.icon_edit.setMaxLength(4)
        layout.addWidget(self.icon_edit)

        layout.addStretch()

        # Buttons unten
        btn_bar = QHBoxLayout()
        btn_bar.addStretch()
        cancel_btn = QPushButton("Abbrechen")
        cancel_btn.setStyleSheet("background: transparent; color: #94a3b8; border: none; padding: 8px 14px;")
        cancel_btn.clicked.connect(self.reject)
        btn_bar.addWidget(cancel_btn)

        save_btn = QPushButton("Speichern")
        save_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #2563eb;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 8px 18px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #3b82f6;
            }
            """
        )
        save_btn.clicked.connect(self.on_save)
        btn_bar.addWidget(save_btn)
        layout.addLayout(btn_bar)

    def _set_type(self, t: str):
        self.current_type = t
        if t == "app":
            self.btn_type_app.setChecked(True)
            self.btn_type_web.setChecked(False)
            if hasattr(self, "lbl_target"):
                self.lbl_target.setText("Pfad zum Programm / AppImage oder Befehlsname:")
                self.browse_btn.setVisible(True)
                if not self.target_edit.text() or self.target_edit.text().startswith("http"):
                    self.target_edit.setPlaceholderText("z. B. proggibe oder /home/user/Applications/proggibe.AppImage")
        else:
            self.btn_type_app.setChecked(False)
            self.btn_type_web.setChecked(True)
            if hasattr(self, "lbl_target"):
                self.lbl_target.setText("Webseiten-URL (z. B. https://...):")
                self.browse_btn.setVisible(False)
                if not self.target_edit.text() or not self.target_edit.text().startswith("http"):
                    self.target_edit.setPlaceholderText("https://meine-seite.de")

    def on_browse(self):
        start_dir = os.path.expanduser("~/Applications")
        if not os.path.exists(start_dir):
            start_dir = os.path.expanduser("~")
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Programm oder AppImage auswählen",
            start_dir,
            "Programme (*.AppImage *.desktop *.*);;Alle Dateien (*)"
        )
        if file_path:
            self.target_edit.setText(file_path)
            if not self.name_edit.text():
                base_name = os.path.splitext(os.path.basename(file_path))[0]
                self.name_edit.setText(base_name.capitalize())

    def on_save(self):
        name = self.name_edit.text().strip()
        target = self.target_edit.text().strip()
        if not name or not target:
            QMessageBox.warning(self, "Fehlende Angaben", "Bitte gib mindestens einen Namen und ein Ziel an!")
            return

        kws = [k.strip().lower() for k in self.kws_edit.text().split(",") if k.strip()]
        if name.lower() not in kws:
            kws.insert(0, name.lower())

        icon = self.icon_edit.text().strip() or ("🎨" if self.current_type == "app" else "🌐")

        self.result_item = {
            "id": self.item.get("id") or f"custom_{int(os.times().elapsed * 1000)}",
            "name": name,
            "type": self.current_type,
            "target": target,
            "subtext": self.item.get("subtext") or ("Lokales Programm" if self.current_type == "app" else "Webseite"),
            "keywords": kws,
            "icon": icon
        }
        self.accept()


class ManageQuickLaunchDialog(QDialog):
    """Übersichts- und Verwaltungsfenster für eigene Apps & Webseiten."""

    def __init__(self, mixin_parent):
        super().__init__(mixin_parent)
        self.mixin = mixin_parent
        self.setWindowTitle("🚀 Meine Apps & Webseiten")
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        self.resize(540, 440)
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
        title = QLabel("🚀 Meine persönlichen Programme & Webseiten")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #38bdf8;")
        sub = QLabel("Starte eigene AppImages (wie Proggibe Bildbearbeitung) oder Webapps direkt per Klick oder Sprache!")
        sub.setStyleSheet("font-size: 11px; color: #94a3b8;")
        layout.addWidget(title)
        layout.addWidget(sub)

        # Scrollbare Liste
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
        add_btn = QPushButton("➕ Neue App / Webseite hinzufügen...")
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
        while self.items_layout.count():
            item = self.items_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for it in self.mixin.quicklaunch_items:
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

            # Icon
            lbl_icon = QLabel(it.get("icon", "🚀"))
            lbl_icon.setStyleSheet("font-size: 24px; padding-right: 6px;")
            h.addWidget(lbl_icon)

            # Info
            info = QVBoxLayout()
            lbl_name = QLabel(f"<b>{it.get('name')}</b> ({'Programm' if it.get('type') == 'app' else 'Weblink'})")
            lbl_name.setStyleSheet("font-size: 13px; color: #f8fafc;")
            lbl_target = QLabel(it.get("target", ""))
            lbl_target.setStyleSheet("font-size: 11px; color: #94a3b8;")
            info.addWidget(lbl_name)
            info.addWidget(lbl_target)
            h.addLayout(info, stretch=1)

            # Starten Button
            start_btn = QPushButton("▶ Starten")
            start_btn.setStyleSheet(
                """
                QPushButton {
                    background-color: #065f46;
                    color: #ecfdf5;
                    border: 1px solid #10b981;
                    border-radius: 6px;
                    padding: 5px 10px;
                    font-size: 11px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #047857;
                }
                """
            )
            start_btn.clicked.connect(lambda _, item=it: self.mixin.launch_quick_item(item))
            h.addWidget(start_btn)

            # Bearbeiten Button
            edit_btn = QPushButton("✏️")
            edit_btn.setToolTip("Bearbeiten")
            edit_btn.setStyleSheet("background: transparent; border: none; font-size: 13px;")
            edit_btn.clicked.connect(lambda _, item=it: self.on_edit_clicked(item))
            h.addWidget(edit_btn)

            # Löschen Button
            del_btn = QPushButton("🗑️")
            del_btn.setToolTip("Löschen")
            del_btn.setStyleSheet("background: transparent; border: none; font-size: 13px;")
            del_btn.clicked.connect(lambda _, item=it: self.on_delete_clicked(item))
            h.addWidget(del_btn)

            self.items_layout.addWidget(card)

        self.items_layout.addStretch()

    def on_add_clicked(self):
        diag = AddQuickLaunchDialog(self)
        if diag.exec() == QDialog.DialogCode.Accepted:
            self.mixin.quicklaunch_items.append(diag.result_item)
            self.mixin.save_quicklaunch_data()
            self.refresh_list()

    def on_edit_clicked(self, item: Dict):
        diag = AddQuickLaunchDialog(self, item=item)
        if diag.exec() == QDialog.DialogCode.Accepted:
            idx = self.mixin.quicklaunch_items.index(item)
            self.mixin.quicklaunch_items[idx] = diag.result_item
            self.mixin.save_quicklaunch_data()
            self.refresh_list()

    def on_delete_clicked(self, item: Dict):
        if QMessageBox.question(self, "Löschen", f"Möchtest du '{item.get('name')}' wirklich entfernen?") == QMessageBox.StandardButton.Yes:
            self.mixin.quicklaunch_items.remove(item)
            self.mixin.save_quicklaunch_data()
            self.refresh_list()


class DeskimonQuickLaunchMixin:
    """Mixin für persönliche Programme, AppImages und Webseiten."""

    def init_quicklaunch(self):
        self.quicklaunch_file = os.path.expanduser("~/.config/deskimoni/quicklaunch.json")
        self.quicklaunch_items: List[Dict] = []
        self.load_quicklaunch_data()

    def load_quicklaunch_data(self):
        try:
            if os.path.exists(self.quicklaunch_file):
                with open(self.quicklaunch_file, "r", encoding="utf-8") as f:
                    self.quicklaunch_items = json.load(f)
            else:
                self.quicklaunch_items = list(DEFAULT_QUICKLAUNCH)
                self.save_quicklaunch_data()
        except Exception:
            self.quicklaunch_items = list(DEFAULT_QUICKLAUNCH)

    def save_quicklaunch_data(self):
        try:
            os.makedirs(os.path.dirname(self.quicklaunch_file), exist_ok=True)
            with open(self.quicklaunch_file, "w", encoding="utf-8") as f:
                json.dump(self.quicklaunch_items, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def open_quicklaunch_dialog(self):
        diag = ManageQuickLaunchDialog(self)
        diag.exec()

    def prompt_add_quicklaunch(self):
        diag = AddQuickLaunchDialog(self)
        if diag.exec() == QDialog.DialogCode.Accepted:
            self.quicklaunch_items.append(diag.result_item)
            self.save_quicklaunch_data()
            self.show_bubble(f"✨ '{diag.result_item['name']}' zu Schnellstartern hinzugefügt!", 3.5)
            self.sound.play_chirp("happy")

    def launch_quick_item(self, item: Dict):
        target = item.get("target", "").strip()
        item_type = item.get("type", "app")
        name = item.get("name", "Tool")
        icon = item.get("icon", "🚀")

        self.trigger_bounce(6.0)
        self.sound.play_chirp("happy")

        # 1. Webseite / URL
        if item_type == "web" or target.startswith("http://") or target.startswith("https://"):
            self.show_bubble(f"{icon} Öffne {name} im Browser...", 3.5)
            self.sound.speak(f"Ich öffne {name} für dich!", "happy")
            self._open_url_crossplatform(target)
            return

        # 2. Lokales Programm / AppImage
        expanded_target = os.path.expanduser(target)

        # Prüfen ob Pfad direkt existiert (z.B. AppImage)
        resolved_path = None
        if os.path.isfile(expanded_target):
            resolved_path = expanded_target
        elif shutil.which(target):
            resolved_path = target
        else:
            # Häufige Nobara/Linux AppImage-Verzeichnisse durchsuchen
            candidates = [
                os.path.expanduser(f"~/Applications/{target}"),
                os.path.expanduser(f"~/Applications/{target}.AppImage"),
                os.path.expanduser(f"~/.local/bin/{target}"),
                os.path.expanduser(f"~/Downloads/{target}"),
                os.path.expanduser(f"~/Downloads/{target}.AppImage"),
            ]
            for cand in candidates:
                if os.path.isfile(cand):
                    resolved_path = cand
                    break

        if resolved_path:
            # Sicherstellen, dass Datei ausführbar ist
            if os.path.isfile(resolved_path) and not os.access(resolved_path, os.X_OK):
                try:
                    os.chmod(resolved_path, 0o755)
                except Exception:
                    pass

            try:
                subprocess.Popen(
                    [resolved_path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True
                )
                self.show_bubble(f"{icon} Starte {name}...", 3.5)
                self.sound.speak(f"Starte {name} für dich!", "happy")
            except Exception as e:
                self.show_bubble(f"⚠️ Fehler beim Starten von {name}: {e}", 4.5)
        else:
            self.show_bubble(f"⚠️ Konnte '{target}' nicht finden!\nBitte Pfad prüfen.", 4.5)
            self.sound.play_chirp("error")

    def handle_voice_quicklaunch(self, text_low: str) -> bool:
        """Prüft, ob der gesprochene Text zu einem Schnellstarter passt."""
        for item in self.quicklaunch_items:
            kws = item.get("keywords", [])
            name = item.get("name", "").lower()
            all_triggers = list(kws) + [name, f"starte {name}", f"öffne {name}"]

            for kw in all_triggers:
                if kw and kw in text_low:
                    self.launch_quick_item(item)
                    return True
        return False
