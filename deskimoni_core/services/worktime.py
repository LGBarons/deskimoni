#!/usr/bin/env python3
"""
Deskimoni v2.1 - Arbeitszeit- & Feierabend-Rechner (Work Time Module)
Eigenständiges Modul für:
- Montag bis Mittwoch: 9 Stunden Soll-Arbeitszeit
- Kernarbeitszeit: 09:00 - 15:00 Uhr (Präsenzpflicht)
- Donnerstag: 15:00 Uhr Feierabend („Ab gehts - nach hause!“)
- Gesetzliche Ruhepausen nach § 4 ArbZG:
    * Bis 6h Arbeit: Keine Pflichtpause
    * 6h bis 9h: Mindestens 30 Minuten Pause (spätestens nach 6h)
    * Mehr als 9h: Mindestens 45 Minuten Pause (spätestens nach 9h)
- Feierabend-Countdown & Ansage („Noch 3 Stunden, dann ist endlich Feierabend!“)
- Überstunden-Erfassung
- Pausentracking (Pause starten / Pause beenden)
"""

import os
import time
import json
from datetime import datetime, date, timedelta

from deskimoni_core.qt import QInputDialog, QMessageBox


class DeskimonWorkTimeMixin:
    """Mixin für Arbeitszeit, Pausen (§ 4 ArbZG), Feierabend und Überstunden."""

    def init_worktime(self):
        """Initialisiert den Arbeitszeit-Zustand für den heutigen Tag."""
        self.worktime_file = os.path.expanduser("~/.config/deskimoni/worktime.json")
        self.work_start_time = None
        self.work_pause_active = False
        self.work_pause_start = None
        self.work_pause_seconds = 0
        self.work_overtime_total = 0
        self.work_last_alert_check = 0.0
        self.work_6h_alert_fired = False
        self.work_feierabend_alert_fired = False
        self.work_thu_15_alert_fired = False

        self.load_worktime_data()

        # Wenn heute noch kein Arbeitsbeginn erfasst wurde, stempelt Deskimoni den heutigen Start automatisch ein!
        now = time.time()
        today_str = date.today().isoformat()
        if self.work_start_time is None:
            self.work_start_time = now
            self.save_worktime_data()

    def get_worktime_settings(self) -> dict:
        return {
            "mon_wed_hours": 9.0,         # Mo - Mi: 9h Soll
            "thu_leave_time": "15:00",     # Do: 15:00 Uhr pünktlich Feierabend
            "fri_hours": 5.0,             # Fr: 5h Soll (flexibel)
            "core_start": "09:00",        # Kernzeit 09:00 Uhr
            "core_end": "15:00",          # Kernzeit 15:00 Uhr
        }

    def load_worktime_data(self):
        try:
            if not os.path.exists(self.worktime_file):
                return
            with open(self.worktime_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            today_str = date.today().isoformat()
            days = data.get("days", {})
            if today_str in days:
                d = days[today_str]
                self.work_start_time = d.get("start_time")
                self.work_pause_seconds = int(d.get("pause_seconds", 0))
                self.work_pause_active = bool(d.get("pause_active", False))
                self.work_pause_start = d.get("pause_start")
            self.work_overtime_total = int(data.get("overtime_total_seconds", 0))
        except Exception:
            pass

    def save_worktime_data(self):
        try:
            os.makedirs(os.path.dirname(self.worktime_file), exist_ok=True)
            data = {}
            if os.path.exists(self.worktime_file):
                try:
                    with open(self.worktime_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except Exception:
                    data = {}
            if "days" not in data:
                data["days"] = {}
            today_str = date.today().isoformat()
            data["days"][today_str] = {
                "start_time": self.work_start_time,
                "pause_seconds": self.work_pause_seconds,
                "pause_active": self.work_pause_active,
                "pause_start": self.work_pause_start,
                "updated_at": datetime.now().isoformat(),
            }
            data["overtime_total_seconds"] = self.work_overtime_total
            with open(self.worktime_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    # ==========================================
    # --- Berechnung nach ArbZG & Wochentagen ---
    # ==========================================
    def get_feierabend_info(self) -> dict:
        """Berechnet exakte Arbeitszeit, Pflichtpausen nach § 4 ArbZG, Feierabendzeit und Überstunden."""
        now = time.time()
        dt_now = datetime.now()
        weekday = dt_now.weekday()  # 0=Mo, 1=Di, 2=Mi, 3=Do, 4=Fr, 5=Sa, 6=So

        start_ts = self.work_start_time or now
        gross_elapsed = max(0, int(now - start_ts))

        # Aktuelle Pausenzeit (gespeicherte Pausen + laufende Pause)
        current_pause = self.work_pause_seconds
        if self.work_pause_active and self.work_pause_start:
            current_pause += max(0, int(now - self.work_pause_start))

        # Reale Anwesenheit abzüglich genommener Pausen
        net_worked_seconds = max(0, gross_elapsed - current_pause)

        # 1. Gesetzliche Pflichtpause nach § 4 ArbZG ermitteln:
        # - bis 6 Stunden Arbeit: 0 Min Pause
        # - mehr als 6 bis 9 Stunden: mind. 30 Minuten Pause
        # - mehr als 9 Stunden: mind. 45 Minuten Pause
        if net_worked_seconds > 9 * 3600:
            arbzg_min_pause = 45 * 60
        elif net_worked_seconds > 6 * 3600:
            arbzg_min_pause = 30 * 60
        else:
            arbzg_min_pause = 0

        # Die tatsächliche Pause für die Feierabend-Berechnung ist mindestens die gesetzliche Mindestpause
        effective_pause = max(current_pause, arbzg_min_pause)

        # 2. Soll-Arbeitszeit für den heutigen Tag
        if weekday in (0, 1, 2):
            # Montag bis Mittwoch: genau 9 Stunden Soll
            target_work_seconds = int(9.0 * 3600)
            is_thursday = False
            is_weekend = False
        elif weekday == 3:
            # Donnerstag: Pünktlich um 15:00 Uhr Feierabend!
            is_thursday = True
            is_weekend = False
            # Fester Zielzeitpunkt 15:00 Uhr
            thu_target_dt = dt_now.replace(hour=15, minute=0, second=0, microsecond=0)
            target_work_seconds = max(0, int((thu_target_dt.timestamp() - start_ts) - effective_pause))
        elif weekday == 4:
            # Freitag: z.B. 5 Stunden
            target_work_seconds = int(5.0 * 3600)
            is_thursday = False
            is_weekend = False
        else:
            # Wochenende
            target_work_seconds = 0
            is_thursday = False
            is_weekend = True

        # 3. Geplante Feierabend-Uhrzeit berechnen
        if is_thursday:
            feierabend_dt = dt_now.replace(hour=15, minute=0, second=0, microsecond=0)
            feierabend_ts = feierabend_dt.timestamp()
        elif is_weekend:
            feierabend_ts = now
            feierabend_dt = dt_now
        else:
            # Feierabend = Startzeit + Soll-Netto-Stunden + gesetzliche/genommene Pause
            # (Für 9h Arbeit sind das 9h 30m brutto)
            total_required_pause = 30 * 60 if target_work_seconds >= 6 * 3600 else 0
            final_pause = max(current_pause, total_required_pause)
            feierabend_ts = start_ts + target_work_seconds + final_pause
            feierabend_dt = datetime.fromtimestamp(feierabend_ts)

        remaining_seconds = int(feierabend_ts - now)
        is_feierabend = remaining_seconds <= 0

        # Überstunden heute (wenn über Soll hinausgearbeitet wird)
        overtime_today = max(0, net_worked_seconds - target_work_seconds) if not is_weekend else 0

        # Formatierte Strings
        worked_h = net_worked_seconds // 3600
        worked_m = (net_worked_seconds % 3600) // 60
        target_h = target_work_seconds // 3600
        target_m = (target_work_seconds % 3600) // 60

        rem_abs = abs(remaining_seconds)
        rem_h = rem_abs // 3600
        rem_m = (rem_abs % 3600) // 60

        pause_m = current_pause // 60
        arbzg_pause_m = arbzg_min_pause // 60

        return {
            "weekday": weekday,
            "is_thursday": is_thursday,
            "is_weekend": is_weekend,
            "start_time_str": datetime.fromtimestamp(start_ts).strftime("%H:%M"),
            "feierabend_time_str": feierabend_dt.strftime("%H:%M"),
            "net_worked_seconds": net_worked_seconds,
            "worked_str": f"{worked_h}h {worked_m:02d}m",
            "target_str": f"{target_h}h {target_m:02d}m" if not is_thursday else "15:00 Uhr",
            "remaining_seconds": remaining_seconds,
            "remaining_str": f"{rem_h}h {rem_m:02d}m",
            "is_feierabend": is_feierabend,
            "overtime_today_seconds": overtime_today,
            "overtime_str": f"+{overtime_today // 3600}h {(overtime_today % 3600) // 60:02d}m",
            "pause_seconds": current_pause,
            "pause_minutes": pause_m,
            "arbzg_min_pause_minutes": arbzg_pause_m,
            "pause_active": self.work_pause_active,
        }

    # ==========================================
    # --- Pausen- & Stempel-Steuerung ---
    # ==========================================
    def toggle_work_pause(self):
        """Startet oder beendet die Arbeitsunterbrechung (Pause)."""
        now = time.time()
        if not self.work_pause_active:
            self.work_pause_active = True
            self.work_pause_start = now
            self.save_worktime_data()
            self.trigger_bounce(6.0)
            self.sound.play_chirp("chill")
            msg = "☕ Pause gestartet! Erhole dich gut – Deskimoni stoppt deine Arbeitszeit!"
            self.show_bubble(msg, 4.5)
            self.sound.speak("Schöne Pause! Ich stoppe deine Arbeitszeit.", "chill")
        else:
            elapsed_pause = max(0, int(now - (self.work_pause_start or now)))
            self.work_pause_seconds += elapsed_pause
            self.work_pause_active = False
            self.work_pause_start = None
            self.save_worktime_data()
            self.trigger_bounce(7.0)
            self.sound.play_chirp("happy")
            p_mins = self.work_pause_seconds // 60
            msg = f"💼 Willkommen zurück! Pause beendet (heute insgesamt {p_mins} Min. Pause)."
            self.show_bubble(msg, 4.5)
            self.sound.speak(f"Willkommen zurück! Heute hast du insgesamt {p_mins} Minuten Pause gemacht.", "happy")
        self.update()

    def speak_feierabend_status(self):
        """Sagt die verbleibende Arbeitszeit bis zum Feierabend laut und humorvoll an."""
        info = self.get_feierabend_info()
        now_hour = datetime.now().hour

        if info["is_weekend"]:
            msg = "Heute ist Wochenende! Keine Arbeitszeit – genieß die freie Zeit in vollen Zügen! 🏖️"
            self.show_bubble(msg, 5.0)
            self.sound.speak("Heute ist Wochenende! Keine Arbeitszeit. Genieß deinen freien Tag!", "happy")
            return

        if info["is_thursday"]:
            if info["is_feierabend"]:
                msg = "🎉 Es ist nach 15:00 Uhr am Donnerstag! Ab geht's nach Hause! 🚀"
                self.show_bubble(msg, 6.0)
                self.sound.speak_and_play_gohome("Es ist Donnerstag 15 Uhr vorbei! Ab geht's nach Hause!", "excited")
            else:
                msg = f"🚀 Donnerstag! Pünktlich um 15:00 Uhr ist Feierabend! Noch {info['remaining_str']} bis zur Heimfahrt!"
                self.show_bubble(msg, 6.0)
                self.sound.speak(f"Heute ist Donnerstag! Um 15:00 Uhr geht es ab nach Hause! Noch {info['remaining_str']}!", "excited")
            return

        if info["is_feierabend"]:
            msg = f"🎉 Feierabend erreicht! Deine {info['target_str']} sind geschafft! Überstunden heute: {info['overtime_str']}! ✨"
            self.show_bubble(msg, 6.0)
            self.sound.speak(f"Juhu, Feierabend! Deine Sollzeit ist voll! Du hast heute schon {info['overtime_str']} Überstunden gesammelt.", "love")
            return

        msg = (
            f"💼 Arbeitszeit heute: {info['worked_str']} von {info['target_str']}.\n"
            f"🏁 Geplanter Feierabend: {info['feierabend_time_str']} Uhr (noch {info['remaining_str']})!\n"
            f"☕ Pause: {info['pause_minutes']}m (Pflicht nach § 4 ArbZG: {info['arbzg_min_pause_minutes']}m)."
        )
        voice_msg = f"Noch {info['remaining_str']}, dann ist endlich Feierabend! Um {info['feierabend_time_str']} Uhr hast du deine neun Stunden geschafft!"
        self.show_bubble(msg, 7.5)
        self.sound.speak(voice_msg, "happy")

    def prompt_set_work_start_dialog(self):
        """Erlaubt das nachträgliche Anpassen des Arbeitsbeginns."""
        info = self.get_feierabend_info()
        txt, ok = QInputDialog.getText(
            self,
            "⏰ Arbeitsbeginn anpassen",
            "Wann hast du heute angefangen zu arbeiten? (HH:MM):",
            text=info["start_time_str"]
        )
        if ok and txt.strip():
            import re
            m = re.search(r"(\d{1,2})[:\.](\d{2})", txt.strip())
            if m:
                h, mi = int(m.group(1)), int(m.group(2))
                if 0 <= h <= 23 and 0 <= mi <= 59:
                    dt_now = datetime.now()
                    new_start_dt = dt_now.replace(hour=h, minute=mi, second=0, microsecond=0)
                    self.work_start_time = new_start_dt.timestamp()
                    self.save_worktime_data()
                    self.trigger_bounce(6.0)
                    self.show_bubble(f"⏰ Arbeitsbeginn heute auf {h:02d}:{mi:02d} Uhr gesetzt!", 4.0)
                    self.update()
                    return
            QMessageBox.warning(self, "Ungültige Uhrzeit", "Bitte das Format HH:MM verwenden (z. B. 08:30).")

    # ==========================================
    # --- Periodische Prüfung & Alarme ---
    # ==========================================
    def check_worktime_alerts(self, now: float):
        """Wird regelmäßig aus update_animation aufgerufen und prüft ArbZG-Pausen und Feierabend."""
        if now - self.work_last_alert_check < 30.0:
            return
        self.work_last_alert_check = now

        info = self.get_feierabend_info()
        if info["is_weekend"]:
            return

        dt_now = datetime.now()

        # 1. Donnerstag 15:00 Uhr: „Ab gehts - nach hause!“
        if info["is_thursday"]:
            if dt_now.hour == 15 and dt_now.minute < 3 and not self.work_thu_15_alert_fired:
                self.work_thu_15_alert_fired = True
                self.trigger_bounce(12.0)
                msg = "🚀 15:00 Uhr am Donnerstag! Kernarbeitszeit beendet – Ab geht's nach Hause! 🎶"
                self.show_bubble(msg, 12.0)
                self.sound.speak_and_play_gohome("15 Uhr! Ab geht's nach Hause!", "excited")
                self.start_walk_home_to_primary()
                return

        # 2. § 4 ArbZG Pausen-Erinnerung: Nach 6 Stunden Arbeitszeit
        if info["net_worked_seconds"] >= 6 * 3600 and info["pause_seconds"] < 30 * 60:
            if not self.work_6h_alert_fired:
                self.work_6h_alert_fired = True
                self.trigger_bounce(9.0)
                self.sound.play_chirp("curious")
                msg = (
                    "⚠️ Gesetzliche Pause nach § 4 ArbZG fällig!\n"
                    "Du arbeitest seit 6 Stunden. Jetzt sind mindestens 30 Minuten Ruhepause gesetzlich vorgeschrieben!"
                )
                self.show_bubble(msg, 10.0)
                self.sound.speak("Achtung! Nach sechs Stunden Arbeit ist laut Arbeitszeitgesetz eine Pause von mindestens dreißig Minuten fällig.", "chill")
                return

        # 3. Feierabend erreicht! (Mo - Mi: 9h Netto geschafft)
        if info["is_feierabend"] and not self.work_feierabend_alert_fired and not info["is_thursday"]:
            self.work_feierabend_alert_fired = True
            self.trigger_bounce(12.0)
            self.sound.play_chirp("happy")
            for _ in range(8):
                self.spawn_particle("star")
            msg = f"🎉 Feierabend! Deine 9 Stunden Arbeitszeit plus gesetzliche Pause sind vollbracht! Schönen Feierabend! ✨"
            self.show_bubble(msg, 12.0)
            self.sound.speak("Juhu, Feierabend! Du hast deine neun Stunden Arbeitszeit geschafft! Genieß deinen Feierabend!", "love")
