#!/usr/bin/env python3
"""
NorskMus (Lillemus) - Deine kleine norwegische B1/B2-Vokabel- & Grammatik-Maus! 🐭🇳🇴
Eigenständiges Mini-Desktop-Haustier passend zu Deskimoni.
- B1/B2 Bokmål: Redewendungen, Sätze, komplexe Vokabeln & Grammatik
- Schnelles Multiple-Choice-Quiz & Karteikarten direkt beim Anklicken
- Natürliche norwegische Aussprache (edge-tts: nb-NO-PernilleNeural / nb-NO-FinnNeural)
- KI-Erweiterung über Google Gemini API oder lokales Ollama (teilt ~/.config/deskimoni/settings.json)
"""

import os
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
import shutil
import struct
import random
import asyncio
import tempfile
import threading
import subprocess
import requests
import edge_tts

from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF, pyqtSignal, QObject
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
)
from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QMenu,
    QSystemTrayIcon,
    QStyle,
    QPushButton,
    QInputDialog,
)


# --- Kuratierter B1/B2 Bokmål-Wortschatz (Sätze, Redewendungen, Grammatik & Nuancen) ---
DEFAULT_B1_B2_DECK = [
    {
        "no": "Det er ugler i mosen.",
        "de": "Da ist etwas faul / verdächtig.",
        "cat": "Redewendung",
        "example": "Han smilte altfor bredt – her er det ugler i mosen.",
        "note": "Wörtlich: 'Es sind Eulen im Moor' (aus dem Dänischen 'ulve i mosen' = Wölfe im Moor).",
        "wrong": [
            "Es ist nachts sehr ruhig im Wald.",
            "Man sollte die Natur besser schützen.",
            "Jemand hat heute besonders viel Glück.",
        ],
    },
    {
        "no": "Å gå rundt grøten",
        "de": "Um den heißen Brei herumreden",
        "cat": "Redewendung",
        "example": "Slutt å gå rundt grøten og si hva du egentlig mener!",
        "note": "Verwendet wie im Deutschen: Nicht direkt zum Punkt kommen.",
        "wrong": [
            "Ein traditionelles Essen kochen",
            "Einen langen Spaziergang machen",
            "Sich über eine Kleinigkeit ärgern",
        ],
    },
    {
        "no": "Til tross for at det regnet, dro vi på fjelltur.",
        "de": "Obwohl es regnete, machten wir eine Bergtour.",
        "cat": "Grammatik (Konzessivsatz)",
        "example": "Til tross for at han var sliten, fullførte han oppgaven.",
        "note": "'Til tross for at' leitet einen Nebensatz ein (Subjekt + Verb). Ohne 'at' steht ein Nomen: 'til tross for regnet'.",
        "wrong": [
            "Weil es stark regnete, blieben wir im Tal.",
            "Falls es morgen regnet, verschieben wir die Tour.",
            "Sobald der Regen aufhörte, gingen wir los.",
        ],
    },
    {
        "no": "Jo mer jeg øver, desto lettere går det.",
        "de": "Je mehr ich übe, desto leichter geht es.",
        "cat": "Grammatik (Proportionalsatz)",
        "example": "Jo tidligere vi drar, desto mindre trafikk møter vi.",
        "note": "'Jo ... desto/dess ...': Im 'jo'-Satz gilt Nebensatzwortstellung, im 'desto'-Satz steht das Verb an 2. Stelle (Inversion!).",
        "wrong": [
            "Obwohl ich viel übe, fällt es mir noch schwer.",
            "Sowohl das Üben als auch das Lesen helfen mir.",
            "Entweder übe ich jetzt oder es wird zu spät.",
        ],
    },
    {
        "no": "Å ta noe for gitt",
        "de": "Etwas für selbstverständlich halten",
        "cat": "Redewendung",
        "example": "Man bør ikke ta god helse for gitt.",
        "note": "'gitt' ist das Partizip Perfekt von 'å gi' (geben).",
        "wrong": [
            "Etwas dankend als Geschenk annehmen",
            "Einen Vertrag endgültig unterschreiben",
            "Eine schwierige Aufgabe sofort aufgeben",
        ],
    },
    {
        "no": "Hadde jeg visst det, ville jeg ha sagt ifra.",
        "de": "Hätte ich das gewusst, hätte ich Bescheid gesagt.",
        "cat": "Grammatik (Irrealis / Konditional)",
        "example": "Hadde vi hatt bedre tid, kunne vi ha besøkt museet.",
        "note": "Bedingungssatz ohne 'hvis/dersom' durch Verb-Erststellung ('Hadde jeg...'). 'å si ifra' = Bescheid geben.",
        "wrong": [
            "Wenn ich es erfahre, sage ich dir morgen Bescheid.",
            "Da ich es wusste, habe ich sofort angerufen.",
            "Ich wusste nicht, ob er schon Bescheid gesagt hatte.",
        ],
    },
    {
        "no": "en forutsetning",
        "de": "eine Voraussetzung / Bedingung",
        "cat": "Wortschatz B2",
        "example": "Gode norskkunnskaper er en viktig forutsetning for jobben.",
        "note": "Verb dazu: 'å forutsette' (voraussetzen). 'under forutsetning av at...' = unter der Voraussetzung, dass...",
        "wrong": [
            "eine unerwartete Fortsetzung",
            "eine offizielle Übersetzung",
            "eine persönliche Vorstellung",
        ],
    },
    {
        "no": "å sette pris på noe",
        "de": "etwas zu schätzen wissen / wertschätzen",
        "cat": "Ausdruck B1/B2",
        "example": "Jeg setter stor pris på at du hjalp meg i går.",
        "note": "Falscher Freund: Bedeutet im Alltag meist nicht 'einen Preis festlegen', sondern 'wertschätzen'.",
        "wrong": [
            "den Preis für eine Ware senken",
            "einen Wettbewerb gewinnen",
            "etwas im Geschäft reklamieren",
        ],
    },
    {
        "no": "Det spørs om han rekker toget.",
        "de": "Es ist fraglich, ob er den Zug noch schafft.",
        "cat": "Ausdruck B2",
        "example": "Det spørs om vi blir ferdige før helgen.",
        "note": "'Det spørs' = Es ist ungewiss / fraglich / kommt darauf an. 'å rekke' = rechtzeitig erreichen.",
        "wrong": [
            "Er fragt am Schalter nach dem nächsten Zug.",
            "Es wurde beschlossen, dass er den Zug nimmt.",
            "Er hat den Zug leider schon wieder verpasst.",
        ],
    },
    {
        "no": "midlertidig",
        "de": "vorübergehend / provisorisch / temporär",
        "cat": "Wortschatz B2",
        "example": "Dette er bare en midlertidig løsning til vi finner noe bedre.",
        "note": "Gegenteil: 'varig' oder 'permanent'.",
        "wrong": [
            "mittelalterlich / historisch",
            "durchschnittlich / mittelmäßig",
            "gleichzeitig / parallel",
        ],
    },
    {
        "no": "Å kaste blår i øynene på noen",
        "de": "Jemandem Sand in die Augen streuen (täuschen)",
        "cat": "Redewendung",
        "example": "Ikke la deg lure – han prøver bare å kaste blår i øynene på deg.",
        "note": "'blår' sind grobe Hanf-/Flachsfasern, die früher die Sicht vernebelten.",
        "wrong": [
            "Jemandem tief und verliebt in die Augen schauen",
            "Jemanden bei kaltem Wetter draußen warten lassen",
            "Einer Person ehrlich die Meinung sagen",
        ],
    },
    {
        "no": "I motsetning til broren sin er hun svært tålmodig.",
        "de": "Im Gegensatz zu ihrem Bruder ist sie sehr geduldig.",
        "cat": "Grammatik (Reflexivpronomen sin/hans)",
        "example": "Han liker å planlegge, i motsetning til kollegaen sin.",
        "note": "'sin' bezieht sich auf das Subjekt des Satzes ('hun'). Nach Vorfeld ('I motsetning til...') steht das Verb 'er' an 2. Stelle.",
        "wrong": [
            "Genau wie ihr Bruder verliert sie schnell die Geduld.",
            "Zusammen mit ihrem Bruder wartet sie geduldig.",
            "Wegen ihres Bruders musste sie lange geduldig sein.",
        ],
    },
    {
        "no": "å ombestemme seg",
        "de": "es sich anders überlegen / seine Meinung ändern",
        "cat": "Wortschatz B1/B2",
        "example": "Jeg skulle egentlig bli hjemme, men jeg ombestemte meg.",
        "note": "Reflexives Verb: 'jeg ombestemmer meg, du ombestemmer deg...'",
        "wrong": [
            "über andere Personen bestimmen",
            "einen Termin im Voraus bestätigen",
            "sich an einem neuen Ort orientieren",
        ],
    },
    {
        "no": "Boken ble skrevet av en kjent forfatter.",
        "de": "Das Buch wurde von einem bekannten Autor geschrieben.",
        "cat": "Grammatik (bli-Passiv)",
        "example": "Huset ble bygget på slutten av 1800-tallet.",
        "note": "Im Präteritum/Perfekt nutzt man fast immer das 'bli'-Passiv (ble + Partizip), während das '-s'-Passiv meist nach Modalverben oder für Regeln genutzt wird.",
        "wrong": [
            "Das Buch wird gerade von einem Autor überarbeitet.",
            "Der bekannte Autor möchte bald ein neues Buch schreiben.",
            "Das Buch sollte eigentlich schon letztes Jahr erscheinen.",
        ],
    },
    {
        "no": "Man skal ikke skue hunden på hårene.",
        "de": "Man soll nicht nach dem Äußeren urteilen.",
        "cat": "Redewendung",
        "example": "Bilen ser gammel ut, men motoren er ny – man skal ikke skue hunden på hårene!",
        "note": "Wörtlich: 'Man soll den Hund nicht nach den Haaren beurteilen.'",
        "wrong": [
            "Man sollte fremde Hunde nicht einfach streicheln.",
            "Wer viel arbeitet, macht auch manchmal Fehler.",
            "Kleine Geschenke erhalten die Freundschaft.",
        ],
    },
    {
        "no": "hensiktsmessig",
        "de": "zweckmäßig / sinnvoll / angebracht",
        "cat": "Wortschatz B2",
        "example": "Vi må vurdere om tiltaket faktisk er hensiktsmessig.",
        "note": "Von 'en hensikt' (Absicht / Zweck). Sehr häufig in Beruf, Politik und Sachtexten.",
        "wrong": [
            "rücksichtslos / egoistisch",
            "unbeabsichtigt / zufällig",
            "offensichtlich / unübersehbar",
        ],
    },
    {
        "no": "Jeg tviler på om det lar seg gjøre.",
        "de": "Ich bezweifle, ob sich das machen lässt.",
        "cat": "Ausdruck B2",
        "example": "Det lar seg dessverre ikke gjøre på så kort varsel.",
        "note": "'å la seg gjøre' = machbar sein / sich realisieren lassen. 'på kort varsel' = kurzfristig.",
        "wrong": [
            "Ich bin mir sicher, dass wir das sofort erledigen.",
            "Ich frage mich, wer diese Arbeit gemacht hat.",
            "Es freut mich, dass alles so gut geklappt hat.",
        ],
    },
    {
        "no": "å ha is i magen",
        "de": "einen kühlen Kopf bewahren / die Nerven behalten",
        "cat": "Redewendung",
        "example": "Når markedet svinger, gjelder det å ha is i magen.",
        "note": "Wörtlich: 'Eis im Bauch haben' – ruhig und besonnen bleiben.",
        "wrong": [
            "Vor Aufregung Bauchschmerzen bekommen",
            "Bei kaltem Wetter zu wenig gegessen haben",
            "Jemandem gegenüber eiskalt und abweisend sein",
        ],
    },
    {
        "no": "ettersom / siden",
        "de": "da / weil (kausal)",
        "cat": "Grammatik (Konnektoren)",
        "example": "Ettersom ingen hadde innvendinger, ble forslaget vedtatt.",
        "note": "'ettersom' und 'siden' stehen oft am Satzanfang für bekannte Gründe ('Da...'). 'en innvending' = ein Einwand.",
        "wrong": [
            "nachdem / sobald (temporal)",
            "obwohl / selbst wenn (konzessiv)",
            "damit / um zu (final)",
        ],
    },
    {
        "no": "å legge merke til noe",
        "de": "etwas bemerken / wahrnehmen",
        "cat": "Ausdruck B1",
        "example": "La du merke til hva han sa på slutten av møtet?",
        "note": "Wichtige feste Wendung im Alltag. Präteritum: 'la merke til'.",
        "wrong": [
            "etwas mit einem Etikett beschriften",
            "sich eine Telefonnummer aufschreiben",
            "jemanden heftig kritisieren",
        ],
    },
    {
        "no": "gjensidig",
        "de": "gegenseitig / beiderseitig",
        "cat": "Wortschatz B2",
        "example": "Et godt samarbeid bygger på gjensidig tillit.",
        "note": "'tillit' = Vertrauen. 'Det er gjensidig!' = 'Ganz meinerseits!'",
        "wrong": [
            "einseitig / parteiisch",
            "wiederholt / mehrmalig",
            "gleichgültig / neutral",
        ],
    },
    {
        "no": "Å sitte med skjegget i postkassa",
        "de": "Dumm dastehen / das Nachsehen haben / in der Patsche sitzen",
        "cat": "Redewendung",
        "example": "Hvis vi ikke bestiller nå, blir det utsolgt, og da sitter vi med skjegget i postkassa.",
        "note": "Wörtlich: 'Mit dem Bart im Briefkasten sitzen' – eine der beliebtesten norwegischen Redewendungen!",
        "wrong": [
            "Ungeduldig auf einen wichtigen Brief warten",
            "Sich zu Hause vor der Arbeit verstecken",
            "Eine überraschend gute Nachricht erhalten",
        ],
    },
    {
        "no": "Det er ikke til å komme utenom at...",
        "de": "Es lässt sich nicht leugnen / vermeiden, dass...",
        "cat": "Ausdruck B2",
        "example": "Det er ikke til å komme utenom at kostnadene har økt betydelig.",
        "note": "Elegante B2-Formulierung für Argumentationen und Diskussionen.",
        "wrong": [
            "Es ist völlig ausgeschlossen, dass...",
            "Man kann den Weg leicht umgehen, indem...",
            "Es spielt überhaupt keine Rolle, ob...",
        ],
    },
    {
        "no": "uavhengig av",
        "de": "unabhängig von",
        "cat": "Wortschatz B1/B2",
        "example": "Alle kan delta, uavhengig av alder og erfaring.",
        "note": "Gegenteil: 'avhengig av' (abhängig von).",
        "wrong": [
            "aufgrund von / wegen",
            "im Vergleich zu",
            "in Übereinstimmung mit",
        ],
    },
    {
        "no": "Hun spurte om jeg ikke hadde lyst til å bli med.",
        "de": "Sie fragte, ob ich nicht Lust hätte mitzukommen.",
        "cat": "Grammatik (Wortstellung im Nebensatz)",
        "example": "Han lurte på hvorfor vi ikke hadde ringt tidligere.",
        "note": "Merke: Im Nebensatz steht 'ikke' VOR dem gebeugten Verb ('om jeg ikke hadde...').",
        "wrong": [
            "Sie sagte, dass sie heute leider nicht mitkommen kann.",
            "Sie fragte, wann wir endlich zusammen losgehen.",
            "Sie hoffte, dass ich alleine dorthin gehen würde.",
        ],
    },
]


