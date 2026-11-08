#!/usr/bin/env python3
"""
Deskimoni v2 - Menus & Tray Mixin
Rechtsklick-Menü, System-Tray-Icon, Mehrsprachigkeit (DE/EN/NB),
Skin- und Modus-Auswahl.
"""

import os
import sys
import shutil
import subprocess
from datetime import datetime

from deskimoni_core.qt import (
    Qt, QSize,
    QAction, QActionGroup, QIcon,
    QApplication, QMenu, QSystemTrayIcon, QStyle, QInputDialog, QPushButton, QLineEdit
)

from deskimoni_core.audio.sound_engine import RobotSoundEngine


class DeskimonMenuMixin:
    """Mixin für Kontextmenüs, Taskleiste und Spracheinstellungen."""

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
        if lang_code in ("de", "en", "nb"):
            self.app_language = lang_code
            self.save_user_settings()
            if hasattr(self, "tray_icon"):
                self.tray_icon.setContextMenu(self.build_context_menu())
            msg = {
                "de": "🌐 Menüsprache auf Deutsch umgestellt!",
                "en": "🌐 Language switched to English!",
                "nb": "🌐 Språk endret til norsk (bokmål)!",
            }.get(lang_code, "🌐 Sprache geändert!")
            self.show_bubble(msg, 3.5)
            self.sound.play_chirp("happy")

    def get_app_icon(self, name: str) -> QIcon:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        path = os.path.join(base_dir, "assets", "icons", f"{name}.svg")
        if os.path.exists(path):
            return QIcon(path)
        return QIcon()

    def setup_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        icon = self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
        self.tray_icon.setIcon(icon)
        self.tray_icon.setToolTip("Deskimoni – Dein Desktop-Buddy")
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

        # 1. Menüsprache
        lang_menu = menu.addMenu(self.t("menu_lang"))
        lang_group = QActionGroup(self)
        for code, label in [("de", "🇩🇪 Deutsch (Standard)"), ("en", "🇬🇧 English"), ("nb", "🇳🇴 Norsk (Bokmål)")]:
            act_lg = QAction(label, self, checkable=True)
            act_lg.setChecked(self.app_language == code)
            act_lg.triggered.connect(lambda checked, c=code: self.set_app_language(c))
            lang_group.addAction(act_lg)
            lang_menu.addAction(act_lg)

        menu.addSeparator()

        # 2. Skin-Auswahl
        skin_menu = menu.addMenu(self.t("menu_skin"))
        skin_group = QActionGroup(self)
        for skin_id, _ in self.SKINS:
            label = self.get_skin_label(skin_id)
            act = QAction(label, self, checkable=True)
            act.setChecked(self.skin == skin_id)
            act.triggered.connect(lambda checked, s=skin_id: self.set_skin(s))
            skin_group.addAction(act)
            skin_menu.addAction(act)

        # 3. Modus-Auswahl
        mode_menu = menu.addMenu(self.t("menu_mode"))
        mode_group = QActionGroup(self)
        for mode_id, _ in self.MODES:
            label = self.get_mode_label(mode_id)
            act = QAction(label, self, checkable=True)
            act.setChecked(self.mode == mode_id)
            act.triggered.connect(lambda checked, m=mode_id: self.set_mode(m))
            mode_group.addAction(act)
            mode_menu.addAction(act)

        # 4. Emotion-Auswahl
        emo_menu = menu.addMenu(self.t("menu_emo"))
        emo_group = QActionGroup(self)
        for emo_id, _ in self.EMOTIONS:
            label = self.get_emotion_label(emo_id)
            act = QAction(label, self, checkable=True)
            act.setChecked(self.forced_emotion == emo_id)
            act.triggered.connect(lambda checked, e=emo_id: self.set_forced_emotion(e))
            emo_group.addAction(act)
            emo_menu.addAction(act)

        # 5. Gedächtnis & Identität
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

        # 6. Sprache & KI-Einstellungen
        voice_menu = menu.addMenu(self.t("menu_voice_ai"))
        act_tts = QAction(self.t("act_tts"), self, checkable=True)
        act_tts.setChecked(self.sound.voice_enabled)
        act_tts.triggered.connect(self.toggle_voice)
        voice_menu.addAction(act_tts)

        act_chirp = QAction(self.t("act_chirps"), self, checkable=True)
        act_chirp.setChecked(self.sound.chirps_enabled)
        act_chirp.triggered.connect(self.toggle_chirps)
        voice_menu.addAction(act_chirp)

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

        # 7. Arbeitszeit- & Feierabend-Planer (§ 4 ArbZG)
        work_menu = menu.addMenu("💼 Arbeitszeit & Feierabend (Mo-Mi 9h / Do 15h)")
        act_work_status = QAction("🕒 Feierabend-Status & Restzeit jetzt ansagen", self)
        act_work_status.triggered.connect(self.speak_feierabend_status)
        work_menu.addAction(act_work_status)

        act_work_mode = QAction("📟 Display auf Arbeitszeit-Modus schalten", self)
        act_work_mode.triggered.connect(lambda: self.set_mode("work"))
        work_menu.addAction(act_work_mode)

        work_menu.addSeparator()
        pause_txt = "▶ Pause beenden (Weiterarbeiten)" if getattr(self, "work_pause_active", False) else "☕ Pause starten (nach § 4 ArbZG)"
        act_work_pause = QAction(pause_txt, self)
        act_work_pause.triggered.connect(self.toggle_work_pause)
        work_menu.addAction(act_work_pause)

        act_work_start = QAction("⏰ Arbeitsbeginn heute anpassen...", self)
        act_work_start.triggered.connect(self.prompt_set_work_start_dialog)
        work_menu.addAction(act_work_start)

        act_thu_leave = QAction("🚀 Donnerstag Feierabend-Gong testen (15:00 Uhr)", self)
        act_thu_leave.triggered.connect(lambda: (self.trigger_bounce(9.0), self.sound.speak_and_play_gohome("15 Uhr am Donnerstag! Ab geht's nach Hause!", "excited"), self.start_walk_home_to_primary()))
        work_menu.addAction(act_thu_leave)

        # 8. Pomodoro & Wecker
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
        act_pomo_sound.triggered.connect(lambda checked: setattr(self, "pomo_sound_enabled", checked) or self.save_user_settings())
        pomo_menu.addAction(act_pomo_sound)

        pomo_menu.addSeparator()
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

        # 8. Befehle
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
        ]:
            act_c = QAction(self.t(cmd_key), self)
            act_c.triggered.connect(lambda checked, c=cmd_str: self.ask_deskimoni(c))
            cmd_menu.addAction(act_c)

        # 9. RSS-News
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

        # 10. Gesundheit & Pausen
        health_menu = menu.addMenu(self.t("menu_health"))
        act_water = QAction(self.t("act_water", mins=self.water_reminder_mins), self, checkable=True)
        act_water.setChecked(self.water_reminder_enabled)
        act_water.triggered.connect(lambda checked: setattr(self, "water_reminder_enabled", checked) or self.save_user_settings())
        health_menu.addAction(act_water)

        act_move = QAction(self.t("act_move", mins=self.move_reminder_mins), self, checkable=True)
        act_move.setChecked(self.move_reminder_enabled)
        act_move.triggered.connect(lambda checked: setattr(self, "move_reminder_enabled", checked) or self.save_user_settings())
        health_menu.addAction(act_move)

        health_menu.addSeparator()
        act_test_w = QAction(self.t("act_water_test"), self)
        act_test_w.triggered.connect(self.trigger_water_reminder)
        health_menu.addAction(act_test_w)

        act_test_m = QAction(self.t("act_move_test"), self)
        act_test_m.triggered.connect(self.trigger_move_reminder)
        health_menu.addAction(act_test_m)

        # 11. Web-Radio & Podcasts
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
        act_dance_auto = QAction("🕺 Automatisch tanzen bei Musik", self, checkable=True)
        act_dance_auto.setChecked(getattr(self, "dance_enabled", True))
        act_dance_auto.triggered.connect(lambda checked: setattr(self, "dance_enabled", checked) or self.save_user_settings())
        radio_menu.addAction(act_dance_auto)

        act_not_music = QAction("🤫 „Das ist keine Musik!“ (Tanz sofort stoppen)", self)
        act_not_music.triggered.connect(self.mark_current_not_music)
        radio_menu.addAction(act_not_music)

        # 12. Plaudern, Witze & Filmzitate
        chatter_menu = menu.addMenu(self.t("menu_chatter"))
        act_chat_toggle = QAction(self.t("act_chatter_toggle", mins=self.chatter_interval_mins), self, checkable=True)
        act_chat_toggle.setChecked(self.chatter_enabled)
        act_chat_toggle.triggered.connect(lambda checked: setattr(self, "chatter_enabled", checked) or self.save_user_settings())
        chatter_menu.addAction(act_chat_toggle)

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

        # 12b. Begleiter & Freunde
        friends_menu = menu.addMenu("👥 Begleiter & Freunde")
        crow_running = self.is_jothecrow_running()
        crow_label = "🐦‍⬛ Jo the Crow schlafen legen" if crow_running else "🐦‍⬛ Jo the Crow rufen (Slang-Übersetzerin)"
        act_crow = QAction(crow_label, self)
        act_crow.triggered.connect(self.toggle_jothecrow)
        friends_menu.addAction(act_crow)

        mouse_running = self.is_norskmus_running()
        mouse_label = "🐭 NorskMus schlafen legen" if mouse_running else "🐭 NorskMus rufen (Mauszeiger-Fänger)"
        act_mouse = QAction(mouse_label, self)
        act_mouse.triggered.connect(self.toggle_norskmus)
        friends_menu.addAction(act_mouse)

        menu.addSeparator()

        # 13. Größe & Verhalten
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

        act_pet = QAction(self.t("act_pet"), self)
        act_pet.triggered.connect(self.trigger_love_burst)
        menu.addAction(act_pet)

        menu.addSeparator()
        act_quit = QAction(self.t("act_quit"), self)
        act_quit.triggered.connect(QApplication.instance().quit)
        menu.addAction(act_quit)

        return menu
