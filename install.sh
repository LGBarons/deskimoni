#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"
PROJECT_DIR="$(pwd)"

echo "🤖 Installiere Deskimoni auf $(hostname)..."

# 1. Virtuelle Python-Umgebung mit Zugriff auf System-Pakete (PyQt6) erstellen
echo "📦 Richte virtuelle Python-Umgebung (.venv) ein..."
python3 -m venv --system-site-packages .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

# 2. Skripte ausführbar machen
chmod +x "$PROJECT_DIR/deskimoni.py" "$PROJECT_DIR/run.sh" "$PROJECT_DIR/norskmus.py" "$PROJECT_DIR/run_mouse.sh"

# 3. Desktop-Datei mit dem korrekten Pfad auf diesem Laptop/PC erzeugen
cat > "$PROJECT_DIR/deskimoni.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Deskimoni
GenericName=Schreibtisch-Roboter (Desk Pet)
Comment=Interaktiver & sprechender Deskimon Desktop-Begleiter für KDE Plasma
Exec=$PROJECT_DIR/run.sh
Icon=$PROJECT_DIR/deskimoni.svg
Terminal=false
Categories=Utility;Amusement;
Keywords=deskimon;robot;pet;ollama;buddy;
StartupNotify=false
EOF

# 4. Ins Startmenü und in den KDE-Autostart eintragen
mkdir -p "$HOME/.local/share/applications" "$HOME/.config/autostart"
cp "$PROJECT_DIR/deskimoni.desktop" "$HOME/.local/share/applications/deskimoni.desktop"
cp "$PROJECT_DIR/deskimoni.desktop" "$HOME/.config/autostart/deskimoni.desktop"

# 5. Prüfen, ob Ollama installiert ist
echo ""
if command -v ollama >/dev/null 2>&1; then
    echo "🟢 Ollama wurde gefunden! Prüfe Modell gemma3:4b..."
    if ! ollama list 2>/dev/null | grep -q "gemma3:4b"; then
        echo "💡 Tipp: Lade das empfohlene Sprachmodell mit: ollama pull gemma3:4b"
    fi
else
    echo "🟠 Hinweis: Ollama ist auf diesem Gerät (z. B. Laptop) nicht installiert."
    echo "   ☁️ Tipp: Du kannst in Deskimoni per Rechtsklick -> 'Sprache & KI' einfach deinen Google Gemini API-Key eingeben!"
    echo "   Damit läuft die komplette KI & Bildschirmanalyse blitzschnell über die Cloud ohne lokale Hardware-Last."
fi

echo ""
echo "✅ Installation abgeschlossen! Deskimoni ist im Startmenü und im Autostart eingetragen."
echo "🚀 Starte Deskimoni mit: ./run.sh"
