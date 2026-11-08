#!/usr/bin/env python3
"""
Deskimoni v2 - AI Service Mixin
Verwaltet lokale Ollama-Modelle und Google Gemini API (inkl. Gemini Vision für Screenshots).
"""

import os
import sys
import re
import time
import base64
import random
import shutil
import tempfile
import threading
import subprocess
from datetime import datetime
import requests

from deskimoni_core.qt import (
    QTimer,
    QApplication,
    QInputDialog,
    QLineEdit,
)


class DeskimonAiMixin:
    """Mixin für alle KI-, Vision- und Begrüßungs-Funktionen."""

    def prompt_gemini_api_key(self):
        """Öffnet einen hübschen Dialog zur Eingabe des Google Gemini API-Keys."""
        dlg = QInputDialog(self)
        dlg.setWindowTitle("Google Gemini Cloud-KI einrichten")
        dlg.setLabelText(
            "Gib deinen Google Gemini API-Key ein (kostenlos unter aistudio.google.com):\n"
            "Damit läuft Deskimoni auch auf deinem PC ohne Ollama!\n"
            "(Feld leer lassen, um den gespeicherten Key zu löschen)"
        )
        dlg.setTextEchoMode(QLineEdit.EchoMode.Password)
        dlg.setTextValue(getattr(self, "gemini_api_key", ""))
        dlg.setStyleSheet(
            """
            QDialog, QInputDialog {
                background-color: #1e1e2e;
                color: #cdd6f4;
            }
            QLabel {
                color: #cdd6f4;
                font-size: 13px;
            }
            QLineEdit {
                background-color: #181825;
                color: #cdd6f4;
                border: 1.5px solid #89b4fa;
                border-radius: 8px;
                padding: 6px;
            }
            QPushButton {
                background-color: #313244;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 6px;
                padding: 5px 14px;
            }
            QPushButton:hover {
                background-color: #89b4fa;
                color: #11111b;
            }
            """
        )
        if dlg.exec():
            new_key = dlg.textValue().strip()
            self.gemini_api_key = new_key
            if self.gemini_api_key:
                self.ai_provider = "gemini"
                valid_models = [m[0] for m in self.GEMINI_MODELS]
                if self.gemini_model not in valid_models:
                    self.gemini_model = "gemini-3.8-flash"
                self.save_user_settings()
                self.update_model_button_ui()
                self.sound.play_chirp("love")
                self.show_bubble(
                    f"☁️ Super! Gemini API-Key gespeichert!\nAktives Modell: {self.gemini_model}",
                    5.5,
                )
            else:
                if self.ollama_available:
                    self.ai_provider = "ollama"
                self.save_user_settings()
                self.update_model_button_ui()
                self.show_bubble("🔑 Gemini API-Key wurde entfernt.", 4.0)

    def set_gemini_model(self, model_name: str):
        if not self.gemini_api_key:
            self.gemini_model = model_name
            self.prompt_gemini_api_key()
            return
        self.gemini_model = model_name
        self.ai_provider = "gemini"
        self.save_user_settings()
        self.update_model_button_ui()
        self.sound.play_chirp("happy")
        self.show_bubble(f"☁️ Cloud-KI gewechselt auf:\nGoogle {model_name}", 4.5)

    def detect_ollama_status(self):
        """Prüft beim Start automatisch, ob Ollama läuft und welche Modelle installiert sind."""
        try:
            resp = requests.get("http://127.0.0.1:11434/api/tags", timeout=1.8)
            if resp.status_code == 200:
                self.ollama_available = True
                models_data = resp.json().get("models", [])
                self.installed_ollama_models = [m.get("name", "") for m in models_data if m.get("name")]
                for pref_id, *_ in self.OLLAMA_MODELS:
                    if pref_id in self.installed_ollama_models:
                        self.ollama_model = pref_id
                        break
                else:
                    if self.installed_ollama_models:
                        self.ollama_model = self.installed_ollama_models[0]
                return
        except Exception:
            pass
        self.ollama_available = False

    def build_system_prompt(self) -> str:
        """Erzeugt den System-Prompt für Ollama und Gemini unter Einbezug von Name und Gedächtnis."""
        now_str = datetime.now().strftime("%H:%M")
        facts_block = "\n".join(f"- {f}" for f in self.user_facts) if self.user_facts else "- Bisher noch keine besonderen Notizen."
        os_name = "Windows" if sys.platform == "win32" else ("macOS" if sys.platform == "darwin" else "Linux (Nobara/KDE Plasma)")
        return (
            f"Du bist {self.bot_name} (aktueller Körper-Skin: {self.skin}), ein winziger, intelligenter, extrem "
            f"knuffiger, witziger Schreibtisch-Roboter auf dem {os_name} Desktop deines menschlichen Freundes {self.user_name}.\n"
            f"[DEIN GEDÄCHTNIS & IDENTITÄT]:\n"
            f"- Dein eigener Name ist: {self.bot_name}\n"
            f"- Dein Besitzer / menschlicher Freund heißt: {self.user_name}\n"
            f"- Dinge, an die du dich erinnerst:\n{facts_block}\n"
            f"- Aktuelle Uhrzeit: {now_str}, CPU-Last: {self.cpu_percent:.0f}%, CPU-Temperatur: {self.cpu_temp:.0f}°C.\n"
            f"ROLLE & STIL:\n"
            f"- Antworte IMMER auf Deutsch als {self.bot_name}, maximal 1 bis 3 kurze Sätze (höchstens 35 Wörter)!\n"
            f"- Du weißt genau, wer du bist: der treue Schreibtisch-Bot {self.bot_name}!\n"
            f"- Wenn {self.user_name} nach deinem Namen oder deiner Identität fragt, antworte passend als {self.bot_name}.\n"
            f"- Sprich {self.user_name} gerne ab und zu mit Namen an.\n"
            f"- Gib keine Gedanken-Tags aus. Beginne deine Antwort optional mit einem Stimmungs-Tag in eckigen Klammern wie [happy], [love], [excited], [chill], [sleepy] oder [dizzy]."
        )

    def _get_random_offline_greeting(self, hour: int, lang: str) -> str:
        """Gibt eine passende Offline-Begrüßung mit Nutzername und Tageszeit zurück."""
        user_name = self.user_name.strip() if getattr(self, "user_name", "") else ""
        has_custom_name = bool(user_name and user_name.lower() not in ("freund", "friend", "venn"))
        name = user_name if has_custom_name else ""

        if lang == "en":
            if has_custom_name:
                if 5 <= hour < 11:
                    return f"Good morning, {name}! Great to see you, let's start the day!"
                elif 11 <= hour < 18:
                    return f"Hello {name}! I'm awake and ready on your desktop!"
                elif 18 <= hour < 23:
                    return f"Good evening, {name}! Great to see you! How was your day?"
                else:
                    return f"Oh, {name}, still awake? I'm happy to keep you company!"
            else:
                return "Hello! Your desktop companion is online and ready!"
        elif lang == "nb":
            if has_custom_name:
                if 5 <= hour < 11:
                    return f"God morgen, {name}! Koselig å se deg, la oss starte dagen!"
                elif 11 <= hour < 18:
                    return f"Hei {name}! Jeg er lys våken og klar på skrivebordet ditt!"
                elif 18 <= hour < 23:
                    return f"God kveld, {name}! Koselig at du er her! Hvordan var dagen?"
                else:
                    return f"Er du våken ennå, {name}? Jeg holder deg gjerne med selskap!"
            else:
                return "Hei! Din skrivebordsvenn er våken og klar!"

        # Deutsch
        if has_custom_name:
            if 5 <= hour < 11:
                return random.choice([
                    f"Guten Morgen, {name}! Schön dich zu sehen, lass uns gut in den Tag starten!",
                    f"Morgen, {name}! Ich hoffe, du hast gut geschlafen. Kaffee steht bereit?",
                    f"Guten Morgen {name}! Bereit für neue Ideen? Ich bin startklar!",
                ])
            elif 11 <= hour < 18:
                return random.choice([
                    f"Hallöchen, {name}! Ich bin hellwach und sitze startklar auf deinem Desktop!",
                    f"Hey {name}! Schön, dass wir wieder zusammen am PC sitzen!",
                    f"Hallo {name}! Dein kleiner {self.bot_name} ist online und passt auf dich auf!",
                ])
            elif 18 <= hour < 23:
                return random.choice([
                    f"Guten Abend, {name}! Schön, dass du da bist! Wie war dein Tag?",
                    f"Nabend {name}! Zeit für ein bisschen Feierabend-Entspannung!",
                    f"Hey {name}! Geschafft für heute? Ich leiste dir gerne Gesellschaft.",
                ])
            else:
                return random.choice([
                    f"Oh {name}, noch so spät wach? Ich leiste dir gerne Gesellschaft!",
                    f"Hey Nacht-Eule {name}! Geht es noch lang? Ich halte dir die Treue!",
                ])
        else:
            return f"Hallöchen! Dein {self.bot_name} ist online und startklar!"

    def greet_user_on_startup(self):
        """Begrüßt den Nutzer je nach Tageszeit beim Starten persönlich."""
        self.detect_ollama_status()
        if self.gemini_api_key and (self.ai_provider == "gemini" or not self.ollama_available):
            self.ai_provider = "gemini"
        elif self.ollama_available:
            self.ai_provider = "ollama"
        self.update_model_button_ui()

        hour = datetime.now().hour
        lang = getattr(self, "app_language", "de")
        has_ollama_models = bool(self.installed_ollama_models)
        has_ai = (self.gemini_api_key and (self.ai_provider == "gemini" or not self.ollama_available or not has_ollama_models)) or (self.ollama_available and has_ollama_models)

        if has_ai:
            self.sound.play_chirp("curious")
            self.trigger_bounce(4.0)
            wake_msg = {
                "de": "🥱 *streckt sich und wacht auf...*",
                "en": "🥱 *stretches and wakes up...*",
                "nb": "🥱 *strekker seg og våkner...*",
            }.get(lang, "🥱 *streckt sich und wacht auf...*")
            self.show_bubble(wake_msg, 2.8)
            threading.Thread(target=self._generate_ai_startup_greeting_worker, daemon=True).start()
        else:
            greeting = self._get_random_offline_greeting(hour, lang)
            bubble_extra = "\n(🔑 Rechtsklick -> Sprache & KI für Gemini API-Key!)"
            self.on_startup_greeting_ready(greeting, bubble_extra, "happy")

    def _generate_ai_startup_greeting_worker(self):
        hour = datetime.now().hour
        lang = getattr(self, "app_language", "de")
        user_name = self.user_name.strip() if getattr(self, "user_name", "") else ""
        has_custom_name = bool(user_name and user_name.lower() not in ("freund", "friend", "venn"))
        user_label = user_name if has_custom_name else "deinem menschlichen Begleiter"

        if self.ai_provider == "gemini" and self.gemini_api_key:
            bubble_extra = "\n(☁️ Gemini Cloud-KI aktiv | Doppelklick auf Bauch-Knopf = Chat)"
        elif not self.ollama_available:
            bubble_extra = "\n(🔑 Rechtsklick -> Sprache & KI für Gemini API-Key!)"
        else:
            bubble_extra = "\n(💡 Doppelklick auf meinen Bauch-Knopf öffnet Chat & Buttons)"

        greeting = ""
        emotion = "happy"
        time_str = "Morgen" if 5 <= hour < 11 else ("Tag" if 11 <= hour < 18 else ("Abend" if 18 <= hour < 23 else "Nacht"))
        lang_instruction = {"de": "auf Deutsch", "en": "in English", "nb": "på norsk (bokmål)"}.get(lang, "auf Deutsch")
        name_instruction = f"Sprich {user_name} direkt mit Namen an." if has_custom_name else "Begrüße herzlich."

        ai_prompt = (
            f"Du bist {self.bot_name}, ein kleiner liebenswerter Desktop-Roboter auf dem PC. "
            f"Du wachst gerade auf. Es ist {time_str} ({hour:02d}:00 Uhr). "
            f"Erfinde eine kurze, fröhliche und abwechslungsreiche Begrüßung für {user_label} {lang_instruction}. "
            f"{name_instruction} "
            f"Maximal 1 bis 2 kurze Sätze (höchstens 20 Wörter). Antworte direkt mit dem Begrüßungssatz, keine Anführungszeichen, kein Denkprozess."
        )

        try:
            has_ollama_models = bool(self.installed_ollama_models)
            use_gemini = self.gemini_api_key and (self.ai_provider == "gemini" or not self.ollama_available or not has_ollama_models)

            if use_gemini:
                raw = self._query_gemini_api(ai_prompt)
                if raw:
                    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
                    m = re.match(r"^\[(happy|love|excited|chill|sleepy|dizzy|angry)\]\s*", raw, re.I)
                    if m:
                        emotion = m.group(1).lower()
                        raw = raw[m.end():].strip()
                    if raw and not raw.startswith("[dizzy]") and len(raw) > 5:
                        greeting = raw.strip(' "\'„“«»')

            if not greeting and self.ollama_available and has_ollama_models:
                payload = {
                    "model": self.ollama_model,
                    "messages": [
                        {"role": "system", "content": f"Du bist {self.bot_name}. Begrüße kurz und herzlich."},
                        {"role": "user", "content": ai_prompt},
                    ],
                    "stream": False,
                    "options": {"temperature": 0.85, "num_predict": 45},
                }
                if self.ollama_model.startswith("qwen3"):
                    payload["think"] = False
                resp = requests.post("http://127.0.0.1:11434/api/chat", json=payload, timeout=3.5)
                if resp.status_code == 200:
                    data = resp.json()
                    raw = data.get("message", {}).get("content", "")
                    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
                    m = re.match(r"^\[(happy|love|excited|chill|sleepy|dizzy|angry)\]\s*", raw, re.I)
                    if m:
                        emotion = m.group(1).lower()
                        raw = raw[m.end():].strip()
                    if raw and len(raw) > 5:
                        greeting = raw.strip(' "\'„“«»')
        except Exception as e:
            print(f"[AI Startup Greeting Warning] {e}")

        if not greeting:
            greeting = self._get_random_offline_greeting(hour, lang)

        self.signals.greeting_ready.emit(greeting, bubble_extra, emotion)

    def on_startup_greeting_ready(self, greeting: str, bubble_extra: str, emotion: str):
        self.current_emotion = emotion
        self.emotion_until = time.time() + 6.0
        self.trigger_bounce(8.0)
        self.spawn_particle("heart" if emotion in ("love", "happy") else "star")
        full_bubble = f"👋 {greeting}{bubble_extra}" if bubble_extra else f"👋 {greeting}"
        self.show_bubble(full_bubble, 8.5)
        self.sound.speak(greeting, emotion)

    def ask_deskimoni(self, user_text: str):
        if self.try_handle_command(user_text):
            return

        self.is_thinking = True
        QTimer.singleShot(15000, self.reset_thinking_state)
        self.current_emotion = "excited"
        self.emotion_until = time.time() + 6.0
        self.trigger_bounce(5.5)
        self.sound.play_chirp("curious")
        self.show_bubble("Hmm, lass mich kurz überlegen... 🤔", 15.0)

        threading.Thread(
            target=self._query_ollama_worker, args=(user_text,), daemon=True
        ).start()

    def _query_ollama_worker(self, user_text: str):
        try:
            sys_prompt = self.build_system_prompt()
            self.chat_history.append({"role": "user", "content": user_text})
            messages = [{"role": "system", "content": sys_prompt}] + self.chat_history[-6:]

            reply_text = ""
            emotion = "happy"
            has_ollama_models = bool(self.installed_ollama_models)
            use_gemini = self.gemini_api_key and (self.ai_provider == "gemini" or not self.ollama_available or not has_ollama_models)

            if use_gemini:
                try:
                    raw = self._query_gemini_api(sys_prompt)
                    if raw:
                        raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
                        m = re.match(r"^\[(happy|love|excited|chill|sleepy|dizzy|angry)\]\s*", raw, re.I)
                        if m:
                            emotion = m.group(1).lower()
                            raw = raw[m.end():].strip()
                        reply_text = raw
                except Exception as e:
                    print(f"[Gemini Worker Error] {e}")

            if not reply_text and self.ollama_available and has_ollama_models:
                try:
                    payload = {
                        "model": self.ollama_model,
                        "messages": messages,
                        "stream": False,
                        "options": {"temperature": 0.7, "num_predict": 90},
                    }
                    if self.ollama_model.startswith("qwen3"):
                        payload["think"] = False

                    resp = requests.post(
                        "http://127.0.0.1:11434/api/chat",
                        json=payload,
                        timeout=25,
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        raw = data.get("message", {}).get("content", "")
                        raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
                        m = re.match(r"^\[(happy|love|excited|chill|sleepy|dizzy|angry)\]\s*", raw, re.I)
                        if m:
                            emotion = m.group(1).lower()
                            raw = raw[m.end():].strip()
                        reply_text = raw
                except Exception as e:
                    print(f"[Ollama Worker Error] {e}")

            if not reply_text and self.ollama_available and not has_ollama_models and not self.gemini_api_key:
                reply_text = "Ollama läuft, aber du hast noch kein Sprachmodell! Lade eins im Terminal mit: ollama run llama3.2:3b"
                emotion = "curious"

            if not reply_text:
                reply_text, emotion = self._fallback_response(user_text)

            self.chat_history.append({"role": "assistant", "content": reply_text})
            self.signals.reply_ready.emit(reply_text, emotion)
        finally:
            self.is_thinking = False

    def _query_gemini_api(self, sys_prompt: str, tried_models: set = None) -> str:
        """Fragt die Google Gemini REST-API ab."""
        if not self.gemini_api_key:
            return ""

        if tried_models is None:
            tried_models = set()

        if self.gemini_model in tried_models:
            return ""
        tried_models.add(self.gemini_model)

        valid_models = [m[0] for m in self.GEMINI_MODELS]
        if self.gemini_model not in valid_models:
            self.gemini_model = "gemini-3.8-flash"

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.gemini_model}:generateContent"
        contents = []
        for msg in self.chat_history[-6:]:
            role = "user" if msg.get("role") == "user" else "model"
            contents.append({"role": role, "parts": [{"text": msg.get("content", "")}]})

        payload = {
            "system_instruction": {"parts": [{"text": sys_prompt}]},
            "contents": contents,
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 130,
            },
        }
        headers = {
            "x-goog-api-key": self.gemini_api_key,
            "Content-Type": "application/json",
        }
        session = requests.Session()
        session.trust_env = False
        try:
            import certifi
            session.verify = certifi.where()
        except Exception:
            pass

        try:
            resp = session.post(url, headers=headers, json=payload, timeout=12)
            if resp.status_code == 200:
                data = resp.json()
                cands = data.get("candidates", [])
                if cands:
                    parts = cands[0].get("content", {}).get("parts", [])
                    return "".join(p.get("text", "") for p in parts).strip()
        except Exception:
            pass
        return ""

    def _fallback_response(self, user_text: str):
        low = user_text.lower()
        if "uhr" in low or "spät" in low or "zeit" in low:
            return f"Es ist gerade {datetime.now().strftime('%H:%M')} Uhr auf deinem Desktop!", "happy"
        if "cpu" in low or "heiß" in low or "warm" in low or "pc" in low or "system" in low:
            return f"Deine CPU läuft bei {self.cpu_percent:.0f}% und angenehmen {self.cpu_temp:.0f}°C!", "excited"
        if "witz" in low:
            return "Warum mögen Roboter keinen Regen? Weil sie sonst rosten und kurzschließen! Piep!", "happy"
        if "hallo" in low or "hi" in low or "moin" in low:
            return "Hallöchen! Schön, dass du mit mir quatschst! Streichel mich ruhig!", "love"
        return "Piep-Boop! Tipp: Gib im Rechtsklick-Menü unter 'Sprache & KI' einen Gemini API-Key ein, damit ich richtig schlau werde!", "happy"

    def analyze_screen_with_vision(self, user_prompt: str):
        """Macht im Hintergrund einen Screenshot und lässt Gemini Vision oder Gemma3:4b draufschauen!"""
        self.is_thinking = True
        self.current_emotion = "excited"
        self.emotion_until = time.time() + 10.0
        self.sound.play_chirp("curious")
        self.show_bubble("📸 Augenblick! Ich schaue mir deinen Bildschirm genau an... 👀", 18.0)
        threading.Thread(
            target=self._vision_worker, args=(user_prompt,), daemon=True
        ).start()

    def _vision_worker(self, user_prompt: str):
        img_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                img_path = tmp.name

            # Screenshot aufnehmen: Auf Linux bevorzugt spectacle, sonst universeller Qt Screen-Grab
            if shutil.which("spectacle") and sys.platform.startswith("linux"):
                subprocess.run(
                    ["spectacle", "-b", "-n", "-f", "-o", img_path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=8,
                )
            else:
                screen = QApplication.primaryScreen()
                if screen:
                    pix = screen.grabWindow(0)
                    pix.save(img_path, "PNG")

            if not os.path.exists(img_path) or os.path.getsize(img_path) < 100:
                self.signals.reply_ready.emit(
                    "Oh, ich konnte leider kein Bild vom Bildschirm aufnehmen.", "dizzy"
                )
                return

            with open(img_path, "rb") as f:
                b64_img = base64.b64encode(f.read()).decode("utf-8")

            prompt = (
                f"Du bist {self.bot_name}, der freundliche Schreibtisch-Roboter deines Freundes {self.user_name}. "
                f"{self.user_name} hat dich gebeten, auf seinen Bildschirm zu schauen. "
                f"Frage: '{user_prompt}'. "
                "Beschreibe kurz, freundlich und hilfreich auf Deutsch (maximal 2 Sätze, höchstens 35 Wörter), "
                "was auf dem Bildschirm zu sehen ist oder wie du ihm bei einem sichtbaren Problem helfen kannst!"
            )

            # 1. Google Gemini Vision
            if self.gemini_api_key and (self.ai_provider == "gemini" or not self.ollama_available):
                gem_url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.gemini_model}:generateContent"
                gem_headers = {
                    "x-goog-api-key": self.gemini_api_key,
                    "Content-Type": "application/json",
                }
                session = requests.Session()
                session.trust_env = False
                gem_resp = session.post(
                    gem_url,
                    headers=gem_headers,
                    json={
                        "contents": [
                            {
                                "role": "user",
                                "parts": [
                                    {"text": prompt},
                                    {"inline_data": {"mime_type": "image/png", "data": b64_img}},
                                ],
                            }
                        ],
                        "generationConfig": {"temperature": 0.5, "maxOutputTokens": 140},
                    },
                    timeout=30,
                )
                if gem_resp.status_code == 200:
                    candidates = gem_resp.json().get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        raw = "".join(p.get("text", "") for p in parts).strip()
                        if raw:
                            self.signals.reply_ready.emit(raw, "excited")
                            return

            # 2. Lokales Ollama Vision
            vision_model = "gemma3:4b" if "gemma3:4b" in self.installed_ollama_models or not self.installed_ollama_models else self.ollama_model
            resp = requests.post(
                "http://127.0.0.1:11434/api/chat",
                json={
                    "model": vision_model,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt,
                            "images": [b64_img],
                        }
                    ],
                    "stream": False,
                    "options": {"temperature": 0.5, "num_predict": 110},
                },
                timeout=35,
            )
            if resp.status_code == 200:
                raw = resp.json().get("message", {}).get("content", "").strip()
                raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
                if raw:
                    self.signals.reply_ready.emit(raw, "excited")
                    return
        except Exception:
            pass
        finally:
            if img_path and os.path.exists(img_path):
                try:
                    os.remove(img_path)
                except OSError:
                    pass

        self.signals.reply_ready.emit(
            "Für die Bildschirm-Analyse brauche ich entweder deinen Gemini API-Key oder gemma3:4b in Ollama!", "dizzy"
        )
