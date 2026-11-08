#!/usr/bin/env python3
"""
Deskimoni v2 - Robot Sound Engine
Erzeugt R2D2-Piepser, Kwai-Pfeifmelodie, spielt lokale Musik ab und
synthetisiert natürliche Sprachausgabe via edge-tts mit Lippen-Synchronisation.
"""

import os
import sys
import re
import math
import time
import wave
import struct
import shutil
import random
import asyncio
import tempfile
import threading
import subprocess

import edge_tts
from deskimoni_core.signals import WorkerSignals


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
        """Spielt eine WAV-Datei mit dem besten verfügbaren Audio-Tool ab."""
        if sys.platform == "win32":
            try:
                import winsound
                winsound.PlaySound(wav_path, winsound.SND_FILENAME)
                return
            except Exception:
                pass

        for tool in ["pw-play", "paplay", "aplay", "ffplay"]:
            if shutil.which(tool):
                try:
                    args = [tool, "-nodisp", "-autoexit", "-loglevel", "quiet", wav_path] if tool == "ffplay" else [tool, wav_path]
                    subprocess.run(
                        args,
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

            def _delayed_speech_start():
                time.sleep(0.12)
                self.signals.speech_state.emit(True)

            t_sync = threading.Thread(target=_delayed_speech_start, daemon=True)
            t_sync.start()

            if shutil.which("ffplay"):
                subprocess.run(
                    ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", mp3_path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=30,
                )
            elif shutil.which("mpv"):
                subprocess.run(
                    ["mpv", "--no-video", "--really-quiet", mp3_path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=30,
                )
            elif sys.platform == "win32":
                # Windows Media Player PowerShell Fallback
                ps_cmd = f"(New-Object Media.SoundPlayer '{mp3_path}').PlaySync()"
                subprocess.run(["powershell", "-c", ps_cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
        except Exception as e:
            print(f"[TTS Info] edge-tts (Online-Stimme) nicht erreichbar ({type(e).__name__}: {e}) -> wechsle zu Offline-Stimme")
            try:
                self.signals.speech_state.emit(True)
                if shutil.which("espeak-ng"):
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
