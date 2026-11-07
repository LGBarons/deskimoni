# 🤖 Deskimoni & NorskMus

[🇬🇧 Switch to English README](README.md)

**Deskimoni** ist ein intelligenter, lebendiger Desktop-Begleiter (Desktop Pet & AI Assistant) für Linux, Windows und macOS, geschrieben in Python und PyQt6. Er vereint charmante Vektor-Animationen mit lokaler/cloudbasierter KI, Sprachausgabe, Systemüberwachung, Produktivitäts-Tools und Unterhaltung.

Mit **NorskMus** ist zudem ein spezialisierter Lernbegleiter für die norwegische Sprache (B1/B2 Niveau) mit Vokabel-Trainingssystem und Grammatik-Tipps enthalten!

---

## ✨ Hauptfunktionen

### 🐾 Lebendiger Desktop-Begleiter
* **Reichhaltige Animationen**: Blinzeln, Schweben, Wandern über den Bildschirm, Schlafen, Neugierig-Sein und Reagieren auf Mauszeiger und Klicks.
* **Musik & Headbangen 🎸**: Schlägt im Rhythmus mit dem Kopf (Headbanging) oder groovt bei Musik und Webradio mit Partikeleffekten.
* **Verschiedene Skins**:
  * 👹 *Classic Oni*
  * 🐱 *Cyber Cat*
  * 👾 *Retro Pixel*
  * 👻 *Cozy Ghost*
  * 🚀 *Space Bot*
* **Window Physics & Dragging**: Kann frei auf dem Desktop bewegt, minimiert oder an den Rand gepinnt werden.
* **Multimonitor-Heimweg & eigene Musik 🏠**: Wird das Pet auf einen Zweitbildschirm gezogen, watschelt es gemütlich zurück zum Hauptbildschirm und spielt dabei Musik oder pfeift. Eigene Lieblingssongs (`.mp3`, `.wav`, `.ogg`, `.flac`) können einfach in `~/.config/deskimoni/sounds/gohome/` abgelegt werden!

### 🧠 KI-Gehirn & Gedächtnis
* **Ollama (Lokal)** & **Google Gemini (Cloud-Fallback)**: Reagiert direkt auf Fragen, Aufgaben oder Unterhaltungen.
* **Persönliches Gedächtnis**: Kann mit eigenem Namen und deinem Namen personalisiert werden; merkt sich Vorlieben, Notizen und Fakten dauerhaft (`~/.config/deskimoni/memory.json`).
* **Sprachsynthese (TTS)**: Natürlich klingende deutsche Sprachausgabe via `edge-tts` (Katja / Conrad Neural).
* **Spracheingabe**: Sprich direkt per Mikrofon mit deinem Pet.

### ⏰ Produktivität & Gesundheit
* **Pomodoro-Timer**: Einstellbare Arbeits- und Pausenzeiten mit diskreten Audio-Signalen.
* **Wecker & Countdown**: Flexible Timer-Einstellung (z. B. relative Minuten oder feste Uhrzeit `HH:MM`).
* **Erinnerungen**: Sanfte Reminder zum Trinken, Aufstehen und Durchatmen.
* **Smalltalk & Witze**: Erzählt auf Wunsch oder zufällig Witze, Denkanstöße und fragt nach deinem Befinden.

### 📻 News, Radio & Podcasts
* **RSS-Newsfeed**: Liest aktuelle Schlagzeilen (Tagesschau, Heise, BBC oder eigene Feeds) mit Sprachausgabe vor.
* **Internetradio & Musik**: Integrierter Stream-Player (Lofi Chill, Rock Antenne, 80s Synthwave, NDR Info, u. v. m.).

### 🌐 Dreisprachige Menüs
* **Mehrsprachiges Kontextmenü**: Schneller Wechsel zwischen **Deutsch**, **Englisch** und **Norwegisch (Bokmål)** direkt über Rechtsklick oder per Chatbefehl.
* **Persistente Einstellungen**: Menüsprache, Skin, Position und Skalierung bleiben nach dem Neustart dauerhaft erhalten.

---

## 🇳🇴 NorskMus (Norwegisch-Trainer)

Im Projekt enthalten ist **`norskmus.py`**:
* Interaktive Maus mit norwegischem Schal als Desktop-Pet.
* B1/B2 Multiple-Choice-Fragen, Vokabelkarten und Grammatikhilfen (z. B. Satzstellung, Präpositionen).
* KI-Erklärungen auf Knopfdruck bei falschen oder schwierigen Antworten.
* Sprachausgabe mit nativer norwegischer Aussprache (`no-NO-PernilleNeural`).

---

## 🚀 Installation & Schnellstart

### 🐧 Linux (Nobara / Fedora / Ubuntu / Arch)
```bash
# Systempakete (Ubuntu/Debian)
sudo apt install python3-pip python3-venv mpv ffmpeg

# Fedora / Nobara
sudo dnf install python3-pip mpv ffmpeg

# Setup & Start
git clone https://github.com/LGBarons/deskimoni.git
cd deskimoni
./install.sh
./run.sh
```

### 🪟 Windows
```powershell
git clone https://github.com/LGBarons/deskimoni.git
cd deskimoni

python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# Deskimoni starten
python deskimoni.py

# NorskMus starten
python norskmus.py
```
*(Tipp für Radio/Audio auf Windows: `winget install mpv.mpv`)*

### 🍏 macOS
```bash
brew install mpv ffmpeg
git clone https://github.com/LGBarons/deskimoni.git
cd deskimoni

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 deskimoni.py
```

---

## ⚙️ Konfiguration & Privatsphäre

Alle individuellen Einstellungen und API-Keys werden **ausschließlich lokal** in deinem Benutzerverzeichnis unter `~/.config/deskimoni/` gespeichert und **niemals** ins Git-Repository übertragen:
* `config.json`: Fenstereinstellungen, Lautstärke, ausgewählte Feeds & Radiosender, Timer-Werte, ggf. Gemini API-Key.
* `memory.json`: Name des Begleiters, Benutzername und persönliche Notizen/Fakten.

---

## 📄 Lizenz
Dieses Projekt steht unter der [MIT-Lizenz](LICENSE).
