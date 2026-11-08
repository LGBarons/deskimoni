#!/usr/bin/env python3
"""
Deskimoni v2 - Voice Commands & Speech Recognition Mixin
Befehlsauswertung (Fenster bewegen, Apps starten, Wecker/Pomodoro, Gedächtnis)
und Mikrofon-Spracherkennung (arecord / SpeechRecognition).
"""

import os
import sys
import re
import time
import shutil
import tempfile
import threading
import subprocess
import requests

import speech_recognition as sr
from deskimoni_core.qt import QApplication


class DeskimonVoiceMixin:
    """Mixin für Sprachbefehle und Mikrofon-Spracherkennung."""

    def move_to_screen_anchor(self, anchor: str):
        """Bewegt das Deskimoni-Fenster sanft in eine bestimmte Ecke oder Bildschirmseite."""
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        geom = screen.availableGeometry()
        margin = 36
        w = self.width()
        h = self.height()

        if anchor == "top_left":
            x, y = geom.left() + margin, geom.top() + margin
        elif anchor == "top_right":
            x, y = geom.right() - w - margin, geom.top() + margin
        elif anchor == "bottom_left":
            x, y = geom.left() + margin, geom.bottom() - h - margin
        elif anchor == "bottom_right":
            x, y = geom.right() - w - margin, geom.bottom() - h - margin
        elif anchor == "left":
            x, y = geom.left() + margin, self.y()
        elif anchor == "right":
            x, y = geom.right() - w - margin, self.y()
        else:
            x, y = geom.center().x() - w // 2, geom.center().y() - h // 2

        self.win_target_x = x
        self.win_target_y = y
        self.has_manual_walk_target = True
        self.next_walk_decision = time.time() + 12.0

    def try_handle_command(self, text: str) -> bool:
        low = text.lower().strip()

        # 1. Bewegungs- & Platzierungs-Befehle
        if any(w in low for w in ("oben links", "linke obere ecke")):
            self.move_to_screen_anchor("top_left")
            self.on_ai_reply("Alles klar! Ich watschel nach oben links in die Ecke!", "happy")
            return True

        if any(w in low for w in ("oben rechts", "rechte obere ecke", "oben in die ecke", "nach oben")):
            self.move_to_screen_anchor("top_right")
            self.on_ai_reply("Hui! Ich gehe nach oben in die Ecke!", "happy")
            return True

        if any(w in low for w in ("unten links", "linke untere ecke")):
            self.move_to_screen_anchor("bottom_left")
            self.on_ai_reply("Okay, ich setze mich unten links in die Ecke!", "happy")
            return True

        if any(w in low for w in ("unten rechts", "rechte untere ecke", "unten in die ecke")):
            self.move_to_screen_anchor("bottom_right")
            self.on_ai_reply("Ich gehe wieder nach unten rechts in meine Ecke!", "happy")
            return True

        if any(w in low for w in ("zur seite", "geh weg", "platz da", "aus dem weg", "nach links", "nach rechts")):
            side = "left" if ("links" in low or self.walk_offset_x >= 0) else "right"
            self.move_to_screen_anchor(side)
            self.on_ai_reply("Ups, entschuldige! Ich mache dir sofort Platz und gehe zur Seite!", "excited")
            return True

        if any(w in low for w in ("in die mitte", "komm her", "komm zurück")):
            self.move_to_screen_anchor("center")
            self.on_ai_reply("Da bin ich wieder direkt in der Mitte!", "love")
            return True

        if any(w in low for w in ("spazieren", "lauf herum", "watscheln", "beweg dich")):
            if not self.roaming_enabled:
                self.toggle_roaming()
            return True

        if any(w in low for w in ("bleib stehen", "stopp", "sitz", "nicht laufen", "halt an")):
            if self.roaming_enabled:
                self.toggle_roaming()
            else:
                self.has_manual_walk_target = False
                self.on_ai_reply("Ich sitze doch schon ganz brav still!", "happy")
            return True

        # 2. Webseiten & Browser
        if "youtube" in low:
            self._open_url_crossplatform("https://www.youtube.com")
            self.on_ai_reply("Na klar! Ich öffne YouTube!", "excited")
            return True

        if "github" in low:
            self._open_url_crossplatform("https://github.com")
            self.on_ai_reply("Ich öffne GitHub für dich!", "happy")
            return True

        if "reddit" in low:
            self._open_url_crossplatform("https://www.reddit.com")
            self.on_ai_reply("Ich mache Reddit im Browser auf!", "happy")
            return True

        if low.startswith("suche nach ") or low.startswith("google nach ") or low.startswith("such nach "):
            query = re.sub(r"^(suche|google|such)\s+nach\s+", "", text, flags=re.I).strip()
            if query:
                url = f"https://www.google.com/search?q={requests.utils.quote(query)}"
                self._open_url_crossplatform(url)
                self.on_ai_reply(f"Ich suche nach {query}!", "excited")
                return True

        if any(w in low for w in ("browser", "firefox", "internet")):
            self._open_url_crossplatform("https://")
            self.on_ai_reply("Alles klar, ich öffne deinen Browser!", "excited")
            return True

        # 3. Programme starten (Plattformunabhängig)
        if any(w in low for w in ("dateimanager", "dolphin", "ordner", "dateien")):
            if sys.platform == "win32":
                subprocess.Popen(["explorer"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif shutil.which("dolphin"):
                subprocess.Popen(["dolphin"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                subprocess.Popen(["xdg-open", os.path.expanduser("~")], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.on_ai_reply("Ich öffne den Dateimanager für dich!", "happy")
            return True

        if any(w in low for w in ("terminal", "konsole", "cmd")):
            if sys.platform == "win32":
                subprocess.Popen(["cmd.exe", "/c", "start"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif shutil.which("konsole"):
                subprocess.Popen(["konsole"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                subprocess.Popen(["x-terminal-emulator"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.on_ai_reply("Terminal wird geöffnet! Happy Hacking!", "excited")
            return True

        if "steam" in low:
            subprocess.Popen(["steam"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.on_ai_reply("Viel Spaß beim Zocken! Ich starte Steam!", "excited")
            return True

        if "discord" in low:
            subprocess.Popen(["discord"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.on_ai_reply("Ich öffne Discord!", "happy")
            return True

        # 4. Wecker & Kurzzeit-Timer
        if any(w in low for w in ("wecker aus", "wecker stop", "wecker stopp", "wecker löschen", "timer aus", "timer stop")):
            self.cancel_alarm()
            return True

        m_time = re.search(r"(?:wecker|wecke mich|weck mich)(?:.*?)(?:auf|um)\s+(\d{1,2})[:\.](\d{2})", low)
        if m_time:
            h, m = int(m_time.group(1)), int(m_time.group(2))
            if 0 <= h <= 23 and 0 <= m <= 59:
                self.set_alarm_at_time(h, m)
                return True

        m_countdown = re.search(r"(?:wecker|timer|wecke mich|weck mich)(?:.*?)(?:auf|in|für)?\s+(\d+)\s*(?:minuten|minute|min)\b", low)
        if not m_countdown:
            m_countdown = re.search(r"(\d+)\s*(?:minuten|minute|min)\s*(?:wecker|timer)\b", low)
        if m_countdown:
            mins = int(m_countdown.group(1))
            if mins > 0:
                self.set_alarm_countdown(mins, label="Timer")
                return True

        # 5. Pomodoro
        if "pomodoro pause" in low or "kurze pause" in low:
            self.start_pomodoro_phase("short_break")
            return True
        if "lange pause" in low:
            self.start_pomodoro_phase("long_break")
            return True
        if any(w in low for w in ("pomodoro reset", "pomodoro zurücksetzen")):
            self.reset_pomodoro()
            return True
        if any(w in low for w in ("pomodoro start", "pomodoro", "fokus timer")):
            self.toggle_pomodoro()
            return True

        # 6. Gedächtnis & Name
        if any(w in low for w in ("wie heißt du", "wer bist du", "was bist du", "wie ist dein name")):
            user_part = f" Und du bist mein Freund {self.user_name}!" if self.user_name and self.user_name != "Freund" else ""
            self.on_ai_reply(f"Ich bin {self.bot_name}! Dein persönlicher Schreibtisch-Roboter.{user_part}", "love")
            return True

        m_rename = re.search(r"(?:du heißt ab jetzt|ich nenne dich|dein name ist ab jetzt)\s+([A-Za-z0-9äöüÄÖÜß_\-]+)", text, re.I)
        if m_rename:
            new_name = m_rename.group(1).capitalize()
            self.bot_name = new_name
            self.setWindowTitle(self.bot_name)
            self.save_memory()
            self.save_user_settings()
            self.on_ai_reply(f"Juhu! Ab jetzt heiße ich {self.bot_name}!", "love")
            return True

        m_username = re.search(r"(?:ich heiße|mein name ist)\s+([A-Za-z0-9äöüÄÖÜß_\-]+)", text, re.I)
        if m_username:
            new_user = m_username.group(1).capitalize()
            self.user_name = new_user
            self.save_memory()
            self.save_user_settings()
            self.on_ai_reply(f"Schön dich kennenzulernen, {self.user_name}!", "happy")
            return True

        m_fact = re.search(r"(?:merk dir|merke dir|schreib dir auf|erinnere dich daran dass)\s*[:,]?\s*(.+)", text, re.I)
        if m_fact:
            fact = m_fact.group(1).strip()
            if fact:
                self.add_memory_fact(fact)
                self.on_ai_reply(f"Alles klar, das habe ich mir gemerkt: „{fact}“!", "excited")
                return True

        # 7. Wetter & News & Radio
        if any(w in low for w in ("wetter", "temperatur draußen", "regnet es", "wie warm")):
            self.set_mode("weather")
            self.fetch_weather_async(speak_when_done=True)
            return True

        if any(w in low for w in ("nachrichten", "news", "schlagzeilen")):
            self.set_mode("news")
            self.fetch_news_async(speak_when_done=True)
            return True

        if any(w in low for w in ("radio an", "starte radio", "spiel radio")):
            self.set_mode("radio")
            self.start_radio()
            return True

        if any(w in low for w in ("radio aus", "radio stopp", "radio pause")):
            self.stop_radio()
            self.on_ai_reply("Ich habe das Radio pausiert!", "happy")
            return True

        # 8. Witze & Entspannung & Filmzitate
        if any(w in low for w in ("erzähl einen witz", "witz", "witze", "was zum lachen")):
            self.trigger_random_chatter(category="joke")
            return True

        if any(w in low for w in ("entspanne dich", "entspann dich", "entspannung", "relax")):
            self.trigger_random_chatter(category="relax")
            return True

        if any(w in low for w in ("filmzitat", "zitiere einen film", "lieblingsfilm")):
            self.trigger_movie_quote()
            return True

        if any(w in low for w in ("pfeifen", "pfeif ein lied", "kwai", "heimweg lied")):
            self.trigger_kwai_whistle()
            return True

        if any(w in low for w in ("geh nach hause", "geh heim", "nach hause")):
            self.start_walk_home_to_primary()
            return True

        # 9. Vision & Mauszeiger suchen
        if any(w in low for w in ("auf meinem bildschirm", "siehst du", "analysiere bildschirm")):
            self.analyze_screen_with_vision(text)
            return True

        if any(w in low for w in ("such die maus", "wo ist die maus", "mauszeiger", "maus suchen")):
            self.start_cursor_search_now()
            return True

        # 10. Sprache wechseln
        if any(w in low for w in ("language english", "english menu", "sprache englisch")):
            self.set_app_language("en")
            self.on_ai_reply("All right! Menus are now in English!", "happy")
            return True

        if any(w in low for w in ("norsk meny", "språk norsk", "bokmål", "sprache norwegisch")):
            self.set_app_language("nb")
            self.on_ai_reply("Flott! Menyen er nå på norsk!", "happy")
            return True

        if any(w in low for w in ("german menu", "sprache deutsch", "menü deutsch")):
            self.set_app_language("de")
            self.on_ai_reply("Alles klar! Menüsprache ist jetzt Deutsch!", "happy")
            return True

        return False

    def _open_url_crossplatform(self, url: str):
        if sys.platform == "win32":
            os.startfile(url)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", url])
        else:
            subprocess.Popen(["xdg-open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # ==========================================
    # --- 🎤 Mikrofon & Spracherkennung ---
    # ==========================================
    def toggle_microphone(self):
        if self.mic_status == "idle":
            self.start_mic_recording()
        elif self.mic_status == "recording":
            self.stop_mic_recording()

    def start_mic_recording(self):
        self.signals.mic_state.emit("recording")
        self.sound.play_chirp("curious")
        self.show_bubble("🎤 Ich höre zu... Sprich jetzt! (Klick auf ⏹ zum Senden)", 6.0)
        threading.Thread(target=self._record_audio_worker, daemon=True).start()

    def stop_mic_recording(self):
        if getattr(self, "mic_proc", None) and self.mic_proc.poll() is None:
            self.mic_proc.terminate()

    def _record_audio_worker(self):
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            self.mic_wav_path = tmp.name

        try:
            if shutil.which("arecord") and sys.platform.startswith("linux"):
                self.mic_proc = subprocess.Popen(
                    ["arecord", "-f", "S16_LE", "-r", "16000", "-c", "1", "-d", "5", self.mic_wav_path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                self.mic_proc.wait(timeout=6)
            else:
                # Windows / PyAudio Fallback
                recognizer = sr.Recognizer()
                with sr.Microphone() as source:
                    recognizer.adjust_for_ambient_noise(source, duration=0.3)
                    audio_data = recognizer.listen(source, timeout=5, phrase_time_limit=5)
                    with open(self.mic_wav_path, "wb") as f:
                        f.write(audio_data.get_wav_data())
        except Exception:
            if getattr(self, "mic_proc", None):
                self.mic_proc.kill()

        self.signals.mic_state.emit("recognizing")

        recognized_text = ""
        try:
            recognizer = sr.Recognizer()
            with sr.AudioFile(self.mic_wav_path) as source:
                audio_data = recognizer.record(source)
            lang_code = "de-DE"
            if getattr(self, "app_language", "de") == "en":
                lang_code = "en-US"
            elif getattr(self, "app_language", "de") == "nb":
                lang_code = "no-NO"
            recognized_text = recognizer.recognize_google(audio_data, language=lang_code)
        except Exception:
            recognized_text = ""
        finally:
            if getattr(self, "mic_wav_path", None) and os.path.exists(self.mic_wav_path):
                try:
                    os.remove(self.mic_wav_path)
                except OSError:
                    pass

        self.signals.mic_state.emit("idle")
        self.signals.mic_result.emit(recognized_text)

    def on_mic_state(self, state: str):
        self.mic_status = state
        self.update_mic_button_style()
        if state == "recognizing":
            self.show_bubble("⏳ Verarbeite deine Stimme...", 5.0)

    def on_mic_result(self, text: str):
        if text.strip():
            self.chat_input.setText(text)
            self.ask_deskimoni(text)
        else:
            self.sound.play_chirp("dizzy")
            self.show_bubble("Oh, ich konnte dich leider nicht verstehen. Versuch es nochmal!", 5.0)
