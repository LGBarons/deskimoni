#!/usr/bin/env python3
"""
Deskimoni v2 - Worker Signals
"""

from deskimoni_core.qt import QObject, Signal


class WorkerSignals(QObject):
    """Qt-Signale für threadsichere UI-Aktualisierungen aus Hintergrund-Workern."""
    reply_ready = Signal(str, str)             # (reply_text, emotion)
    greeting_ready = Signal(str, str, str)     # (spoken_greeting, bubble_extra, emotion)
    speech_state = Signal(bool)                # (is_speaking)
    mic_state = Signal(str)                    # ("idle" | "recording" | "recognizing")
    mic_result = Signal(str)                   # (recognized_text)
