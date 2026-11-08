#!/usr/bin/env python3
"""
Deskimoni v2 - Cross-Platform Desktop Companion
Interaktiver Desktop-Begleiter für Linux (Nobara/Fedora/KDE Plasma Wayland & X11),
Windows und macOS.
"""

import sys
from deskimoni_core import main
from deskimoni_core.ui.widget import DeskimonWidget

__all__ = ["main", "DeskimonWidget"]

if __name__ == "__main__":
    main()
