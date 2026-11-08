#!/usr/bin/env python3
"""
Deskimoni v2 - Memory & Settings Dialogs Mixin
Verwaltet das lokale Gedächtnis (memory.json), Namen und Fakten.
"""

import os
import json
from datetime import datetime

from deskimoni_core.qt import (
    QInputDialog,
    QMessageBox,
)

from deskimoni_core.config import log_event


class DeskimonMemoryMixin:
    """Mixin für Bot- und Nutzer-Gedächtnis sowie Einstellungs-Dialoge."""

    def get_memory_path(self) -> str:
        return os.path.expanduser("~/.config/deskimoni/memory.json")

    def load_memory(self):
        """Lädt dauerhafte Erinnerungen und Identität aus memory.json."""
        path = self.get_memory_path()
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    self.bot_name = str(data.get("bot_name", self.bot_name)).strip() or "Deskimoni"
                    self.user_name = str(data.get("user_name", self.user_name)).strip() or "Freund"
                    raw_facts = data.get("facts", [])
                    if isinstance(raw_facts, list):
                        self.user_facts = [str(x).strip() for x in raw_facts if str(x).strip()]
            else:
                self.user_facts = [
                    "Mag einen aufgeräumten und freundlichen Desktop",
                ]
                self.save_memory()
        except Exception as e:
            log_event(f"Fehler beim Laden von memory.json: {e}")

    def save_memory(self):
        """Speichert Identität und Fakten dauerhaft in memory.json."""
        path = self.get_memory_path()
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            data = {
                "bot_name": self.bot_name,
                "user_name": self.user_name,
                "facts": self.user_facts,
                "updated_at": datetime.now().isoformat(),
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            if hasattr(os, "chmod"):
                try:
                    os.chmod(path, 0o600)
                except Exception:
                    pass
        except Exception as e:
            log_event(f"Fehler beim Speichern von memory.json: {e}")

    def add_memory_fact(self, fact: str) -> bool:
        fact = fact.strip()
        if not fact:
            return False
        if fact not in self.user_facts:
            self.user_facts.append(fact)
            self.save_memory()
            return True
        return False

    def clear_memory(self):
        self.user_facts = []
        self.save_memory()

    def prompt_set_bot_name(self):
        new_name, ok = QInputDialog.getText(
            self,
            "🏷️ Meinen Namen ändern",
            "Wie möchtest du mich nennen?",
            text=self.bot_name,
        )
        if ok and new_name.strip():
            self.bot_name = new_name.strip()
            self.setWindowTitle(self.bot_name)
            self.save_memory()
            self.save_user_settings()
            self.trigger_bounce(8.0)
            self.sound.play_chirp("love")
            msg = f"Juhu! Ab jetzt heiße ich {self.bot_name}! Danke, {self.user_name}! ✨"
            self.show_bubble(msg, 5.0)
            self.sound.speak(f"Danke! Ab jetzt heiße ich {self.bot_name}!", "love")

    def prompt_set_user_name(self):
        new_name, ok = QInputDialog.getText(
            self,
            "👤 Deinen Namen einstellen",
            "Wie darf ich dich nennen?",
            text=self.user_name if self.user_name != "Freund" else "",
        )
        if ok and new_name.strip():
            self.user_name = new_name.strip()
            self.save_memory()
            self.save_user_settings()
            self.trigger_bounce(7.0)
            self.sound.play_chirp("happy")
            msg = f"Freut mich sehr, {self.user_name}! Ich habe mir deinen Namen fest gemerkt! 😊"
            self.show_bubble(msg, 5.0)
            self.sound.speak(f"Sehr angenehm, {self.user_name}! Ich habe mir deinen Namen gemerkt.", "happy")

    def show_memory_dialog(self):
        facts_text = "\n".join(f"• {f}" for f in self.user_facts) if self.user_facts else "Noch keine besonderen Fakten notiert."
        text = (
            f"🤖 Mein Name: {self.bot_name}\n"
            f"👤 Dein Name: {self.user_name}\n\n"
            f"📝 Was ich über dich und mich weiß:\n{facts_text}\n\n"
            f"💡 Befehle im Chat oder per Sprache:\n"
            f"• „Du heißt ab jetzt Pixel“\n"
            f"• „Ich heiße Alex“\n"
            f"• „Merk dir: Ich trinke gerne Tee“\n"
            f"• „Wer bist du?“ / „Was weißt du über mich?“"
        )
        QMessageBox.information(self, f"🧠 Gedächtnis von {self.bot_name}", text)

    def prompt_add_fact_dialog(self):
        fact, ok = QInputDialog.getText(
            self,
            "➕ Fakt ins Gedächtnis schreiben",
            f"Was soll sich {self.bot_name} über dich merken?",
            text="Trinkt gerne Espresso",
        )
        if ok and fact.strip():
            if self.add_memory_fact(fact.strip()):
                self.show_bubble(f"🧠 Gemerkt: „{fact.strip()}“!", 4.0)
                self.sound.speak("Alles klar, das habe ich mir in mein Gedächtnis notiert!", "happy")

    def prompt_clear_memory(self):
        res = QMessageBox.question(
            self,
            "🗑️ Gedächtnis zurücksetzen",
            f"Möchtest du wirklich alle gespeicherten Notizen von {self.bot_name} löschen?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if res == QMessageBox.StandardButton.Yes:
            self.clear_memory()
            self.show_bubble("🧠 Gedächtnis wurde geleert!", 3.0)