class MouseSignals(QObject):
    speech_state = pyqtSignal(bool)
    ai_cards_ready = pyqtSignal(list, str)


class NorskSoundEngine:
    """Erzeugt niedliche Mäuse-Piepser (Squeaks) und echte norwegische Sprachausgabe (Bokmål)."""

    NO_VOICES = [
        ("pernille", "🇳🇴 Pernille (Weiblich, Klar & Natürlich)", "nb-NO-PernilleNeural"),
        ("finn", "🇳🇴 Finn (Männlich, Ruhig & Deutlich)", "nb-NO-FinnNeural"),
        ("iselin", "🇳🇴 Iselin (Weiblich, Freundlich)", "nb-NO-IselinNeural"),
    ]

    def __init__(self, signals: MouseSignals):
        self.signals = signals
        self.voice_enabled = True
        self.squeaks_enabled = True
        self.voice_id = "pernille"
        self.tts_voice = "nb-NO-PernilleNeural"

    def set_voice(self, vid: str):
        for v_id, _label, v_name in self.NO_VOICES:
            if v_id == vid:
                self.voice_id = v_id
                self.tts_voice = v_name
                break

    def play_squeak(self, mood="happy"):
        if not self.squeaks_enabled:
            return
        threading.Thread(target=self._squeak_worker, args=(mood,), daemon=True).start()

    def _squeak_worker(self, mood="happy"):
        try:
            sr = 24000
            if mood == "happy":
                notes = [(1350, 1850, 0.045), (1500, 2100, 0.055)]
            elif mood == "wrong":
                notes = [(620, 410, 0.08), (480, 340, 0.09)]
            else:
                notes = [(1200, 1650, 0.05)]

            frames = bytearray()
            for f0, f1, dur in notes:
                n = int(sr * dur)
                for i in range(n):
                    t = i / sr
                    prog = i / max(1, n)
                    freq = f0 + (f1 - f0) * prog
                    env = math.sin(prog * math.pi)
                    val = int(8500 * env * math.sin(2 * math.pi * freq * t))
                    frames.extend(struct.pack("<h", val))
                frames.extend(b"\x00\x00" * int(sr * 0.015))

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                path = tmp.name
            with wave.open(path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sr)
                wf.writeframes(bytes(frames))
            self._play_file(path)
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            pass

    def speak_norwegian(self, text: str):
        if not self.voice_enabled or not text.strip():
            return
        threading.Thread(target=self._tts_worker, args=(text.strip(),), daemon=True).start()

    def _tts_worker(self, text: str):
        self.signals.speech_state.emit(True)
        mp3_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                mp3_path = tmp.name

            # Versuche edge-tts mit Wiederholung bei kurzen Netzwerk-Lags
            success = False
            last_err = None
            for attempt in range(2):
                try:
                    async def _gen():
                        comm = edge_tts.Communicate(text, self.tts_voice, rate="-4%")
                        await comm.save(mp3_path)
                    asyncio.run(_gen())
                    if os.path.exists(mp3_path) and os.path.getsize(mp3_path) > 100:
                        success = True
                        break
                except Exception as ex:
                    last_err = ex
                    time.sleep(0.3)

            if success:
                self._play_file(mp3_path)
            else:
                raise last_err or RuntimeError("edge-tts failed")
        except Exception:
            if shutil.which("espeak-ng"):
                subprocess.run(["espeak-ng", "-v", "nb", text], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        finally:
            self.signals.speech_state.emit(False)
            if mp3_path and os.path.exists(mp3_path):
                try:
                    os.remove(mp3_path)
                except OSError:
                    pass

    def _play_file(self, path: str):
        # Bevorzuge ffplay (spielt MP3s auf Linux/Wayland am zuverlässigsten)
        for cmd in (
            ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", path],
            ["pw-play", path],
            ["paplay", path],
            ["mpv", "--no-video", "--really-quiet", path],
        ):
            if shutil.which(cmd[0]):
                res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if res.returncode == 0:
                    return


class NorskMusWidget(QWidget):
    """Kleine norwegische Vokabel-Maus mit ausklappbarem B1/B2-Quiz- & Karteikarten-Panel."""

    def __init__(self):
        super().__init__()
        self.signals = MouseSignals()
        self.signals.speech_state.connect(self._on_speech_state)
        self.signals.ai_cards_ready.connect(self._on_ai_cards_ready)
        self.sound = NorskSoundEngine(self.signals)

        # Fenstergröße: Kompakt wenn eingeklappt, größer wenn Quiz-Karte offen ist
        self.always_on_top = True
        self.quiz_open = True
        self.quiz_mode = "mc"  # "mc" (Multiple-Choice) oder "flashcard" (Karteikarte)
        self.flashcard_revealed = False
        self.auto_speak_no = True

        # Lern-Daten & Statistiken
        self.deck = list(DEFAULT_B1_B2_DECK)
        self.streak = 0
        self.total_correct = 0
        self.load_vocab_progress()

        self.current_card = None
        self.mc_options = []
        self.selected_mc_idx = None
        self.mc_answered_correctly = None
        self.status_msg = "Klikk på riktig svar! (Klicke auf die richtige Antwort)"
        self.is_speaking = False
        self.is_generating_ai = False

        # Animations-Variablen
        self.tick = 0
        self.breath = 0.0
        self.tail_phase = 0.0
        self.ear_wiggle = 0.0
        self.bounce_y = 0.0
        self.bounce_vy = 0.0
        self.particles = []
        self.is_dragging = False
        self.drag_offset = QPointF(0, 0)

        self.setup_window()
        self.setup_ui_buttons()
        self.setup_tray()
        self.next_question(speak=False)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_anim)
        self.timer.start(20)

    def get_vocab_path(self) -> str:
        return os.path.expanduser("~/.config/deskimoni/norskmus_vocab.json")

    def get_deskimoni_settings_path(self) -> str:
        return os.path.expanduser("~/.config/deskimoni/settings.json")

    def load_vocab_progress(self):
        path = self.get_vocab_path()
        if not os.path.exists(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                self.streak = int(data.get("streak", 0))
                self.total_correct = int(data.get("total_correct", 0))
                custom_cards = data.get("custom_cards", [])
                if isinstance(custom_cards, list):
                    existing_no = {c["no"] for c in self.deck}
                    for card in custom_cards:
                        if isinstance(card, dict) and card.get("no") and card["no"] not in existing_no:
                            self.deck.append(card)
                            existing_no.add(card["no"])
        except Exception:
            pass

    def save_vocab_progress(self):
        path = self.get_vocab_path()
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            default_no = {c["no"] for c in DEFAULT_B1_B2_DECK}
            custom_cards = [c for c in self.deck if c.get("no") not in default_no]
            data = {
                "streak": self.streak,
                "total_correct": self.total_correct,
                "custom_cards": custom_cards,
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def setup_window(self):
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        if self.always_on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.update_window_size()
        self.setWindowTitle("NorskMus – Norwegisch B1/B2")

    def update_window_size(self):
        if self.quiz_open:
            self.resize(440, 560)
        else:
            self.resize(190, 180)

    def setup_ui_buttons(self):
        # 4 Multiple-Choice-Buttons + Steuer-Buttons im Quiz-Panel
        self.opt_buttons = []
        for i in range(4):
            btn = QPushButton("", self)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _checked=False, idx=i: self.on_answer_clicked(idx))
            self.opt_buttons.append(btn)

        # Obere Aktions-Buttons auf der Karte: Vorlesen, Modus (MC/Karteikarte), KI-Generierung, Weiter
        self.btn_speak = QPushButton("🔊", self)
        self.btn_speak.setToolTip("Norwegische Aussprache anhören")
        self.btn_speak.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_speak.clicked.connect(self.speak_current_card)

        self.btn_mode = QPushButton("🃏", self)
        self.btn_mode.setToolTip("Zwischen Multiple-Choice und Karteikarte umschalten")
        self.btn_mode.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_mode.clicked.connect(self.toggle_quiz_mode)

        self.btn_ai = QPushButton("✨ KI+", self)
        self.btn_ai.setToolTip("Neue B1/B2-Vokabeln & Redewendungen per Gemini/Ollama generieren")
        self.btn_ai.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_ai.clicked.connect(self.generate_ai_cards_prompt)

        self.btn_next = QPushButton("Nächste ➔", self)
        self.btn_next.setToolTip("Nächste B1/B2-Vokabel")
        self.btn_next.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_next.clicked.connect(lambda: self.next_question(speak=self.auto_speak_no))

        small_style = """
            QPushButton {
                background-color: rgba(49, 50, 68, 235);
                color: #cdd6f4;
                border: 1.2px solid #89b4fa;
                border-radius: 9px;
                font-size: 11px;
                font-weight: bold;
                padding: 2px 6px;
            }
            QPushButton:hover {
                background-color: rgba(88, 91, 112, 245);
                border-color: #f5c2e7;
            }
        """
        for b in (self.btn_speak, self.btn_mode, self.btn_ai, self.btn_next):
            b.setStyleSheet(small_style)

        self.layout_ui()

    def layout_ui(self):
        if not self.quiz_open:
            for b in self.opt_buttons + [self.btn_speak, self.btn_mode, self.btn_ai, self.btn_next]:
                b.hide()
            return

        self.btn_speak.setGeometry(20, 142, 36, 28)
        self.btn_mode.setGeometry(62, 142, 36, 28)
        self.btn_ai.setGeometry(104, 142, 62, 28)
        self.btn_next.setGeometry(332, 142, 88, 28)
        for b in (self.btn_speak, self.btn_mode, self.btn_ai, self.btn_next):
            b.show()

        if self.quiz_mode == "mc":
            y = 254
            for i, btn in enumerate(self.opt_buttons):
                btn.setGeometry(20, y + i * 42, 400, 36)
                btn.show()
        else:
            # Karteikarten-Modus: Nur 1 großer Button zum Aufdecken / Weiterblättern
            self.opt_buttons[0].setGeometry(20, 376, 400, 40)
            self.opt_buttons[0].show()
            for btn in self.opt_buttons[1:]:
                btn.hide()

        self.update_option_button_styles()

    def update_option_button_styles(self):
        if self.quiz_mode == "flashcard":
            label = "👀 Lösung & Grammatik aufdecken" if not self.flashcard_revealed else "✅ Verstanden – Nächste Karte ➔"
            self.opt_buttons[0].setText(label)
            self.opt_buttons[0].setStyleSheet(
                """
                QPushButton {
                    background-color: rgba(49, 50, 68, 240);
                    color: #f9e2af;
                    border: 1.5px solid #f9e2af;
                    border-radius: 10px;
                    font-size: 12px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: rgba(69, 71, 90, 250);
                }
                """
            )
            return

        letters = ["A", "B", "C", "D"]
        for i, btn in enumerate(self.opt_buttons):
            if i >= len(self.mc_options):
                continue
            txt, is_correct = self.mc_options[i]
            btn.setText(f"{letters[i]})  {txt}")

            if self.selected_mc_idx is None:
                border_col = "#585b70"
                bg_col = "rgba(30, 30, 46, 235)"
                fg_col = "#cdd6f4"
            elif is_correct:
                border_col = "#a6e3a1"
                bg_col = "rgba(35, 78, 52, 245)"
                fg_col = "#a6e3a1"
            elif i == self.selected_mc_idx and not is_correct:
                border_col = "#f38ba8"
                bg_col = "rgba(90, 34, 48, 245)"
                fg_col = "#f38ba8"
            else:
                border_col = "#45475a"
                bg_col = "rgba(24, 24, 37, 200)"
                fg_col = "#7f849c"

            btn.setStyleSheet(
                f"""
                QPushButton {{
                    background-color: {bg_col};
                    color: {fg_col};
                    border: 1.5px solid {border_col};
                    border-radius: 9px;
                    font-size: 11px;
                    text-align: left;
                    padding: 4px 12px;
                }}
                QPushButton:hover {{
                    border-color: #89b4fa;
                }}
                """
            )

    def next_question(self, speak=True):
        if not self.deck:
            return
        prev_no = self.current_card["no"] if self.current_card else None
        candidates = [c for c in self.deck if c["no"] != prev_no] or self.deck
        self.current_card = random.choice(candidates)
        self.selected_mc_idx = None
        self.mc_answered_correctly = None
        self.flashcard_revealed = False

        # 1 richtige + 3 falsche Antworten mischen
        wrongs = list(self.current_card.get("wrong", []))
        while len(wrongs) < 3:
            other = random.choice(self.deck)
            if other["de"] != self.current_card["de"] and other["de"] not in wrongs:
                wrongs.append(other["de"])
        opts = [(self.current_card["de"], True)] + [(w, False) for w in wrongs[:3]]
        random.shuffle(opts)
        self.mc_options = opts
        self.status_msg = f"💡 Eksempel: „{self.current_card.get('example', '')}“"

        self.layout_ui()
        self.trigger_bounce(5.0)
        if speak and self.auto_speak_no:
            self.speak_current_card()
        self.update()

    def on_answer_clicked(self, idx: int):
        if not self.current_card:
            return

        if self.quiz_mode == "flashcard":
            if not self.flashcard_revealed:
                self.flashcard_revealed = True
                self.sound.play_squeak("happy")
                if self.auto_speak_no:
                    self.speak_current_card()
                self.update_option_button_styles()
                self.update()
            else:
                self.streak += 1
                self.total_correct += 1
                self.save_vocab_progress()
                self.next_question(speak=self.auto_speak_no)
            return

        if self.selected_mc_idx is not None:
            # Wenn bereits beantwortet -> Klick springt direkt zur nächsten Vokabel!
            self.next_question(speak=self.auto_speak_no)
            return

        self.selected_mc_idx = idx
        _txt, is_correct = self.mc_options[idx]
        self.mc_answered_correctly = is_correct

        if is_correct:
            self.streak += 1
            self.total_correct += 1
            self.save_vocab_progress()
            self.sound.play_squeak("happy")
            self.trigger_bounce(8.0)
            for _ in range(5):
                self.spawn_particle("cheese")
            self.status_msg = f"🎉 Kjempebra!\n{self.current_card.get('note', '')}"
            if self.auto_speak_no:
                self.speak_current_card()
        else:
            self.streak = 0
            self.save_vocab_progress()
            self.sound.play_squeak("wrong")
            self.status_msg = f"❌ Nesten!\n{self.current_card.get('note', '')}"

        self.update_option_button_styles()
        self.update()

    def speak_current_card(self):
        if self.current_card:
            self.sound.speak_norwegian(self.current_card["no"])

    def toggle_quiz_mode(self):
        self.quiz_mode = "flashcard" if self.quiz_mode == "mc" else "mc"
        self.flashcard_revealed = False
        self.layout_ui()
        self.update()

    def toggle_quiz_panel(self):
        self.quiz_open = not self.quiz_open
        self.update_window_size()
        self.layout_ui()
        self.sound.play_squeak("happy")
        self.trigger_bounce(6.0)
        self.update()

    def _on_speech_state(self, speaking: bool):
        self.is_speaking = speaking
        self.update()

    # --- KI-Generator für neue B1/B2 Norwegisch-Karten (Gemini API / Ollama) ---
    def generate_ai_cards_prompt(self):
        if self.is_generating_ai:
            return
        topic, ok = QInputDialog.getText(
            self,
            "✨ Neue B1/B2 Norwegisch-Karten per KI",
            "Zu welchem Thema soll Lillemus 4 neue B1/B2-Ausdrücke/Sätze erstellen?\n"
            "(z.B. 'Redewendungen', 'Arbeit & Büro', 'Konjunktiv & Nebensätze', 'Natur & Fjorde'):",
            text="Redewendungen & B2-Ausdrücke",
        )
        if not ok or not topic.strip():
            return
        self.is_generating_ai = True
        self.btn_ai.setText("⏳...")
        self.status_msg = f"🤖 Erstelle neue B1/B2-Karten zu '{topic.strip()}'..."
        self.update()
        threading.Thread(target=self._ai_worker, args=(topic.strip(),), daemon=True).start()

    def _ai_worker(self, topic: str):
        gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
        gemini_model = "gemini-3.8-flash"
        ai_provider = "ollama"
        try:
            spath = self.get_deskimoni_settings_path()
            if os.path.exists(spath):
                with open(spath, "r", encoding="utf-8") as f:
                    sdata = json.load(f)
                gemini_key = sdata.get("gemini_api_key", gemini_key).strip()
                gemini_model = sdata.get("gemini_model", gemini_model).strip()
                ai_provider = sdata.get("ai_provider", ai_provider).strip()
        except Exception:
            pass

        prompt = (
            f"Erstelle exakt 4 fortgeschrittene Norwegisch-Lernkarten (Bokmål, Niveau B1/B2) zum Thema '{topic}'. "
            "Antworte AUSSCHLIESSLICH mit einem validen JSON-Array ohne Markdown-Blöcke. "
            "Jedes Objekt im Array MUSS exakt diese Schlüssel haben:\n"
            '{"no": "Norwegischer Satz, Ausdruck oder Redewendung (Bokmål)", '
            '"de": "Korrekte deutsche Übersetzung", '
            '"cat": "Kategorie (z.B. Redewendung, Grammatik B2, Wortschatz B2)", '
            '"example": "Kurzer norwegischer Beispielsatz", '
            '"note": "Kurze deutsche Erklärung zu Grammatik oder Wortwahl (max. 110 Zeichen)", '
            '"wrong": ["Falsche deutsche Option 1", "Falsche deutsche Option 2", "Falsche deutsche Option 3"]}'
        )

        raw = ""
        try:
            if gemini_key and ai_provider == "gemini":
                # Google Gemini API mit header-basierter Authentifizierung für AQ.-Keys
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{gemini_model}:generateContent"
                headers = {
                    "Content-Type": "application/json",
                    "x-goog-api-key": gemini_key,
                }
                resp = requests.post(
                    url,
                    headers=headers,
                    json={"contents": [{"role": "user", "parts": [{"text": prompt}]}]},
                    timeout=35,
                )
                if resp.status_code == 200:
                    raw = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
            if not raw:
                # Fallback auf lokales Ollama
                resp = requests.post(
                    "http://127.0.0.1:11434/api/generate",
                    json={"model": "gemma3:4b", "prompt": prompt, "stream": False},
                    timeout=45,
                )
                if resp.status_code == 200:
                    raw = resp.json().get("response", "")
        except Exception as e:
            self.signals.ai_cards_ready.emit([], f"⚠️ KI-Fehler: {e}")
            return

        try:
            match = re.search(r"\[.*\]", raw, re.DOTALL)
            if not match:
                self.signals.ai_cards_ready.emit([], "⚠️ Konnte KI-Antwort nicht lesen.")
                return
            cards = json.loads(match.group(0))
            valid = []
            for c in cards:
                if isinstance(c, dict) and c.get("no") and c.get("de") and isinstance(c.get("wrong"), list):
                    valid.append(c)
            self.signals.ai_cards_ready.emit(valid, f"✨ {len(valid)} neue B1/B2-Karten hinzugefügt!")
        except Exception:
            self.signals.ai_cards_ready.emit([], "⚠️ Ungültiges JSON von der KI.")

    def _on_ai_cards_ready(self, cards: list, msg: str):
        self.is_generating_ai = False
        self.btn_ai.setText("✨ KI+")
        self.status_msg = msg
        if cards:
            existing = {c["no"] for c in self.deck}
            for c in cards:
                if c["no"] not in existing:
                    self.deck.append(c)
                    existing.add(c["no"])
            self.save_vocab_progress()
            self.current_card = cards[0]
            self.next_question(speak=self.auto_speak_no)
        self.update()

    # --- Tray & Rechtsklick-Menü ---
    def setup_tray(self):
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogHelpButton))
        self.tray.setToolTip("NorskMus – Norwegisch B1/B2 Trainer")
        self.tray.setContextMenu(self.build_menu())
        self.tray.show()

    def build_menu(self):
        menu = QMenu()
        menu.setStyleSheet(
            """
            QMenu { background-color: #1e1e2e; color: #cdd6f4; border: 1px solid #89b4fa; border-radius: 8px; padding: 6px; }
            QMenu::item { padding: 5px 18px; border-radius: 4px; }
            QMenu::item:selected { background-color: #45475a; }
            """
        )
        act_toggle = QAction("📖 Quiz-Karte ein-/ausklappen (Klick auf Maus)", self)
        act_toggle.triggered.connect(self.toggle_quiz_panel)
        menu.addAction(act_toggle)

        act_next = QAction("⏭️ Nächste B1/B2-Vokabel", self)
        act_next.triggered.connect(lambda: self.next_question(speak=self.auto_speak_no))
        menu.addAction(act_next)

        act_ai = QAction("✨ 4 neue B1/B2-Karten per KI generieren...", self)
        act_ai.triggered.connect(self.generate_ai_cards_prompt)
        menu.addAction(act_ai)

        menu.addSeparator()
        voice_menu = menu.addMenu("🗣️ Norwegische Stimme (Bokmål)")
        vg = QActionGroup(self)
        for vid, label, _vname in NorskSoundEngine.NO_VOICES:
            a = QAction(label, self, checkable=True)
            a.setChecked(self.sound.voice_id == vid)
            a.triggered.connect(lambda _c=False, v=vid: self.sound.set_voice(v))
            vg.addAction(a)
            voice_menu.addAction(a)

        act_auto_tts = QAction("🔊 Neue Sätze automatisch vorlesen", self, checkable=True)
        act_auto_tts.setChecked(self.auto_speak_no)
        act_auto_tts.triggered.connect(self._toggle_auto_tts)
        menu.addAction(act_auto_tts)

        menu.addSeparator()
        act_quit = QAction("🚪 NorskMus schließen (Ha det bra!)", self)
        act_quit.triggered.connect(QApplication.instance().quit)
        menu.addAction(act_quit)
        return menu

    def _toggle_auto_tts(self):
        self.auto_speak_no = not self.auto_speak_no

    def trigger_bounce(self, strength=6.0):
        self.bounce_vy = -strength

    def spawn_particle(self, ptype="cheese"):
        self.particles.append(
            {
                "type": ptype,
                "x": random.uniform(40, 140),
                "y": random.uniform(30, 85),
                "vx": random.uniform(-0.9, 0.9),
                "vy": random.uniform(-2.0, -0.8),
                "life": 1.0,
            }
        )

    def update_anim(self):
        self.tick += 1
        self.breath += 0.08
        self.tail_phase += 0.14
        self.ear_wiggle = math.sin(self.tick * 0.09) * 3.0

        self.bounce_y += self.bounce_vy
        self.bounce_vy += 0.65
        if self.bounce_y > 0:
            self.bounce_y = 0
            self.bounce_vy *= -0.35
            if abs(self.bounce_vy) < 0.4:
                self.bounce_vy = 0.0

        alive = []
        for p in self.particles:
            p["x"] += p["vx"]
            p["y"] += p["vy"]
            p["life"] -= 0.03
            if p["life"] > 0:
                alive.append(p)
        self.particles = alive
        self.update()

    # --- Maus-Events ---
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position()
            # Klick auf die kleine Maus oben (y < 140) -> Ziehen starten
            self.is_dragging = True
            self.drag_offset = event.globalPosition() - QPointF(self.pos())
            win = self.windowHandle()
            if win is not None:
                win.startSystemMove()
        elif event.button() == Qt.MouseButton.RightButton:
            self.build_menu().exec(event.globalPosition().toPoint())

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # Doppelklick auf die Maus klappt die Vokabel-Karte ein oder aus!
            self.toggle_quiz_panel()

    def mouseMoveEvent(self, event):
        if self.is_dragging and (event.buttons() & Qt.MouseButton.LeftButton):
            new_pos = event.globalPosition() - self.drag_offset
            self.move(int(new_pos.x()), int(new_pos.y()))

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging = False

    # --- Zeichnen der süßen Norwegisch-Maus & des B1/B2-Vokabel-Panels ---
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        # 1. Kleine Fjord-Maus oben zeichnen
        mx = 110 if self.quiz_open else 25
        my = 10 + self.bounce_y + math.sin(self.breath) * 1.8
        self.draw_norsk_mouse(painter, mx, my)

        # Streak- & Level-Badge neben der Maus
        if self.quiz_open:
            badge_rect = QRectF(280, 20, 144, 56)
            painter.setPen(QPen(QColor("#89b4fa"), 1.5))
            painter.setBrush(QColor(24, 25, 38, 230))
            painter.drawRoundedRect(badge_rect, 11, 11)

            painter.setPen(QColor("#f9e2af"))
            painter.setFont(QFont("SansSerif", 9, QFont.Weight.Bold))
            painter.drawText(QRectF(284, 24, 136, 18), Qt.AlignmentFlag.AlignCenter, "🇳🇴 Norsk B1/B2")

            painter.setPen(QColor("#a6e3a1"))
            painter.setFont(QFont("SansSerif", 8, QFont.Weight.Medium))
            painter.drawText(
                QRectF(284, 42, 136, 28),
                Qt.AlignmentFlag.AlignCenter,
                f"🔥 Streak: {self.streak}  |  ✓ {self.total_correct}\n({len(self.deck)} Karten)",
            )
        else:
            # Kompakt-Badge wenn eingeklappt
            mini_rect = QRectF(14, 142, 162, 26)
            painter.setPen(QPen(QColor("#89b4fa"), 1.2))
            painter.setBrush(QColor(24, 25, 38, 225))
            painter.drawRoundedRect(mini_rect, 8, 8)
            painter.setPen(QColor("#cdd6f4"))
            painter.setFont(QFont("SansSerif", 8, QFont.Weight.Bold))
            painter.drawText(mini_rect, Qt.AlignmentFlag.AlignCenter, f"🇳🇴 Doppelklick = Quiz (🔥{self.streak})")
            return

        # 2. Ausgeklapptes B1/B2 Vokabel-Panel (großzügig dimensioniert)
        panel_rect = QRectF(10, 130, 420, 420)
        painter.setPen(QPen(QColor("#89b4fa"), 2.0))
        painter.setBrush(QColor(24, 25, 38, 245))
        painter.drawRoundedRect(panel_rect, 16, 16)

        if not self.current_card:
            return

        # Kategorie-Label mittig in der oberen Button-Leiste
        cat_txt = self.current_card.get("cat", "B1/B2")
        painter.setPen(QColor("#f5c2e7"))
        painter.setFont(QFont("SansSerif", 8, QFont.Weight.Bold))
        painter.drawText(
            QRectF(170, 142, 158, 28),
            Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
            cat_txt,
        )

        # Norwegischer Satz / Ausdruck (Hauptfeld)
        q_rect = QRectF(20, 178, 400, 68)
        painter.setPen(QPen(QColor("#45475a"), 1.2))
        painter.setBrush(QColor(30, 30, 46, 250))
        painter.drawRoundedRect(q_rect, 11, 11)

        painter.setPen(QColor("#ffffff"))
        painter.setFont(QFont("SansSerif", 11, QFont.Weight.Bold))
        painter.drawText(
            QRectF(26, 181, 388, 62),
            Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
            self.current_card["no"],
        )

        if self.quiz_mode == "flashcard":
            # Karteikarten-Ansicht
            fc_rect = QRectF(20, 254, 400, 114)
            painter.setPen(QPen(QColor("#585b70"), 1.2))
            painter.setBrush(QColor(36, 39, 58, 235))
            painter.drawRoundedRect(fc_rect, 10, 10)

            if self.flashcard_revealed:
                painter.setPen(QColor("#a6e3a1"))
                painter.setFont(QFont("SansSerif", 11, QFont.Weight.Bold))
                painter.drawText(
                    QRectF(28, 260, 384, 42),
                    Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                    self.current_card["de"],
                )
                painter.setPen(QColor("#f9e2af"))
                painter.setFont(QFont("SansSerif", 9))
                painter.drawText(
                    QRectF(28, 304, 384, 56),
                    Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                    self.current_card.get("note", ""),
                )
            else:
                painter.setPen(QColor("#9399b2"))
                painter.setFont(QFont("SansSerif", 10, QFont.Weight.Medium))
                painter.drawText(
                    QRectF(28, 268, 384, 84),
                    Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                    f"Beispiel:\n„{self.current_card.get('example', '')}“",
                )

        # 3. Eigene Erklärungs- & Feedback-Box unten (abgehoben & ohne Überlappung!)
        expl_box = QRectF(20, 428, 400, 112)
        if self.selected_mc_idx is not None:
            border_col = QColor("#a6e3a1") if self.mc_answered_correctly else QColor("#f38ba8")
            bg_col = QColor(35, 78, 52, 140) if self.mc_answered_correctly else QColor(90, 34, 48, 140)
            text_col = QColor("#ffffff")
        else:
            border_col = QColor("#45475a")
            bg_col = QColor(30, 30, 46, 235)
            text_col = QColor("#bac2de")

        painter.setPen(QPen(border_col, 1.2))
        painter.setBrush(bg_col)
        painter.drawRoundedRect(expl_box, 10, 10)

        painter.setPen(text_col)
        painter.setFont(QFont("SansSerif", 8, QFont.Weight.Medium))
        painter.drawText(
            QRectF(30, 432, 380, 104),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextWordWrap,
            self.status_msg,
        )

    def draw_norsk_mouse(self, painter: QPainter, ox: float, oy: float):
        painter.save()
        painter.translate(ox, oy)

        # 0. Schatten
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 80))
        painter.drawEllipse(QRectF(25, 114, 90, 14))

        # 1. Wackelndes Mäuse-Schwänzchen rechts
        tail_path = QPainterPath()
        tail_path.moveTo(102, 98)
        wag = math.sin(self.tail_phase) * 9.0
        tail_path.cubicTo(132, 95 + wag, 138, 65 - wag, 124, 52 + wag * 0.6)
        painter.setPen(QPen(QColor("#f2b5c4"), 4.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(tail_path)

        # 2. Große runde Mäuse-Ohren (links & rechts)
        for ex, sign in ((32, -1), (108, 1)):
            painter.save()
            painter.translate(ex, 34)
            painter.rotate(sign * self.ear_wiggle)
            painter.setPen(QPen(QColor("#585b70"), 2.0))
            painter.setBrush(QColor("#9399b2"))
            painter.drawEllipse(QPointF(0, 0), 22, 22)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#f5c2e7"))
            painter.drawEllipse(QPointF(0, 1), 13, 13)
            painter.restore()

        # 3. Molliger Mäuse-Körper (3D-Gradient in Samtgrau/Blaugrau)
        body_grad = QLinearGradient(70, 26, 70, 118)
        body_grad.setColorAt(0.0, QColor("#bac2de"))
        body_grad.setColorAt(1.0, QColor("#7f849c"))
        painter.setPen(QPen(QColor("#45475a"), 2.0))
        painter.setBrush(QBrush(body_grad))
        painter.drawRoundedRect(QRectF(28, 30, 84, 86), 38, 38)

        # Heller Bauchfleck
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#cdd6f4"))
        painter.drawEllipse(QRectF(44, 66, 52, 42))

        # 4. Kleiner norwegischer Schal (Rot-Weiß-Blau 🇳🇴)
        scarf_rect = QRectF(34, 74, 72, 13)
        painter.setBrush(QColor("#ba0c2f"))  # Norwegisches Rot
        painter.drawRoundedRect(scarf_rect, 6, 6)
        painter.setBrush(QColor("#ffffff"))
        painter.drawRect(QRectF(36, 78, 68, 5))
        painter.setBrush(QColor("#00205b"))  # Norwegisches Dunkelblau
        painter.drawRect(QRectF(36, 79.5, 68, 2.2))
        # Schal-Zipfel
        painter.setBrush(QColor("#ba0c2f"))
        painter.drawRoundedRect(QRectF(80, 82, 13, 20), 4, 4)

        # 5. Glänzende Knopfaugen (folgen leicht dem Mauszeiger)
        global_cur = QCursor.pos()
        local_cur = self.mapFromGlobal(global_cur)
        dx = max(-3.0, min(3.0, (local_cur.x() - (ox + 70)) / 90.0))
        dy = max(-2.5, min(2.5, (local_cur.y() - (oy + 55)) / 90.0))

        for cx in (53, 87):
            painter.setBrush(QColor("#11111b"))
            painter.drawEllipse(QPointF(cx + dx, 54 + dy), 6.5, 7.2)
            painter.setBrush(QColor("#ffffff"))
            painter.drawEllipse(QPointF(cx + dx - 2.0, 51.5 + dy), 2.3, 2.3)

        # Rosa Stupsnase & Schnurrhaare
        painter.setBrush(QColor("#f38ba8"))
        painter.drawEllipse(QPointF(70 + dx * 0.6, 63 + dy * 0.5), 5.0, 3.8)

        painter.setPen(QPen(QColor("#45475a"), 1.3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        for wy in (-3, 2):
            painter.drawLine(QPointF(20, 62 + wy), QPointF(46, 63 + wy * 0.5))
            painter.drawLine(QPointF(94, 63 + wy * 0.5), QPointF(120, 62 + wy))

        # Kleiner Mund (offen beim Vorlesen!)
        if self.is_speaking and (self.tick // 3) % 2 == 0:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#eb6f92"))
            painter.drawEllipse(QPointF(70, 70), 4.5, 3.5)
        else:
            mouth = QPainterPath()
            mouth.moveTo(65, 69)
            mouth.quadTo(70, 73, 75, 69)
            painter.setPen(QPen(QColor("#45475a"), 1.6))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(mouth)

        # Kleine rosa Pfötchen unten
        painter.setPen(QPen(QColor("#585b70"), 1.2))
        painter.setBrush(QColor("#f5c2e7"))
        painter.drawEllipse(QRectF(38, 109, 20, 10))
        painter.drawEllipse(QRectF(82, 109, 20, 10))

        # Partikel (Käseecken bei richtiger Antwort)
        for p in self.particles:
            alpha = int(max(0.0, min(1.0, p["life"])) * 255)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(249, 226, 175, alpha))
            painter.drawEllipse(QPointF(p["x"], p["y"]), 5, 5)

        painter.restore()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("NorskMus")
    app.setQuitOnLastWindowClosed(False)

    mouse = NorskMusWidget()
    screen = app.primaryScreen()
    if screen is not None:
        geom = screen.availableGeometry()
        # Startet standardmäßig links neben Deskimoni unten rechts
        mouse.move(geom.right() - mouse.width() - 330, geom.bottom() - mouse.height() - 40)

    mouse.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
