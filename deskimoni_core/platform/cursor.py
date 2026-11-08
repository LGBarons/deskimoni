#!/usr/bin/env python3
"""
Deskimoni v2 - Cross-Platform Cursor Tracker & Shaker
- Windows: Win32 native tracking & mouse_event shaking.
- Linux Wayland: /dev/input/mice Kernel-Stream & /dev/uinput KDE Plasma shakecursor.
- macOS: CoreGraphics / QCursor oscillation (Shake-to-Find).
"""

import os
import sys
import time
import math
import struct
import select
import threading
try:
    import fcntl
except ImportError:
    fcntl = None

from deskimoni_core.qt import QPoint, QCursor, QApplication


class GlobalCursorTracker:
    """Verfolgt die Mausposition in Echtzeit über alle Monitore.
    
    Auf Windows & macOS: Fragt die native OS-Position ab.
    Auf Linux Wayland: Liest den Kernel-Maus-Aggregator (/dev/input/mice) und
    kalibriert sich automatisch, sobald die Maus über Deskimonis Fenster fährt.
    """
    def __init__(self):
        self.is_linux_wayland = sys.platform.startswith("linux") and bool(os.environ.get("WAYLAND_DISPLAY"))
        self._fd = None
        self._running = False
        self._thread = None
        self._cur_x = 0.0
        self._cur_y = 0.0
        self._has_calibrated = False
        self._last_move_time = time.time()
        self._lock = threading.Lock()

        if self.is_linux_wayland:
            self._start_linux_stream()

    def _start_linux_stream(self):
        if not os.path.exists("/dev/input/mice"):
            return
        try:
            self._fd = os.open("/dev/input/mice", os.O_RDONLY | os.O_NONBLOCK)
            self._running = True
            self._thread = threading.Thread(target=self._read_loop, daemon=True)
            self._thread.start()
        except Exception:
            self._fd = None

    def calibrate(self, qpos: QPoint):
        """Wird aufgerufen, wenn die Maus das Fenster berührt (exakte Referenzposition)."""
        with self._lock:
            self._cur_x = float(qpos.x())
            self._cur_y = float(qpos.y())
            self._has_calibrated = True
            self._last_move_time = time.time()

    def _read_loop(self):
        while self._running and self._fd is not None:
            try:
                r, _, _ = select.select([self._fd], [], [], 0.04)
                if r:
                    buf = os.read(self._fd, 3)
                    if len(buf) == 3:
                        _, dx, dy = struct.unpack("bbb", buf)
                        if dx != 0 or dy != 0:
                            with self._lock:
                                if not self._has_calibrated:
                                    # Fallback: Starte bei Deskimonis aktueller Fensterposition
                                    init_pos = QCursor.pos()
                                    self._cur_x = float(init_pos.x())
                                    self._cur_y = float(init_pos.y())
                                    self._has_calibrated = True
                                self._cur_x += dx
                                self._cur_y -= dy  # PS/2 Y ist invertiert zur Bildschirmoberfläche
                                self._last_move_time = time.time()
            except Exception:
                time.sleep(0.02)

    def get_pos(self) -> QPoint:
        """Liefert die aktuelle Mauszeigerposition als QPoint."""
        if not self.is_linux_wayland or not self._has_calibrated:
            return QCursor.pos()
        with self._lock:
            # Begrenze auf den virtuellen Desktop aller verbundenen Monitore
            return QPoint(int(round(self._cur_x)), int(round(self._cur_y)))

    def last_move_time(self) -> float:
        with self._lock:
            return self._last_move_time

    def close(self):
        self._running = False
        if self._fd is not None:
            try:
                os.close(self._fd)
            except Exception:
                pass
            self._fd = None


