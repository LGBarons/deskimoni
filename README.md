# 🤖 Deskimoni & NorskMus

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![GUI: PyQt6](https://img.shields.io/badge/GUI-PyQt6-green.svg)](https://riverbankcomputing.com/software/pyqt/)

[🇩🇪 Zur deutschen Version wechseln (README.de.md)](README.de.md)

**Deskimoni** is an interactive, animated desktop pet and AI companion built in Python with PyQt6. Designed to bring life to your screen, it combines charming vector animations with local or cloud-based AI, neural text-to-speech, system monitoring, productivity tools, and entertainment.

Also included is **NorskMus**, a dedicated Norwegian language learning companion (B1/B2 level) with interactive flashcards, grammar hints, and AI-powered feedback!

---

## ✨ Features

### 🐾 Living Desktop Companion
* **Expressive Animations**: Blinking, floating, wandering across screens, sleeping, curious glances, and reacting to mouse movement and clicks.
* **Music Groove & Headbanging 🎸**: Automatically grooves or headbangs to music and online radio with animated particle effects (notes & stars).
* **Multiple Skins**:
  * 👹 *Classic Oni*
  * 🐱 *Cyber Cat*
  * 👾 *Retro Pixel*
  * 👻 *Cozy Ghost*
  * 🚀 *Space Bot*
* **Physics & Window Dragging**: Freely move it anywhere on your desktop, minimize it, or pin it to screen edges.

### 🧠 Dual AI Brain & Persistent Memory
* **Local Ollama & Google Gemini Failover**: Chat and ask questions anytime. Uses your local Ollama models (e.g. `llama3`, `gemma3`) and can seamlessly fall back to Google Gemini.
* **Persistent Memory**: Name your pet and give it your own name. It remembers facts, user preferences, and notes across sessions (`~/.config/deskimoni/memory.json`).
* **Neural TTS (Speech)**: Realistic spoken responses via `edge-tts`.
* **Voice Input**: Talk directly to your pet using your microphone.

### ⏰ Productivity & Health
* **Pomodoro Timer**: Customizable work and break cycles with subtle audio chimes.
* **Alarm Clock & Countdown Timer**: Set timers in minutes or specify an exact target time (`HH:MM`).
* **Wellness Reminders**: Gentle notifications to stay hydrated, stretch, and take posture breaks.
* **Friendly Check-Ins & Jokes**: Asks how your day is going, shares random thoughts, or tells a joke.

### 📻 News, Internet Radio & Podcasts
* **RSS News Reader**: Reads aloud the latest headlines (Tagesschau, Heise, BBC, or custom feeds).
* **Built-in Internet Radio**: Stream web radio stations (Lofi Chill, Rock Antenne, 80s Synthwave, News, etc.) while you work.

---

## 🇳🇴 NorskMus (Norwegian Language Trainer)

Included as **`norskmus.py`**:
* An animated desktop mouse wearing a Norwegian scarf.
* B1/B2 Norwegian vocabulary quizzes, sentence structure drills, and grammar tips.
* On-demand AI explanations for tricky answers.
* Native Norwegian pronunciation using `no-NO-PernilleNeural`.

---

## 🚀 Installation & Getting Started

### 🐧 Linux (Ubuntu, Debian, Fedora, Arch, Nobara)

1. **Install system dependencies**:
   ```bash
   # Ubuntu / Debian
   sudo apt install python3-pip python3-venv mpv ffmpeg

   # Fedora / Nobara
   sudo dnf install python3-pip mpv ffmpeg

   # Arch Linux
   sudo pacman -S python-pip mpv ffmpeg
   ```

2. **Clone and setup**:
   ```bash
   git clone https://github.com/LGBarons/deskimoni.git
   cd deskimoni
   ./install.sh
   ```

3. **Run**:
   * Deskimoni: `./run.sh`
   * NorskMus: `./run_mouse.sh`

---

### 🪟 Windows

1. **Clone repository**:
   ```powershell
   git clone https://github.com/LGBarons/deskimoni.git
   cd deskimoni
   ```

2. **Create virtual environment and install requirements**:
   ```powershell
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```
   *(Optional for streaming audio/radio: install [mpv](https://mpv.io) via `winget install mpv.mpv`)*

3. **Run**:
   ```powershell
   python deskimoni.py
   # Or for NorskMus:
   python norskmus.py
   ```

---

### 🍏 macOS

1. **Install tools & clone**:
   ```bash
   brew install mpv ffmpeg
   git clone https://github.com/LGBarons/deskimoni.git
   cd deskimoni
   ```

2. **Setup and run**:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   python3 deskimoni.py
   ```

---

## 🔒 Configuration & Privacy

All user configurations, custom names, and optional API keys are stored **strictly on your local machine** under `~/.config/deskimoni/`:
* `config.json`: Volume, active feeds, radio stations, window position, and optional Gemini API key.
* `memory.json`: Pet identity, user name, and remembered facts.

**No private tokens, personal memory, or telemetry data are ever tracked or sent to Git.**

---

## 📋 Requirements
* `Python >= 3.10`
* `PyQt6 >= 6.5.0`
* `psutil >= 5.9.0`
* `requests >= 2.28.0`
* `edge-tts >= 6.1.0`
* `SpeechRecognition >= 3.10.0`

---

## 📄 License
This project is licensed under the [MIT License](LICENSE).
