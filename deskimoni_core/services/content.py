#!/usr/bin/env python3
"""
Deskimoni v2 - Content & Media Service Mixin
Wetter (Open-Meteo), RSS-News Feeds, Web-Radio, Podcasts,
Gesundheits-Erinnerungen, Filmzitate, Witze und Heimweg-Verhalten.
"""

import os
import sys
import re
import time
import random
import threading
import subprocess
import xml.etree.ElementTree as ET
import requests

from deskimoni_core.qt import QTimer, QApplication, QInputDialog


class DeskimonContentMixin:
    """Mixin für externe Inhalte, Medien-Steuerung, Witze und Heimweg."""

    def show_linux_tip(self, idx: int = None):
        self.mode = "linux"
        if idx is None:
            self.linux_tip_idx = (self.linux_tip_idx + 1) % len(self.LINUX_TIPS)
        else:
            self.linux_tip_idx = idx % len(self.LINUX_TIPS)
        title, body = self.LINUX_TIPS[self.linux_tip_idx]
        self.on_ai_reply(f"{title}: {body}", "excited")

    # ==========================================
    # --- 🌤️ Live-Wetter ---
    # ==========================================
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
            headers = {"User-Agent": "Deskimoni/1.0 (Desktop Buddy)"}
            resp = requests.get(url, headers=headers, timeout=10.0)
            if resp.status_code == 200:
                xml_text = resp.content
                root = ET.fromstring(xml_text)
                items = []

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
        """Startet den gemütlichen Heimweg zum Hauptbildschirm."""
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
        if cur_screen is not None and cur_screen != primary:
            QTimer.singleShot(400, self.start_walk_home_to_primary)
        else:
            if self.is_walking_home:
                self.is_walking_home = False
                self.sound.stop_gohome_music()

    def trigger_walk_home_reaction(self):
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
        self.sound.stop_kwai_whistle()
        self.trigger_bounce(7.5)
        for _ in range(6):
            self.spawn_particle("heart")
        self.show_bubble("Endlich wieder daheim! Hier ist es doch am schönsten! 💖", 4.5)
        self.sound.play_chirp("love")

    def trigger_random_chatter(self, category: str = "random"):
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
        self.sound.stop_kwai_whistle()
        self.save_user_settings()
        self.stop_radio()
        if getattr(self, "cursor_tracker", None) is not None:
            self.cursor_tracker.close()
        if getattr(self, "cursor_shaker", None) is not None:
            self.cursor_shaker.close()
        if getattr(self, "norskmus_proc", None) and self.norskmus_proc.poll() is None:
            try:
                self.norskmus_proc.terminate()
            except Exception:
                pass

    def update_mpris_metadata(self):
        if sys.platform != "linux":
            return
        try:
            services = subprocess.getoutput("qdbus-qt6 org.mpris.MediaPlayer2.* 2>/dev/null").splitlines()
            services = [s.strip() for s in services if "org.mpris.MediaPlayer2." in s]
            if not services:
                self.music_playing = False
                self.music_service = ""
                return

            chosen = services[0]
            status = "Stopped"
            for srv in services:
                st = subprocess.getoutput(
                    f"qdbus-qt6 {srv} /org/mpris/MediaPlayer2 org.mpris.MediaPlayer2.Player.PlaybackStatus 2>/dev/null"
                ).strip()
                if st == "Playing":
                    chosen = srv
                    status = "Playing"
                    break
                status = st

            self.music_service = chosen
            self.music_playing = status == "Playing"

            meta = subprocess.getoutput(
                f"qdbus-qt6 {chosen} /org/mpris/MediaPlayer2 org.mpris.MediaPlayer2.Player.Metadata 2>/dev/null"
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
        if sys.platform != "linux":
            return
        self.update_mpris_metadata()
        if self.music_service:
            subprocess.Popen(
                ["qdbus-qt6", self.music_service, "/org/mpris/MediaPlayer2", f"org.mpris.MediaPlayer2.Player.{method}"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
