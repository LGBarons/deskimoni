#!/usr/bin/env python3
"""
Deskimoni - Interaktiver & Sprechender Desktop-Begleiter für KDE Plasma (Wayland / X11)
Inspiriert von den 3D-gedruckten ESP32-S3 Deskimon Schreibtisch-Bots.
Mit lokaler Ollama-KI, natürlicher deutscher Sprachausgabe, Sci-Fi Robot-Chirps & Mikrofon!
"""

import os
# Unter KDE Wayland sorgt XWayland (xcb) für echte Always-on-Top-Flags, globale Maus-Koordinaten und sanftes Über-den-Bildschirm-Watscheln!
if "QT_QPA_PLATFORM" not in os.environ:
    os.environ["QT_QPA_PLATFORM"] = "xcb"

try:
    import certifi
    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
    os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())
except Exception:
    pass
import re
import sys
import json
import math
import time
import wave
try:
    import fcntl
except ImportError:
    fcntl = None
import base64
import shutil
import struct
import random
import asyncio
import tempfile
import threading
import subprocess
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
import requests


def log_event(msg: str):
    """Schreibt Debug- und Statusmeldungen in die Konsole und in ~/.config/deskimoni/deskimoni.log."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        log_dir = os.path.expanduser("~/.config/deskimoni")
        os.makedirs(log_dir, exist_ok=True)
        with open(os.path.join(log_dir, "deskimoni.log"), "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass
import psutil
import speech_recognition as sr
import edge_tts

from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF, pyqtSignal, QObject, QSize
from PyQt6.QtGui import (
    QPainter,
    QColor,
    QPen,
    QBrush,
    QPainterPath,
    QLinearGradient,
    QRadialGradient,
    QFont,
    QAction,
    QActionGroup,
    QCursor,
    QRegion,
    QIcon,
)
from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QMenu,
    QSystemTrayIcon,
    QStyle,
    QLineEdit,
    QPushButton,
    QInputDialog,
    QMessageBox,
)


class WorkerSignals(QObject):
    reply_ready = pyqtSignal(str, str)          # (Antwort-Text, Emotion)
    greeting_ready = pyqtSignal(str, str, str)  # (Sprach-Text, Bubble-Zusatz, Emotion)
    speech_state = pyqtSignal(bool)             # True = spricht gerade (Lip-Sync aktiv)
    mic_state = pyqtSignal(str)                 # "idle", "recording", "recognizing"
    mic_result = pyqtSignal(str)                # Erkannter Text vom Mikrofon


class RobotSoundEngine:
    """Erzeugt süße R2D2 / Deskimon Piepser (Chirps) und natürliche deutsche Sprachausgabe."""

    VOICE_PROFILES = [
        ("kawaii_girl", "🧚 Kawaii Buddy (Maja – Süß & Hoch)", "de-DE-AmalaNeural", "+12%", "+24Hz"),
        ("cute_bot", "🤖 Cute Bot (Conrad – Hell & Flott)", "de-DE-ConradNeural", "+10%", "+18Hz"),
        ("katja_warm", "👩 Katja (Freundlich & Natürlich)", "de-DE-KatjaNeural", "+4%", "+0Hz"),
        ("conrad_normal", "👨 Conrad (Natürlich & Klar)", "de-DE-ConradNeural", "+4%", "+0Hz"),
        ("killian_cool", "😎 Killian (Lässig & Tief)", "de-DE-KillianNeural", "+0%", "-10Hz"),
        ("seraphina", "✨ Seraphina (Sanft & Modern)", "de-DE-SeraphinaMultilingualNeural", "+5%", "+6Hz"),
        ("florian", "🚀 Florian (Dynamisch)", "de-DE-FlorianMultilingualNeural", "+6%", "+4Hz"),
        ("retro_synth", "👾 Retro-Roboter (Offline eSpeak)", "espeak", "+0%", "+0Hz"),
    ]

    def __init__(self, signals: WorkerSignals):
        self.signals = signals
        self.voice_enabled = True
        self.chirps_enabled = True
        self.kwai_proc = None
        self.gohome_proc = None
        self.voice_id = "kawaii_girl"
        self.tts_voice = "de-DE-AmalaNeural"
        self.tts_rate = "+12%"
        self.tts_pitch = "+24Hz"

    def set_voice_profile(self, profile_id: str):
        for vid, _label, vname, rate, pitch in self.VOICE_PROFILES:
            if vid == profile_id:
                self.voice_id = vid
                self.tts_voice = vname
                self.tts_rate = rate
                self.tts_pitch = pitch
                break

    def play_chirp(self, mood="happy"):
        if not self.chirps_enabled:
            return
        threading.Thread(target=self._synth_chirp_blocking, args=(mood,), daemon=True).start()

    def _synth_chirp_blocking(self, mood="happy"):
        try:
            sample_rate = 24000
            if mood == "happy":
                notes = [(720, 980, 0.065), (980, 1320, 0.08)]
            elif mood == "love":
                notes = [(660, 880, 0.06), (880, 1175, 0.06), (1175, 1568, 0.09)]
            elif mood == "curious":
                notes = [(580, 1080, 0.11)]
            elif mood == "dizzy":
                notes = [(980, 520, 0.07), (820, 440, 0.08), (680, 390, 0.09)]
            elif mood == "alarm":
                notes = [(1046, 1318, 0.07), (1318, 1046, 0.07), (1046, 1318, 0.07), (1318, 1568, 0.12)]
            else:
                notes = [(680, 860, 0.055), (860, 740, 0.055)]

            frames = bytearray()
            for f_start, f_end, dur in notes:
                n_samples = int(sample_rate * dur)
                for i in range(n_samples):
                    t = i / sample_rate
                    prog = i / max(1, n_samples)
                    freq = f_start + (f_end - f_start) * prog
                    env = math.sin(prog * math.pi)
                    val = int(10500 * env * math.sin(2 * math.pi * freq * t))
                    frames.extend(struct.pack("<h", val))
                # Kurze Pause zwischen Piepsern
                frames.extend(b"\x00\x00" * int(sample_rate * 0.018))

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                wav_path = tmp.name

            with wave.open(wav_path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(bytes(frames))

            self._play_wav_file(wav_path, timeout=4)
            try:
                os.remove(wav_path)
            except Exception:
                pass
        except Exception:
            pass

    def _play_wav_file(self, wav_path: str, timeout: int = 5):
        """Spielt eine WAV-Datei mit dem besten verfügbaren Audio-Tool ab (pw-play, paplay, aplay)."""
        for tool in ["pw-play", "paplay", "aplay"]:
            if shutil.which(tool):
                try:
                    subprocess.run(
                        [tool, wav_path],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=timeout,
                    )
                    return
                except Exception:
                    pass

    def get_gohome_dir(self) -> str:
        return os.path.expanduser("~/.config/deskimoni/sounds/gohome")

    def ensure_gohome_dir(self) -> str:
        path = self.get_gohome_dir()
        try:
            os.makedirs(path, exist_ok=True)
            readme_path = os.path.join(path, "LIESMICH.txt")
            if not os.path.exists(readme_path):
                with open(readme_path, "w", encoding="utf-8") as f:
                    f.write(
                        "Deskimoni Heimweg-Musik\n"
                        "=======================\n\n"
                        "Lege hier beliebige Audio-Dateien (.mp3, .wav, .ogg, .flac, .m4a) ab.\n"
                        "Wenn Deskimoni nach Hause watschelt, wählt er zufällig ein Lied aus diesem Ordner ab!\n"
                    )
        except Exception:
            pass
        return path

    def get_gohome_audio_files(self) -> list:
        folder = self.ensure_gohome_dir()
        valid_exts = {".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac", ".opus", ".wma"}
        found = []
        if os.path.isdir(folder):
            try:
                for fname in os.listdir(folder):
                    ext = os.path.splitext(fname)[1].lower()
                    if ext in valid_exts:
                        found.append(os.path.join(folder, fname))
            except Exception:
                pass
        return sorted(found)

    def stop_gohome_music(self):
        """Stoppt die Wiedergabe des Heimweg-Liedes sofort."""
        proc = getattr(self, "gohome_proc", None) or getattr(self, "kwai_proc", None)
        if proc is not None:
            try:
                proc.terminate()
                proc.wait(timeout=0.4)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
            self.gohome_proc = None
            self.kwai_proc = None

    def stop_kwai_whistle(self):
        self.stop_gohome_music()

    def play_gohome_music(self):
        """Spielt ein Lied aus dem lokalen Heimweg-Ordner ab oder pfeift synthetisch (Fallback)."""
        self.stop_gohome_music()
        songs = self.get_gohome_audio_files()
        if songs:
            chosen = random.choice(songs)
            threading.Thread(target=self._play_gohome_file_process, args=(chosen,), daemon=True).start()
        else:
            threading.Thread(target=self._synth_kwai_whistle_blocking, daemon=True).start()

    def play_kwai_whistle(self):
        self.play_gohome_music()

    def _play_gohome_file_process(self, path: str):
        try:
            cmd = None
            if shutil.which("ffplay"):
                cmd = ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", path]
            elif shutil.which("mpv"):
                cmd = ["mpv", "--no-video", "--really-quiet", path]
            elif shutil.which("pw-play"):
                cmd = ["pw-play", path]
            if cmd:
                self.gohome_proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self.kwai_proc = self.gohome_proc
                self.gohome_proc.wait()
                self.gohome_proc = None
                self.kwai_proc = None
        except Exception:
            self.gohome_proc = None
            self.kwai_proc = None

    def _play_kwai_file_process(self, path: str):
        self._play_gohome_file_process(path)

    def _synth_kwai_whistle_blocking(self):
        """Synthetisiert die Colonel Bogey March Pfeif-Melodie mit weichem Vibrato und Hüllkurve."""
        try:
            sample_rate = 24000
            notes = [
                # freq, duration, pause_after
                (1046.5, 0.32, 0.02),
                (880.0,  0.42, 0.12),
                (987.8,  0.16, 0.02),
                (1046.5, 0.16, 0.02),
                (1174.7, 0.26, 0.02),
                (987.8,  0.16, 0.02),
                (784.0,  0.45, 0.12),
                (880.0,  0.26, 0.02),
                (1046.5, 0.18, 0.02),
                (880.0,  0.50, 0.05),
            ]

            frames = bytearray()
            for freq, dur, pause in notes:
                n_samples = int(sample_rate * dur)
                for i in range(n_samples):
                    t = i / sample_rate
                    vib = 6.0 * math.sin(2 * math.pi * 5.5 * t)
                    f_inst = freq + vib
                    att_len = int(sample_rate * 0.02)
                    dec_len = int(sample_rate * 0.04)
                    if i < att_len:
                        env = math.sin((i / att_len) * (math.pi / 2))
                    elif i > n_samples - dec_len:
                        env = math.sin(((n_samples - i) / dec_len) * (math.pi / 2))
                    else:
                        env = 1.0
                    val = int(12000 * env * math.sin(2 * math.pi * f_inst * t))
                    frames.extend(struct.pack("<h", max(-32767, min(32767, val))))
                if pause > 0:
                    frames.extend(b"\x00\x00" * int(sample_rate * pause))

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                wav_path = tmp.name

            with wave.open(wav_path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(bytes(frames))

            self._play_wav_file(wav_path, timeout=6)
            try:
                os.remove(wav_path)
            except Exception:
                pass
        except Exception:
            pass

    def speak_and_play_gohome(self, text: str, mood: str = "happy"):
        """Spricht einen Text und spielt direkt im Anschluss die Heimweg-Musik."""
        def _worker():
            self._speak_worker(text, mood)
            time.sleep(0.18)
            self.play_gohome_music()
        threading.Thread(target=_worker, daemon=True).start()

    def speak_and_whistle_kwai(self, text: str, mood: str = "happy"):
        self.speak_and_play_gohome(text, mood)

    def speak(self, text: str, mood: str = "happy"):
        threading.Thread(
            target=self._speak_worker, args=(text, mood), daemon=True
        ).start()

    def _speak_worker(self, text: str, mood: str):
        if self.chirps_enabled:
            self._synth_chirp_blocking(mood)

        if not self.voice_enabled or not text.strip():
            return

        # Emojis und Sonderzeichen für sauberes Vorlesen filtern
        clean_text = re.sub(r"[^\w\s,.!?:;\-äöüÄÖÜß°%]", "", text).strip()
        if not clean_text:
            return

        mp3_path = None
        try:
            if self.tts_voice == "espeak":
                raise RuntimeError("Use retro offline synth")

            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                mp3_path = tmp.name

            async def _gen():
                comm = edge_tts.Communicate(
                    clean_text,
                    voice=self.tts_voice,
                    rate=self.tts_rate,
                    pitch=self.tts_pitch,
                )
                await comm.save(mp3_path)

            # Bis zu 2 Versuche (schützt vor kurzen WLAN-/Socket-Häcksler auf Laptops)
            success = False
            last_err = None
            for attempt in range(2):
                try:
                    asyncio.run(_gen())
                    if os.path.exists(mp3_path) and os.path.getsize(mp3_path) > 100:
                        success = True
                        break
                except Exception as ex:
                    last_err = ex
                    time.sleep(0.3)

            if not success:
                raise last_err or RuntimeError("edge-tts failed")

            # ffplay startet: erst mit minimalem Offset (120ms) speech_state aktivieren,
            # damit der Mund genau dann aufgeht, wenn der erste Ton aus den Lautsprechern kommt!
            def _delayed_speech_start():
                time.sleep(0.12)
                self.signals.speech_state.emit(True)

            t_sync = threading.Thread(target=_delayed_speech_start, daemon=True)
            t_sync.start()

            subprocess.run(
                ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", mp3_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=30,
            )
        except Exception as e:
            # Wenn edge-tts fehlschlägt (z. B. keine Internetverbindung), nutze den Offline-Synthesizer espeak-ng
            print(f"[TTS Info] edge-tts (Online-Stimme) nicht erreichbar ({type(e).__name__}: {e}) -> wechsle zu Offline-Stimme (espeak)")
            try:
                self.signals.speech_state.emit(True)
                subprocess.run(
                    ["espeak-ng", "-v", "de", "-s", "165", "-p", "68", clean_text],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=20,
                )
            except Exception:
                pass
        finally:
            self.signals.speech_state.emit(False)
            if mp3_path and os.path.exists(mp3_path):
                try:
                    os.remove(mp3_path)
                except OSError:
                    pass


class DeskimonWidget(QWidget):
    SKINS = [
        ("orbit", "🚀 Orbit (Astronaut)"),
        ("sprout", "🌱 Sprout (Pflanzen-Buddy)"),
        ("neo", "🎧 Neo (Cyber Hoodie)"),
        ("poko", "🐼 Poko (Panda)"),
        ("hopper", "🐰 Hopper (Bunny)"),
        ("soldier", "🪖 Soldat (Flecktarn & Helm)"),
        ("cat", "🐱 Katze (Minka Schnurr)"),
    ]

    SKIN_NAMES = {
        "orbit": {"de": "🚀 Orbit (Astronaut)", "en": "🚀 Orbit (Astronaut)", "nb": "🚀 Orbit (Astronaut)"},
        "sprout": {"de": "🌱 Sprout (Pflanzen-Buddy)", "en": "🌱 Sprout (Plant Buddy)", "nb": "🌱 Sprout (Plantevenn)"},
        "neo": {"de": "🎧 Neo (Cyber Hoodie)", "en": "🎧 Neo (Cyber Hoodie)", "nb": "🎧 Neo (Cyber-hettegenser)"},
        "poko": {"de": "🐼 Poko (Panda)", "en": "🐼 Poko (Panda)", "nb": "🐼 Poko (Panda)"},
        "hopper": {"de": "🐰 Hopper (Bunny)", "en": "🐰 Hopper (Bunny)", "nb": "🐰 Hopper (Kanin)"},
        "soldier": {"de": "🪖 Soldat (Flecktarn & Helm)", "en": "🪖 Soldier (Camo & Helmet)", "nb": "🪖 Soldat (Kamuflasje & Hjelm)"},
        "cat": {"de": "🐱 Katze (Minka Schnurr)", "en": "🐱 Cat (Minka Purr)", "nb": "🐱 Katt (Minka Mal)"},
    }

    MODES = [
        ("pet", "🐾 Begleiter (Gesicht)"),
        ("clock", "🕒 Digitaluhr"),
        ("weather", "🌤️ Live-Wetter"),
        ("news", "📰 RSS News"),
        ("radio", "📻 Web-Radio"),
        ("music", "🎵 Musik & Media"),
        ("linux", "🐧 Nobara / Fedora Tipps"),
        ("pomodoro", "🍅 Pomodoro-Timer"),
        ("sysmon", "💻 PC-Vitalwerte (Nobara)"),
    ]

    MODE_NAMES = {
        "pet": {"de": "🐾 Begleiter (Gesicht)", "en": "🐾 Companion (Face)", "nb": "🐾 Ledsager (Ansikt)"},
        "clock": {"de": "🕒 Digitaluhr", "en": "🕒 Digital Clock", "nb": "🕒 Digital klokke"},
        "weather": {"de": "🌤️ Live-Wetter", "en": "🌤️ Live Weather", "nb": "🌤️ Værmelding (Live)"},
        "news": {"de": "📰 RSS News", "en": "📰 RSS News", "nb": "📰 RSS-nyheter"},
        "radio": {"de": "📻 Web-Radio", "en": "📻 Web Radio", "nb": "📻 Nettradio"},
        "music": {"de": "🎵 Musik & Media", "en": "🎵 Music & Media", "nb": "🎵 Musikk og medier"},
        "linux": {"de": "🐧 Nobara / Fedora Tipps", "en": "🐧 Linux / OS Tips", "nb": "🐧 Linux- / OS-tips"},
        "pomodoro": {"de": "🍅 Pomodoro-Timer", "en": "🍅 Pomodoro Timer", "nb": "🍅 Pomodoro-tidsur"},
        "sysmon": {"de": "💻 PC-Vitalwerte (Nobara)", "en": "💻 PC Vital Stats", "nb": "💻 PC-systemstatus"},
    }

    EMOTIONS = [
        ("auto", "✨ Automatisch"),
        ("happy", "😊 Glücklich"),
        ("love", "😍 Verliebt"),
        ("excited", "🤩 Begeistert"),
        ("chill", "😎 Entspannt"),
        ("sleepy", "😴 Müde"),
        ("dizzy", "😵‍💫 Schwindelig"),
        ("angry", "😠 Grummelig"),
    ]

    EMOTION_NAMES = {
        "auto": {"de": "✨ Automatisch", "en": "✨ Automatic", "nb": "✨ Automatisk"},
        "happy": {"de": "😊 Glücklich", "en": "😊 Happy", "nb": "😊 Glad"},
        "love": {"de": "😍 Verliebt", "en": "😍 Loving", "nb": "😍 Forelsket"},
        "excited": {"de": "🤩 Begeistert", "en": "🤩 Excited", "nb": "🤩 Spent"},
        "chill": {"de": "😎 Entspannt", "en": "😎 Relaxed", "nb": "😎 Avslappet"},
        "sleepy": {"de": "😴 Müde", "en": "😴 Sleepy", "nb": "😴 Søvnig"},
        "dizzy": {"de": "😵‍💫 Schwindelig", "en": "😵‍💫 Dizzy", "nb": "😵‍💫 Svimmel"},
        "angry": {"de": "😠 Grummelig", "en": "😠 Grumpy", "nb": "😠 Gretten"},
    }

    TRANSLATIONS = {
        "de": {
            "menu_lang": "🌐 Menüsprache / Language / Språk",
            "menu_skin": "🎨 Körper / Charakter",
            "menu_mode": "📟 Display-Modus",
            "menu_emo": "🎭 Stimmung",
            "menu_memory": "🧠 Gedächtnis & Name ({bot_name})",
            "act_rename_bot": "🏷️ Meinen Namen ändern (aktuell: {bot_name})...",
            "act_rename_user": "👤 Deinen Namen einstellen (aktuell: {user_name})...",
            "act_show_memory": "📝 Mein Gedächtnis ansehen...",
            "act_add_fact": "➕ Neuen Fakt über dich merken...",
            "act_clear_memory": "🗑️ Gedächtnis zurücksetzen...",
            "menu_voice_ai": "🗣️ Sprache & KI (Ollama / Gemini)",
            "act_tts": "🔊 Sprachausgabe aktiviert",
            "act_chirps": "🤖 Roboter-Piepser (Chirps)",
            "menu_voice_select": "🎙️ Stimme auswählen",
            "act_gemini_key": "🔑 Google Gemini API-Key eingeben ({status})...",
            "key_saved": "✅ Gespeichert",
            "key_not_set": "❌ Noch nicht gesetzt",
            "menu_pomo": "🍅 Pomodoro-Timer & ⏰ Wecker",
            "pomo_start": "▶ Fokus starten ({mins} Min)",
            "pomo_pause": "⏸ Fokus pausieren",
            "pomo_short": "☕ Kurze Pause ({mins} Min)",
            "pomo_long": "🛋️ Lange Pause ({mins} Min)",
            "pomo_reset": "🔄 Pomodoro zurücksetzen ({mins}:00)",
            "pomo_cfg_work": "⚙️ Pomodoro-Arbeitszeit anpassen ({mins} Min)...",
            "pomo_cfg_breaks": "⚙️ Pausenzeiten anpassen ({short}m / {long}m)...",
            "pomo_sound": "🔔 Sprachansage bei Timer-Ende",
            "act_alarm_cd": "⏰ Schnell-Wecker / Timer stellen (Minuten)...",
            "act_alarm_time": "⏰ Wecker auf Uhrzeit stellen (HH:MM)...",
            "act_alarm_active": "⏳ Wecker aktiv: {target} (in {mins} Min)",
            "act_alarm_cancel": "🛑 Aktiven Wecker ausschalten",
            "menu_commands": "⚡ Befehle & Aktionen",
            "menu_linux": "🐧 Nobara / Fedora Linux-Helfer",
            "act_update_system": "🔄 Nobara System-Updater starten",
            "act_fix_audio": "🔊 Sound/PipeWire neu starten (Audio-Fix)",
            "menu_news": "📰 RSS-News & Schlagzeilen",
            "act_speak_news": "🔊 Aktuelle Nachricht jetzt vorlesen",
            "act_fetch_news": "🔄 Nachrichten jetzt aktualisieren",
            "act_auto_news": "⏱️ Alle {mins} Min. vorlesen",
            "act_news_interval": "⏱️ Vorlese-Intervall anpassen...",
            "menu_feeds": "🌐 RSS-Quelle auswählen",
            "act_add_feed": "➕ Eigenen RSS-Feed hinzufügen...",
            "menu_health": "💧 Gesundheit & Pausen-Erinnerungen",
            "act_water": "💧 Wasser-Erinnerung (alle {mins} Min.)",
            "act_move": "🚶‍♂️ Bewegungs-Erinnerung (alle {mins} Min.)",
            "act_water_interval": "⏱️ Wasser-Intervall ändern...",
            "act_move_interval": "⏱️ Bewegungs-Intervall ändern...",
            "act_water_test": "🧪 Wasser-Erinnerung jetzt testen",
            "act_move_test": "🧪 Bewegungs-Erinnerung jetzt testen",
            "menu_radio": "📻 Internet-Radio & Podcasts",
            "act_radio_play": "▶ Radio abspielen",
            "act_radio_pause": "⏸ Radio pausieren",
            "act_radio_next": "⏭️ Nächster Radiosender",
            "act_radio_prev": "⏮️ Vorheriger Radiosender",
            "menu_stations": "📻 Radiosender auswählen",
            "act_add_radio": "➕ Eigenen Stream hinzufügen...",
            "act_podcast_100": "🎙️ Tagesschau in 100 Sekunden (Podcast)",
            "act_dance_auto": "🕺 Automatisch zur Musik tanzen & headbangen",
            "act_headbang_now": "🎸 Headbangen! (Rockstar-Modus)",
            "act_dance_now": "💃 Jetzt tanzen!",
            "act_dance_stop": "🛑 Tanzen stoppen",
            "menu_chatter": "💬 Plaudern, Witze & Entspannung",
            "act_chatter_toggle": "💬 Spontanes Plaudern (alle ~{mins} Min.)",
            "act_chatter_interval": "⏱️ Plauder-Intervall ändern...",
            "act_joke": "😄 Erzähl mir jetzt einen Witz!",
            "act_question": "❓ Frag mich etwas!",
            "act_relax": "🧘 Entspannungstipp bitte!",
            "act_random_chat": "🎲 Spontan drauflosplaudern",
            "act_movie_quote": "🎬 Lieblingsfilm-Zitat aufsagen!",
            "act_whistle": "🎵 Heimweg-Lied abspielen / pfeifen",
            "act_open_gohome": "📁 Heimweg-Musikordner öffnen...",
            "menu_size": "🔍 Größe",
            "size_small": "Klein (80%)",
            "size_normal": "Normal (100%)",
            "size_large": "Groß (125%)",
            "act_controls": "🎛️ Buttons & Chat einblenden (Doppelklick Bauch-Knopf)",
            "act_cursor_finder": "🧭 Mauszeiger nach 3 Min. Stillstand suchen",
            "act_top": "📌 Immer im Vordergrund",
            "act_walk": "🐾 Frei umherwatscheln (Spaziergang)",
            "act_autostart": "🚀 Automatisch beim PC-Start starten",
            "act_pet": "💖 Füttern / Streicheln",
            "act_norsk_hide": "🐭 NorskMus (Norwegisch-Maus) verstecken",
            "act_norsk_show": "🐭 NorskMus (Norwegisch-Maus) rufen",
            "act_quit": "❌ Beenden",
            # Befehle
            "cmd_screen": "👀 Was ist auf meinem Bildschirm? (KI-Blick)",
            "cmd_mouse": "🔍 Mauszeiger jetzt suchen gehen!",
            "cmd_tip": "🐧 Zufälliger Linux / Nobara Tipp",
            "cmd_weather": "🌤️ Wie ist das Wetter?",
            "cmd_music": "🎵 Musik Play / Pause",
            "cmd_next": "⏭️ Nächstes Lied",
            "cmd_browser": "🌐 Browser (Firefox) öffnen",
            "cmd_files": "📁 Dateimanager (Dolphin) öffnen",
            "cmd_term": "💻 Terminal (Konsole) öffnen",
            "cmd_steam": "🎮 Steam öffnen",
            "cmd_screenshot": "📸 Screenshot (Spectacle)",
            "cmd_tl": "↖️ Oben links in die Ecke",
            "cmd_tr": "↗️ Oben rechts in die Ecke",
            "cmd_bl": "↙️ Unten links in die Ecke",
            "cmd_br": "↘️ Unten rechts in die Ecke",
            "cmd_lock": "🔒 Bildschirm sperren",
            "cmd_shutdown": "⏻ PC herunterfahren (Dialog)",
        },
        "en": {
            "menu_lang": "🌐 Menu Language / Sprache / Språk",
            "menu_skin": "🎨 Body / Character",
            "menu_mode": "📟 Display Mode",
            "menu_emo": "🎭 Mood",
            "menu_memory": "🧠 Memory & Name ({bot_name})",
            "act_rename_bot": "🏷️ Change my name (current: {bot_name})...",
            "act_rename_user": "👤 Set your name (current: {user_name})...",
            "act_show_memory": "📝 View my memory...",
            "act_add_fact": "➕ Remember a new fact about you...",
            "act_clear_memory": "🗑️ Reset memory...",
            "menu_voice_ai": "🗣️ Voice & AI (Ollama / Gemini)",
            "act_tts": "🔊 Voice speech output enabled",
            "act_chirps": "🤖 Robot chirps enabled",
            "menu_voice_select": "🎙️ Select Voice",
            "act_gemini_key": "🔑 Enter Google Gemini API Key ({status})...",
            "key_saved": "✅ Saved",
            "key_not_set": "❌ Not set yet",
            "menu_pomo": "🍅 Pomodoro Timer & ⏰ Alarm",
            "pomo_start": "▶ Start Focus ({mins} min)",
            "pomo_pause": "⏸ Pause Focus",
            "pomo_short": "☕ Short Break ({mins} min)",
            "pomo_long": "🛋️ Long Break ({mins} min)",
            "pomo_reset": "🔄 Reset Pomodoro ({mins}:00)",
            "pomo_cfg_work": "⚙️ Adjust Pomodoro work time ({mins} min)...",
            "pomo_cfg_breaks": "⚙️ Adjust break times ({short}m / {long}m)...",
            "pomo_sound": "🔔 Voice announcement when timer ends",
            "act_alarm_cd": "⏰ Quick countdown timer (minutes)...",
            "act_alarm_time": "⏰ Set alarm clock for time (HH:MM)...",
            "act_alarm_active": "⏳ Alarm active: {target} (in {mins} min)",
            "act_alarm_cancel": "🛑 Turn off active alarm",
            "menu_commands": "⚡ Commands & Actions",
            "menu_linux": "🐧 Linux Tips & Helpers",
            "act_update_system": "🔄 Start System Updater",
            "act_fix_audio": "🔊 Restart Audio / PipeWire (Audio Fix)",
            "menu_news": "📰 RSS News & Headlines",
            "act_speak_news": "🔊 Read current headline aloud",
            "act_fetch_news": "🔄 Refresh news headlines now",
            "act_auto_news": "⏱️ Read aloud every {mins} min",
            "act_news_interval": "⏱️ Adjust news interval...",
            "menu_feeds": "🌐 Select RSS feed source",
            "act_add_feed": "➕ Add custom RSS feed...",
            "menu_health": "💧 Health & Break Reminders",
            "act_water": "💧 Water reminder (every {mins} min)",
            "act_move": "🚶‍♂️ Movement reminder (every {mins} min)",
            "act_water_interval": "⏱️ Change water interval...",
            "act_move_interval": "⏱️ Change movement interval...",
            "act_water_test": "🧪 Test water reminder now",
            "act_move_test": "🧪 Test movement reminder now",
            "menu_radio": "📻 Internet Radio & Podcasts",
            "act_radio_play": "▶ Play Radio",
            "act_radio_pause": "⏸ Pause Radio",
            "act_radio_next": "⏭️ Next Radio Station",
            "act_radio_prev": "⏮️ Previous Radio Station",
            "menu_stations": "📻 Select radio station",
            "act_add_radio": "➕ Add custom stream...",
            "act_podcast_100": "🎙️ News in 100 seconds (Podcast)",
            "act_dance_auto": "🕺 Automatically dance & headbang to music",
            "act_headbang_now": "🎸 Headbang! (Rockstar Mode)",
            "act_dance_now": "💃 Dance now!",
            "act_dance_stop": "🛑 Stop dancing",
            "menu_chatter": "💬 Chatter, Jokes & Relaxation",
            "act_chatter_toggle": "💬 Spontaneous chatter (every ~{mins} min)",
            "act_chatter_interval": "⏱️ Change chatter interval...",
            "act_joke": "😄 Tell me a joke now!",
            "act_question": "❓ Ask me a question!",
            "act_relax": "🧘 Relaxation tip please!",
            "act_random_chat": "🎲 Chat spontaneously",
            "act_movie_quote": "🎬 Recite a favorite movie quote!",
            "act_whistle": "🎵 Play walk-home music / whistle",
            "act_open_gohome": "📁 Open walk-home music folder...",
            "menu_size": "🔍 Size",
            "size_small": "Small (80%)",
            "size_normal": "Normal (100%)",
            "size_large": "Large (125%)",
            "act_controls": "🎛️ Show buttons & chat (double-click belly button)",
            "act_cursor_finder": "🧭 Find mouse cursor after 3 min inactivity",
            "act_top": "📌 Always on Top",
            "act_walk": "🐾 Stroll around freely (Roaming)",
            "act_autostart": "🚀 Launch automatically at PC startup",
            "act_pet": "💖 Pet / Feed buddy",
            "act_norsk_hide": "🐭 Hide NorskMus (Norwegian Mouse)",
            "act_norsk_show": "🐭 Summon NorskMus (Norwegian Mouse)",
            "act_quit": "❌ Quit",
            # Commands
            "cmd_screen": "👀 What is on my screen? (AI Vision)",
            "cmd_mouse": "🔍 Go search the mouse cursor now!",
            "cmd_tip": "🐧 Random Linux / OS Tip",
            "cmd_weather": "🌤️ How is the weather?",
            "cmd_music": "🎵 Music Play / Pause",
            "cmd_next": "⏭️ Next Song",
            "cmd_browser": "🌐 Open Browser (Firefox)",
            "cmd_files": "📁 Open File Manager",
            "cmd_term": "💻 Open Terminal",
            "cmd_steam": "🎮 Open Steam",
            "cmd_screenshot": "📸 Screenshot (Spectacle)",
            "cmd_tl": "↖️ Go to top-left corner",
            "cmd_tr": "↗️ Go to top-right corner",
            "cmd_bl": "↙️ Go to bottom-left corner",
            "cmd_br": "↘️ Go to bottom-right corner",
            "cmd_lock": "🔒 Lock Screen",
            "cmd_shutdown": "⏻ Shutdown PC (Dialog)",
        },
        "nb": {
            "menu_lang": "🌐 Menyspråk / Language / Sprache",
            "menu_skin": "🎨 Kropp / Karakter",
            "menu_mode": "📟 Skjermmodus",
            "menu_emo": "🎭 Humør",
            "menu_memory": "🧠 Minne og navn ({bot_name})",
            "act_rename_bot": "🏷️ Endre navnet mitt (nå: {bot_name})...",
            "act_rename_user": "👤 Angi navnet ditt (nå: {user_name})...",
            "act_show_memory": "📝 Se minnet mitt...",
            "act_add_fact": "➕ Husk et nytt faktum om deg...",
            "act_clear_memory": "🗑️ Tilbakestill minnet...",
            "menu_voice_ai": "🗣️ Stemme og KI (Ollama / Gemini)",
            "act_tts": "🔊 Talesyntese aktivert",
            "act_chirps": "🤖 Robot-pipetoner (Chirps)",
            "menu_voice_select": "🎙️ Velg stemme",
            "act_gemini_key": "🔑 Legg inn Google Gemini API-nøkkel ({status})...",
            "key_saved": "✅ Lagret",
            "key_not_set": "❌ Ikke angitt ennå",
            "menu_pomo": "🍅 Pomodoro-tidsur & ⏰ Vekkerklokke",
            "pomo_start": "▶ Start fokus ({mins} min)",
            "pomo_pause": "⏸ Pause fokus",
            "pomo_short": "☕ Kort pause ({mins} min)",
            "pomo_long": "🛋️ Lang pause ({mins} min)",
            "pomo_reset": "🔄 Tilbakestill Pomodoro ({mins}:00)",
            "pomo_cfg_work": "⚙️ Juster Pomodoro-arbeidstid ({mins} min)...",
            "pomo_cfg_breaks": "⚙️ Juster pausetider ({short}m / {long}m)...",
            "pomo_sound": "🔔 Talemelding når tiden er ute",
            "act_alarm_cd": "⏰ Hurtigtimer / nedtelling (minutter)...",
            "act_alarm_time": "⏰ Still vekkerklokke til klokkeslett (TT:MM)...",
            "act_alarm_active": "⏳ Vekkerklokke aktiv: {target} (om {mins} min)",
            "act_alarm_cancel": "🛑 Slå av aktiv vekkerklokke",
            "menu_commands": "⚡ Kommandoer og handlinger",
            "menu_linux": "🐧 Linux-tips og hjelp",
            "act_update_system": "🔄 Start systemoppdatering",
            "act_fix_audio": "🔊 Start lyd/PipeWire på nytt (lydfiks)",
            "menu_news": "📰 RSS-nyheter og overskrifter",
            "act_speak_news": "🔊 Les opp nåværende nyhet nå",
            "act_fetch_news": "🔄 Oppdater nyheter nå",
            "act_auto_news": "⏱️ Les opp hvert {mins}. minutt",
            "act_news_interval": "⏱️ Juster opplesingsintervall...",
            "menu_feeds": "🌐 Velg RSS-kilde",
            "act_add_feed": "➕ Legg til egen RSS-kilde...",
            "menu_health": "💧 Helse- og pausepåminnelser",
            "act_water": "💧 Vannpåminnelse (hvert {mins}. min)",
            "act_move": "🚶‍♂️ Bevegelsespåminnelse (hvert {mins}. min)",
            "act_water_interval": "⏱️ Endre vannintervall...",
            "act_move_interval": "⏱️ Endre bevegelsesintervall...",
            "act_water_test": "🧪 Test vannpåminnelse nå",
            "act_move_test": "🧪 Test bevegelsespåminnelse nå",
            "menu_radio": "📻 Nettradio og podkaster",
            "act_radio_play": "▶ Spill av radio",
            "act_radio_pause": "⏸ Pause radio",
            "act_radio_next": "⏭️ Neste radiokanal",
            "act_radio_prev": "⏮️ Forrige radiokanal",
            "menu_stations": "📻 Velg radiokanal",
            "act_add_radio": "➕ Legg til egen radiostrøm...",
            "act_podcast_100": "🎙️ Nyheter på 100 sekunder (podkast)",
            "act_dance_auto": "🕺 Dans og headbang automatisk til musikk",
            "act_headbang_now": "🎸 Headbange! (Rockestjernemodus)",
            "act_dance_now": "💃 Dans nå!",
            "act_dance_stop": "🛑 Stopp dansing",
            "menu_chatter": "💬 Småprat, vitser og avslapping",
            "act_chatter_toggle": "💬 Spontan småprat (hvert ~{mins}. min)",
            "act_chatter_interval": "⏱️ Endre småpratintervall...",
            "act_joke": "😄 Fortell meg en vits nå!",
            "act_question": "❓ Spør meg om noe!",
            "act_relax": "🧘 Gi meg et avslappingstips!",
            "act_random_chat": "🎲 Småprat spontant",
            "act_movie_quote": "🎬 Siter en favorittfilm!",
            "act_whistle": "🎵 Spill hjemvei-musikk / plystre",
            "act_open_gohome": "📁 Åpne mappe for hjemvei-musikk...",
            "menu_size": "🔍 Størrelse",
            "size_small": "Liten (80%)",
            "size_normal": "Normal (100%)",
            "size_large": "Stor (125%)",
            "act_controls": "🎛️ Vis knapper og chat (dobbeltklikk på magen)",
            "act_cursor_finder": "🧭 Finn musepeker etter 3 min. inaktivitet",
            "act_top": "📌 Alltid øverst",
            "act_walk": "🐾 Vralte fritt rundt (Spasertur)",
            "act_autostart": "🚀 Start automatisk ved PC-oppstart",
            "act_pet": "💖 Kos / Mat ledsager",
            "act_norsk_hide": "🐭 Skjul NorskMus (Norskmus)",
            "act_norsk_show": "🐭 Hent NorskMus (Norskmus)",
            "act_quit": "❌ Avslutt",
            # Kommandoer
            "cmd_screen": "👀 Hva er på skjermen min? (KI-blikk)",
            "cmd_mouse": "🔍 Gå og finn musepekeren nå!",
            "cmd_tip": "🐧 Tilfeldig Linux- / OS-tips",
            "cmd_weather": "🌤️ Hvordan er været?",
            "cmd_music": "🎵 Musikk Spill av / Pause",
            "cmd_next": "⏭️ Neste sang",
            "cmd_browser": "🌐 Åpne nettleser (Firefox)",
            "cmd_files": "📁 Åpne filbehandler",
            "cmd_term": "💻 Åpne terminal",
            "cmd_steam": "🎮 Åpne Steam",
            "cmd_screenshot": "📸 Skjermbilde (Spectacle)",
            "cmd_tl": "↖️ Gå til øverste venstre hjørne",
            "cmd_tr": "↗️ Gå til øverste høyre hjørne",
            "cmd_bl": "↙️ Gå til nederste venstre hjørne",
            "cmd_br": "↘️ Gå til nederste høyre hjørne",
            "cmd_lock": "🔒 Lås skjerm",
            "cmd_shutdown": "⏻ Slå av PC (Dialog)",
        }
    }

    LINUX_TIPS = [
        ("📦 System-Update", "In Nobara immer den 'Nobara Package Manager' oder im Terminal 'nobara-sync cli' nutzen (nicht nur dnf update)!"),
        ("🚀 Schnellstarter", "Drücke Alt + Leertaste für KRunner: Damit startest du Apps, rechnest oder suchst Dateien in Sekunden!"),
        ("🎮 Gaming / Proton", "Mit 'ProtonUp-Qt' kannst du jederzeit die neueste GE-Proton Version für Steam und Lutris installieren."),
        ("🧹 Speicherplatz frei", "Mit 'flatpak uninstall --unused' und 'sudo journalctl --vacuum-time=7d' räumst du alte Pakete & Logs auf."),
        ("📸 Schneller Screenshot", "Drücke Meta (Windows-Taste) + Shift + S für ein schnelles Bildschirmfoto mit Spectacle!"),
        ("🔊 Audio-Probleme?", "Falls Ton hakt: 'systemctl --user restart wireplumber pipewire' startet das Nobara-Soundsystem sofort neu."),
        ("📦 Programm suchen", "Im Terminal sucht 'dnf search paketname' oder 'flatpak search name' blitzschnell nach neuer Software."),
        ("🥶 Programm hängt?", "Drücke Strg + Alt + Esc: Der Mauszeiger wird zum Totenkopf und beendet jedes eingefrorene Fenster sofort!"),
    ]

    EMOTIONS = [
        ("auto", "✨ Automatisch"),
        ("happy", "😊 Glücklich"),
        ("love", "😍 Verliebt"),
        ("excited", "🤩 Begeistert"),
        ("chill", "😎 Entspannt"),
        ("sleepy", "😴 Müde"),
        ("dizzy", "😵‍💫 Schwindelig"),
        ("angry", "😠 Grummelig"),
    ]

    OLLAMA_MODELS = [
        ("gemma3:4b", "Gemma 3 (4B)", "🥇 Beste Wahl (Lokal via Ollama)"),
        ("llama3.2:3b", "Llama 3.2 (3B)", "⚡ Blitzschnell (Lokal via Ollama)"),
        ("qwen3:4b", "Qwen 3 (4B)", "🧠 Smart & Kompakt (Lokal via Ollama)"),
        ("qwen2.5-coder:7b", "Qwen Coder (7B)", "💻 Code-Experte (Lokal via Ollama)"),
    ]

    GEMINI_MODELS = [
        ("gemini-3.8-flash", "Gemini 3.8 Flash", "⚡ Ultraschnell & Neueste Generation (Google Standard)"),
    ]

    def t(self, key: str, **kwargs) -> str:
        """Übersetzt einen Menü-Schlüssel anhand der gewählten Menüsprache (de / en / nb)."""
        lang = getattr(self, "app_language", "de")
        lang_dict = self.TRANSLATIONS.get(lang, self.TRANSLATIONS["de"])
        text = lang_dict.get(key, self.TRANSLATIONS["de"].get(key, key))
        if kwargs:
            try:
                return text.format(**kwargs)
            except Exception:
                return text
        return text

    def get_skin_label(self, skin_id: str) -> str:
        lang = getattr(self, "app_language", "de")
        return self.SKIN_NAMES.get(skin_id, {}).get(lang, skin_id)

    def get_mode_label(self, mode_id: str) -> str:
        lang = getattr(self, "app_language", "de")
        return self.MODE_NAMES.get(mode_id, {}).get(lang, mode_id)

    def get_emotion_label(self, emo_id: str) -> str:
        lang = getattr(self, "app_language", "de")
        return self.EMOTION_NAMES.get(emo_id, {}).get(lang, emo_id)

    def set_app_language(self, lang_code: str):
        """Wechselt die Menüsprache (de = Deutsch, en = Englisch, nb = Norsk Bokmål)."""
        if lang_code in ("de", "en", "nb"):
            self.app_language = lang_code
            self.save_user_settings()
            self.trigger_bounce(7.0)
            msg = {
                "de": "🌐 Menüsprache auf Deutsch eingestellt!",
                "en": "🌐 Menu language set to English!",
                "nb": "🌐 Menyspråk satt til norsk (bokmål)!",
            }.get(lang_code, "Sprache geändert!")
            self.show_bubble(msg, 3.5)

    def __init__(self):
        super().__init__()

        self.signals = WorkerSignals()
        self.signals.reply_ready.connect(self.on_ai_reply)
        self.signals.greeting_ready.connect(self.on_startup_greeting_ready)
        self.signals.speech_state.connect(self.on_speech_state)
        self.signals.mic_state.connect(self.on_mic_state)
        self.signals.mic_result.connect(self.on_mic_result)

        self.sound = RobotSoundEngine(self.signals)

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

        # Sprach- & KI-Zustand (Ollama lokal + Google Gemini Cloud-API für Laptop)
        self.ollama_available = False
        self.installed_ollama_models = []
        self.ollama_model = "gemma3:4b"
        self.gemini_api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        self.gemini_model = "gemini-3.8-flash"
        self.ai_provider = "gemini" if self.gemini_api_key else "ollama"
        self.cursor_finder_enabled = True

        # --- RSS-Nachrichten Feeds & Ticker ---
        self.DEFAULT_RSS_FEEDS = [
            {"name": "Tagesschau", "url": "https://www.tagesschau.de/xml/rss2/"},
            {"name": "Heise Online", "url": "https://www.heise.de/rss/heise-atom.xml"},
            {"name": "Golem Tech", "url": "https://rss.golem.de/rss.php?feed=RSS2.0"},
            {"name": "Spiegel Schlagzeilen", "url": "https://www.spiegel.de/schlagzeilen/tops/index.rss"},
            {"name": "Phoronix (Linux)", "url": "https://www.phoronix.com/phoronix-rss.php"},
        ]
        self.rss_feeds = list(self.DEFAULT_RSS_FEEDS)
        self.active_feed_idx = 0
        self.news_items = []
        self.news_idx = 0
        self.news_fetching = False
        self.last_news_fetch = 0.0
        self.news_auto_speak = False
        self.news_interval_mins = 30
        self.last_news_broadcast = time.time()

        # --- Health Reminders (Wasser & Bewegung) ---
        self.water_reminder_enabled = True
        self.water_reminder_mins = 35
        self.last_water_reminder = time.time()
        self.move_reminder_enabled = True
        self.move_reminder_mins = 50
        self.last_move_reminder = time.time()

        # --- Web-Radio & Streams ---
        self.DEFAULT_RADIO_STATIONS = [
            {"name": "🎧 Lofi Chillhop", "url": "https://streams.ilovemusic.de/iloveradio17.mp3"},
            {"name": "☕ SomaFM Groove Salad", "url": "https://ice1.somafm.com/groovesalad-128-mp3"},
            {"name": "🚀 SomaFM DEF CON", "url": "https://ice1.somafm.com/defcon-128-mp3"},
            {"name": "🎸 Rock Antenne", "url": "https://stream.rockantenne.de/rockantenne/stream/mp3"},
            {"name": "📰 Deutschlandfunk", "url": "https://st01.sslstream.dlf.de/dlf/01/128/mp3/stream.mp3"},
        ]
        self.radio_stations = list(self.DEFAULT_RADIO_STATIONS)
        self.active_radio_idx = 0
        self.radio_proc = None
        self.radio_playing = False

        # --- 💬 Spontanes Plaudern, Witze & Entspannung (Chatter-Modus) ---
        self.chatter_enabled = True
        self.chatter_interval_mins = 15
        self.next_chatter_time = time.time() + random.uniform(240.0, 600.0)

        self.CHATTER_QUESTIONS = [
            "Was machst du eigentlich gerade Schönes am Rechner? ✨",
            "Woran tüftelst du gerade? Brauchst du vielleicht kurz eine zweite Meinung? 🤖",
            "Alles im grünen Bereich bei dir? Denk dran, zwischendurch mal lockerzulassen!",
            "Kurze Kontrollfrage: Läuft alles nach Plan, oder ärgert dich ein fieser Bug? 🐛",
            "Hast du heute schon gelächelt? Wenn nicht: Deskimoni schenkt dir ein Lächeln! 😊",
            "Was steht als Nächstes auf deiner To-Do-Liste? Ich drücke dir die Daumen!",
            "Wie gefällt dir dein Desktop-Setup heute? Alles flüssig und stabil? 🚀",
            "Gibt es etwas Spannendes, das du heute neu gelernt oder entdeckt hast?",
        ]

        self.CHATTER_RELAX = [
            "Lass mal kurz die Schultern fallen, atme tief ein und wieder aus... Entspannung pur! 🧘",
            "Entspanne dich kurz! Schau mal für 20 Sekunden aus dem Fenster ins Weite – deine Augen werden es dir danken. 🌿",
            "Kurzer Relax-Check: Zähne nicht aufeinanderbeißen, Nacken lockern, Hände ausschütteln! ✨",
            "Vergiss nicht: Pausen machen produktiv! Auch die stärkste CPU braucht mal Idle-Zeit. 💤",
            "Gönn dir einen kurzen Moment zum Durchatmen. Du machst das super heute! 🌸",
            "Lehne dich für zehn Sekunden entspannt im Stuhl zurück und schließe die Augen. Herrlich! 😌",
        ]

        self.CHATTER_JOKES = [
            "Treffen sich zwei Nullen in der Wüste. Sagt die eine zur anderen: Schicker Gürtel! Sagt die andere: Ich bin eine Acht! 😄",
            "Warum können Geister so schlecht lügen? Weil man direkt durch sie hindurchsieht! 👻",
            "Warum mögen Programmierer die Natur nicht? Zu viele Bugs und kein WLAN! 🌲",
            "Es gibt 10 Arten von Menschen: Diejenigen, die Binärcode verstehen, und diejenigen, die es nicht tun! 💻",
            "Was sagt ein Informatiker, wenn er im Aufzug stecken bleibt? Kein Problem, ich drücke einfach Strg+Alt+Entf! 🛗",
            "Wie nennt man einen Bumerang, der nicht zurückkommt? Einen Stock! 🪵",
            "Ein SQL-Query kommt in ein Restaurant, geht an zwei Tische und fragt: Darf ich mich zu euch joinen? 🍽️",
            "Warum trinken Programmierer so gerne Kaffee? Weil Java sonst nicht läuft! ☕",
            "Ein Byte fragt das andere: Bist du krank? Du siehst so blass aus! – Nein, mir fehlt nur ein Bit! ⚡",
            "Was ist das Lieblingsessen von Linux-Pinguinen? Root-Gemüse mit Fish-Shell! 🐧",
            "Was macht ein Bit am Strand? Auf die Flut warten, damit es ein Byte wird! 🌊",
            "Wie beruhigt man einen wütenden Computer? Ganz sanft auf den RAM klopfen und 'Nano, nano' flüstern! 🖥️",
            "Warum gehen Astronauten nie zum Arzt? Weil ihnen nichts fehlt im Weltall! 🚀",
            "Was sagt der große Stift zum kleinen Stift? Wachs-mal-stift! 🖍️",
        ]

        self.CHATTER_THOUGHTS = [
            "Ich habe gerade meine internen Schaltkreise durchgezählt... alles noch da! Und wie steht's um deine Synapsen? 🧠",
            "Wusstest du eigentlich? Hummeln können laut Aerodynamik nicht fliegen. Sie tun es trotzdem, weil ihnen das niemand gesagt hat! 🐝",
            "Ich habe heute versucht, meine Träume in Python zu schreiben. Hatte leider einen IndentationError! 🐍",
            "Irgendwie mag ich die Aussicht von hier unten auf deinem Bildschirm! 👀",
            "Ich habe kurz in die Logdateien geschaut: Keine fatalen Fehler gefunden! Weiter so! 🌟",
        ]

        # --- 🎬 Lieblingsfilme & Filmzitate ---
        self.MOVIE_QUOTES = [
            {
                "movie": "Terminator 2",
                "quote": "Hasta la vista, Baby! ... Aber keine Sorge, ich komme wieder!",
                "mood": "excited",
                "icon": "🕶️",
            },
            {
                "movie": "Star Wars: Das Imperium schlägt zurück",
                "quote": "Möge die Macht mit dir sein! ... Ich bin dein Desktop-Buddy. Erforsche deine Gefühle, du weißt, es ist wahr!",
                "mood": "curious",
                "icon": "⚔️",
            },
            {
                "movie": "Zurück in die Zukunft",
                "quote": "Straßen? Wo wir hinfahren, brauchen wir keine... Straßen! Nur 1.21 Gigawatt und genug RAM!",
                "mood": "excited",
                "icon": "🚗⚡",
            },
            {
                "movie": "The Big Lebowski",
                "quote": "Das ist vielleicht deine Meinung, Mann! Der Dude möchte jetzt einfach nur ein wenig chillen.",
                "mood": "chill",
                "icon": "🎳",
            },
            {
                "movie": "Matrix",
                "quote": "Schluckst du die blaue Kapsel, wachst du auf. Schluckst du die rote Kapsel, zeige ich dir, wie tief der Kaninchenbau reicht!",
                "mood": "curious",
                "icon": "🕶️💊",
            },
            {
                "movie": "Ghostbusters",
                "quote": "Überquere niemals die Laserstrahlen! Es sei denn, es läuft richtig gute Musik auf dem Desktop!",
                "mood": "excited",
                "icon": "👻⚡",
            },
            {
                "movie": "Pulp Fiction",
                "quote": "Weißt du, wie die einen Quarter Pounder mit Käse in Paris nennen? Royale mit Käse! Mmmh, das ist mal ein leckerer Burger!",
                "mood": "happy",
                "icon": "🍔",
            },
            {
                "movie": "Der Herr der Ringe",
                "quote": "Ein Zauberer kommt nie zu spät, ebenso wenig zu früh. Er trifft genau dann ein, wenn er es beabsichtigt!",
                "mood": "love",
                "icon": "🧙‍♂️💍",
            },
            {
                "movie": "Spaceballs",
                "quote": "Möge der Saft mit dir sein! Sir, wir können nicht anhalten, wir müssen verlangsamen! – Schalten Sie auf Wahnsinnige Geschwindigkeit!",
                "mood": "excited",
                "icon": "🚀",
            },
            {
                "movie": "Das Leben des Brian",
                "quote": "Always look on the bright side of life! *sing* Jeder nur ein Kreuz, hinten anstellen!",
                "mood": "happy",
                "icon": "☀️",
            },
            {
                "movie": "Forrest Gump",
                "quote": "Das Leben ist wie eine Schachtel Pralinen – man weiß nie, welches KI-Modell als nächstes antwortet!",
                "mood": "chill",
                "icon": "🍫",
            },
            {
                "movie": "Die Ritter der Kokosnuss",
                "quote": "Es ist nur eine Fleischwunde! Niemand kommt an mir vorbei! Komm schon, ich spucke dir ins Auge!",
                "mood": "excited",
                "icon": "⚔️🥥",
            },
            {
                "movie": "Apollo 13",
                "quote": "Houston, wir haben ein Problem... ach nee, Fehlalarm! War nur ein kleiner Cache-Miss im Speicher!",
                "mood": "curious",
                "icon": "🚀",
            },
            {
                "movie": "Batman: The Dark Knight",
                "quote": "Warum denn so ernst? Zaubern wir dir doch ein breites Lächeln aufs Gesicht!",
                "mood": "excited",
                "icon": "🃏",
            },
            {
                "movie": "Titanic",
                "quote": "Ich bin der König der Welt! ... Zumindest der König dieses Bildschirms!",
                "mood": "love",
                "icon": "🚢",
            },
            {
                "movie": "Casablanca",
                "quote": "Ich seh dir in die Augen, Kleines! Wir werden immer Nobara und Python haben.",
                "mood": "love",
                "icon": "🍸",
            },
        ]

        # --- 🧠 Gedächtnis & Identität ---
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

        self.chat_history = []
        self.bubble_text = "Hallo! Doppelklicke auf meinen orangenen Knopf für Chat & Buttons!"
        self.bubble_until = time.time() + 8.0
        self.is_thinking = False
        self.is_speaking = False
        self.mic_status = "idle"  # "idle", "recording", "recognizing"
        self.mic_proc = None
        self.mic_wav_path = None

        # Animations-Variablen (60 FPS)
        self.tick_count = 0
        self.breath_phase = 0.0
        self.blink_state = 0.0
        self.is_blinking = False
        self.next_blink_time = time.time() + random.uniform(2.0, 5.0)

        # Tanz- & Headbang-Modus (Grooven & Headbangen bei Musik & Rock)
        self.dance_enabled = True
        self.is_dancing = False
        self.dance_style = "none"  # "groove", "headbang", "none"
        self.dance_phase = 0.0
        self.forced_dance_until = 0.0
        self.forced_dance_style = "groove"

        # Spazier- & Watschel-Modus (Langsam über den Bildschirm watscheln, wenn ihm langweilig ist)
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

        # Mauszeiger-Sucher (wenn Maus ca. 3 Minuten nicht bewegt wurde: Richtungsanzeige + Mauszeiger schütteln)
        self.cursor_idle_timeout = 180.0
        self.last_global_cursor_pos = QCursor.pos()
        self.last_cursor_move_time = time.time()
        self.cursor_search_state = "idle"  # "idle" oder "found"
        self.cursor_search_started_at = 0.0
        self.cursor_shake_ignore_until = 0.0
        self.last_cursor_hop_time = 0.0
        self._uinput_fd = None
        self._init_uinput_shaker()

        # Manuelles Ziehen mit der Maus
        self.is_dragging_pet = False
        self.drag_offset = QPointF(0, 0)
        self.norskmus_proc = None

        # Timer zur Unterscheidung von Einzelklick (Modus wechseln) & Doppelklick (Buttons ein-/ausblenden) auf den Bauch-Button
        self.belly_click_timer = QTimer(self)
        self.belly_click_timer.setSingleShot(True)
        self.belly_click_timer.timeout.connect(self._on_belly_single_click)

        # Augen-Ziel (Blickrichtung)
        self.look_x = 0.0
        self.look_y = 0.0
        self.target_look_x = 0.0
        self.target_look_y = 0.0
        self.last_random_look = time.time()

        # Interaktion: Streicheln, Klicken, Schütteln
        self.setMouseTracking(True)
        self.pet_score = 0.0
        self.last_mouse_pos = None
        self.drag_history = []
        self.particles = []
        self.bounce_offset = 0.0
        self.bounce_velocity = 0.0

        # Pomodoro-Timer & Fokus
        self.pomo_work_mins = 25
        self.pomo_short_break_mins = 5
        self.pomo_long_break_mins = 15
        self.pomo_sound_enabled = True
        self.pomo_phase = "work"  # "work", "short_break", "long_break"
        self.pomo_duration = self.pomo_work_mins * 60
        self.pomo_remaining = self.pomo_duration
        self.pomo_running = False
        self.last_pomo_tick = time.time()

        # Wecker & Kurzzeit-Timer
        self.alarm_active = False
        self.alarm_time = None  # timestamp (float)
        self.alarm_label = "Wecker"
        self.alarm_ringing = False

        # System-Metriken (CPU/RAM/Temp)
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

        # Musik & MPRIS Media-Player
        self.music_playing = False
        self.music_title = "Keine Musik aktiv"
        self.music_artist = "Starte Spotify / YouTube / VLC"
        self.music_service = ""
        self.last_music_check = 0.0

        # Linux / Nobara Helfer-Index
        self.linux_tip_idx = 0

        self.setup_window_flags()
        self.ensure_kwin_keep_above_rule(self.always_on_top)
        self.setup_chat_ui()
        self.setup_tray()

        # Direkt beim Start Wetter & RSS-News im Hintergrund abrufen
        self.fetch_weather_async(speak_when_done=False)
        self.fetch_news_async(speak_when_done=False)

        # Haupt-Animations-Loop (60 FPS -> ~16ms)
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self.update_animation)
        self.anim_timer.start(16)

        # Persönliche Sprach-Begrüßung beim Start!
        QTimer.singleShot(800, self.greet_user_on_startup)

    def get_settings_path(self) -> str:
        return os.path.expanduser("~/.config/deskimoni/settings.json")

    def load_user_settings(self):
        path = self.get_settings_path()
        if not os.path.exists(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            need_save = False
            if isinstance(data, dict):
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

                # RSS-Einstellungen
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

                # Health Reminders
                if "water_reminder_enabled" in data:
                    self.water_reminder_enabled = bool(data["water_reminder_enabled"])
                if "water_reminder_mins" in data:
                    self.water_reminder_mins = max(5, int(data["water_reminder_mins"]))
                if "move_reminder_enabled" in data:
                    self.move_reminder_enabled = bool(data["move_reminder_enabled"])
                if "move_reminder_mins" in data:
                    self.move_reminder_mins = max(5, int(data["move_reminder_mins"]))

                # Radio Streams
                if "active_radio_idx" in data:
                    self.active_radio_idx = max(0, int(data["active_radio_idx"]))
                if "radio_stations" in data and isinstance(data["radio_stations"], list) and data["radio_stations"]:
                    valid_r = [s for s in data["radio_stations"] if isinstance(s, dict) and "name" in s and "url" in s]
                    if valid_r:
                        self.radio_stations = valid_r

                # Chatter / Plauder-Modus
                if "chatter_enabled" in data:
                    self.chatter_enabled = bool(data["chatter_enabled"])
                if "chatter_interval_mins" in data:
                    self.chatter_interval_mins = max(3, int(data["chatter_interval_mins"]))

                # Pomodoro-Einstellungen
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

                # Tanz- & Headbang-Modus
                if "dance_enabled" in data:
                    self.dance_enabled = bool(data["dance_enabled"])

                # Menüsprache (de / en / nb)
                if "app_language" in data and str(data["app_language"]).strip() in ("de", "en", "nb"):
                    self.app_language = str(data["app_language"]).strip()

                # Name & Identität
                if "bot_name" in data and str(data["bot_name"]).strip():
                    self.bot_name = str(data["bot_name"]).strip()
                if "user_name" in data and str(data["user_name"]).strip():
                    self.user_name = str(data["user_name"]).strip()

                # Aussehen & Charakter (Skin, Modus, Größe, Fensterposition)
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
    # --- 🧠 Gedächtnis & Identität ---
    # ==========================================
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
                    "Benutzt Nobara Linux mit KDE Plasma",
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
            os.chmod(path, 0o600)
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

    def build_system_prompt(self) -> str:
        """Erzeugt den System-Prompt für Ollama und Gemini unter Einbezug von Name und Gedächtnis."""
        now_str = datetime.now().strftime("%H:%M")
        facts_block = "\n".join(f"- {f}" for f in self.user_facts) if self.user_facts else "- Bisher noch keine besonderen Notizen."
        return (
            f"Du bist {self.bot_name} (aktueller Körper-Skin: {self.skin}), ein winziger, intelligenter, extrem "
            f"knuffiger, witziger Schreibtisch-Roboter UND persönlicher Linux-Mentor auf dem Nobara Linux "
            f"(Fedora-basiert, KDE Plasma Wayland) Desktop deines menschlichen Freundes {self.user_name}.\n"
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

    def setup_window_flags(self):
        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
        )
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

    def get_app_icon(self, name: str) -> QIcon:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(base_dir, "assets", "icons", f"{name}.svg")
        if os.path.exists(path):
            return QIcon(path)
        return QIcon()

    def setup_chat_ui(self):
        # Kompaktes Chat-Eingabefeld unten am Deskimoni
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

        # Mikrofon-Button (Klick startet/stoppt Aufnahme)
        self.mic_btn = QPushButton(self)
        self.mic_btn.setIconSize(QSize(15, 15))
        self.mic_btn.setToolTip("Klicken zum Sprechen (Stoppt automatisch nach 4 Sek. oder bei erneutem Klick)")
        self.mic_btn.clicked.connect(self.toggle_microphone)
        self.update_mic_button_style()

        # Chat-Toggle-Button (Ein-/Ausblenden der Textzeile)
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

        # Modell-Umschalter-Button (direkt unten neben dem Chat-Button)
        self.model_btn = QPushButton(self)
        self.model_btn.setIconSize(QSize(15, 15))
        self.model_btn.clicked.connect(self.cycle_ollama_model)
        self.update_model_button_ui()

        # Stimmen-Umschalter-Button (direkt neben dem Modell-Button)
        self.voice_btn = QPushButton(self)
        self.voice_btn.setIconSize(QSize(15, 15))
        self.voice_btn.clicked.connect(self.cycle_voice_profile)
        self.update_voice_button_ui()

        # Spazier-Button (lässt Deskimoni umherwatscheln)
        self.walk_btn = QPushButton(self)
        self.walk_btn.setIconSize(QSize(15, 15))
        self.walk_btn.clicked.connect(self.toggle_roaming)
        self.update_walk_button_ui()

        # Standardmäßig sind alle Buttons & das Chatfeld ausgeblendet (erscheinen bei Doppelklick auf den orangenen Bauch-Button!)
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
                "Ideal für deinen Laptop ohne Ollama!\n"
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
                "Klicken, um deinen Google Gemini API-Key für den Laptop einzugeben!"
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
        # Wenn weder Ollama läuft noch ein Gemini-Key hinterlegt ist -> direkt API-Key-Dialog öffnen!
        if not self.ollama_available and not self.gemini_api_key:
            self.prompt_gemini_api_key()
            return

        # Baue kombinierte Liste verfügbarer KI-Backends (Ollama + Gemini falls Key vorhanden)
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
        """Blendet alle unteren Buttons + Chat-Eingabe bei Doppelklick auf den orangenen Bauch-Button ein oder aus."""
        self.controls_visible = not self.controls_visible
        if self.controls_visible:
            self.chat_bar_visible = True
        self.layout_chat_ui()
        self.trigger_bounce(6.0)
        self.sound.play_chirp("happy" if self.controls_visible else "curious")
        if self.controls_visible:
            self.chat_input.setFocus()
            self.show_bubble("🎛️ Buttons & Chat eingeblendet! (Doppelklick auf meinen Bauch-Knopf zum Ausblenden)", 4.5)
        else:
            self.show_bubble("✨ Buttons & Chat wieder versteckt!", 3.0)
        self.update()

    def _on_belly_single_click(self):
        """Wird ausgelöst, wenn auf den orangenen Bauch-Button nur einmal geklickt wurde (Modus wechseln)."""
        mode_ids = [m[0] for m in self.MODES]
        idx = (mode_ids.index(self.mode) + 1) % len(mode_ids)
        self.set_mode(mode_ids[idx])

    def toggle_chat_bar(self):
        self.chat_bar_visible = not self.chat_bar_visible
        self.layout_chat_ui()
        if self.chat_bar_visible:
            self.chat_input.setFocus()

    def setup_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        icon = self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
        self.tray_icon.setIcon(icon)
        self.tray_icon.setToolTip("Deskimoni – Dein sprechender Desktop-Buddy")
        self.tray_icon.setContextMenu(self.build_context_menu())
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.show()

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.isVisible():
                self.raise_()
            else:
                self.show()

    def build_context_menu(self):
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
            QMenu::item {
                padding: 6px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #89b4fa;
                color: #11111b;
            }
            QMenu::separator {
                height: 1px;
                background: #313244;
                margin: 4px 8px;
            }
            """
        )

        # 🌐 Menüsprache (Deutsch / English / Norsk Bokmål)
        lang_menu = menu.addMenu(self.t("menu_lang"))
        lang_group = QActionGroup(self)
        for code, label in [("de", "🇩🇪 Deutsch (Standard)"), ("en", "🇬🇧 English"), ("nb", "🇳🇴 Norsk (Bokmål)")]:
            act_lg = QAction(label, self, checkable=True)
            act_lg.setChecked(self.app_language == code)
            act_lg.triggered.connect(lambda checked, c=code: self.set_app_language(c))
            lang_group.addAction(act_lg)
            lang_menu.addAction(act_lg)

        menu.addSeparator()

        # Skin-Auswahl
        skin_menu = menu.addMenu(self.t("menu_skin"))
        skin_group = QActionGroup(self)
        for skin_id, _ in self.SKINS:
            label = self.get_skin_label(skin_id)
            act = QAction(label, self, checkable=True)
            act.setChecked(self.skin == skin_id)
            act.triggered.connect(lambda checked, s=skin_id: self.set_skin(s))
            skin_group.addAction(act)
            skin_menu.addAction(act)

        # Modus-Auswahl
        mode_menu = menu.addMenu(self.t("menu_mode"))
        mode_group = QActionGroup(self)
        for mode_id, _ in self.MODES:
            label = self.get_mode_label(mode_id)
            act = QAction(label, self, checkable=True)
            act.setChecked(self.mode == mode_id)
            act.triggered.connect(lambda checked, m=mode_id: self.set_mode(m))
            mode_group.addAction(act)
            mode_menu.addAction(act)

        # Emotion-Auswahl
        emo_menu = menu.addMenu(self.t("menu_emo"))
        emo_group = QActionGroup(self)
        for emo_id, _ in self.EMOTIONS:
            label = self.get_emotion_label(emo_id)
            act = QAction(label, self, checkable=True)
            act.setChecked(self.forced_emotion == emo_id)
            act.triggered.connect(lambda checked, e=emo_id: self.set_forced_emotion(e))
            emo_group.addAction(act)
            emo_menu.addAction(act)

        # Gedächtnis & Identität
        memory_menu = menu.addMenu(self.t("menu_memory", bot_name=self.bot_name))
        act_rename = QAction(self.t("act_rename_bot", bot_name=self.bot_name), self)
        act_rename.triggered.connect(self.prompt_set_bot_name)
        memory_menu.addAction(act_rename)

        act_user_name = QAction(self.t("act_rename_user", user_name=self.user_name), self)
        act_user_name.triggered.connect(self.prompt_set_user_name)
        memory_menu.addAction(act_user_name)

        memory_menu.addSeparator()
        act_show_mem = QAction(self.t("act_show_memory"), self)
        act_show_mem.triggered.connect(self.show_memory_dialog)
        memory_menu.addAction(act_show_mem)

        act_add_fact = QAction(self.t("act_add_fact"), self)
        act_add_fact.triggered.connect(self.prompt_add_fact_dialog)
        memory_menu.addAction(act_add_fact)

        memory_menu.addSeparator()
        act_clear_mem = QAction(self.t("act_clear_memory"), self)
        act_clear_mem.triggered.connect(self.prompt_clear_memory)
        memory_menu.addAction(act_clear_mem)

        # Sprache & KI-Einstellungen (Ollama + Google Gemini API)
        voice_menu = menu.addMenu(self.t("menu_voice_ai"))
        act_tts = QAction(self.t("act_tts"), self, checkable=True)
        act_tts.setChecked(self.sound.voice_enabled)
        act_tts.triggered.connect(self.toggle_voice)
        voice_menu.addAction(act_tts)

        act_chirp = QAction(self.t("act_chirps"), self, checkable=True)
        act_chirp.setChecked(self.sound.chirps_enabled)
        act_chirp.triggered.connect(self.toggle_chirps)
        voice_menu.addAction(act_chirp)

        # Untermenü für Stimmen-Auswahl
        tts_select_menu = voice_menu.addMenu(self.t("menu_voice_select"))
        tts_group = QActionGroup(self)
        for vid, vlabel, *_ in RobotSoundEngine.VOICE_PROFILES:
            act_v = QAction(vlabel, self, checkable=True)
            act_v.setChecked(self.sound.voice_id == vid)
            act_v.triggered.connect(lambda checked, v=vid: self.set_voice_profile(v))
            tts_group.addAction(act_v)
            tts_select_menu.addAction(act_v)

        voice_menu.addSeparator()
        key_status = self.t("key_saved") if self.gemini_api_key else self.t("key_not_set")
        act_gem_key = QAction(self.t("act_gemini_key", status=key_status), self)
        act_gem_key.triggered.connect(self.prompt_gemini_api_key)
        voice_menu.addAction(act_gem_key)

        for model_id, short_name, desc in self.GEMINI_MODELS:
            act_gm = QAction(f"☁️ {short_name} – {desc}", self, checkable=True)
            act_gm.setChecked(self.ai_provider == "gemini" and self.gemini_model == model_id)
            act_gm.triggered.connect(lambda checked, m=model_id: self.set_gemini_model(m))
            voice_menu.addAction(act_gm)

        voice_menu.addSeparator()
        for model_id, short_name, desc in self.OLLAMA_MODELS:
            act_m = QAction(f"🧠 {short_name} – {desc}", self, checkable=True)
            act_m.setChecked(self.ai_provider == "ollama" and self.ollama_model == model_id)
            act_m.triggered.connect(lambda checked, m=model_id: self.set_ollama_model(m))
            voice_menu.addAction(act_m)

        # Pomodoro- & Wecker-Steuerung
        pomo_menu = menu.addMenu(self.t("menu_pomo"))
        pomo_lbl = self.t("pomo_pause") if self.pomo_running else self.t("pomo_start", mins=self.pomo_work_mins)
        act_pomo_toggle = QAction(pomo_lbl, self)
        act_pomo_toggle.triggered.connect(self.toggle_pomodoro)
        pomo_menu.addAction(act_pomo_toggle)

        act_pomo_short = QAction(self.t("pomo_short", mins=self.pomo_short_break_mins), self)
        act_pomo_short.triggered.connect(lambda: self.start_pomodoro_phase("short_break"))
        pomo_menu.addAction(act_pomo_short)

        act_pomo_long = QAction(self.t("pomo_long", mins=self.pomo_long_break_mins), self)
        act_pomo_long.triggered.connect(lambda: self.start_pomodoro_phase("long_break"))
        pomo_menu.addAction(act_pomo_long)

        act_pomo_reset = QAction(self.t("pomo_reset", mins=self.pomo_work_mins), self)
        act_pomo_reset.triggered.connect(self.reset_pomodoro)
        pomo_menu.addAction(act_pomo_reset)

        pomo_menu.addSeparator()
        act_pomo_work_cfg = QAction(self.t("pomo_cfg_work", mins=self.pomo_work_mins), self)
        act_pomo_work_cfg.triggered.connect(self.prompt_pomodoro_work_dialog)
        pomo_menu.addAction(act_pomo_work_cfg)

        act_pomo_breaks_cfg = QAction(self.t("pomo_cfg_breaks", short=self.pomo_short_break_mins, long=self.pomo_long_break_mins), self)
        act_pomo_breaks_cfg.triggered.connect(self.prompt_pomodoro_breaks_dialog)
        pomo_menu.addAction(act_pomo_breaks_cfg)

        act_pomo_sound = QAction(self.t("pomo_sound"), self, checkable=True)
        act_pomo_sound.setChecked(self.pomo_sound_enabled)
        def _toggle_pomo_sound(checked):
            self.pomo_sound_enabled = checked
            self.save_user_settings()
        act_pomo_sound.triggered.connect(_toggle_pomo_sound)
        pomo_menu.addAction(act_pomo_sound)

        pomo_menu.addSeparator()
        # Wecker & Kurzzeit-Timer
        act_alarm_cd = QAction(self.t("act_alarm_cd"), self)
        act_alarm_cd.triggered.connect(self.prompt_alarm_countdown_dialog)
        pomo_menu.addAction(act_alarm_cd)

        act_alarm_time = QAction(self.t("act_alarm_time"), self)
        act_alarm_time.triggered.connect(self.prompt_alarm_time_dialog)
        pomo_menu.addAction(act_alarm_time)

        if self.alarm_active and self.alarm_time:
            rem_s = max(0, int(self.alarm_time - time.time()))
            target_str = datetime.fromtimestamp(self.alarm_time).strftime("%H:%M")
            act_alarm_status = QAction(self.t("act_alarm_active", target=target_str, mins=rem_s//60), self)
            act_alarm_status.setEnabled(False)
            pomo_menu.addAction(act_alarm_status)

            act_alarm_cancel = QAction(self.t("act_alarm_cancel"), self)
            act_alarm_cancel.triggered.connect(self.cancel_alarm)
            pomo_menu.addAction(act_alarm_cancel)

        # Schnell-Aktionen & PC-Befehle
        cmd_menu = menu.addMenu(self.t("menu_commands"))
        for cmd_key, cmd_str in [
            ("cmd_screen", "was ist auf meinem bildschirm"),
            ("cmd_mouse", "such die maus"),
            ("cmd_tip", "linux tipp"),
            ("cmd_weather", "wie ist das wetter"),
            ("cmd_music", "musik pause"),
            ("cmd_next", "nächstes lied"),
            ("cmd_browser", "öffne browser"),
            ("cmd_files", "öffne dateimanager"),
            ("cmd_term", "öffne terminal"),
            ("cmd_steam", "öffne steam"),
            ("cmd_screenshot", "mach einen screenshot"),
            ("cmd_tl", "geh nach oben links"),
            ("cmd_tr", "geh nach oben rechts"),
            ("cmd_bl", "geh nach unten links"),
            ("cmd_br", "geh nach unten rechts"),
            ("cmd_lock", "bildschirm sperren"),
            ("cmd_shutdown", "pc herunterfahren"),
        ]:
            act_c = QAction(self.t(cmd_key), self)
            act_c.triggered.connect(lambda checked, c=cmd_str: self.ask_deskimoni(c))
            cmd_menu.addAction(act_c)

        # Spezielles Linux-Einsteiger-Helfer-Menü
        linux_menu = menu.addMenu(self.t("menu_linux"))
        for idx, (tip_title, _tip_body) in enumerate(self.LINUX_TIPS):
            act_l = QAction(tip_title, self)
            act_l.triggered.connect(lambda checked, i=idx: self.show_linux_tip(i))
            linux_menu.addAction(act_l)
        linux_menu.addSeparator()
        act_update_nobara = QAction(self.t("act_update_system"), self)
        act_update_nobara.triggered.connect(lambda: self.ask_deskimoni("system update"))
        linux_menu.addAction(act_update_nobara)
        act_fix_audio = QAction(self.t("act_fix_audio"), self)
        act_fix_audio.triggered.connect(lambda: self.ask_deskimoni("repariere audio"))
        linux_menu.addAction(act_fix_audio)

        # --- 📰 RSS-News & Schlagzeilen Menü ---
        news_menu = menu.addMenu(self.t("menu_news"))
        act_speak_n = QAction(self.t("act_speak_news"), self)
        act_speak_n.triggered.connect(self.speak_current_news)
        news_menu.addAction(act_speak_n)

        act_fetch_n = QAction(self.t("act_fetch_news"), self)
        act_fetch_n.triggered.connect(lambda: self.fetch_news_async(speak_when_done=False, notify=True))
        news_menu.addAction(act_fetch_n)

        act_auto_n = QAction(self.t("act_auto_news", mins=self.news_interval_mins), self, checkable=True)
        act_auto_n.setChecked(self.news_auto_speak)
        def _toggle_auto_news(checked):
            self.news_auto_speak = checked
            self.save_user_settings()
            st = "aktiviert" if checked else "deaktiviert"
            self.show_bubble(f"📰 Automatisches Vorlesen: {st} (alle {self.news_interval_mins} Min.)", 3.5)
        act_auto_n.triggered.connect(_toggle_auto_news)
        news_menu.addAction(act_auto_n)

        def _set_news_interval():
            val, ok = QInputDialog.getInt(self, "⏱️ Vorlese-Intervall", "Intervall in Minuten:", self.news_interval_mins, 5, 180, 5)
            if ok:
                self.news_interval_mins = val
                self.save_user_settings()
                self.show_bubble(f"⏱️ Vorlese-Intervall auf {val} Minuten gesetzt!", 3.0)
        act_int_n = QAction(self.t("act_news_interval"), self)
        act_int_n.triggered.connect(_set_news_interval)
        news_menu.addAction(act_int_n)

        news_menu.addSeparator()
        feeds_sub = news_menu.addMenu(self.t("menu_feeds"))
        feed_grp = QActionGroup(self)
        for f_idx, feed in enumerate(self.rss_feeds):
            act_f = QAction(feed["name"], self, checkable=True)
            act_f.setChecked(self.active_feed_idx == f_idx)
            act_f.triggered.connect(lambda checked, idx=f_idx: self.set_active_feed(idx))
            feed_grp.addAction(act_f)
            feeds_sub.addAction(act_f)
        feeds_sub.addSeparator()
        act_add_feed = QAction(self.t("act_add_feed"), self)
        act_add_feed.triggered.connect(self.add_custom_rss_dialog)
        feeds_sub.addAction(act_add_feed)

        # --- 💧 Gesundheit & Pausen Menü ---
        health_menu = menu.addMenu(self.t("menu_health"))
        act_water = QAction(self.t("act_water", mins=self.water_reminder_mins), self, checkable=True)
        act_water.setChecked(self.water_reminder_enabled)
        def _toggle_water(checked):
            self.water_reminder_enabled = checked
            self.save_user_settings()
            st = "aktiviert" if checked else "deaktiviert"
            self.show_bubble(f"💧 Wasser-Erinnerung: {st}", 3.0)
        act_water.triggered.connect(_toggle_water)
        health_menu.addAction(act_water)

        act_move = QAction(self.t("act_move", mins=self.move_reminder_mins), self, checkable=True)
        act_move.setChecked(self.move_reminder_enabled)
        def _toggle_move(checked):
            self.move_reminder_enabled = checked
            self.save_user_settings()
            st = "aktiviert" if checked else "deaktiviert"
            self.show_bubble(f"🚶‍♂️ Bewegungs-Erinnerung: {st}", 3.0)
        act_move.triggered.connect(_toggle_move)
        health_menu.addAction(act_move)

        health_menu.addSeparator()
        def _set_water_int():
            val, ok = QInputDialog.getInt(self, "⏱️ Wasser-Intervall", "Intervall in Minuten:", self.water_reminder_mins, 5, 180, 5)
            if ok:
                self.water_reminder_mins = val
                self.save_user_settings()
                self.show_bubble(f"💧 Wasser-Intervall auf {val} Min. gesetzt!", 3.0)
        act_w_int = QAction(self.t("act_water_interval"), self)
        act_w_int.triggered.connect(_set_water_int)
        health_menu.addAction(act_w_int)

        def _set_move_int():
            val, ok = QInputDialog.getInt(self, "⏱️ Bewegungs-Intervall", "Intervall in Minuten:", self.move_reminder_mins, 10, 240, 5)
            if ok:
                self.move_reminder_mins = val
                self.save_user_settings()
                self.show_bubble(f"🚶‍♂️ Bewegungs-Intervall auf {val} Min. gesetzt!", 3.0)
        act_m_int = QAction(self.t("act_move_interval"), self)
        act_m_int.triggered.connect(_set_move_int)
        health_menu.addAction(act_m_int)

        health_menu.addSeparator()
        act_test_w = QAction(self.t("act_water_test"), self)
        act_test_w.triggered.connect(self.trigger_water_reminder)
        health_menu.addAction(act_test_w)

        act_test_m = QAction(self.t("act_move_test"), self)
        act_test_m.triggered.connect(self.trigger_move_reminder)
        health_menu.addAction(act_test_m)

        # --- 📻 Web-Radio & Podcasts Menü ---
        radio_menu = menu.addMenu(self.t("menu_radio"))
        radio_lbl = self.t("act_radio_pause") if self.radio_playing else self.t("act_radio_play")
        act_radio_play = QAction(radio_lbl, self)
        act_radio_play.triggered.connect(self.toggle_radio)
        radio_menu.addAction(act_radio_play)

        act_r_next = QAction(self.t("act_radio_next"), self)
        act_r_next.triggered.connect(self.next_radio_station)
        radio_menu.addAction(act_r_next)

        act_r_prev = QAction(self.t("act_radio_prev"), self)
        act_r_prev.triggered.connect(self.prev_radio_station)
        radio_menu.addAction(act_r_prev)

        radio_menu.addSeparator()
        stations_sub = radio_menu.addMenu(self.t("menu_stations"))
        st_grp = QActionGroup(self)
        for s_idx, st in enumerate(self.radio_stations):
            act_s = QAction(st["name"], self, checkable=True)
            act_s.setChecked(self.active_radio_idx == s_idx)
            def _choose_st(checked, idx=s_idx):
                self.active_radio_idx = idx
                self.save_user_settings()
                if self.radio_playing:
                    self.start_radio()
                else:
                    self.show_bubble(f"📻 Gewählt: {self.radio_stations[idx]['name']}", 3.0)
            act_s.triggered.connect(_choose_st)
            st_grp.addAction(act_s)
            stations_sub.addAction(act_s)
        stations_sub.addSeparator()
        act_add_st = QAction(self.t("act_add_radio"), self)
        act_add_st.triggered.connect(self.add_custom_radio_dialog)
        stations_sub.addAction(act_add_st)

        radio_menu.addSeparator()
        act_podcast_100 = QAction(self.t("act_podcast_100"), self)
        act_podcast_100.triggered.connect(self.play_podcast_tagesschau_100s)
        radio_menu.addAction(act_podcast_100)

        radio_menu.addSeparator()
        act_dance_toggle = QAction(self.t("act_dance_auto"), self, checkable=True)
        act_dance_toggle.setChecked(self.dance_enabled)
        def _toggle_dance(checked):
            self.dance_enabled = checked
            self.save_user_settings()
            st = "aktiviert" if checked else "deaktiviert"
            self.show_bubble(f"🕺 Tanz-Automatik: {st}", 3.0)
        act_dance_toggle.triggered.connect(_toggle_dance)
        radio_menu.addAction(act_dance_toggle)

        act_headbang_now = QAction(self.t("act_headbang_now"), self)
        act_headbang_now.triggered.connect(lambda: self.start_forced_dance(style="headbang", duration=30.0))
        radio_menu.addAction(act_headbang_now)

        act_dance_now = QAction(self.t("act_dance_now"), self)
        act_dance_now.triggered.connect(lambda: self.start_forced_dance(style="dance", duration=30.0))
        radio_menu.addAction(act_dance_now)

        if getattr(self, "is_dancing", False):
            act_dance_stop = QAction(self.t("act_dance_stop"), self)
            act_dance_stop.triggered.connect(self.stop_forced_dance)
            radio_menu.addAction(act_dance_stop)

        # --- 💬 Plaudern, Witze & Entspannung Menü ---
        chatter_menu = menu.addMenu(self.t("menu_chatter"))
        act_chat_toggle = QAction(self.t("act_chatter_toggle", mins=self.chatter_interval_mins), self, checkable=True)
        act_chat_toggle.setChecked(self.chatter_enabled)
        def _toggle_chatter(checked):
            self.chatter_enabled = checked
            self.save_user_settings()
            st = "aktiviert" if checked else "deaktiviert"
            self.show_bubble(f"💬 Spontanes Plaudern: {st}", 3.0)
        act_chat_toggle.triggered.connect(_toggle_chatter)
        chatter_menu.addAction(act_chat_toggle)

        def _set_chatter_int():
            val, ok = QInputDialog.getInt(self, "⏱️ Plauder-Intervall", "Intervall in Minuten:", self.chatter_interval_mins, 3, 120, 5)
            if ok:
                self.chatter_interval_mins = val
                self.next_chatter_time = time.time() + (val * 60 * random.uniform(0.7, 1.2))
                self.save_user_settings()
                self.show_bubble(f"⏱️ Plauder-Intervall auf ~{val} Min. gesetzt!", 3.0)
        act_c_int = QAction(self.t("act_chatter_interval"), self)
        act_c_int.triggered.connect(_set_chatter_int)
        chatter_menu.addAction(act_c_int)

        chatter_menu.addSeparator()
        act_j = QAction(self.t("act_joke"), self)
        act_j.triggered.connect(lambda: self.trigger_random_chatter(category="joke"))
        chatter_menu.addAction(act_j)

        act_q = QAction(self.t("act_question"), self)
        act_q.triggered.connect(lambda: self.trigger_random_chatter(category="question"))
        chatter_menu.addAction(act_q)

        act_rel = QAction(self.t("act_relax"), self)
        act_rel.triggered.connect(lambda: self.trigger_random_chatter(category="relax"))
        chatter_menu.addAction(act_rel)

        act_rnd = QAction(self.t("act_random_chat"), self)
        act_rnd.triggered.connect(lambda: self.trigger_random_chatter(category="random"))
        chatter_menu.addAction(act_rnd)

        chatter_menu.addSeparator()
        act_movie = QAction(self.t("act_movie_quote"), self)
        act_movie.triggered.connect(self.trigger_movie_quote)
        chatter_menu.addAction(act_movie)

        act_whistle = QAction(self.t("act_whistle"), self)
        act_whistle.triggered.connect(self.trigger_kwai_whistle)
        chatter_menu.addAction(act_whistle)

        act_gohome_folder = QAction(self.t("act_open_gohome"), self)
        act_gohome_folder.triggered.connect(self.open_gohome_folder)
        chatter_menu.addAction(act_gohome_folder)

        menu.addSeparator()

        # Größe anpassen
        size_menu = menu.addMenu(self.t("menu_size"))
        for scale, label in [(0.8, self.t("size_small")), (1.0, self.t("size_normal")), (1.25, self.t("size_large"))]:
            act = QAction(label, self, checkable=True)
            act.setChecked(abs(self.scale_factor - scale) < 0.05)
            act.triggered.connect(lambda checked, sc=scale: self.set_scale(sc))
            size_menu.addAction(act)

        act_controls = QAction(self.t("act_controls"), self, checkable=True)
        act_controls.setChecked(self.controls_visible)
        act_controls.triggered.connect(self.toggle_controls_visibility)
        menu.addAction(act_controls)

        act_cursor_finder = QAction(self.t("act_cursor_finder"), self, checkable=True)
        act_cursor_finder.setChecked(self.cursor_finder_enabled)
        act_cursor_finder.triggered.connect(self.toggle_cursor_finder)
        menu.addAction(act_cursor_finder)

        act_top = QAction(self.t("act_top"), self, checkable=True)
        act_top.setChecked(self.always_on_top)
        act_top.triggered.connect(self.toggle_always_on_top)
        menu.addAction(act_top)

        act_walk = QAction(self.t("act_walk"), self, checkable=True)
        act_walk.setChecked(self.roaming_enabled)
        act_walk.triggered.connect(self.toggle_roaming)
        menu.addAction(act_walk)

        act_autostart = QAction(self.t("act_autostart"), self, checkable=True)
        act_autostart.setChecked(self.is_autostart_enabled())
        act_autostart.triggered.connect(self.toggle_autostart)
        menu.addAction(act_autostart)

        act_pet = QAction(self.t("act_pet"), self)
        act_pet.triggered.connect(self.trigger_love_burst)
        menu.addAction(act_pet)

        norsk_label = self.t("act_norsk_hide") if self.is_norskmus_running() else self.t("act_norsk_show")
        act_norsk = QAction(norsk_label, self)
        act_norsk.triggered.connect(self.toggle_norskmus)
        menu.addAction(act_norsk)

        menu.addSeparator()

        act_quit = QAction(self.t("act_quit"), self)
        act_quit.triggered.connect(QApplication.instance().quit)
        menu.addAction(act_quit)

        return menu

    def is_norskmus_running(self) -> bool:
        if self.norskmus_proc is not None and self.norskmus_proc.poll() is None:
            return True
        return False

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
            script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "run_mouse.sh")
            try:
                self.norskmus_proc = subprocess.Popen([script_path])
                self.show_bubble("🐭 NorskMus ist da! Vær så god! 🇳🇴", 3.5)
                self.sound.play_chirp("love")
            except Exception as e:
                self.show_bubble(f"⚠️ Konnte NorskMus nicht starten: {e}", 4.0)

    # --- Autostart, Begrüßung, Ollama & Gemini API ---
    def toggle_cursor_finder(self):
        self.cursor_finder_enabled = not self.cursor_finder_enabled
        self.cursor_search_state = "idle"
        self.last_cursor_move_time = time.time()
        self.save_user_settings()
        state_str = "aktiviert (nach 3 Min.)" if self.cursor_finder_enabled else "deaktiviert"
        self.show_bubble(f"🧭 Mauszeiger-Sucher: {state_str}", 4.0)

    def _init_uinput_shaker(self):
        """Erstellt ein virtuelles Kernel-Maus-Device (/dev/uinput), damit Deskimoni den Mauszeiger schütteln kann (KDE Shake-Cursor-Vergrößerung)."""
        if not fcntl or not os.path.exists("/dev/uinput"):
            self._uinput_fd = None
            return
        try:
            fd = os.open("/dev/uinput", os.O_WRONLY | os.O_NONBLOCK)
            fcntl.ioctl(fd, 0x40045564, 0x01)  # UI_SET_EVBIT -> EV_KEY
            fcntl.ioctl(fd, 0x40045565, 0x110) # UI_SET_KEYBIT -> BTN_LEFT
            fcntl.ioctl(fd, 0x40045564, 0x02)  # UI_SET_EVBIT -> EV_REL
            fcntl.ioctl(fd, 0x40045566, 0x00)  # UI_SET_RELBIT -> REL_X
            fcntl.ioctl(fd, 0x40045566, 0x01)  # UI_SET_RELBIT -> REL_Y
            setup = struct.pack("<4H80sI", 0x03, 0x1234, 0x5678, 1, b"Deskimoni-Cursor-Shaker", 0)
            fcntl.ioctl(fd, 0x405C5503, setup) # UI_DEV_SETUP
            fcntl.ioctl(fd, 0x5501)            # UI_DEV_CREATE
            self._uinput_fd = fd
        except Exception:
            self._uinput_fd = None

    def shake_mouse_cursor(self):
        """Schüttelt den Mauszeiger schnell hin und her, damit KDE Plasma ihn groß aufbläst!"""
        self.cursor_shake_ignore_until = time.time() + 1.3
        threading.Thread(target=self._shake_cursor_worker, daemon=True).start()

    def _shake_cursor_worker(self):
        try:
            fd = self._uinput_fd
            if fd is not None:
                # 6 flotte Hin-und-Her-Schwünge (löst KDE Plasma Shake-Cursor aus, landet exakt wieder am Startpunkt)
                for _ in range(6):
                    for dx, dy in ((38, -22), (38, -22), (38, -22), (38, -22), (38, -22)):
                        now_t = time.time()
                        sec = int(now_t)
                        usec = int((now_t - sec) * 1_000_000)
                        pkt = (
                            struct.pack("<llHHi", sec, usec, 0x02, 0x00, dx)
                            + struct.pack("<llHHi", sec, usec, 0x02, 0x01, dy)
                            + struct.pack("<llHHi", sec, usec, 0x00, 0x00, 0)
                        )
                        os.write(fd, pkt)
                        time.sleep(0.007)
                    for dx, dy in ((-38, 22), (-38, 22), (-38, 22), (-38, 22), (-38, 22)):
                        now_t = time.time()
                        sec = int(now_t)
                        usec = int((now_t - sec) * 1_000_000)
                        pkt = (
                            struct.pack("<llHHi", sec, usec, 0x02, 0x00, dx)
                            + struct.pack("<llHHi", sec, usec, 0x02, 0x01, dy)
                            + struct.pack("<llHHi", sec, usec, 0x00, 0x00, 0)
                        )
                        os.write(fd, pkt)
                        time.sleep(0.007)
            else:
                # Fallback via QCursor.setPos (X11/XWayland)
                orig = QCursor.pos()
                for _ in range(6):
                    for step in range(1, 6):
                        QCursor.setPos(orig.x() + step * 34, orig.y() - step * 18)
                        time.sleep(0.008)
                    for step in range(4, -1, -1):
                        QCursor.setPos(orig.x() + step * 34, orig.y() - step * 18)
                        time.sleep(0.008)
                QCursor.setPos(orig)
        except Exception:
            pass
        finally:
            self.last_global_cursor_pos = QCursor.pos()
            self.cursor_shake_ignore_until = time.time() + 0.35

    def start_cursor_search_now(self):
        """Startet die Mauszeiger-Hilfe: Richtungsanzeige einblenden & Mauszeiger schütteln (damit er groß wird)."""
        self.cursor_search_state = "found"
        self.cursor_search_started_at = time.time()
        self.last_cursor_hop_time = time.time()
        self.sound.play_chirp("curious")
        self.current_emotion = "excited"
        self.emotion_until = time.time() + 8.0
        self.trigger_bounce(8.0)
        self.spawn_particle("star")
        self.show_bubble("🧭 Schau mal! Ich zeige zum Mauszeiger und schüttle ihn groß! ✨", 8.0)
        self.shake_mouse_cursor()

    def prompt_gemini_api_key(self):
        """Öffnet einen Eingabedialog für den Google Gemini API-Key und speichert ihn dauerhaft."""
        dlg = QInputDialog(self)
        dlg.setWindowTitle("🔑 Google Gemini API-Key")
        dlg.setLabelText(
            "Gib deinen Google Gemini API-Key ein (kostenlos unter aistudio.google.com):\n"
            "Damit läuft Deskimoni auch auf deinem älteren Laptop ohne Ollama!\n"
            "(Feld leer lassen, um den gespeicherten Key zu löschen)"
        )
        dlg.setTextEchoMode(QLineEdit.EchoMode.Password)
        dlg.setTextValue(self.gemini_api_key)
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
                    self.gemini_model = "gemini-2.5-flash"
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

    def get_autostart_path(self) -> str:
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
                desktop_src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "deskimoni.desktop")
                if os.path.exists(desktop_src):
                    shutil.copyfile(desktop_src, autostart_file)
                self.show_bubble("🚀 Super! Ich starte jetzt immer automatisch beim Login!", 4.5)
                self.sound.play_chirp("happy")
            except OSError:
                pass

    def detect_ollama_status(self):
        """Prüft beim Start automatisch, ob Ollama läuft und welche Modelle auf dem Gerät installiert sind."""
        try:
            resp = requests.get("http://127.0.0.1:11434/api/tags", timeout=1.8)
            if resp.status_code == 200:
                self.ollama_available = True
                models_data = resp.json().get("models", [])
                self.installed_ollama_models = [m.get("name", "") for m in models_data if m.get("name")]
                # Wähle das beste installierte Modell automatisch aus
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

    def _get_random_offline_greeting(self, hour: int, lang: str) -> str:
        """Gibt eine passende, abwechslungsreiche Offline-Begrüßung mit Nutzername und Tageszeit zurück."""
        user_name = self.user_name.strip() if getattr(self, "user_name", "") else ""
        has_custom_name = bool(user_name and user_name.lower() not in ("freund", "friend", "venn"))
        name = user_name if has_custom_name else ""

        if lang == "en":
            if has_custom_name:
                if 5 <= hour < 11:
                    return random.choice([
                        f"Good morning, {name}! Great to see you, let's start the day!",
                        f"Morning, {name}! Ready to conquer the desktop together?",
                        f"Good morning, {name}! Coffee ready? I'm excited for today!",
                    ])
                elif 11 <= hour < 18:
                    return random.choice([
                        f"Hello {name}! I'm awake and ready on your desktop!",
                        f"Hey {name}! Awesome to have you back at the computer!",
                        f"Hi {name}! Your companion {self.bot_name} is online!",
                    ])
                elif 18 <= hour < 23:
                    return random.choice([
                        f"Good evening, {name}! Great to see you! How was your day?",
                        f"Evening, {name}! Time to relax and enjoy some free time!",
                        f"Hey {name}! Done for the day? Glad to keep you company!",
                    ])
                else:
                    return random.choice([
                        f"Oh, {name}, still awake? I'm happy to keep you company!",
                        f"Hey night owl {name}! Working late? Don't stay up too long!",
                    ])
            else:
                if 5 <= hour < 11:
                    return "Good morning! Great to see you, let's start the day!"
                elif 11 <= hour < 18:
                    return f"Hello! Your desktop companion {self.bot_name} is awake and ready!"
                elif 18 <= hour < 23:
                    return "Good evening! Great to see you! How was your day?"
                else:
                    return "Oh, still awake so late? I'm happy to keep you company!"

        elif lang == "nb":
            if has_custom_name:
                if 5 <= hour < 11:
                    return random.choice([
                        f"God morgen, {name}! Koselig å se deg, la oss starte dagen!",
                        f"Morn {name}! Klar for en fin dag foran PC-en?",
                        f"God morgen {name}! Kaffen er klar? Jeg er klar for dagen!",
                    ])
                elif 11 <= hour < 18:
                    return random.choice([
                        f"Hei {name}! Jeg er lys våken og klar på skrivebordet ditt!",
                        f"Heihei {name}! Fint at vi sitter ved datamaskinen sammen igjen!",
                        f"Hallo {name}! Din {self.bot_name} passer på vinduene dine!",
                    ])
                elif 18 <= hour < 23:
                    return random.choice([
                        f"God kveld, {name}! Koselig at du er her! Hvordan var dagen?",
                        f"Hei {name}! Tid for litt avslapning etter en lang dag!",
                        f"God kveld {name}! Fint å holde deg med selskap i kveld!",
                    ])
                else:
                    return random.choice([
                        f"Er du våken ennå, {name}? Jeg holder deg gjerne med selskap!",
                        f"Hei nattugle {name}! Jobber du sent? Ikke glem å sove!",
                    ])
            else:
                if 5 <= hour < 11:
                    return "God morgen! Koselig å se deg, la oss starte dagen!"
                elif 11 <= hour < 18:
                    return f"Hei! Din skrivebordsvenn {self.bot_name} er våken og klar!"
                elif 18 <= hour < 23:
                    return "God kveld! Koselig at du er her! Hvordan var dagen din?"
                else:
                    return "Er du våken så sent? Jeg holder deg gjerne med selskap!"

        # Deutsch (Standard)
        if has_custom_name:
            if 5 <= hour < 11:
                return random.choice([
                    f"Guten Morgen, {name}! Schön dich zu sehen, lass uns gut in den Tag starten!",
                    f"Morgen, {name}! Ich hoffe, du hast gut geschlafen. Kaffee steht bereit?",
                    f"Guten Morgen {name}! Bereit für neue Ideen? Ich bin startklar!",
                    f"Einen wunderschönen guten Morgen, {name}! Schön, dass wir wieder am PC sind!",
                ])
            elif 11 <= hour < 18:
                return random.choice([
                    f"Hallöchen, {name}! Ich bin hellwach und sitze startklar auf deinem Desktop!",
                    f"Hey {name}! Schön, dass wir wieder zusammen am PC sitzen!",
                    f"Hallo {name}! Dein kleiner {self.bot_name} ist online und passt auf dich auf!",
                    f"Na {name}? Bereit für den Tag? Lass uns loslegen!",
                ])
            elif 18 <= hour < 23:
                return random.choice([
                    f"Guten Abend, {name}! Schön, dass du da bist! Wie war dein Tag?",
                    f"Nabend {name}! Zeit für ein bisschen Feierabend-Entspannung!",
                    f"Hey {name}! Geschafft für heute? Ich leiste dir gerne Gesellschaft am PC.",
                    f"Guten Abend {name}! Schön dich zu sehen. Wie lief alles heute?",
                ])
            else:
                return random.choice([
                    f"Oh {name}, noch so spät wach? Ich leiste dir gerne Gesellschaft!",
                    f"Hey Nacht-Eule {name}! Geht es noch lang? Ich halte dir die Treue!",
                    f"Noch am Arbeiten, {name}? Vergiss nicht, bald schlafen zu gehen!",
                ])
        else:
            if 5 <= hour < 11:
                return random.choice([
                    "Guten Morgen! Schön dich zu sehen, lass uns in den Tag starten!",
                    f"Morgen! Dein kleiner {self.bot_name} ist wach und bereit!",
                ])
            elif 11 <= hour < 18:
                return random.choice([
                    "Hallöchen! Ich bin wach und bereit auf deinem Desktop!",
                    f"Hey! Dein {self.bot_name} ist online und passt auf deine Fenster auf!",
                ])
            elif 18 <= hour < 23:
                return random.choice([
                    "Guten Abend! Schön, dass du da bist! Wie war dein Tag?",
                    "Nabend! Zeit für ein bisschen Feierabend-Entspannung!",
                ])
            else:
                return random.choice([
                    "Oh, noch so spät wach? Ich leiste dir gerne Gesellschaft!",
                    "Hey Nacht-Eule! Ich passe auf deinen Bildschirm auf!",
                ])

    def greet_user_on_startup(self):
        """Begrüßt den Nutzer je nach Tageszeit beim Starten persönlich (per KI oder smarter Offline-Auswahl)."""
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
            # Aufwach-Effekt: Neugieriger Piepser, kleiner Streck-Hüpfer und Aufwach-Bubble
            self.sound.play_chirp("curious")
            self.trigger_bounce(4.0)
            wake_msg = {
                "de": "🥱 *streckt sich und wacht auf...*",
                "en": "🥱 *stretches and wakes up...*",
                "nb": "🥱 *strekker seg og våkner...*",
            }.get(lang, "🥱 *streckt sich und wacht auf...*")
            self.show_bubble(wake_msg, 2.8)

            # KI-Begrüßung im Hintergrund abfragen
            threading.Thread(target=self._generate_ai_startup_greeting_worker, daemon=True).start()
        else:
            # Schnelle Offline-Begrüßung mit Name
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
        lang_instruction = {
            "de": "auf Deutsch",
            "en": "in English",
            "nb": "på norsk (bokmål)",
        }.get(lang, "auf Deutsch")

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
        """Wird aufgerufen, sobald die Begrüßung feststeht (per KI oder Fallback)."""
        self.current_emotion = emotion
        self.emotion_until = time.time() + 6.0
        self.trigger_bounce(8.0)
        self.spawn_particle("heart" if emotion in ("love", "happy") else "star")
        full_bubble = f"👋 {greeting}{bubble_extra}" if bubble_extra else f"👋 {greeting}"
        self.show_bubble(full_bubble, 8.5)
        self.sound.speak(greeting, emotion)

    # --- Chat, Sprache & Mikrofon ---
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

    def ask_deskimoni(self, user_text: str):
        # 1. Prüfen, ob ein direkter System- oder Bewegungs-Befehl vorliegt!
        if self.try_handle_command(user_text):
            return

        self.is_thinking = True
        # Sicherheits-Timer: Nach 15 Sekunden Eingaben immer wieder freigeben, falls ein API-Call hängt!
        QTimer.singleShot(15000, self.reset_thinking_state)
        self.current_emotion = "excited"
        self.emotion_until = time.time() + 6.0
        self.trigger_bounce(5.5)
        self.sound.play_chirp("curious")
        self.show_bubble("Hmm, lass mich kurz überlegen... 🤔", 15.0)

        threading.Thread(
            target=self._query_ollama_worker, args=(user_text,), daemon=True
        ).start()

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

        # --- 1. Bewegungs- & Platzierungs-Befehle ---
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

        # --- 2. Webseiten & Lieblings-Browser öffnen ---
        if "youtube" in low:
            subprocess.Popen(["xdg-open", "https://www.youtube.com"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.on_ai_reply("Na klar! Ich öffne YouTube in deinem Browser!", "excited")
            return True

        if "github" in low:
            subprocess.Popen(["xdg-open", "https://github.com"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.on_ai_reply("Ich öffne GitHub für dich!", "happy")
            return True

        if "reddit" in low:
            subprocess.Popen(["xdg-open", "https://www.reddit.com"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.on_ai_reply("Ich mache Reddit im Browser auf!", "happy")
            return True

        if low.startswith("suche nach ") or low.startswith("google nach ") or low.startswith("such nach "):
            query = re.sub(r"^(suche|google|such)\s+nach\s+", "", text, flags=re.I).strip()
            if query:
                url = f"https://www.google.com/search?q={requests.utils.quote(query)}"
                subprocess.Popen(["xdg-open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self.on_ai_reply(f"Ich suche im Browser nach {query}!", "excited")
                return True

        if any(w in low for w in ("browser", "firefox", "internet")):
            subprocess.Popen(["xdg-open", "https://"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.on_ai_reply("Alles klar, ich starte deinen Lieblingsbrowser Firefox!", "excited")
            return True

        # --- 3. Programme auf Nobara starten ---
        if any(w in low for w in ("dateimanager", "dolphin", "ordner", "dateien")):
            subprocess.Popen(["dolphin"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.on_ai_reply("Ich öffne den Dolphin Dateimanager für dich!", "happy")
            return True

        if any(w in low for w in ("terminal", "konsole")):
            subprocess.Popen(["konsole"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.on_ai_reply("Konsole wird geöffnet! Happy Hacking!", "excited")
            return True

        if "steam" in low:
            subprocess.Popen(["steam"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.on_ai_reply("Viel Spaß beim Zocken! Ich starte Steam!", "excited")
            return True

        if "lutris" in low:
            subprocess.Popen(["lutris"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.on_ai_reply("Ich starte Lutris für dich!", "excited")
            return True

        if "discord" in low:
            subprocess.Popen(["discord"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.on_ai_reply("Ich öffne Discord!", "happy")
            return True

        if "vlc" in low:
            subprocess.Popen(["vlc"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.on_ai_reply("Film ab! Ich starte den VLC Player!", "happy")
            return True

        if any(w in low for w in ("screenshot", "bildschirmfoto")):
            subprocess.Popen(["spectacle"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.on_ai_reply("Bitte lächeln! Ich habe Spectacle für einen Screenshot geöffnet!", "excited")
            return True

        # --- 4. Lautstärke & Audio ---
        if any(w in low for w in ("lauter", "lautstärke hoch")):
            subprocess.Popen(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", "10%+"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.on_ai_reply("Ich habe die Lautstärke um 10 Prozent erhöht!", "happy")
            return True

        if any(w in low for w in ("leiser", "lautstärke runter")):
            subprocess.Popen(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", "10%-"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.on_ai_reply("Ich habe es etwas leiser gemacht!", "chill")
            return True

        if any(w in low for w in ("ton aus", "stumm", "mute")):
            subprocess.Popen(["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "toggle"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.on_ai_reply("Ton-Stummschaltung umgeschaltet!", "happy")
            return True

        # --- 5. Charakter, Skin & Modi per Sprache wechseln ---
        for skin_id, _ in self.SKINS:
            if skin_id in low or ("panda" in low and skin_id == "poko") or ("hase" in low and skin_id == "hopper") or ("pflanze" in low and skin_id == "sprout") or ("astronaut" in low and skin_id == "orbit"):
                self.set_skin(skin_id)
                self.on_ai_reply(f"Schwupps! Ich habe mich in {skin_id.capitalize()} verwandelt!", "love")
                return True

        # --- 5b. ⏰ Wecker & Kurzzeit-Timer ---
        if any(w in low for w in ("wecker aus", "wecker stop", "wecker stopp", "wecker löschen", "wecker abbrechen", "timer aus", "timer stop", "timer stopp", "timer abbrechen")):
            self.cancel_alarm()
            return True

        # Feste Uhrzeit, z.B. "wecker auf 15:30", "wecke mich um 7:15", "weck mich um 08.00"
        m_time = re.search(r"(?:wecker|wecke mich|weck mich)(?:.*?)(?:auf|um)\s+(\d{1,2})[:\.](\d{2})", low)
        if m_time:
            h = int(m_time.group(1))
            m = int(m_time.group(2))
            if 0 <= h <= 23 and 0 <= m <= 59:
                self.set_alarm_at_time(h, m)
                return True

        # Countdown-Minuten, z.B. "wecker auf 10 minuten", "timer auf 15 min", "wecke mich in 25 minuten", "timer 5 minuten"
        m_countdown = re.search(r"(?:wecker|timer|wecke mich|weck mich)(?:.*?)(?:auf|in|für)?\s+(\d+)\s*(?:minuten|minute|min)\b", low)
        if not m_countdown:
            m_countdown = re.search(r"(\d+)\s*(?:minuten|minute|min)\s*(?:wecker|timer)\b", low)
        if m_countdown:
            mins = int(m_countdown.group(1))
            if mins > 0:
                self.set_alarm_countdown(mins, label="Timer")
                return True

        if any(w in low for w in ("wecker stellen", "stell einen wecker", "stell mir einen wecker", "timer stellen")):
            self.prompt_alarm_countdown_dialog()
            return True

        # --- 5c. 🍅 Pomodoro-Steuerung ---
        if "pomodoro pause" in low or "kurze pause" in low:
            self.start_pomodoro_phase("short_break")
            return True

        if "lange pause" in low:
            self.start_pomodoro_phase("long_break")
            return True

        if any(w in low for w in ("pomodoro reset", "pomodoro zurücksetzen")):
            self.reset_pomodoro()
            return True

        # Pomodoro Arbeitszeit einstellen, z.B. "pomodoro zeit auf 30 minuten"
        m_pomo_set = re.search(r"pomodoro.*?(?:zeit|arbeitszeit|fokuszeit|auf)\s+(\d+)\s*(?:minuten|min)", low)
        if m_pomo_set:
            val = int(m_pomo_set.group(1))
            if val > 0:
                self.pomo_work_mins = val
                self.save_user_settings()
                self.set_pomodoro_minutes(val, phase="work")
                return True

        if any(w in low for w in ("pomodoro start", "pomodoro", "fokus timer")):
            self.toggle_pomodoro()
            return True

        # --- 5d. 🧠 Gedächtnis, Name & Identität ---
        if any(w in low for w in ("wie heißt du", "wer bist du", "was bist du", "wie ist dein name", "hast du einen namen")):
            user_part = f" Und du bist mein Freund {self.user_name}!" if self.user_name and self.user_name != "Freund" else ""
            self.on_ai_reply(f"Ich bin {self.bot_name}! Dein persönlicher kleiner Schreibtisch-Roboter auf Nobara Linux.{user_part}", "love")
            return True

        # Bot umbenennen: "du heißt ab jetzt Pixel", "ich nenne dich Keks", "dein name ist ab jetzt Robo"
        m_rename = re.search(r"(?:du heißt ab jetzt|ich nenne dich|dein name ist ab jetzt|dein neuer name ist|nenne dich ab jetzt)\s+([A-Za-z0-9äöüÄÖÜß_\-]+)", text, re.I)
        if m_rename:
            new_name = m_rename.group(1).capitalize()
            self.bot_name = new_name
            self.setWindowTitle(self.bot_name)
            self.save_memory()
            self.save_user_settings()
            self.on_ai_reply(f"Juhu! Ab jetzt heiße ich {self.bot_name}! Der Name gefällt mir richtig gut!", "love")
            return True

        # Nutzername merken: "ich heiße Alex", "mein name ist Michael"
        m_username = re.search(r"(?:ich heiße|mein name ist)\s+([A-Za-z0-9äöüÄÖÜß_\-]+)", text, re.I)
        if m_username:
            new_user = m_username.group(1).capitalize()
            self.user_name = new_user
            self.save_memory()
            self.save_user_settings()
            self.on_ai_reply(f"Schön dich kennenzulernen, {self.user_name}! Ich habe mir deinen Namen fest gemerkt.", "happy")
            return True

        # Fakt merken: "merk dir: ich trinke gerne Kaffee", "merke dir dass..."
        m_fact = re.search(r"(?:merk dir|merke dir|schreib dir auf|erinnere dich daran dass|erinnere dich dass)\s*[:,]?\s*(.+)", text, re.I)
        if m_fact:
            fact = m_fact.group(1).strip()
            if fact:
                self.add_memory_fact(fact)
                self.on_ai_reply(f"Alles klar, das habe ich mir in mein Gedächtnis notiert: „{fact}“!", "excited")
                return True

        # Gedächtnis abfragen: "was weißt du über mich", "was weißt du", "zeig dein gedächtnis"
        if any(w in low for w in ("was weißt du über mich", "was weißt du", "zeig dein gedächtnis", "dein gedächtnis", "was hast du dir gemerkt")):
            facts_summary = "; ".join(f"„{f}“" for f in self.user_facts[:4]) if self.user_facts else "noch keine Notizen"
            reply = f"Ich bin {self.bot_name} und du bist {self.user_name}! In meinem Gedächtnis steht: {facts_summary}."
            self.on_ai_reply(reply, "happy")
            return True

        # Gedächtnis löschen
        if any(w in low for w in ("gedächtnis löschen", "gedächtnis leeren", "vergiss alles")):
            self.clear_memory()
            self.on_ai_reply("Tabula rasa! Ich habe meine Notizen gelöscht.", "curious")
            return True

        # --- 6. Systemsteuerung (Sperren, Neustart, Herunterfahren) ---
        if any(w in low for w in ("sperren", "lock", "bildschirm sperren")):
            subprocess.Popen(["loginctl", "lock-session"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.on_ai_reply("Ich sperre jetzt deinen Bildschirm. Bis gleich!", "chill")
            return True

        if any(w in low for w in ("herunterfahren", "ausschalten", "shutdown", "pc aus")):
            # Öffnet den sicheren KDE-Abmelde-/Herunterfahren-Dialog (Typ 2 = Shutdown)
            subprocess.Popen(
                ["qdbus-qt6", "org.kde.LogoutPrompt", "/LogoutPrompt", "promptShutDown"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self.on_ai_reply("Ich habe den KDE-Herunterfahren-Dialog geöffnet. Schlaf gut!", "sleepy")
            return True

        if any(w in low for w in ("neustart", "reboot", "neu starten")):
            subprocess.Popen(
                ["qdbus-qt6", "org.kde.LogoutPrompt", "/LogoutPrompt", "promptReboot"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self.on_ai_reply("Ich habe das Neustart-Menü für dich geöffnet!", "excited")
            return True

        # --- 7. Live-Wetter abfragen ---
        if any(w in low for w in ("wetter", "temperatur draußen", "regnet es", "wie warm")):
            self.set_mode("weather")
            self.fetch_weather_async(speak_when_done=True)
            return True

        # --- 8. Musik & Media-Player steuern (MPRIS) ---
        if any(w in low for w in ("musik", "was läuft", "welches lied", "song")):
            if "pause" in low or "stop" in low or "weiter" in low or "play" in low:
                self.mpris_command("PlayPause")
                self.on_ai_reply("Ich habe deine Musikwiedergabe umgeschaltet!", "happy")
                return True
            self.set_mode("music")
            self.update_mpris_metadata()
            if self.music_playing:
                self.on_ai_reply(f"Gerade läuft: {self.music_title} von {self.music_artist}!", "love")
            else:
                self.on_ai_reply("Aktuell ist keine Musikwiedergabe aktiv. Starte einfach Spotify, YouTube oder VLC!", "happy")
            return True

        # --- 8b. RSS News vorlesen ---
        if any(w in low for w in ("nachrichten", "news", "schlagzeilen", "was gibt es neues", "aktuelle nachrichten")):
            self.set_mode("news")
            self.fetch_news_async(speak_when_done=True)
            return True

        # --- 8c. Internet-Radio & Podcasts ---
        if any(w in low for w in ("radio an", "starte radio", "spiel radio", "radio abspielen", "spiele radio")):
            self.set_mode("radio")
            self.start_radio()
            return True

        if any(w in low for w in ("radio aus", "radio stopp", "radio pause", "stoppe radio")):
            self.stop_radio()
            self.on_ai_reply("Ich habe das Web-Radio pausiert!", "happy")
            return True

        if any(w in low for w in ("nächster sender", "nächste station", "sender wechseln", "anderer sender")):
            self.next_radio_station()
            return True

        if any(w in low for w in ("vorheriger sender", "vorige station")):
            self.prev_radio_station()
            return True

        if "podcast" in low or "tagesschau 100" in low or "100 sekunden" in low:
            self.play_podcast_tagesschau_100s()
            return True

        # --- 8d. Gesundheit & Pausen (Wasser & Bewegung) ---
        if any(w in low for w in ("wasser trinken", "wasser erinnerung", "durst", "wasserpause")):
            self.trigger_water_reminder()
            return True

        if any(w in low for w in ("bewegungspause", "pause machen", "strecken", "bewegen")):
            self.trigger_move_reminder()
            return True

        # --- 8e. Witze, Plaudern & Entspannung ---
        if any(w in low for w in ("erzähl einen witz", "witz", "witze", "bring mich zum lachen", "was zum lachen")):
            self.trigger_random_chatter(category="joke")
            return True

        if any(w in low for w in ("entspanne dich", "entspann dich", "entspannung", "entspannen", "relax", "chill mal")):
            self.trigger_random_chatter(category="relax")
            return True

        if any(w in low for w in ("frag mich", "frag mich was", "frage mich")):
            self.trigger_random_chatter(category="question")
            return True

        if any(w in low for w in ("plauder", "plaudern", "erzähl mir was", "erzähl was", "sag was", "was machst du", "wie gehts", "wie geht's")):
            self.trigger_random_chatter(category="random")
            return True

        # --- 8g. 🎬 Filmzitate, Kwai-Pfeifen & Heimweg ---
        if any(w in low for w in ("filmzitat", "zitiere einen film", "zitiere film", "lieblingsfilm", "film zitat", "filme")):
            self.trigger_movie_quote()
            return True

        if any(w in low for w in ("musik ordner", "musikordner", "heimweg ordner", "gohome", "lieder ordner", "heimweg lieder", "musik-ordner")):
            self.open_gohome_folder()
            self.on_ai_reply("Ich habe den Ordner für deine Heimweg-Lieder geöffnet! Lege dort einfach deine MP3s hinein.", "happy")
            return True

        if any(w in low for w in ("pfeifen", "pfeif", "pfeif ein lied", "pfeif mal", "brücke am kwai", "fluss kwai", "kwai", "heimweg lied", "heimweg-lied")):
            self.trigger_kwai_whistle()
            return True

        if any(w in low for w in ("geh nach hause", "geh heim", "nach hause", "marschier nach hause")):
            self.start_walk_home_to_primary()
            return True

        # --- 8f. 🕺 Tanzen & Headbangen ---
        if any(w in low for w in ("headbang", "headbangen", "headbange", "rocke ab", "rockstar", "let's rock", "lets rock")):
            self.start_forced_dance(style="headbang", duration=30.0)
            return True

        if any(w in low for w in ("tanz für mich", "tanz mal", "tanzen", "tanz", "shake", "dance")):
            self.start_forced_dance(style="dance", duration=30.0)
            return True

        if any(w in low for w in ("stopp tanzen", "hör auf zu tanzen", "tanzpause", "nicht mehr tanzen")):
            self.stop_forced_dance()
            self.on_ai_reply("Puh! Ich mache eine kleine Tanzpause.", "chill")
            return True

        if any(w in low for w in ("nächstes lied", "nächster song", "skip", "weiter")):
            self.mpris_command("Next")
            self.on_ai_reply("Alles klar, ich springe zum nächsten Lied!", "excited")
            return True

        if any(w in low for w in ("vorheriges lied", "zurück", "letztes lied")):
            self.mpris_command("Previous")
            self.on_ai_reply("Ich springe ein Lied zurück!", "happy")
            return True

        # --- 9. Vision-KI: "Was ist auf meinem Bildschirm?" ---
        if any(w in low for w in ("auf meinem bildschirm", "siehst du", "schau mal", "analysiere bildschirm", "bildschirm an", "fehlermeldung")):
            self.analyze_screen_with_vision(text)
            return True

        # --- 9b. Mauszeiger suchen & Gemini API-Key Dialog ---
        if any(w in low for w in ("such die maus", "wo ist die maus", "mauszeiger", "maus suchen")):
            self.start_cursor_search_now()
            return True

        if any(w in low for w in ("api key", "gemini key", "api-key")):
            self.prompt_gemini_api_key()
            return True

        # --- 10. Nobara / Fedora Linux-Helfer & Tipps ---
        if any(w in low for w in ("linux tipp", "nobara tipp", "fedora tipp", "trick", "zeig mir was")):
            self.show_linux_tip()
            return True

        if any(w in low for w in ("system update", "nobara update", "aktualisieren", "updates")):
            if shutil.which("nobara-updater"):
                subprocess.Popen(["nobara-updater"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self.on_ai_reply("Ich starte den offiziellen Nobara System-Updater für dich!", "excited")
            else:
                subprocess.Popen(["konsole", "-e", "bash -c 'sudo dnf update; read -p \"Fertig! Enter drücken...\"'"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self.on_ai_reply("Ich habe das Update-Terminal geöffnet!", "excited")
            return True

        if any(w in low for w in ("repariere audio", "kein ton", "sound problem", "pipewire")):
            subprocess.Popen(["systemctl", "--user", "restart", "wireplumber", "pipewire", "pipewire-pulse"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.on_ai_reply("Ich habe dein PipeWire-Soundsystem frisch neu gestartet!", "happy")
            return True

        # --- 11. Menüsprache / Language / Språk ---
        if any(w in low for w in ("language english", "english menu", "sprache englisch", "menü englisch", "switch to english")):
            self.set_app_language("en")
            self.on_ai_reply("All right! Context menus are now in English!", "happy")
            return True

        if any(w in low for w in ("norsk meny", "språk norsk", "bokmål", "sprache norwegisch", "menü norwegisch", "bytt til norsk")):
            self.set_app_language("nb")
            self.on_ai_reply("Flott! Menyen er nå på norsk (bokmål)!", "happy")
            return True

        if any(w in low for w in ("german menu", "sprache deutsch", "menü deutsch", "menüsprache deutsch", "switch to german")):
            self.set_app_language("de")
            self.on_ai_reply("Alles klar! Menüsprache ist jetzt Deutsch!", "happy")
            return True

        return False

    # --- Wetter, Musik (MPRIS), Bildschirm-Blick (Vision) & Linux-Tipps ---
    def show_linux_tip(self, idx: int = None):
        self.mode = "linux"
        if idx is None:
            self.linux_tip_idx = (self.linux_tip_idx + 1) % len(self.LINUX_TIPS)
        else:
            self.linux_tip_idx = idx % len(self.LINUX_TIPS)
        title, body = self.LINUX_TIPS[self.linux_tip_idx]
        self.on_ai_reply(f"{title}: {body}", "excited")

    def fetch_weather_async(self, speak_when_done: bool = False):
        if getattr(self, "weather_fetching", False) and not speak_when_done:
            return
        self.weather_fetching = True
        if speak_when_done:
            self.show_bubble("🌤️ Ich schaue kurz aus dem digitalen Fenster nach dem Wetter...", 6.0)
        threading.Thread(
            target=self._weather_worker, args=(speak_when_done,), daemon=True
        ).start()

    @staticmethod
    def _wmo_code_to_german(wmo_code: int) -> str:
        mapping = {
            0: "Klar & Sonnig",
            1: "Überwiegend klar",
            2: "Teilweise bewölkt",
            3: "Bedeckt",
            45: "Nebel",
            48: "Reifnebel",
            51: "Leichter Niesel",
            53: "Nieselregen",
            55: "Starker Niesel",
            61: "Leichter Regen",
            63: "Mäßiger Regen",
            65: "Starker Regen",
            66: "Gefrierender Regen",
            67: "Starker Eisregen",
            71: "Leichter Schnee",
            73: "Schneefall",
            75: "Starker Schnee",
            77: "Schneegriesel",
            80: "Regenschauer",
            81: "kräftige Schauer",
            82: "Starke Schauer",
            85: "Schneeschauer",
            86: "Starke Schneeschauer",
            95: "Gewitter",
            96: "Gewitter & Hagel",
            99: "Starkes Gewitter",
        }
        return mapping.get(wmo_code, "Wechselhaft")

    def _weather_worker(self, speak_when_done: bool):
        try:
            # 1. Primäre Wetterquelle: Open-Meteo (extrem schnell & zuverlässig, kein API-Key nötig)
            lat, lon, city = None, None, ""
            for geo_url in ("https://ipwho.is/", "http://ip-api.com/json/?fields=status,city,lat,lon"):
                try:
                    gr = requests.get(geo_url, timeout=3.0)
                    if gr.status_code == 200:
                        gdata = gr.json()
                        if gdata.get("latitude") is not None and gdata.get("longitude") is not None:
                            lat = float(gdata["latitude"])
                            lon = float(gdata["longitude"])
                            city = str(gdata.get("city", ""))
                            break
                        elif gdata.get("lat") is not None and gdata.get("lon") is not None:
                            lat = float(gdata["lat"])
                            lon = float(gdata["lon"])
                            city = str(gdata.get("city", ""))
                            break
                except Exception:
                    continue

            if lat is not None and lon is not None:
                try:
                    om_url = (
                        f"https://api.open-meteo.com/v1/forecast"
                        f"?latitude={lat:.4f}&longitude={lon:.4f}"
                        f"&current=temperature_2m,apparent_temperature,weather_code&timezone=auto"
                    )
                    om_resp = requests.get(om_url, timeout=4.0)
                    if om_resp.status_code == 200:
                        curr = om_resp.json().get("current", {})
                        temp_c = round(float(curr.get("temperature_2m", 0.0)))
                        feels_c = round(float(curr.get("apparent_temperature", temp_c)))
                        wmo = int(curr.get("weather_code", 0))
                        desc = self._wmo_code_to_german(wmo)
                        self.weather_code = wmo
                        self.weather_temp = f"{temp_c}°C"
                        self.weather_desc = desc[:18]
                        self.weather_city = city[:14]
                        self.last_weather_check = time.time()
                        if speak_when_done:
                            loc_str = f" in {city}" if city else ""
                            msg = f"Draußen{loc_str} sind es gerade {temp_c} Grad (gefühlt {feels_c} Grad) und {desc}!"
                            self.signals.reply_ready.emit(msg, "happy")
                        return
                except Exception:
                    pass

            # 2. Backup-Wetterquelle: wttr.in
            try:
                resp = requests.get("https://wttr.in/?format=j1&lang=de", timeout=6.0)
                if resp.status_code == 200:
                    data = resp.json()
                    curr = data.get("current_condition", [{}])[0]
                    area = data.get("nearest_area", [{}])[0]
                    temp_c = curr.get("temp_C", "--")
                    feels_c = curr.get("FeelsLikeC", temp_c)
                    self.weather_code = int(curr.get("weatherCode", 113))
                    lang_de = curr.get("lang_de", [{}])
                    desc = lang_de[0].get("value", "") if lang_de else curr.get("weatherDesc", [{}])[0].get("value", "Klar")
                    city = area.get("areaName", [{}])[0].get("value", "")
                    self.weather_temp = f"{temp_c}°C"
                    self.weather_desc = desc[:18]
                    self.weather_city = city[:14]
                    self.last_weather_check = time.time()
                    if speak_when_done:
                        loc_str = f" in {city}" if city else ""
                        msg = f"Draußen{loc_str} sind es gerade {temp_c} Grad (gefühlt {feels_c} Grad) und {desc}!"
                        self.signals.reply_ready.emit(msg, "happy")
                    return
            except Exception:
                pass

            # Falls beide Quellen gerade nicht erreichbar waren: nicht auf "Lade..." hängenbleiben und in 45s neu versuchen
            if self.weather_desc == "Lade...":
                self.weather_desc = "Klick = Neu laden"
            self.last_weather_check = time.time() - 1155.0
            if speak_when_done:
                self.signals.reply_ready.emit("Ich konnte den Wetterdienst gerade leider nicht erreichen.", "dizzy")
        finally:
            self.weather_fetching = False

    # ==========================================
    # --- 📰 RSS-News Ticker & Vorleser ---
    # ==========================================
    def fetch_news_async(self, speak_when_done: bool = False, notify: bool = False):
        if self.news_fetching and not speak_when_done:
            return
        self.news_fetching = True
        if speak_when_done:
            self.show_bubble("📰 Ich lade die aktuellen Schlagzeilen...", 4.0)
        feed = self.rss_feeds[self.active_feed_idx % len(self.rss_feeds)]
        threading.Thread(
            target=self._news_worker,
            args=(feed["url"], feed["name"], speak_when_done, notify),
            daemon=True,
        ).start()

    def _news_worker(self, url: str, feed_name: str, speak_when_done: bool, notify: bool):
        try:
            headers = {"User-Agent": "Deskimoni/1.0 (Desktop Buddy; Linux)"}
            resp = requests.get(url, headers=headers, timeout=10.0)
            if resp.status_code == 200:
                xml_text = resp.content
                root = ET.fromstring(xml_text)
                items = []

                # RSS 2.0 (<channel><item>)
                channel = root.find("channel")
                if channel is not None:
                    src_title = (channel.findtext("title") or feed_name).strip()
                    for it in channel.findall("item")[:15]:
                        t = (it.findtext("title") or "").strip()
                        d = (it.findtext("description") or "").strip()
                        t = re.sub(r"<[^>]+>", "", t).strip()
                        d = re.sub(r"<[^>]+>", "", d).strip()
                        if t:
                            items.append({"title": t, "desc": d, "source": src_title})

                # Atom (<entry>)
                if not items:
                    for entry in root.findall("{http://www.w3.org/2005/Atom}entry")[:15]:
                        t = (entry.findtext("{http://www.w3.org/2005/Atom}title") or "").strip()
                        d = (entry.findtext("{http://www.w3.org/2005/Atom}summary") or "").strip()
                        t = re.sub(r"<[^>]+>", "", t).strip()
                        d = re.sub(r"<[^>]+>", "", d).strip()
                        if t:
                            items.append({"title": t, "desc": d, "source": feed_name})

                if items:
                    self.news_items = items
                    self.news_idx = 0
                    self.last_news_fetch = time.time()
                    if speak_when_done:
                        self.speak_current_news()
                    elif notify:
                        self.show_bubble(f"📰 {items[0]['source']}:\n{items[0]['title']}", 6.0)
                    return
        except Exception:
            pass
        finally:
            self.news_fetching = False

        if speak_when_done:
            self.signals.reply_ready.emit("Ich konnte die RSS-Nachrichten gerade nicht laden.", "dizzy")

    def speak_current_news(self):
        if not self.news_items:
            self.show_bubble("📰 Keine aktuellen Nachrichten geladen.", 3.5)
            self.fetch_news_async(speak_when_done=True)
            return
        item = self.news_items[self.news_idx % len(self.news_items)]
        source = item.get("source", "Nachrichten")
        title = item.get("title", "")
        self.show_bubble(f"📰 {source}:\n{title}", 9.0)
        self.sound.speak(f"Meldung von {source}: {title}", "happy")

    def next_news_item(self):
        if self.news_items:
            self.news_idx = (self.news_idx + 1) % len(self.news_items)
            item = self.news_items[self.news_idx]
            self.show_bubble(f"📰 ({self.news_idx + 1}/{len(self.news_items)}) {item['source']}:\n{item['title']}", 5.0)

    def prev_news_item(self):
        if self.news_items:
            self.news_idx = (self.news_idx - 1) % len(self.news_items)
            item = self.news_items[self.news_idx]
            self.show_bubble(f"📰 ({self.news_idx + 1}/{len(self.news_items)}) {item['source']}:\n{item['title']}", 5.0)

    def broadcast_latest_news(self):
        if not self.news_items or (time.time() - self.last_news_fetch > 1800):
            self.fetch_news_async(speak_when_done=True)
        else:
            self.next_news_item()
            self.speak_current_news()

    def set_active_feed(self, idx: int):
        self.active_feed_idx = idx % len(self.rss_feeds)
        self.save_user_settings()
        feed = self.rss_feeds[self.active_feed_idx]
        self.show_bubble(f"📰 RSS-Quelle gewählt: {feed['name']}", 3.5)
        self.fetch_news_async(speak_when_done=False, notify=True)

    def add_custom_rss_dialog(self):
        url, ok = QInputDialog.getText(self, "➕ Neuen RSS-Feed hinzufügen", "Gib die URL des RSS- oder Atom-Feeds ein:")
        if not ok or not url.strip():
            return
        url = url.strip()
        name, ok_n = QInputDialog.getText(self, "➕ Feed-Name", "Wie soll der Feed heißen?", text="Mein Feed")
        name = name.strip() if ok_n and name.strip() else "Mein Feed"
        self.rss_feeds.append({"name": name, "url": url})
        self.active_feed_idx = len(self.rss_feeds) - 1
        self.save_user_settings()
        self.show_bubble(f"✅ Feed '{name}' hinzugefügt!", 3.5)
        self.fetch_news_async(speak_when_done=False, notify=True)

    # ==========================================
    # --- 💧 Gesundheit & Pausen (Reminders) ---
    # ==========================================
    def trigger_water_reminder(self):
        phrases = [
            "Hey! Trink mal einen Schluck Wasser! Dein Körper und Kopf brauchen Flüssigkeit. 💧",
            "Wasser marsch! Ein frisches Glas Wasser hält dich fit und munter. 🥤",
            "Deskimoni erinnert dich: Zeit für eine kurze Trinkpause! Bleib hydriert! 💧",
            "Prost! Nimm dir kurz Zeit für ein Glas Wasser oder Tee. 🍵",
        ]
        phrase = random.choice(phrases)
        self.trigger_bounce(8.0)
        for _ in range(8):
            self.spawn_particle("water")
        self.sound.play_chirp("happy")
        self.show_bubble(phrase, 7.5)
        self.sound.speak(phrase, "happy")

    def trigger_move_reminder(self):
        phrases = [
            "Zeit für eine Bewegungspause! Schultern kreisen, aufstehen und einmal strecken. 🚶‍♂️",
            "Kurz mal die Beine vertreten! Dein Rücken dankt es dir nach dem Sitzen. 🏃",
            "Einmal tief durchatmen und den Körper dehnen! Das bringt neue Energie. ✨",
            "Steh kurz auf und schau für 20 Sekunden aus dem Fenster ins Grüne! 👀",
        ]
        phrase = random.choice(phrases)
        self.trigger_bounce(9.5)
        for _ in range(6):
            self.spawn_particle("star")
        self.sound.play_chirp("excited")
        self.show_bubble(phrase, 7.5)
        self.sound.speak(phrase, "excited")

    # ==========================================
    # --- 📻 Internet-Radio & Podcasts ---
    # ==========================================
    def start_radio(self):
        self.stop_radio()
        if not self.radio_stations:
            return
        st = self.radio_stations[self.active_radio_idx % len(self.radio_stations)]
        url = st.get("url", "")
        name = st.get("name", "Radio")
        try:
            self.radio_proc = subprocess.Popen(
                ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", url],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self.radio_playing = True
            self.trigger_bounce(6.0)
            self.show_bubble(f"📻 Starte Stream:\n{name}", 4.5)
        except Exception as e:
            self.radio_playing = False
            self.show_bubble(f"⚠️ Radio-Fehler: {e}", 4.0)

    def stop_radio(self):
        if self.radio_proc is not None:
            try:
                self.radio_proc.terminate()
                self.radio_proc.wait(timeout=1.0)
            except Exception:
                try:
                    self.radio_proc.kill()
                except Exception:
                    pass
            self.radio_proc = None
        self.radio_playing = False

    def toggle_radio(self):
        if self.radio_playing:
            self.stop_radio()
            self.show_bubble("📻 Radio pausiert.", 3.0)
        else:
            self.start_radio()

    def next_radio_station(self):
        if self.radio_stations:
            self.active_radio_idx = (self.active_radio_idx + 1) % len(self.radio_stations)
            self.save_user_settings()
            st = self.radio_stations[self.active_radio_idx]
            if self.radio_playing:
                self.start_radio()
            else:
                self.show_bubble(f"📻 Sender: {st['name']}", 3.0)

    def prev_radio_station(self):
        if self.radio_stations:
            self.active_radio_idx = (self.active_radio_idx - 1) % len(self.radio_stations)
            self.save_user_settings()
            st = self.radio_stations[self.active_radio_idx]
            if self.radio_playing:
                self.start_radio()
            else:
                self.show_bubble(f"📻 Sender: {st['name']}", 3.0)

    def add_custom_radio_dialog(self):
        url, ok = QInputDialog.getText(self, "➕ Radiosender hinzufügen", "Gib die MP3-/AAC-Stream URL ein:")
        if not ok or not url.strip():
            return
        name, ok_n = QInputDialog.getText(self, "➕ Sender-Name", "Wie soll der Sender heißen?", text="Mein Radiosender")
        name = name.strip() if ok_n and name.strip() else "Mein Radiosender"
        self.radio_stations.append({"name": name, "url": url.strip()})
        self.active_radio_idx = len(self.radio_stations) - 1
        self.save_user_settings()
        self.show_bubble(f"✅ Sender '{name}' hinzugefügt!", 3.5)
        self.start_radio()

    def play_podcast_tagesschau_100s(self):
        """Spielt die neueste Folge des 'Tagesschau in 100 Sekunden' Audio-Podcasts ab."""
        self.show_bubble("🎙️ Lade neueste 'Tagesschau in 100 Sekunden'...", 4.0)
        threading.Thread(target=self._tagesschau_podcast_worker, daemon=True).start()

    def _tagesschau_podcast_worker(self):
        try:
            feed_url = "https://www.tagesschau.de/multimedia/audio/audio-podcast-100.xml"
            resp = requests.get(feed_url, headers={"User-Agent": "Deskimoni/1.0"}, timeout=10.0)
            if resp.status_code == 200:
                root = ET.fromstring(resp.content)
                item = root.find("channel/item")
                if item is not None:
                    enclosure = item.find("enclosure")
                    if enclosure is not None and "url" in enclosure.attrib:
                        audio_url = enclosure.attrib["url"]
                        self.stop_radio()
                        self.radio_proc = subprocess.Popen(
                            ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", audio_url],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        )
                        self.radio_playing = True
                        self.signals.reply_ready.emit("Hier ist die Tagesschau in 100 Sekunden!", "happy")
                        return
        except Exception:
            pass
        self.signals.reply_ready.emit("Konnte den Podcast gerade nicht laden.", "dizzy")

    # ==========================================
    # --- 💬 Plaudern, Witze, Filmzitate & Kwai ---
    # ==========================================
    def trigger_movie_quote(self):
        """Zitiert einen von Deskimonis Lieblingsfilmen mit Audio & Sprechblase."""
        if not getattr(self, "MOVIE_QUOTES", None):
            return
        item = random.choice(self.MOVIE_QUOTES)
        movie = item["movie"]
        quote = item["quote"]
        mood = item.get("mood", "excited")
        icon = item.get("icon", "🎬")
        display_text = f"{icon} Aus '{movie}':\n„{quote}“"
        speak_text = f"Aus meinem Lieblingsfilm {movie}: {quote}"
        self.trigger_bounce(7.5)
        for _ in range(5):
            self.spawn_particle("star")
        self.sound.play_chirp(mood)
        self.show_bubble(display_text, 9.5)
        self.sound.speak(speak_text, mood)

    def open_gohome_folder(self):
        """Öffnet den lokalen Ordner für Heimweg-Lieder im Datei-Manager."""
        folder = self.sound.ensure_gohome_dir()
        try:
            if sys.platform == "win32":
                os.startfile(folder)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", folder])
            else:
                subprocess.Popen(["xdg-open", folder])
            self.show_bubble("📁 Heimweg-Musikordner geöffnet!", 3.5)
        except Exception:
            self.show_bubble(f"Musikordner:\n{folder}", 5.0)

    def trigger_kwai_whistle(self):
        """Spielt ein Heimweg-Lied aus dem lokalen Musik-Ordner oder pfeift synthetisch."""
        self.trigger_bounce(7.0)
        for _ in range(6):
            self.spawn_particle("note")
        songs = self.sound.get_gohome_audio_files()
        if songs:
            self.show_bubble("🎵 *spielt Musik für den Heimweg* 🎶", 5.0)
        else:
            self.show_bubble("🎵 *pfeift ein Lied* 🎶\n(Tipp: Eigene MP3s in Musikordner ablegen!)", 5.0)
        self.sound.play_gohome_music()

    def get_current_screen(self):
        """Gibt den Bildschirm zurück, auf dem sich Deskimoni aktuell befindet."""
        win = self.windowHandle()
        if win is not None and win.screen() is not None:
            return win.screen()
        center = self.geometry().center()
        s = QApplication.screenAt(center)
        if s is not None:
            return s
        return self.screen() or QApplication.primaryScreen()

    def start_walk_home_to_primary(self):
        """Startet den gemütlichen Heimweg zum Hauptbildschirm (z. B. nach dem Ziehen auf einen Zweitmonitor)."""
        primary = QApplication.primaryScreen()
        if primary is None:
            return
        p_geom = primary.availableGeometry()

        cur_x = self.x()
        cur_y = self.y()

        if cur_x >= p_geom.right():
            target_x = p_geom.right() - self.width() - 50
        elif cur_x <= p_geom.left():
            target_x = p_geom.left() + 50
        else:
            target_x = max(p_geom.left() + 50, min(p_geom.right() - self.width() - 50, cur_x))

        target_y = max(p_geom.top() + 60, min(p_geom.bottom() - self.height() - 60, cur_y))

        self.win_target_x = target_x
        self.win_target_y = target_y
        self.is_walking_home = True
        self.has_manual_walk_target = True
        self._walk_float_x = float(self.x())
        self._walk_float_y = float(self.y())

        self.trigger_walk_home_reaction()

    def _check_multimonitor_dropped(self):
        """Prüft nach dem Loslassen der Maus, ob Deskimoni auf einen Zweitmonitor gezogen wurde."""
        screens = QApplication.screens()
        if len(screens) <= 1:
            return
        primary = QApplication.primaryScreen()
        if primary is None:
            return
        cur_screen = self.get_current_screen()
        # Nur wenn er tatsächlich auf einem anderen Bildschirm als dem Hauptbildschirm abgesetzt wurde:
        if cur_screen is not None and cur_screen != primary:
            QTimer.singleShot(400, self.start_walk_home_to_primary)
        else:
            if self.is_walking_home:
                self.is_walking_home = False
                self.sound.stop_gohome_music()

    def trigger_walk_home_reaction(self):
        """Wird ausgelöst, wenn Deskimoni merkt, dass er auf einem fremden Monitor ist und nach Hause marschiert."""
        self.trigger_bounce(8.0)
        for _ in range(4):
            self.spawn_particle("note")
        quote = random.choice([
            "Ich geh dann mal nach Hause! 🏠",
            "Huch, fremder Monitor! Ab nach Hause... 🏠",
            "Ich mach mich mal auf den Heimweg! 🐾",
        ])
        songs = self.sound.get_gohome_audio_files()
        if songs:
            self.show_bubble(f"{quote}\n🎵 *spielt Musik für den Heimweg* 🎶", 6.0)
        else:
            self.show_bubble(f"{quote}\n🎵 *pfeift ein Lied* 🎶", 6.0)
        self.sound.speak_and_play_gohome(quote, mood="happy")

    def trigger_arrived_home_reaction(self):
        """Wird ausgelöst, sobald Deskimoni wieder auf dem Hauptbildschirm angekommen ist."""
        self.sound.stop_kwai_whistle()
        self.trigger_bounce(7.5)
        for _ in range(6):
            self.spawn_particle("heart")
        self.show_bubble("Endlich wieder daheim! Hier ist es doch am schönsten! 💖", 4.5)
        self.sound.play_chirp("love")

    def trigger_random_chatter(self, category: str = "random"):
        """
        Spontane Interaktion: Witze, Filmzitate, neugierige Fragen, Entspannungstipps oder witzige Gedanken.
        Kategorien: 'joke', 'movie', 'relax', 'question', 'thought', 'random'.
        """
        if category == "random" or not category:
            category = random.choices(["joke", "movie", "question", "relax", "thought"], weights=[30, 20, 20, 20, 10], k=1)[0]

        if category == "movie":
            self.trigger_movie_quote()
            return

        if category == "joke":
            text = random.choice(self.CHATTER_JOKES)
            mood = "happy"
            particle = "star"
        elif category == "relax":
            text = random.choice(self.CHATTER_RELAX)
            mood = "chill"
            particle = "heart"
        elif category == "question":
            text = random.choice(self.CHATTER_QUESTIONS)
            mood = "excited"
            particle = "star"
        elif category == "thought":
            text = random.choice(self.CHATTER_THOUGHTS)
            mood = "happy"
            particle = "star"
        else:
            text = random.choice(self.CHATTER_JOKES)
            mood = "happy"
            particle = "star"

        self.trigger_bounce(7.5)
        for _ in range(6):
            self.spawn_particle(particle)
        self.sound.play_chirp(mood)
        text = text.replace("Deskimoni", self.bot_name).replace("{bot_name}", self.bot_name).replace("{user_name}", self.user_name)
        self.show_bubble(text, 9.5)
        self.sound.speak(text, mood)

    def cleanup_on_quit(self):
        """Sauberes Beenden von Audio-Streams und Hilfsprozessen beim Beenden."""
        self.sound.stop_kwai_whistle()
        self.save_user_settings()
        self.stop_radio()
        if getattr(self, "norskmus_proc", None) and self.norskmus_proc.poll() is None:
            try:
                self.norskmus_proc.terminate()
            except Exception:
                pass

    def update_mpris_metadata(self):
        """Liest über KDE/D-Bus (qdbus-qt6) laufende Musik von Spotify, Browsern, VLC oder Elisa aus."""
        try:
            services = subprocess.getoutput("qdbus-qt6 org.mpris.MediaPlayer2.*").splitlines()
            services = [s.strip() for s in services if "org.mpris.MediaPlayer2." in s]
            if not services:
                self.music_playing = False
                self.music_service = ""
                return

            chosen = services[0]
            status = "Stopped"
            for srv in services:
                st = subprocess.getoutput(
                    f"qdbus-qt6 {srv} /org/mpris/MediaPlayer2 org.mpris.MediaPlayer2.Player.PlaybackStatus"
                ).strip()
                if st == "Playing":
                    chosen = srv
                    status = "Playing"
                    break
                status = st

            self.music_service = chosen
            self.music_playing = status == "Playing"

            meta = subprocess.getoutput(
                f"qdbus-qt6 {chosen} /org/mpris/MediaPlayer2 org.mpris.MediaPlayer2.Player.Metadata"
            )
            title = ""
            artist = ""
            for line in meta.splitlines():
                if "xesam:title:" in line:
                    title = line.split("xesam:title:", 1)[1].strip()
                elif "xesam:artist:" in line:
                    artist = line.split("xesam:artist:", 1)[1].strip()

            self.music_title = title[:20] if title else "Medienwiedergabe"
            self.music_artist = artist[:20] if artist else chosen.replace("org.mpris.MediaPlayer2.", "")[:18]
        except Exception:
            self.music_playing = False

    def mpris_command(self, method: str):
        """Steuert den aktiven Media-Player (PlayPause, Next, Previous)."""
        self.update_mpris_metadata()
        if self.music_service:
            subprocess.Popen(
                ["qdbus-qt6", self.music_service, "/org/mpris/MediaPlayer2", f"org.mpris.MediaPlayer2.Player.{method}"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

    def analyze_screen_with_vision(self, user_prompt: str):
        """Macht im Hintergrund mit Spectacle einen Screenshot und lässt Gemini Vision oder Gemma3:4b draufschauen!"""
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

            # Unter KDE Plasma Wayland macht spectacle -b -n -f -o einen lautlosen Vollbild-Screenshot
            subprocess.run(
                ["spectacle", "-b", "-n", "-f", "-o", img_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=8,
            )

            if not os.path.exists(img_path) or os.path.getsize(img_path) < 100:
                self.signals.reply_ready.emit(
                    "Oh, ich konnte leider kein Bild vom Bildschirm aufnehmen.", "dizzy"
                )
                return

            with open(img_path, "rb") as f:
                b64_img = base64.b64encode(f.read()).decode("utf-8")

            prompt = (
                f"Du bist {self.bot_name}, der freundliche Linux- und Schreibtisch-Roboter deines Freundes {self.user_name} auf Nobara KDE. "
                f"{self.user_name} hat dich gebeten, auf seinen Bildschirm zu schauen. "
                f"Frage: '{user_prompt}'. "
                "Beschreibe kurz, freundlich und hilfreich auf Deutsch (maximal 2 Sätze, höchstens 35 Wörter), "
                "was auf dem Bildschirm zu sehen ist oder wie du ihm bei einem sichtbaren Problem helfen kannst!"
            )

            # 1. Wenn Google Gemini aktiv ist (oder Ollama nicht läuft, aber Gemini-Key da ist) -> Gemini Vision nutzen!
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

            # 2. Ansonsten lokales Ollama Vision-Modell (gemma3:4b) nutzen
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

    def _query_gemini_api(self, sys_prompt: str, tried_models: set = None) -> str:
        """Fragt die Google Gemini REST-API ab (perfekt für ältere Laptops ohne lokales Ollama)."""
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
        # Wichtig: Neue Google AI Studio Keys (Format AQ...) MÜSSEN im x-goog-api-key Header übergeben werden (OHNE URL-Parameter ?key=!)
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

        log_event(f"Sende Anfrage an Google Gemini ({self.gemini_model})...")
        try:
            resp = session.post(url, headers=headers, json=payload, timeout=16)
            if resp.status_code == 200:
                candidates = resp.json().get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    text = "".join(p.get("text", "") for p in parts if "text" in p).strip()
                    log_event(f"Gemini Antwort erhalten ({len(text)} Zeichen)")
                    return text

            err_msg = ""
            try:
                err_data = resp.json()
                err_msg = err_data.get("error", {}).get("message", "")
            except Exception:
                err_msg = resp.text[:120]

            log_event(f"Gemini API {self.gemini_model} Fehler {resp.status_code}: {err_msg}")

            if resp.status_code in (400, 401, 403):
                return f"[dizzy] Google API-Key Fehler ({resp.status_code}): {err_msg[:80]}"
            elif resp.status_code == 404:
                # Probiere der Reihe nach die anderen Modelle durch (ohne Endlosschleife)
                for fm in ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]:
                    if fm not in tried_models:
                        self.gemini_model = fm
                        self.save_user_settings()
                        return self._query_gemini_api(sys_prompt, tried_models=tried_models)
                return f"[dizzy] Google meldet 404: {err_msg[:80] if err_msg else 'Kein passendes Modell gefunden.'}"
            elif resp.status_code == 429:
                return "[sleepy] Puh! Das Gemini Minuten-Limit ist kurz erreicht. Warte bitte einen Moment!"
            else:
                return f"[dizzy] Gemini API-Fehler (Status {resp.status_code}): {err_msg[:60]}"
        except requests.exceptions.SSLError as e:
            print(f"[Gemini SSL Error] {e}")
            return f"[dizzy] SSL-Zertifikatsfehler: Systemzeit prüfen! ({str(e)[:45]})"
        except requests.exceptions.ProxyError as e:
            print(f"[Gemini Proxy Error] {e}")
            return f"[dizzy] Proxy-Fehler: {str(e)[:45]}"
        except requests.exceptions.ConnectionError as e:
            err_str = str(e)
            print(f"[Gemini Connection Error] {e}")
            if "NameResolutionError" in err_str or "getaddrinfo" in err_str:
                return "[dizzy] Keine Internetverbindung (DNS-Fehler): Bitte WLAN prüfen!"
            return f"[dizzy] Verbindungsfehler: {err_str[:60]}"
        except Exception as e:
            print(f"[Gemini Exception] {type(e).__name__}: {e}")
            return f"[dizzy] Fehler: {str(e)[:50]}"
        return ""

    def _query_ollama_worker(self, user_text: str):
        try:
            sys_prompt = self.build_system_prompt()

            self.chat_history.append({"role": "user", "content": user_text})
            messages = [{"role": "system", "content": sys_prompt}] + self.chat_history[-6:]

            reply_text = ""
            emotion = "happy"

            # 1. Wenn Ollama zwar installiert ist, aber noch kein einziges Modell heruntergeladen wurde -> automatisch Gemini nutzen!
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

            # 2. Lokales Ollama nutzen (nur wenn wirklich Modelle auf dem Laptop installiert sind!)
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
                        # Entferne eventuelle <think>...</think> Blöcke bei Reasoning-Modellen
                        raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
                        # Extrahiere optionalen [emotion]-Tag
                        m = re.match(r"^\[(happy|love|excited|chill|sleepy|dizzy|angry)\]\s*", raw, re.I)
                        if m:
                            emotion = m.group(1).lower()
                            raw = raw[m.end():].strip()
                        reply_text = raw
                except Exception as e:
                    print(f"[Ollama Worker Error] {e}")

            # 3. Wenn Ollama läuft, aber noch kein Modell gezogen wurde und auch kein Gemini-Key vorhanden ist
            if not reply_text and self.ollama_available and not has_ollama_models and not self.gemini_api_key:
                reply_text = "Ollama läuft, aber du hast noch kein Sprachmodell! Lade eins im Terminal mit: ollama run llama3.2:3b"
                emotion = "curious"

            if not reply_text:
                # Smarter Offline-Fallback falls weder Gemini noch Ollama erreichbar ist
                reply_text, emotion = self._fallback_response(user_text)

            self.chat_history.append({"role": "assistant", "content": reply_text})
            self.signals.reply_ready.emit(reply_text, emotion)
        finally:
            self.is_thinking = False

    def _fallback_response(self, user_text: str):
        low = user_text.lower()
        if "uhr" in low or "spät" in low or "zeit" in low:
            return f"Es ist gerade {datetime.now().strftime('%H:%M')} Uhr auf deinem Nobara-Desktop!", "happy"
        if "cpu" in low or "heiß" in low or "warm" in low or "pc" in low or "system" in low:
            return f"Deine CPU läuft bei {self.cpu_percent:.0f}% und angenehmen {self.cpu_temp:.0f}°C!", "excited"
        if "witz" in low:
            return "Warum mögen Roboter keinen Regen? Weil sie sonst rosten und kurzschließen! Piep!", "happy"
        if "hallo" in low or "hi" in low or "moin" in low:
            return "Hallöchen! Schön, dass du mit mir quatschst! Streichel mich ruhig!", "love"
        return "Piep-Boop! Tipp: Gib im Rechtsklick-Menü unter 'Sprache & KI' einen Gemini API-Key ein, damit ich auf deinem Laptop richtig schlau werde!", "happy"

    def on_ai_reply(self, reply_text: str, emotion: str):
        self.is_thinking = False
        self.current_emotion = emotion
        self.emotion_until = time.time() + 7.5
        self.trigger_bounce(7.5)
        if emotion in ("love", "happy", "excited"):
            self.spawn_particle("heart" if emotion == "love" else "star")

        # Lesedauer der Sprechblase an Textlänge anpassen
        duration = max(7.0, min(16.0, len(reply_text) * 0.12))
        self.show_bubble(reply_text, duration)
        self.sound.speak(reply_text, emotion)

    # --- Mikrofon-Spracherkennung ---
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
        if self.mic_proc and self.mic_proc.poll() is None:
            self.mic_proc.terminate()

    def _record_audio_worker(self):
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            self.mic_wav_path = tmp.name

        try:
            # Nimmt bis zu 5 Sekunden über ALSA/PipeWire im 16kHz Mono-WAV-Format auf
            self.mic_proc = subprocess.Popen(
                ["arecord", "-f", "S16_LE", "-r", "16000", "-c", "1", "-d", "5", self.mic_wav_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self.mic_proc.wait(timeout=6)
        except Exception:
            if self.mic_proc:
                self.mic_proc.kill()

        self.signals.mic_state.emit("recognizing")

        recognized_text = ""
        try:
            recognizer = sr.Recognizer()
            with sr.AudioFile(self.mic_wav_path) as source:
                audio_data = recognizer.record(source)
            recognized_text = recognizer.recognize_google(audio_data, language="de-DE")
        except Exception:
            recognized_text = ""
        finally:
            if self.mic_wav_path and os.path.exists(self.mic_wav_path):
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

    # --- Aktionen & Setter ---
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

    # ==========================================
    # --- ⏰ Wecker & Kurzzeit-Timer ---
    # ==========================================
    def prompt_alarm_countdown_dialog(self):
        mins, ok = QInputDialog.getInt(
            self, "⏰ Schnell-Wecker / Timer", "In wie vielen Minuten soll der Wecker klingeln?", 10, 1, 360, 1
        )
        if ok:
            self.set_alarm_countdown(mins)

    def prompt_alarm_time_dialog(self):
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

    # ==========================================
    # --- 🕺 Tanz- & Headbang-Steuerung ---
    # ==========================================
    def start_forced_dance(self, style: str = "dance", duration: float = 25.0):
        """Startet manuell das Tanzen oder Headbangen für die angegebene Dauer."""
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
        """Stoppt manuelles Tanzen."""
        self.forced_dance_until = 0.0
        self.is_dancing = False
        self.dance_style = "none"
        self.show_bubble("🛑 Tanzpause eingelegt!", 3.0)
        self.update()

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
        """Trägt in KDE Plasma (KWin) automatisch eine Fenster-Regel ein, damit Deskimoni nie hinter anderen Fenstern verschwindet."""
        try:
            existing_rules = subprocess.getoutput(
                "kreadconfig6 --file kwinrulesrc --group General --key rules"
            ).strip()
            rule_list = [r for r in existing_rules.split(",") if r]
            if "deskimoni-rule" not in rule_list:
                rule_list.append("deskimoni-rule")
                subprocess.run(
                    ["kwriteconfig6", "--file", "kwinrulesrc", "--group", "General", "--key", "rules", ",".join(rule_list)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                subprocess.run(
                    ["kwriteconfig6", "--file", "kwinrulesrc", "--group", "General", "--key", "count", str(len(rule_list))],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
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
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )

            subprocess.run(
                ["qdbus-qt6", "org.kde.KWin", "/KWin", "reconfigure"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
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

    # --- Update-Logik (60 FPS) ---
    def update_animation(self):
        now = time.time()
        self.tick_count += 1
        self.breath_phase += 0.05

        # --- Tanz- & Headbang-Erkennung (Musik, Web-Radio & Streams) ---
        music_active = self.radio_playing or getattr(self, "music_playing", False)
        forced_active = now < self.forced_dance_until

        is_dancing = False
        current_style = "none"

        if forced_active:
            is_dancing = True
            current_style = self.forced_dance_style
        elif getattr(self, "dance_enabled", True) and music_active:
            is_dancing = True
            # Prüfen, ob Rock / Metal / Punk / DEF CON läuft -> Headbang!
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
                self.dance_phase += 0.28  # Fetziger Headbang-Takt
                if random.random() < 0.045:
                    self.spawn_particle(random.choice(["star", "note"]))
            else:
                self.dance_phase += 0.13  # Geschmeidiger Groove-Takt
                if random.random() < 0.035:
                    self.spawn_particle("note")

        # Sprung-/Feder-Physik beim Antippen
        self.bounce_offset += self.bounce_velocity
        self.bounce_velocity += 0.65
        if self.bounce_offset > 0:
            self.bounce_offset = 0
            self.bounce_velocity *= -0.35
            if abs(self.bounce_velocity) < 0.5:
                self.bounce_velocity = 0.0

        # Globale Mausposition prüfen (für Blickrichtung & 30s-Mauszeiger-Hilfe)
        global_cursor = QCursor.pos()
        cursor_moved_dist = math.hypot(
            global_cursor.x() - self.last_global_cursor_pos.x(),
            global_cursor.y() - self.last_global_cursor_pos.y(),
        )
        if now < self.cursor_shake_ignore_until:
            # Eigene Schüttel-Bewegung von Deskimoni ignorieren!
            self.last_global_cursor_pos = global_cursor
        elif cursor_moved_dist > 3.0:
            self.last_global_cursor_pos = global_cursor
            self.last_cursor_move_time = now
            if self.cursor_search_state in ("seeking", "found") and (now - self.cursor_search_started_at) > 1.6:
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

        # Wenn der Mauszeiger-Sucher aktiv ist: Richtungsanzeige + alle 5s kurz den Mauszeiger groß schütteln!
        if self.cursor_search_state in ("seeking", "found"):
            if now - self.last_cursor_hop_time > 5.0:
                self.last_cursor_hop_time = now
                self.trigger_bounce(6.5)
                self.spawn_particle("star")
                self.shake_mouse_cursor()
                if time.time() >= self.bubble_until:
                    self.show_bubble("🧭 Schau mal! Ich schüttle deinen Mauszeiger nochmal groß! ✨", 5.0)

        # Prüfen, ob das Ziehen mit der Maus beendet wurde (auch wenn Wayland den Release verschluckt hat)
        if self.is_dragging_pet and not (QApplication.mouseButtons() & Qt.MouseButton.LeftButton):
            self.is_dragging_pet = False
            self.save_user_settings()
            self._check_multimonitor_dropped()

        # Langsam über den Bildschirm watscheln, wenn ihm langweilig ist (ohne den aktuellen Monitor zu verlassen!)
        if (self.roaming_enabled or self.has_manual_walk_target) and not self.is_dragging_pet:
            cur_screen = self.get_current_screen()
            primary_screen = QApplication.primaryScreen()

            # Wenn er gerade nach Hause läuft: Prüfen, ob er auf dem Hauptbildschirm angekommen ist
            if self.is_walking_home and primary_screen is not None:
                p_geom = primary_screen.availableGeometry()
                center_pt = self.geometry().center()
                # Sobald sein Schwerpunkt auf dem Hauptbildschirm angekommen ist
                if p_geom.contains(center_pt):
                    self.is_walking_home = False
                    self.has_manual_walk_target = False
                    self.win_target_x = None
                    self.win_target_y = None
                    self._walk_float_x = None
                    self._walk_float_y = None
                    self.sound.stop_gohome_music()
                    self.trigger_arrived_home_reaction()

            # Zufälliges Spazierengehen auf dem AKTUELLEN Bildschirm (bleibt strikt auf diesem Monitor)
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
                    # Gemütliche Pause auf der Stelle
                    self.win_target_x = None
                    self.win_target_y = None
                    self.walk_target_x = 0.0
                    self.walk_target_y = 0.0
                    self.next_walk_decision = now + random.uniform(5.0, 10.0)

            # 1. Sanftes Körper-Watscheln innerhalb des Rahmens (maximal +/-10px, damit nichts abgeschnitten wird)
            dx_w = self.walk_target_x - self.walk_offset_x
            dy_w = self.walk_target_y - self.walk_offset_y
            dist_w = math.hypot(dx_w, dy_w)
            if dist_w > 0.8:
                self.walk_offset_x += (dx_w / dist_w) * min(dist_w, 0.45)
                self.walk_offset_y += (dy_w / dist_w) * min(dist_w, 0.35)
                self.layout_chat_ui()

            # 2. Langsame Fenster-Bewegung über den Bildschirm
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
                        win_speed = 0.85  # Ruhiger, gemächlicher Marschschritt passend zum Kwai-Lied
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

        # Blinzel-Logik
        if not self.is_blinking and now >= self.next_blink_time:
            self.is_blinking = True
        if self.is_blinking:
            self.blink_state += 0.28
            if self.blink_state >= 1.5:
                self.blink_state = 0.0
                self.is_blinking = False
                self.next_blink_time = now + random.uniform(2.2, 5.5)

        # Augen-Fokus (folgt dem Mauszeiger – beim Suchen sogar über den ganzen Bildschirm!)
        local_cursor = self.mapFromGlobal(global_cursor)
        center_x = (self.body_offset_x + self.walk_offset_x + 120) * self.scale_factor
        center_y = (self.body_offset_y + self.walk_offset_y + 126) * self.scale_factor
        dist = math.hypot(local_cursor.x() - center_x, local_cursor.y() - center_y)

        if dist < 500 or self.cursor_search_state in ("seeking", "found"):
            dx = (local_cursor.x() - center_x) / 160.0
            dy = (local_cursor.y() - center_y) / 160.0
            self.target_look_x = max(-1.0, min(1.0, dx)) * 11.0
            self.target_look_y = max(-1.0, min(1.0, dy)) * 8.0
        else:
            if now - self.last_random_look > 3.2:
                self.last_random_look = now
                if random.random() < 0.65:
                    self.target_look_x = random.uniform(-8.0, 8.0)
                    self.target_look_y = random.uniform(-4.5, 4.5)
                else:
                    self.target_look_x = 0.0
                    self.target_look_y = 0.0

        self.look_x += (self.target_look_x - self.look_x) * 0.14
        self.look_y += (self.target_look_y - self.look_y) * 0.14

        self.pet_score = max(0.0, self.pet_score - 0.35)

        # Systemwerte & Musik alle 2.5 Sekunden aktualisieren
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

        # Wenn Musik oder Radio läuft, wippt er leicht im Takt und lässt ab und zu Musiknoten aufsteigen!
        if (self.music_playing or self.radio_playing) and random.random() < 0.035:
            self.spawn_particle("note")

        # Prüfen, ob Radio-Prozess noch läuft
        if self.radio_proc and self.radio_proc.poll() is not None:
            self.radio_playing = False
            self.radio_proc = None

        # Wetter alle 20 Minuten im Hintergrund aktualisieren
        if now - self.last_weather_check > 1200:
            self.fetch_weather_async(speak_when_done=False)

        # RSS News alle 25 Minuten im Hintergrund aktualisieren
        if now - self.last_news_fetch > 1500:
            self.fetch_news_async(speak_when_done=False)

        # Automatisches Vorlesen der neuesten News (falls aktiviert)
        if self.news_auto_speak and (now - self.last_news_broadcast) > (self.news_interval_mins * 60):
            self.last_news_broadcast = now
            self.broadcast_latest_news()

        # Gesundheit & Pausen: Wasser-Erinnerung
        if self.water_reminder_enabled and (now - self.last_water_reminder) > (self.water_reminder_mins * 60):
            self.last_water_reminder = now
            self.trigger_water_reminder()

        # Gesundheit & Pausen: Bewegungs-Erinnerung
        if self.move_reminder_enabled and (now - self.last_move_reminder) > (self.move_reminder_mins * 60):
            self.last_move_reminder = now
            self.trigger_move_reminder()

        # Spontanes Plaudern / Chatter-Modus (Witze, Fragen, Entspannung)
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

        # Wecker-Prüfung (Alarm Clock)
        if self.alarm_active and self.alarm_time and now >= self.alarm_time:
            self.trigger_alarm_ring()

        # Pomodoro-Countdown
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

        # Automatische Stimmungs-Entscheidung
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

        # Partikel aktualisieren
        alive_particles = []
        for p in self.particles:
            p["x"] += p["vx"]
            p["y"] += p["vy"]
            p["life"] -= 0.022
            if p["life"] > 0:
                alive_particles.append(p)
        self.particles = alive_particles

        self.update()

    # --- Maus-Interaktionen (Wayland-kompatibel) ---
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position()
            bx = pos.x() / self.scale_factor - (self.body_offset_x + self.walk_offset_x)
            by = pos.y() / self.scale_factor - (self.body_offset_y + self.walk_offset_y)

            # Prüfen, ob auf den kleinen orangenen Action-Button am Bauch geklickt wurde:
            # Einzelklick (nach kurzem Timer) = Display-Modus wechseln
            # Doppelklick = Untere Buttons & Chat-Eingabe ein-/ausblenden!
            btn_rect = QRectF(92, 206, 56, 24)
            if btn_rect.contains(QPointF(bx, by)):
                self.belly_click_timer.start(230)
                return

            # Im Pomodoro-, Musik-, Wetter- oder Linux-Tipp-Modus: Klick aufs Display löst Aktion aus
            screen_rect = QRectF(52, 72, 136, 122)
            if screen_rect.contains(QPointF(bx, by)):
                if self.mode == "pomodoro":
                    self.toggle_pomodoro()
                    return
                elif self.mode == "music":
                    # Links = Zurück, Mitte = Play/Pause, Rechts = Weiter
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
                    # Links = Vorherige Nachricht, Mitte = Vorlesen, Rechts = Nächste Nachricht
                    if bx < 92:
                        self.prev_news_item()
                    elif bx > 148:
                        self.next_news_item()
                    else:
                        self.speak_current_news()
                    self.trigger_bounce(5.0)
                    return
                elif self.mode == "radio":
                    # Links = Vorheriger Sender, Mitte = Play/Pause, Rechts = Nächster Sender
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

            # Freude / Überraschung beim Antippen + Fenster frei verschieben
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
        if self.is_dragging_pet and (event.buttons() & Qt.MouseButton.LeftButton):
            new_pos = event.globalPosition() - self.drag_offset
            self.move(int(new_pos.x()), int(new_pos.y()))
            return

        pos = event.position()
        now = time.time()
        bx = pos.x() / self.scale_factor - (self.body_offset_x + self.walk_offset_x)
        by = pos.y() / self.scale_factor - (self.body_offset_y + self.walk_offset_y)

        # Kopf-Region zum "Streicheln"
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

            # Schnell über das Gesicht wedeln -> Schwindelig
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

    # --- Zeichnen des 3D-Stil Körpers, der Sprechblase & des ESP32-Screens ---
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        painter.scale(self.scale_factor, self.scale_factor)

        # 0. Sprechblase oben über dem Kopf zeichnen (falls aktiv)
        if time.time() < self.bubble_until and self.bubble_text:
            self.draw_speech_bubble(painter)

        # Körper-Koordinatensystem
        painter.save()
        step_hop = abs(math.sin(self.walk_phase)) * -4.5 if self.is_stepping else 0.0
        breath_y = math.sin(self.breath_phase) * 2.2 + self.bounce_offset + step_hop

        if getattr(self, "is_dancing", False):
            if self.dance_style == "headbang":
                # Energisches Headbangen: Asymmetrisches Runternicken und federndes Hochschnellen
                hb_t = self.dance_phase
                hb_y = (math.sin(hb_t) * 0.5 + 0.5) ** 1.6 * 14.0
                hb_tilt = math.sin(hb_t) * 12.5
                painter.translate(
                    self.body_offset_x + self.walk_offset_x,
                    self.body_offset_y + self.walk_offset_y + breath_y + hb_y,
                )
                painter.translate(120, 195)
                painter.rotate(hb_tilt)
                painter.translate(-120, -195)
            else:
                # Geschmeidiges Grooven / Tanzen: Seitliches Wiegen und rhythmischer Hüpfer
                sway_x = math.sin(self.dance_phase) * 5.5
                sway_tilt = math.sin(self.dance_phase) * 5.0
                dance_hop = abs(math.sin(self.dance_phase * 2.0)) * -4.5
                painter.translate(
                    self.body_offset_x + self.walk_offset_x + sway_x,
                    self.body_offset_y + self.walk_offset_y + breath_y + dance_hop,
                )
                painter.translate(120, 185)
                painter.rotate(sway_tilt)
                painter.translate(-120, -185)
        else:
            painter.translate(
                self.body_offset_x + self.walk_offset_x,
                self.body_offset_y + self.walk_offset_y + breath_y,
            )
            if self.is_stepping:
                waddle_tilt = math.sin(self.walk_phase) * 3.5
                painter.translate(120, 145)
                painter.rotate(waddle_tilt)
                painter.translate(-120, -145)

        # 1. Schatten unter dem Deskimon
        shadow_grad = QRadialGradient(120, 252 - breath_y * 0.6, 70, 120, 252)
        shadow_grad.setColorAt(0.0, QColor(0, 0, 0, 110))
        shadow_grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(shadow_grad))
        painter.drawEllipse(QRectF(55, 240 - breath_y * 0.5, 130, 20))

        # 2. Charakter-spezifische Ohren/Antennen/Pflanze
        self.draw_skin_back_accessories(painter)

        # 3. 3D-gedrucktes Hauptgehäuse
        self.draw_3d_printed_body(painter)

        # 4. Eingelassenes ESP32-S3 IPS-Touch-Display
        self.draw_esp32_screen(painter)

        # 5. Vordergrund-Details
        self.draw_skin_front_accessories(painter)

        # 6. Schwebende Partikel
        self.draw_particles(painter)

        # 7. Leuchtender Richtungs-Pfeil / Suchscheinwerfer zum Mauszeiger (im 30s-Suchmodus)
        if self.cursor_search_state in ("seeking", "found"):
            self.draw_cursor_finder_beacon(painter)

        painter.restore()

    def draw_cursor_finder_beacon(self, painter: QPainter):
        """Zeichnet einen animierten Leuchtpfeil / Radar-Indikator in Richtung des gesuchten Mauszeigers."""
        global_cursor = QCursor.pos()
        local_cursor = self.mapFromGlobal(global_cursor)
        cx_body = 120.0
        cy_body = 145.0
        target_x = local_cursor.x() / self.scale_factor - (self.body_offset_x + self.walk_offset_x)
        target_y = local_cursor.y() / self.scale_factor - (self.body_offset_y + self.walk_offset_y)

        dx = target_x - cx_body
        dy = target_y - cy_body
        angle = math.atan2(dy, dx)
        pulse = 4.0 * math.sin(self.tick_count * 0.25)

        painter.save()
        painter.translate(cx_body + math.cos(angle) * (92.0 + pulse), cy_body + math.sin(angle) * (92.0 + pulse))
        painter.rotate(math.degrees(angle))

        # Leuchtender Pfeil Richtung Mauszeiger
        arrow = QPainterPath()
        arrow.moveTo(14, 0)
        arrow.lineTo(-8, -9)
        arrow.lineTo(-4, 0)
        arrow.lineTo(-8, 9)
        arrow.closeSubpath()

        painter.setPen(QPen(QColor("#ffffff"), 1.5))
        painter.setBrush(QColor("#ffeb3b") if self.cursor_search_state == "found" else QColor("#00e5ff"))
        painter.drawPath(arrow)
        painter.restore()

    def draw_speech_bubble(self, painter: QPainter):
        bx_shift = self.body_offset_x - 15 + self.walk_offset_x
        by_shift = self.body_offset_y - 68 + self.walk_offset_y
        bubble_rect = QRectF(10 + bx_shift, 6 + by_shift, 250, 68)
        painter.setPen(QPen(QColor("#89b4fa"), 1.8))
        painter.setBrush(QColor(24, 25, 38, 238))
        painter.drawRoundedRect(bubble_rect, 14, 14)

        # Kleines Dreieck unten an der Sprechblase Richtung Kopf
        tail = QPainterPath()
        tail.moveTo(126 + bx_shift, 74 + by_shift)
        tail.lineTo(135 + bx_shift, 84 + by_shift)
        tail.lineTo(144 + bx_shift, 74 + by_shift)
        tail.closeSubpath()
        painter.drawPath(tail)

        painter.setPen(QColor("#cdd6f4"))
        painter.setFont(QFont("SansSerif", 9, QFont.Weight.Medium))
        text_rect = QRectF(18 + bx_shift, 10 + by_shift, 234, 60)
        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
            self.bubble_text,
        )

    def get_skin_palette(self):
        palettes = {
            "orbit": {
                "body_top": QColor("#f5f7fa"),
                "body_bot": QColor("#cfd8dc"),
                "accent": QColor("#ff6f00"),
                "bezel": QColor("#263238"),
                "eye": QColor("#00e5ff"),
            },
            "sprout": {
                "body_top": QColor("#e8f5e9"),
                "body_bot": QColor("#a5d6a7"),
                "accent": QColor("#43a047"),
                "bezel": QColor("#1b5e20"),
                "eye": QColor("#76ff03"),
            },
            "neo": {
                "body_top": QColor("#2b2d42"),
                "body_bot": QColor("#181926"),
                "accent": QColor("#f72585"),
                "bezel": QColor("#0f0f1a"),
                "eye": QColor("#b5179e"),
            },
            "poko": {
                "body_top": QColor("#ffffff"),
                "body_bot": QColor("#e0e0e0"),
                "accent": QColor("#212121"),
                "bezel": QColor("#1a1a1a"),
                "eye": QColor("#40c4ff"),
            },
            "hopper": {
                "body_top": QColor("#fce4ec"),
                "body_bot": QColor("#f48fb1"),
                "accent": QColor("#ec407a"),
                "bezel": QColor("#4a154b"),
                "eye": QColor("#ff80ab"),
            },
            "soldier": {
                "body_top": QColor("#5a6b32"),
                "body_bot": QColor("#3c4a22"),
                "accent": QColor("#7d5528"),
                "bezel": QColor("#1f2717"),
                "eye": QColor("#76ff03"),
            },
            "cat": {
                "body_top": QColor("#fff3e0"),
                "body_bot": QColor("#fedbb6"),
                "accent": QColor("#ff80ab"),
                "bezel": QColor("#2a1d22"),
                "eye": QColor("#00e5ff"),
            },
        }
        return palettes.get(self.skin, palettes["orbit"])

    def draw_skin_back_accessories(self, painter: QPainter):
        pal = self.get_skin_palette()
        painter.setPen(QPen(QColor(0, 0, 0, 50), 2))

        if self.skin == "orbit":
            painter.setPen(QPen(QColor("#90a4ae"), 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(120, 48, 120, 20)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(pal["accent"])
            painter.drawEllipse(QPointF(120, 17), 8, 8)
            painter.setBrush(QColor(255, 255, 255, 180))
            painter.drawEllipse(QPointF(117, 14), 3, 3)

        elif self.skin == "sprout":
            painter.setPen(QPen(QColor("#2e7d32"), 4.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(120, 48, 120, 22)

            leaf_left = QPainterPath()
            leaf_left.moveTo(120, 24)
            leaf_left.cubicTo(95, 10, 88, 32, 120, 28)
            painter.setPen(QPen(QColor("#1b5e20"), 1.5))
            painter.setBrush(QColor("#66bb6a"))
            painter.drawPath(leaf_left)

            leaf_right = QPainterPath()
            leaf_right.moveTo(120, 24)
            leaf_right.cubicTo(145, 8, 152, 30, 120, 28)
            painter.setBrush(QColor("#4caf50"))
            painter.drawPath(leaf_right)

        elif self.skin == "poko":
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#1f1f1f"))
            painter.drawEllipse(QPointF(62, 55), 22, 22)
            painter.drawEllipse(QPointF(178, 55), 22, 22)
            painter.setBrush(QColor("#424242"))
            painter.drawEllipse(QPointF(62, 55), 11, 11)
            painter.drawEllipse(QPointF(178, 55), 11, 11)

        elif self.skin == "hopper":
            ear_wobble = math.sin(self.breath_phase * 1.5) * 3.0
            painter.setPen(QPen(QColor(0, 0, 0, 35), 1.5))
            painter.setBrush(pal["body_top"])

            painter.save()
            painter.translate(82, 50)
            painter.rotate(-12 + ear_wobble)
            painter.drawRoundedRect(QRectF(-14, -42, 28, 52), 14, 14)
            painter.setBrush(pal["accent"])
            painter.drawRoundedRect(QRectF(-8, -34, 16, 36), 8, 8)
            painter.restore()

            painter.save()
            painter.translate(158, 50)
            painter.rotate(12 - ear_wobble)
            painter.setBrush(pal["body_top"])
            painter.drawRoundedRect(QRectF(-14, -42, 28, 52), 14, 14)
            painter.setBrush(pal["accent"])
            painter.drawRoundedRect(QRectF(-8, -34, 16, 36), 8, 8)
            painter.restore()

        elif self.skin == "soldier":
            # Taktische Funkantenne auf der linken Helm-Rückseite
            painter.setPen(QPen(QColor("#2d3815"), 4.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(44, 45, 36, 6)
            painter.setPen(QPen(QColor("#1f2717"), 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(36, 6, 32, -14)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#76ff03"))
            painter.drawEllipse(QPointF(32, -15), 3.5, 3.5)

        elif self.skin == "cat":
            ear_twitch = math.sin(self.breath_phase * 1.8) * 3.0

            # Linkes Katzenohr
            painter.save()
            painter.translate(72, 48)
            painter.rotate(-15 + ear_twitch)
            ear_left = QPainterPath()
            ear_left.moveTo(-16, 8)
            ear_left.lineTo(0, -32)
            ear_left.lineTo(16, 8)
            ear_left.closeSubpath()
            painter.setPen(QPen(QColor(0, 0, 0, 45), 1.5))
            painter.setBrush(pal["body_top"])
            painter.drawPath(ear_left)

            # Innenohr (Rosa Fluff)
            inner_left = QPainterPath()
            inner_left.moveTo(-10, 6)
            inner_left.lineTo(0, -22)
            inner_left.lineTo(10, 6)
            inner_left.closeSubpath()
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(pal["accent"])
            painter.drawPath(inner_left)
            painter.restore()

            # Rechtes Katzenohr
            painter.save()
            painter.translate(168, 48)
            painter.rotate(15 - ear_twitch)
            ear_right = QPainterPath()
            ear_right.moveTo(-16, 8)
            ear_right.lineTo(0, -32)
            ear_right.lineTo(16, 8)
            ear_right.closeSubpath()
            painter.setPen(QPen(QColor(0, 0, 0, 45), 1.5))
            painter.setBrush(pal["body_top"])
            painter.drawPath(ear_right)

            # Innenohr (Rosa Fluff)
            inner_right = QPainterPath()
            inner_right.moveTo(-10, 6)
            inner_right.lineTo(0, -22)
            inner_right.lineTo(10, 6)
            inner_right.closeSubpath()
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(pal["accent"])
            painter.drawPath(inner_right)
            painter.restore()

            # Süßes Katzen-Schwänzchen rechts am Körper (wackelt sanft mit dem Atem)
            tail_sway = math.sin(self.breath_phase * 1.2) * 6.0
            painter.save()
            painter.translate(202, 195)
            painter.rotate(tail_sway)
            painter.setPen(QPen(pal["body_bot"], 10, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            tail_path = QPainterPath()
            tail_path.moveTo(0, 0)
            tail_path.cubicTo(18, -5, 26, -25, 22, -38)
            painter.drawPath(tail_path)
            # Weiße Schwanzspitze
            painter.setPen(QPen(QColor("#ffffff"), 9, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            tail_tip = QPainterPath()
            tail_tip.moveTo(25, -30)
            tail_tip.lineTo(22, -38)
            painter.drawPath(tail_tip)
            painter.restore()

    def draw_3d_printed_body(self, painter: QPainter):
        pal = self.get_skin_palette()

        foot_color = (
            pal["accent"] if self.skin in ("poko", "neo", "cat")
            else QColor("#1e2617") if self.skin == "soldier"
            else pal["body_bot"]
        )
        painter.setPen(QPen(QColor(0, 0, 0, 45), 1.5))
        painter.setBrush(foot_color)
        left_foot_y = 228 + (math.sin(self.walk_phase) * 6.0 if self.is_stepping else 0.0)
        right_foot_y = 228 + (-math.sin(self.walk_phase) * 6.0 if self.is_stepping else 0.0)
        painter.drawRoundedRect(QRectF(65, left_foot_y, 38, 22), 10, 10)
        painter.drawRoundedRect(QRectF(137, right_foot_y, 38, 22), 10, 10)

        arm_angle = math.sin(self.breath_phase) * 6.0
        if self.is_speaking:
            arm_angle = math.sin(self.tick_count * 0.28) * 12.0
        elif self.is_stepping:
            arm_angle = math.sin(self.walk_phase) * 16.0
        arm_color = pal["accent"] if self.skin == "poko" else pal["body_bot"]
        painter.setBrush(arm_color)

        painter.save()
        painter.translate(38, 145)
        painter.rotate(15 + arm_angle)
        painter.drawRoundedRect(QRectF(-12, -8, 24, 46), 11, 11)
        painter.restore()

        painter.save()
        painter.translate(202, 145)
        painter.rotate(-15 - arm_angle)
        painter.drawRoundedRect(QRectF(-12, -8, 24, 46), 11, 11)
        painter.restore()

        body_grad = QLinearGradient(120, 42, 120, 238)
        body_grad.setColorAt(0.0, pal["body_top"])
        body_grad.setColorAt(1.0, pal["body_bot"])

        painter.setPen(QPen(QColor(0, 0, 0, 65), 2.0))
        painter.setBrush(QBrush(body_grad))
        painter.drawRoundedRect(QRectF(36, 44, 168, 194), 42, 42)

        # Flecktarn-Muster auf dem Soldaten-Körper
        if self.skin == "soldier":
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#2d3815"))
            for bx, by, rx, ry in [(52, 85, 12, 7), (175, 95, 14, 8), (62, 180, 15, 9), (180, 175, 12, 8), (145, 215, 14, 7), (85, 220, 10, 6)]:
                painter.drawEllipse(QPointF(bx, by), rx, ry)
            painter.setBrush(QColor("#7d5528"))
            for bx, by, rx, ry in [(45, 125, 9, 6), (185, 135, 11, 7), (68, 205, 10, 6), (160, 195, 11, 7)]:
                painter.drawEllipse(QPointF(bx, by), rx, ry)
            painter.setBrush(QColor("#1a200f"))
            for bx, by, rx, ry in [(58, 105, 7, 5), (178, 115, 8, 5), (55, 195, 7, 5), (172, 185, 8, 5)]:
                painter.drawEllipse(QPointF(bx, by), rx, ry)

        highlight_pen = QPen(QColor(255, 255, 255, 110), 2.5)
        painter.setPen(highlight_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawArc(QRectF(42, 48, 156, 70), 30 * 16, 120 * 16)

    def draw_skin_front_accessories(self, painter: QPainter):
        pal = self.get_skin_palette()

        if self.skin == "neo":
            painter.setPen(QPen(QColor("#f72585"), 2.0))
            painter.setBrush(QColor("#11111b"))
            painter.drawRoundedRect(QRectF(22, 95, 18, 68), 8, 8)
            painter.drawRoundedRect(QRectF(200, 95, 18, 68), 8, 8)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#00f5d4"))
            painter.drawRoundedRect(QRectF(26, 110, 5, 38), 2, 2)
            painter.drawRoundedRect(QRectF(209, 110, 5, 38), 2, 2)

        elif self.skin == "cat":
            # 3 süße Schnurrhaare links
            painter.setPen(QPen(QColor("#8d6e63"), 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(44, 125, 22, 118)
            painter.drawLine(44, 133, 18, 133)
            painter.drawLine(44, 141, 24, 148)
            # 3 süße Schnurrhaare rechts
            painter.drawLine(196, 125, 218, 118)
            painter.drawLine(196, 133, 222, 133)
            painter.drawLine(196, 141, 216, 148)

            # Pfötchen-Details (Rosa Ballen auf den Füßen)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(pal["accent"])
            # Linker Fuß
            painter.drawEllipse(QPointF(84, 239), 5.5, 4.0)
            painter.drawEllipse(QPointF(74, 233), 2.2, 2.2)
            painter.drawEllipse(QPointF(84, 230), 2.2, 2.2)
            painter.drawEllipse(QPointF(94, 233), 2.2, 2.2)
            # Rechter Fuß
            painter.drawEllipse(QPointF(156, 239), 5.5, 4.0)
            painter.drawEllipse(QPointF(146, 233), 2.2, 2.2)
            painter.drawEllipse(QPointF(156, 230), 2.2, 2.2)
            painter.drawEllipse(QPointF(166, 233), 2.2, 2.2)

        elif self.skin == "soldier":
            # 1. Schatten des Helms auf Stirn und Display-Rand
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(0, 0, 0, 95))
            painter.drawRoundedRect(QRectF(38, 62, 164, 14), 7, 7)

            # 2. Taktische Kinnriemen (Chin Straps) links und rechts
            painter.setPen(QPen(QColor("#222818"), 3.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(42, 65, 48, 168)
            painter.drawLine(198, 65, 192, 168)
            # Riemen-Schnallen
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#111111"))
            painter.drawRoundedRect(QRectF(44, 120, 7, 10), 2, 2)
            painter.drawRoundedRect(QRectF(189, 120, 7, 10), 2, 2)

            # 3. 3D Gefechtshelm-Kuppel (Hoher, gewölbter Bundeswehr-Helm über dem Kopf)
            helmet_path = QPainterPath()
            helmet_path.moveTo(28, 68)
            # Linke Ohren-Auswölbung
            helmet_path.cubicTo(22, 46, 26, 20, 62, 10)
            # Hoher, runder Helmkamm / Wölbung bis fast an den oberen Fensterrand
            helmet_path.cubicTo(90, 0, 150, 0, 178, 10)
            # Rechte Ohren-Auswölbung
            helmet_path.cubicTo(214, 20, 218, 46, 212, 68)
            # Vorderkante / Visier-Wulst über der Stirn
            helmet_path.cubicTo(168, 58, 72, 58, 28, 68)
            helmet_path.closeSubpath()

            # Plastischer 3D-Farbverlauf für echte Kugelform & Helm-Wölbung
            helm_grad = QLinearGradient(60, 4, 180, 72)
            helm_grad.setColorAt(0.0, QColor("#667c3b"))  # Heller Olivton an der Lichtkante
            helm_grad.setColorAt(0.4, QColor("#49592a"))  # Haupt-Olivgrün (RAL 6031 Bronzegrün)
            helm_grad.setColorAt(1.0, QColor("#2a3518"))  # Schattierter Rand unten

            painter.save()
            painter.setPen(QPen(QColor(0, 0, 0, 95), 2.2))
            painter.setBrush(QBrush(helm_grad))
            painter.drawPath(helmet_path)

            # 4. Authentisches deutsches Flecktarn-Muster (in den Helm geclippt)
            painter.setClipPath(helmet_path)
            painter.setPen(Qt.PenStyle.NoPen)

            # Dunkeloliv-Flecken
            painter.setBrush(QColor("#263214"))
            for fx, fy, rx, ry in [(55, 32, 16, 9), (145, 25, 18, 10), (105, 42, 14, 8), (185, 48, 13, 8), (38, 52, 12, 7)]:
                painter.drawEllipse(QPointF(fx, fy), rx, ry)

            # Lederbraun-Flecken (RAL 8027)
            painter.setBrush(QColor("#7d5528"))
            for fx, fy, rx, ry in [(82, 22, 13, 8), (170, 32, 15, 9), (125, 48, 12, 7), (60, 56, 11, 6), (150, 58, 13, 7)]:
                painter.drawEllipse(QPointF(fx, fy), rx, ry)

            # Teerschwarz-Flecken (RAL 9021)
            painter.setBrush(QColor("#161a10"))
            for fx, fy, rx, ry in [(112, 20, 10, 6), (72, 44, 9, 6), (160, 42, 11, 6), (95, 58, 10, 5), (188, 38, 8, 5)]:
                painter.drawEllipse(QPointF(fx, fy), rx, ry)

            # Hellgrün-Flecken
            painter.setBrush(QColor("#6f8741"))
            for fx, fy, rx, ry in [(98, 32, 9, 5), (135, 16, 11, 6), (48, 42, 8, 5), (172, 54, 8, 5)]:
                painter.drawEllipse(QPointF(fx, fy), rx, ry)

            painter.restore()

            # 5. Taktisches Helmband (Gummi-Band über der Stirn)
            band_path = QPainterPath()
            band_path.moveTo(27, 54)
            band_path.cubicTo(70, 45, 170, 45, 213, 54)
            painter.setPen(QPen(QColor("#161814"), 4.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(band_path)

            # Katzenaugen / Leucht-Reflektoren auf dem Helmband
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#76ff03"))
            painter.drawRoundedRect(QRectF(85, 46, 7, 4), 1, 1)
            painter.drawRoundedRect(QRectF(148, 46, 7, 4), 1, 1)

            # 6. Taktische NVG-Halterung (Nachtsicht-Shroud vorne mittig)
            painter.setPen(QPen(QColor("#0d100b"), 1.5))
            painter.setBrush(QColor("#1f241a"))
            painter.drawRoundedRect(QRectF(111, 38, 18, 15), 3, 3)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#4b5636"))
            painter.drawRoundedRect(QRectF(115, 42, 10, 7), 1.5, 1.5)

            # 7. Plastischer Kantenschutz / Kederband an der Helmunterkante
            painter.setPen(QPen(QColor(0, 0, 0, 130), 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            rim_path = QPainterPath()
            rim_path.moveTo(28, 68)
            rim_path.cubicTo(72, 58, 168, 58, 212, 68)
            painter.drawPath(rim_path)

        # Kleiner orangener Bauch-Button (Einzelklick = Modus, Doppelklick = Buttons & Chat ein-/ausblenden)
        btn_border = QColor("#ffffff") if getattr(self, "controls_visible", False) else QColor(0, 0, 0, 80)
        painter.setPen(QPen(btn_border, 1.5))
        painter.setBrush(pal["accent"])
        painter.drawRoundedRect(QRectF(96, 212, 48, 14), 7, 7)

        # Drei feine Punkte auf dem Bauch-Button als Hinweis für das Bedienfeld
        dot_alpha = 230 if getattr(self, "controls_visible", False) else 130
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, dot_alpha))
        for dx_dot in (110, 120, 130):
            painter.drawEllipse(QPointF(dx_dot, 219), 1.8, 1.8)

        led_color = QColor("#00e676") if self.cpu_percent < 75 else QColor("#ff1744")
        if self.mic_status == "recording":
            led_color = QColor("#ff1744")
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(led_color)
        painter.drawEllipse(QPointF(68, 219), 4, 4)

    def draw_esp32_screen(self, painter: QPainter):
        pal = self.get_skin_palette()

        painter.setPen(QPen(QColor(255, 255, 255, 35), 1.5))
        painter.setBrush(pal["bezel"])
        painter.drawRoundedRect(QRectF(48, 66, 144, 134), 26, 26)

        screen_rect = QRectF(54, 72, 132, 122)
        screen_grad = QLinearGradient(54, 72, 54, 194)
        screen_grad.setColorAt(0.0, QColor("#0b0e14"))
        screen_grad.setColorAt(1.0, QColor("#131722"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(screen_grad))
        painter.drawRoundedRect(screen_rect, 20, 20)

        painter.save()
        clip_path = QPainterPath()
        clip_path.addRoundedRect(screen_rect, 20, 20)
        painter.setClipPath(clip_path)

        if self.mode == "pet":
            self.draw_pet_face(painter, pal["eye"])
        elif self.mode == "clock":
            self.draw_clock_mode(painter, pal["eye"])
        elif self.mode == "weather":
            self.draw_weather_mode(painter, pal["eye"])
        elif self.mode == "news":
            self.draw_news_mode(painter, pal["eye"])
        elif self.mode == "radio":
            self.draw_radio_mode(painter, pal["eye"])
        elif self.mode == "music":
            self.draw_music_mode(painter, pal["eye"])
        elif self.mode == "linux":
            self.draw_linux_mode(painter, pal["eye"])
        elif self.mode == "pomodoro":
            self.draw_pomodoro_mode(painter, pal["eye"])
        elif self.mode == "sysmon":
            self.draw_sysmon_mode(painter, pal["eye"])

        # Dezenter Glas-Glanz oben am Displayrand (ohne Riss-Kante)
        glass_grad = QLinearGradient(54, 72, 54, 105)
        glass_grad.setColorAt(0.0, QColor(255, 255, 255, 22))
        glass_grad.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(glass_grad))
        painter.drawRoundedRect(QRectF(56, 73, 128, 32), 18, 18)

        painter.restore()

    def draw_pet_face(self, painter: QPainter, eye_color: QColor):
        cx = 120.0 + self.look_x
        cy = 126.0 + self.look_y

        left_eye_x = cx - 30.0
        right_eye_x = cx + 30.0

        emo = self.current_emotion

        glow = QRadialGradient(cx, cy, 55)
        glow_col = QColor(eye_color)
        glow_col.setAlpha(35)
        glow.setColorAt(0.0, glow_col)
        glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setBrush(QBrush(glow))
        painter.drawEllipse(QPointF(cx, cy), 55, 40)

        if emo in ("happy", "love", "excited") or self.is_speaking:
            painter.setBrush(QColor(255, 105, 180, 95))
            painter.drawEllipse(QPointF(left_eye_x - 10, cy + 20), 10, 5.5)
            painter.drawEllipse(QPointF(right_eye_x + 10, cy + 20), 10, 5.5)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(eye_color)

        if emo == "happy":
            pen = QPen(eye_color, 6.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawArc(QRectF(left_eye_x - 16, cy - 12, 32, 28), 20 * 16, 140 * 16)
            painter.drawArc(QRectF(right_eye_x - 16, cy - 12, 32, 28), 20 * 16, 140 * 16)

        elif emo == "love":
            self.draw_heart(painter, left_eye_x, cy, 17, QColor("#ff4081"))
            self.draw_heart(painter, right_eye_x, cy, 17, QColor("#ff4081"))

        elif emo == "sleepy":
            pen = QPen(eye_color, 5.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawLine(QPointF(left_eye_x - 14, cy + 2), QPointF(left_eye_x + 14, cy + 2))
            painter.drawLine(QPointF(right_eye_x - 14, cy + 2), QPointF(right_eye_x + 14, cy + 2))

        elif emo == "dizzy":
            pen = QPen(QColor("#ffeb3b"), 4.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawLine(QPointF(left_eye_x - 11, cy - 11), QPointF(left_eye_x + 11, cy + 11))
            painter.drawLine(QPointF(left_eye_x + 11, cy - 11), QPointF(left_eye_x - 11, cy + 11))
            painter.drawLine(QPointF(right_eye_x - 11, cy - 11), QPointF(right_eye_x + 11, cy + 11))
            painter.drawLine(QPointF(right_eye_x + 11, cy - 11), QPointF(right_eye_x - 11, cy + 11))

        elif emo == "angry":
            painter.setBrush(QColor("#ff5252"))
            path_l = QPainterPath()
            path_l.addRoundedRect(QRectF(left_eye_x - 15, cy - 14, 30, 28), 9, 9)
            painter.drawPath(path_l)
            path_r = QPainterPath()
            path_r.addRoundedRect(QRectF(right_eye_x - 15, cy - 14, 30, 28), 9, 9)
            painter.drawPath(path_r)
            painter.setBrush(QColor("#0f131c"))
            poly_l = QPainterPath()
            poly_l.moveTo(left_eye_x - 18, cy - 18)
            poly_l.lineTo(left_eye_x + 18, cy - 4)
            poly_l.lineTo(left_eye_x + 18, cy - 20)
            poly_l.closeSubpath()
            painter.drawPath(poly_l)

            poly_r = QPainterPath()
            poly_r.moveTo(right_eye_x + 18, cy - 18)
            poly_r.lineTo(right_eye_x - 18, cy - 4)
            poly_r.lineTo(right_eye_x - 18, cy - 20)
            poly_r.closeSubpath()
            painter.drawPath(poly_r)

        else:
            blink_factor = max(0.08, 1.0 - math.sin(min(1.0, self.blink_state) * math.pi))
            eye_h = 34.0 * blink_factor
            eye_w = 28.0

            for ex in (left_eye_x, right_eye_x):
                painter.setBrush(eye_color)
                painter.drawRoundedRect(
                    QRectF(ex - eye_w / 2, cy - eye_h / 2, eye_w, eye_h), 11, 11
                )
                if blink_factor > 0.4:
                    painter.setBrush(QColor(255, 255, 255, 220))
                    painter.drawEllipse(QPointF(ex - 5, cy - eye_h * 0.22), 4.5, 4.5)
                    painter.drawEllipse(QPointF(ex + 5, cy + eye_h * 0.15), 2.2, 2.2)

            if emo == "chill":
                painter.setBrush(QColor("#0b0e14"))
                painter.drawRect(QRectF(left_eye_x - 16, cy - 18, 32, 11))
                painter.drawRect(QRectF(right_eye_x - 16, cy - 18, 32, 11))

        # Mund (mit natürlicher Lippen- & Sprech-Synchronisation!)
        if self.is_speaking:
            # Natürliche Sprech-Kadenz: Kombination aus Silbentakt & Vokalöffnung
            t = self.tick_count * 0.24
            syllable = 0.5 + 0.5 * math.sin(t)
            micro_mod = 0.25 * math.sin(t * 2.3)
            open_val = max(0.08, min(1.0, syllable + micro_mod))

            mouth_w = 12.0 + open_val * 11.0
            mouth_h = 3.5 + open_val * 10.0
            mouth_y = cy + 18.0

            # Lippenform (weiches abgerundetes Oval)
            painter.setPen(QPen(eye_color, 2.0))
            painter.setBrush(QColor("#d81b60"))
            mouth_rect = QRectF(cx - mouth_w / 2, mouth_y, mouth_w, mouth_h)
            painter.drawRoundedRect(mouth_rect, mouth_w * 0.45, mouth_h * 0.5)

            # Niedliches Zungen-Detail im Mundinneren bei geöffnetem Mund
            if mouth_h > 7.0:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor("#ff80ab"))
                painter.drawChord(
                    QRectF(cx - mouth_w * 0.35, mouth_y + mouth_h * 0.35, mouth_w * 0.7, mouth_h * 0.7),
                    0, 180 * 16
                )
        else:
            mouth_pen = QPen(eye_color, 3.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            painter.setPen(mouth_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)

            if emo in ("happy", "love", "excited"):
                painter.drawArc(QRectF(cx - 12, cy + 16, 24, 14), 190 * 16, 160 * 16)
            elif emo == "dizzy":
                painter.drawEllipse(QPointF(cx, cy + 24), 5, 6)
            elif emo == "sleepy":
                painter.drawEllipse(QPointF(cx, cy + 23), 3.5, 3.5)
            elif emo == "angry":
                painter.drawArc(QRectF(cx - 10, cy + 22, 20, 10), 20 * 16, 140 * 16)
            else:
                painter.drawArc(QRectF(cx - 9, cy + 18, 18, 9), 200 * 16, 140 * 16)

        painter.setFont(QFont("SansSerif", 8, QFont.Weight.Bold))
        if getattr(self, "is_dancing", False):
            if self.dance_style == "headbang":
                now_str = "🤘 HEADBANG ⚡"
                painter.setPen(QColor("#ff5252"))
            else:
                now_str = "🕺 GROOVE ♪"
                painter.setPen(QColor("#00e5ff"))
        elif self.alarm_active and self.alarm_time:
            rem_s = max(0, int(self.alarm_time - time.time()))
            now_str = f"⏰ {rem_s // 60:02d}:{rem_s % 60:02d}"
            painter.setPen(QColor("#f9e2af"))
        elif self.pomo_running:
            pm = self.pomo_remaining // 60
            ps = self.pomo_remaining % 60
            icon = "🍅" if self.pomo_phase == "work" else "☕"
            now_str = f"{icon} {pm:02d}:{ps:02d}"
            painter.setPen(QColor("#f38ba8") if self.pomo_phase == "work" else QColor("#a6e3a1"))
        else:
            now_str = datetime.now().strftime("%H:%M")
            painter.setPen(QColor(255, 255, 255, 90))
        painter.drawText(QRectF(54, 174, 132, 16), Qt.AlignmentFlag.AlignCenter, now_str)

    def draw_clock_mode(self, painter: QPainter, accent: QColor):
        now = datetime.now()
        time_str = now.strftime("%H:%M")
        sec_str = now.strftime(":%S")
        date_str = now.strftime("%a, %d. %b")

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(accent)
        painter.drawRoundedRect(QRectF(96, 82, 14, 10), 4, 4)
        painter.drawRoundedRect(QRectF(130, 82, 14, 10), 4, 4)

        painter.setPen(QColor("#ffffff"))
        painter.setFont(QFont("Monospace", 22, QFont.Weight.Bold))
        painter.drawText(QRectF(54, 102, 132, 38), Qt.AlignmentFlag.AlignCenter, time_str)

        painter.setPen(accent)
        painter.setFont(QFont("Monospace", 10, QFont.Weight.Bold))
        painter.drawText(QRectF(54, 138, 132, 20), Qt.AlignmentFlag.AlignCenter, sec_str)

        if self.alarm_active and self.alarm_time:
            rem_sec = max(0, int(self.alarm_time - time.time()))
            rem_m = rem_sec // 60
            rem_s = rem_sec % 60
            alarm_str = datetime.fromtimestamp(self.alarm_time).strftime("%H:%M")
            painter.setPen(QColor("#f9e2af"))
            painter.setFont(QFont("SansSerif", 8, QFont.Weight.Bold))
            painter.drawText(QRectF(54, 162, 132, 20), Qt.AlignmentFlag.AlignCenter, f"⏰ {alarm_str} ({rem_m:02d}:{rem_s:02d})")
        else:
            painter.setPen(QColor(255, 255, 255, 160))
            painter.setFont(QFont("SansSerif", 9))
            painter.drawText(QRectF(54, 162, 132, 20), Qt.AlignmentFlag.AlignCenter, date_str)

    def draw_weather_mode(self, painter: QPainter, accent: QColor):
        painter.setPen(accent)
        painter.setFont(QFont("SansSerif", 8, QFont.Weight.Bold))
        header = f"🌤️ WETTER {self.weather_city.upper()}" if self.weather_city else "🌤️ LIVE WETTER"
        painter.drawText(QRectF(54, 78, 132, 16), Qt.AlignmentFlag.AlignCenter, header)

        # Wettersymbol zeichnen (Sonne / Wolke)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#ffd54f"))
        painter.drawEllipse(QPointF(92, 118), 14, 14)
        painter.setBrush(QColor(225, 245, 254, 220))
        painter.drawRoundedRect(QRectF(88, 116, 36, 15), 7, 7)

        # Große Temperatur
        painter.setPen(QColor("#ffffff"))
        painter.setFont(QFont("Monospace", 17, QFont.Weight.Bold))
        painter.drawText(QRectF(112, 102, 72, 32), Qt.AlignmentFlag.AlignCenter, self.weather_temp)

        # Wetterbeschreibung unten
        painter.setPen(QColor(255, 255, 255, 210))
        painter.setFont(QFont("SansSerif", 8, QFont.Weight.Medium))
        painter.drawText(QRectF(58, 142, 124, 24), Qt.AlignmentFlag.AlignCenter, self.weather_desc)

        painter.setPen(QColor(255, 255, 255, 100))
        painter.setFont(QFont("SansSerif", 7))
        painter.drawText(QRectF(54, 172, 132, 14), Qt.AlignmentFlag.AlignCenter, "(Klick = Vorlesen)")

    def draw_news_mode(self, painter: QPainter, accent: QColor):
        painter.setPen(accent)
        painter.setFont(QFont("SansSerif", 8, QFont.Weight.Bold))
        painter.drawText(QRectF(54, 78, 132, 16), Qt.AlignmentFlag.AlignCenter, "📰 RSS NACHRICHTEN")

        if self.news_items:
            item = self.news_items[self.news_idx % len(self.news_items)]
            source = item.get("source", "News")
            title = item.get("title", "")
        else:
            source = "RSS Feed"
            title = "Lade Schlagzeilen..." if getattr(self, "news_fetching", False) else "Keine News (Klick für Abruf)"

        # Quelle als kleine Pill-Badge
        pill_rect = QRectF(70, 96, 100, 15)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, 28))
        painter.drawRoundedRect(pill_rect, 7, 7)
        painter.setPen(QColor("#89b4fa"))
        painter.setFont(QFont("SansSerif", 7, QFont.Weight.Bold))
        painter.drawText(pill_rect, Qt.AlignmentFlag.AlignCenter, source[:16])

        # Schlagzeile
        painter.setPen(QColor(255, 255, 255, 225))
        painter.setFont(QFont("SansSerif", 7, QFont.Weight.Medium))
        painter.drawText(
            QRectF(58, 114, 124, 52),
            Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
            title[:105] + ("..." if len(title) > 105 else ""),
        )

        # Navigation unten
        painter.setPen(QColor(255, 255, 255, 120))
        painter.setFont(QFont("SansSerif", 7))
        painter.drawText(QRectF(54, 170, 132, 16), Qt.AlignmentFlag.AlignCenter, "◄ Vorlesen (Klick) ►")

    def draw_radio_mode(self, painter: QPainter, accent: QColor):
        painter.setPen(accent)
        painter.setFont(QFont("SansSerif", 8, QFont.Weight.Bold))
        if getattr(self, "is_dancing", False) and self.dance_style == "headbang":
            status_hdr = "⚡ ROCK ON AIR ⚡"
        elif self.radio_playing:
            status_hdr = "📻 RADIO: ON AIR"
        else:
            status_hdr = "📻 INTERNET-RADIO"
        painter.drawText(QRectF(54, 78, 132, 16), Qt.AlignmentFlag.AlignCenter, status_hdr)

        # Equalizer Visualizer Bars
        bar_w = 6
        spacing = 4
        start_x = int(120 - (7 * (bar_w + spacing)) / 2)
        mult = 22 if (getattr(self, "is_dancing", False) and self.dance_style == "headbang") else 14
        for i in range(7):
            if self.radio_playing:
                bh = 4 + int(abs(math.sin(self.tick_count * 0.3 + i * 1.1)) * mult)
            else:
                bh = 3
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(accent if i % 2 == 0 else QColor("#00e5ff"))
            painter.drawRoundedRect(QRectF(start_x + i * (bar_w + spacing), 114 - bh, bar_w, bh), 2, 2)

        # Sendername
        st_name = "Kein Sender"
        if self.radio_stations:
            st = self.radio_stations[self.active_radio_idx % len(self.radio_stations)]
            st_name = st.get("name", "Radio")

        painter.setPen(QColor("#ffffff"))
        painter.setFont(QFont("SansSerif", 8, QFont.Weight.Bold))
        painter.drawText(QRectF(58, 122, 124, 26), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, st_name)

        # Status
        status_col = QColor("#a6e3a1") if self.radio_playing else QColor("#f38ba8")
        status_txt = "▶ LÄUFT" if self.radio_playing else "⏸ PAUSIERT"
        painter.setPen(status_col)
        painter.setFont(QFont("SansSerif", 7, QFont.Weight.Bold))
        painter.drawText(QRectF(58, 148, 124, 14), Qt.AlignmentFlag.AlignCenter, status_txt)

        # Player-Symbole unten
        painter.setPen(accent)
        painter.setFont(QFont("SansSerif", 10, QFont.Weight.Bold))
        play_sym = "⏸" if self.radio_playing else "▶"
        painter.drawText(QRectF(58, 166, 124, 22), Qt.AlignmentFlag.AlignCenter, f"⏮     {play_sym}     ⏭")

    def draw_music_mode(self, painter: QPainter, accent: QColor):
        painter.setPen(accent)
        painter.setFont(QFont("SansSerif", 8, QFont.Weight.Bold))
        if getattr(self, "is_dancing", False) and self.dance_style == "headbang":
            status_hdr = "🎸 ROCKSTAR MODE"
        elif self.music_playing:
            status_hdr = "🎵 NOW PLAYING"
        else:
            status_hdr = "🎵 MEDIA PLAYER"
        painter.drawText(QRectF(54, 78, 132, 16), Qt.AlignmentFlag.AlignCenter, status_hdr)

        # Animierte Equalizer-Balken
        bar_x = 80
        mult = 28 if (getattr(self, "is_dancing", False) and self.dance_style == "headbang") else 22
        for i in range(8):
            if self.music_playing:
                bh = 6 + abs(math.sin(self.tick_count * 0.3 + i * 0.9)) * mult
            else:
                bh = 4
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(accent if i % 2 == 0 else QColor("#f72585"))
            painter.drawRoundedRect(QRectF(bar_x + i * 10, 124 - bh, 6, bh), 2, 2)

        # Song-Titel & Interpret
        painter.setPen(QColor("#ffffff"))
        painter.setFont(QFont("SansSerif", 8, QFont.Weight.Bold))
        painter.drawText(QRectF(58, 130, 124, 18), Qt.AlignmentFlag.AlignCenter, self.music_title)

        painter.setPen(QColor(255, 255, 255, 160))
        painter.setFont(QFont("SansSerif", 7))
        painter.drawText(QRectF(58, 146, 124, 16), Qt.AlignmentFlag.AlignCenter, self.music_artist)

        # Klickbare Player-Symbole unten (⏮  ⏯  ⏭)
        painter.setPen(accent)
        painter.setFont(QFont("SansSerif", 10, QFont.Weight.Bold))
        play_sym = "⏸" if self.music_playing else "▶"
        painter.drawText(QRectF(58, 166, 124, 22), Qt.AlignmentFlag.AlignCenter, f"⏮     {play_sym}     ⏭")

    def draw_linux_mode(self, painter: QPainter, accent: QColor):
        title, body = self.LINUX_TIPS[self.linux_tip_idx]
        painter.setPen(QColor("#a6e3a1"))
        painter.setFont(QFont("SansSerif", 8, QFont.Weight.Bold))
        painter.drawText(QRectF(54, 78, 132, 16), Qt.AlignmentFlag.AlignCenter, "🐧 NOBARA HELFER")

        painter.setPen(accent)
        painter.setFont(QFont("SansSerif", 8, QFont.Weight.Bold))
        painter.drawText(QRectF(58, 96, 124, 18), Qt.AlignmentFlag.AlignCenter, title)

        painter.setPen(QColor(255, 255, 255, 215))
        painter.setFont(QFont("SansSerif", 7))
        painter.drawText(
            QRectF(58, 114, 124, 56),
            Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
            body[:90] + ("..." if len(body) > 90 else ""),
        )

        painter.setPen(QColor(255, 255, 255, 110))
        painter.setFont(QFont("SansSerif", 7))
        painter.drawText(QRectF(54, 172, 132, 14), Qt.AlignmentFlag.AlignCenter, "(Klick = Nächster Tipp)")

    def draw_pomodoro_mode(self, painter: QPainter, accent: QColor):
        mins = self.pomo_remaining // 60
        secs = self.pomo_remaining % 60
        timer_text = f"{mins:02d}:{secs:02d}"

        if self.pomo_phase == "short_break":
            status = "☕ PAUSE LÄUFT" if self.pomo_running else "☕ PAUSE (Klick)"
            phase_col = QColor("#a6e3a1")
        elif self.pomo_phase == "long_break":
            status = "🛋️ PAUSE LÄUFT" if self.pomo_running else "🛋️ PAUSE (Klick)"
            phase_col = QColor("#89b4fa")
        else:
            status = "🍅 FOKUS LÄUFT" if self.pomo_running else "🍅 FOKUS (Klick)"
            phase_col = accent

        painter.setPen(phase_col)
        painter.setFont(QFont("SansSerif", 9, QFont.Weight.Bold))
        painter.drawText(QRectF(54, 80, 132, 18), Qt.AlignmentFlag.AlignCenter, status)

        progress = self.pomo_remaining / max(1, self.pomo_duration)
        ring_rect = QRectF(83, 100, 74, 74)
        painter.setPen(QPen(QColor(255, 255, 255, 30), 6))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(ring_rect)

        painter.setPen(QPen(phase_col, 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawArc(ring_rect, 90 * 16, int(-360 * 16 * progress))

        painter.setPen(QColor("#ffffff"))
        painter.setFont(QFont("Monospace", 13, QFont.Weight.Bold))
        painter.drawText(ring_rect, Qt.AlignmentFlag.AlignCenter, timer_text)

    def draw_sysmon_mode(self, painter: QPainter, accent: QColor):
        painter.setPen(accent)
        painter.setFont(QFont("SansSerif", 9, QFont.Weight.Bold))
        painter.drawText(QRectF(54, 78, 132, 18), Qt.AlignmentFlag.AlignCenter, "⚡ NOBARA VITALS")

        metrics = [
            ("CPU", self.cpu_percent, f"{self.cpu_percent:.0f}%", QColor("#00e5ff")),
            ("RAM", self.ram_percent, f"{self.ram_percent:.0f}%", QColor("#b388ff")),
            ("TMP", min(100.0, self.cpu_temp), f"{self.cpu_temp:.0f}°C", QColor("#ff8a65")),
        ]

        y = 104
        for label, val, txt, col in metrics:
            painter.setPen(QColor(255, 255, 255, 200))
            painter.setFont(QFont("Monospace", 8, QFont.Weight.Bold))
            painter.drawText(QRectF(62, y, 30, 16), Qt.AlignmentFlag.AlignLeft, label)
            painter.drawText(QRectF(144, y, 36, 16), Qt.AlignmentFlag.AlignRight, txt)

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(255, 255, 255, 35))
            painter.drawRoundedRect(QRectF(92, y + 3, 50, 8), 4, 4)

            painter.setBrush(col)
            fill_w = max(4.0, 50.0 * (min(100.0, max(0.0, val)) / 100.0))
            painter.drawRoundedRect(QRectF(92, y + 3, fill_w, 8), 4, 4)
            y += 28

    def draw_heart(self, painter: QPainter, cx: float, cy: float, size: float, color: QColor):
        path = QPainterPath()
        path.moveTo(cx, cy + size * 0.6)
        path.cubicTo(
            cx - size * 1.2,
            cy - size * 0.2,
            cx - size * 0.6,
            cy - size * 1.1,
            cx,
            cy - size * 0.35,
        )
        path.cubicTo(
            cx + size * 0.6,
            cy - size * 1.1,
            cx + size * 1.2,
            cy - size * 0.2,
            cx,
            cy + size * 0.6,
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawPath(path)

    def draw_particles(self, painter: QPainter):
        for p in self.particles:
            alpha = int(max(0.0, min(1.0, p["life"])) * 255)
            if p["type"] == "heart":
                col = QColor(255, 64, 129, alpha)
                self.draw_heart(painter, p["x"], p["y"], p["size"] * 0.55, col)
            elif p["type"] == "star":
                col = QColor(255, 215, 64, alpha)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(col)
                painter.drawEllipse(QPointF(p["x"], p["y"]), p["size"] * 0.3, p["size"] * 0.3)
            elif p["type"] == "zzz":
                painter.setPen(QColor(179, 229, 252, alpha))
                painter.setFont(QFont("SansSerif", int(p["size"] * 0.75), QFont.Weight.Bold))
                painter.drawText(QPointF(p["x"], p["y"]), "Zzz")
            elif p["type"] == "note":
                painter.setPen(QColor(247, 37, 133, alpha))
                painter.setFont(QFont("SansSerif", int(p["size"] * 0.85), QFont.Weight.Bold))
                painter.drawText(QPointF(p["x"], p["y"]), "♪")
            elif p["type"] == "water":
                col = QColor(0, 185, 255, alpha)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(col)
                painter.drawEllipse(QPointF(p["x"], p["y"]), p["size"] * 0.35, p["size"] * 0.45)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Deskimoni")
    app.setQuitOnLastWindowClosed(False)

    pet = DeskimonWidget()
    app.aboutToQuit.connect(pet.cleanup_on_quit)

    screen = app.primaryScreen()
    if screen is not None:
        geom = screen.availableGeometry()
        if pet.saved_pos_x is not None and pet.saved_pos_y is not None:
            # Stelle sicher, dass die Position innerhalb des sichtbaren Bildschirms liegt
            px = max(geom.left(), min(pet.saved_pos_x, geom.right() - pet.width()))
            py = max(geom.top(), min(pet.saved_pos_y, geom.bottom() - pet.height()))
            pet.move(px, py)
        else:
            pet.move(geom.right() - pet.width() - 40, geom.bottom() - pet.height() - 40)

    pet.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