class CursorShaker:
    """Schüttelt den Mauszeiger, damit das Betriebssystem ihn vergrößert."""
    def __init__(self):
        self._uinput_fd = None
        self._ignore_until = 0.0
        self._init_linux_uinput()

    def _init_linux_uinput(self):
        if not fcntl or not os.path.exists("/dev/uinput") or not sys.platform.startswith("linux"):
            return
        try:
            fd = os.open("/dev/uinput", os.O_WRONLY | os.O_NONBLOCK)
            fcntl.ioctl(fd, 0x40045564, 0x01)  # UI_SET_EVBIT -> EV_KEY
            fcntl.ioctl(fd, 0x40045565, 0x110) # UI_SET_KEYBIT -> BTN_LEFT
            fcntl.ioctl(fd, 0x40045564, 0x02)  # UI_SET_EVBIT -> EV_REL
            fcntl.ioctl(fd, 0x40045566, 0x00)  # UI_SET_RELBIT -> REL_X
            fcntl.ioctl(fd, 0x40045566, 0x01)  # UI_SET_RELBIT -> REL_Y
            setup = struct.pack("<4H80sI", 0x03, 0x1234, 0x5678, 1, b"Deskimoni-Cursor-Shaker", 0)
            fcntl.ioctl(fd, 0x405C5503, setup) # UI_DEV_SETUP
            fcntl.ioctl(fd, 0x5501)            # UI_DEV_CREATE
            self._uinput_fd = fd
        except Exception:
            self._uinput_fd = None

    def shake(self):
        threading.Thread(target=self._worker, daemon=True).start()

    def is_shaking(self) -> bool:
        return time.time() < self._ignore_until

    def _worker(self):
        try:
            # 1. Linux Kernel uinput (KDE Plasma Wayland / X11 shakecursor)
            if self._uinput_fd is not None:
                for _ in range(8):
                    for dx, dy in ((50, -20), (50, -20), (50, -20)):
                        now_t = time.time()
                        sec, usec = int(now_t), int((now_t - int(now_t)) * 1_000_000)
                        pkt = struct.pack("<qqHHi", sec, usec, 0x02, 0x00, dx) + \
                              struct.pack("<qqHHi", sec, usec, 0x02, 0x01, dy) + \
                              struct.pack("<qqHHi", sec, usec, 0x00, 0x00, 0)
                        os.write(self._uinput_fd, pkt)
                        time.sleep(0.006)
                    for dx, dy in ((-50, 20), (-50, 20), (-50, 20)):
                        now_t = time.time()
                        sec, usec = int(now_t), int((now_t - int(now_t)) * 1_000_000)
                        pkt = struct.pack("<qqHHi", sec, usec, 0x02, 0x00, dx) + \
                              struct.pack("<qqHHi", sec, usec, 0x02, 0x01, dy) + \
                              struct.pack("<qqHHi", sec, usec, 0x00, 0x00, 0)
                        os.write(self._uinput_fd, pkt)
                        time.sleep(0.006)
                return

            # 2. Windows via Win32 API mouse_event
            if sys.platform == "win32":
                import ctypes
                user32 = ctypes.windll.user32
                for _ in range(8):
                    user32.mouse_event(0x0001, 45, -20, 0, 0)
                    time.sleep(0.008)
                    user32.mouse_event(0x0001, 45, -20, 0, 0)
                    time.sleep(0.008)
                    user32.mouse_event(0x0001, -45, 20, 0, 0)
                    time.sleep(0.008)
                    user32.mouse_event(0x0001, -45, 20, 0, 0)
                    time.sleep(0.008)
                return

            # 3. macOS / Fallback via QCursor.setPos
            orig = QCursor.pos()
            for _ in range(7):
                for step in range(1, 5):
                    QCursor.setPos(orig.x() + step * 40, orig.y() - step * 20)
                    time.sleep(0.008)
                for step in range(3, -1, -1):
                    QCursor.setPos(orig.x() + step * 40, orig.y() - step * 20)
                    time.sleep(0.008)
            QCursor.setPos(orig)
        except Exception:
            pass
        finally:
            self._ignore_until = time.time() + 0.35

    def close(self):
        if self._uinput_fd is not None and fcntl:
            try:
                fcntl.ioctl(self._uinput_fd, 0x5502)  # UI_DEV_DESTROY
                os.close(self._uinput_fd)
            except Exception:
                pass
            self._uinput_fd = None
