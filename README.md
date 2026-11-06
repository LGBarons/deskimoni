# 🤖 Deskimoni & NorskMus

**Deskimoni** ist ein intelligenter, lebendiger Desktop-Begleiter (Desktop Pet & AI Assistant) für Linux, geschrieben in Python und PyQt6. Er vereint charmante Vektor-Animationen mit lokaler/cloudbasierter KI, Sprachausgabe, Systemüberwachung, Produktivitäts-Tools und Unterhaltung.

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

---

## 🇳🇴 NorskMus (Norwegisch-Trainer)

Im Projekt enthalten ist **`norskmus.py`**:
* Interaktive Maus mit norwegischem Schal als Desktop-Pet.
* B1/B2 Multiple-Choice-Fragen, Vokabelkarten und Grammatikhilfen (z. B. Satzstellung, Präpositionen).
* KI-Erklärungen auf Knopfdruck bei falschen oder schwierigen Antworten.
* Sprachausgabe mit nativer norwegischer Aussprache (`no-NO-PernilleNeural`).

---

## 🚀 Installation & Schnellstart

### 1. System-Voraussetzungen (Linux)
Für Audio-Wiedergabe, TTS und System-Tools werden folgende Systempakete empfohlen (Debian/Ubuntu/Fedora/Arch):

```bash
# Ubuntu / Debian
sudo apt install python3-pip python3-venv mpv ffmpeg

# Fedora
sudo dnf install python3-pip mpv ffmpeg

# Arch Linux
sudo pacman -S python-pip mpv ffmpeg
```

### 2. Repository klonen & einrichten
```bash
git clone https://github.com/<DEIN-BENUTZERNAME>/deskimoni.git
cd deskimoni
./install.sh
```

### 3. Starten

**Deskimoni starten:**
```bash
./run.sh
```

**NorskMus starten:**
```bash
./run_mouse.sh
```

---

## ⚙️ Konfiguration

Alle Einstellungen werden automatisch im Benutzerverzeichnis unter `~/.config/deskimoni/` abgelegt:
* `config.json`: Fenstereinstellungen, Lautstärke, ausgewählte Feeds & Radiosender, Timer-Werte.
* `memory.json`: Name des Pets, Benutzername und gespeicherte Fakten.

---

## 📋 Anforderungen (`requirements.txt`)
* `PyQt6>=6.5.0`
* `psutil>=5.9.0`
* `requests>=2.28.0`
* `edge-tts>=6.1.0`
* `SpeechRecognition>=3.10.0`

---

## 📄 Lizenz
Dieses Projekt steht unter der [MIT-Lizenz](LICENSE).
