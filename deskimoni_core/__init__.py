#!/usr/bin/env python3
"""
Deskimoni v2 - Core Package
Modular, cross-platform desktop companion for Linux (Nobara / Fedora KDE Plasma Wayland & X11),
Windows 10/11 and macOS.
"""

import sys
from deskimoni_core.qt import QApplication
from deskimoni_core.ui.widget import DeskimonWidget

__version__ = "2.1.0"


def main():
    """Haupteinstiegspunkt für Deskimoni v2."""
    app = QApplication(sys.argv)
    app.setApplicationName("Deskimoni")
    app.setQuitOnLastWindowClosed(False)

    pet = DeskimonWidget()
    app.aboutToQuit.connect(pet.cleanup_on_quit)

    screen = app.primaryScreen()
    if screen is not None:
        geom = screen.availableGeometry()
        if pet.saved_pos_x is not None and pet.saved_pos_y is not None:
            px = max(geom.left(), min(pet.saved_pos_x, geom.right() - pet.width()))
            py = max(geom.top(), min(pet.saved_pos_y, geom.bottom() - pet.height()))
            pet.move(px, py)
        else:
            pet.move(geom.right() - pet.width() - 40, geom.bottom() - pet.height() - 40)

    pet.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
