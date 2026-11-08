#!/usr/bin/env python3
"""
Deskimoni v2 - Qt Compatibility Layer
Transparently supports both PyQt6 and PySide6 across Linux, Windows and macOS.
"""

try:
    from PyQt6 import QtCore, QtGui, QtWidgets
    Signal = QtCore.pyqtSignal
    Slot = QtCore.pyqtSlot
    QT_BINDING = "PyQt6"
except ImportError:
    try:
        from PySide6 import QtCore, QtGui, QtWidgets
        Signal = QtCore.Signal
        Slot = QtCore.Slot
        QT_BINDING = "PySide6"
    except ImportError:
        raise ImportError(
            "Weder PyQt6 noch PySide6 gefunden! Bitte installiere PyQt6 oder PySide6:\n"
            "  pip install PyQt6\n"
            "oder:\n"
            "  pip install PySide6"
        )

# Core
Qt = QtCore.Qt
QTimer = QtCore.QTimer
QPoint = QtCore.QPoint
QPointF = QtCore.QPointF
QRect = QtCore.QRect
QRectF = QtCore.QRectF
QSize = QtCore.QSize
QObject = QtCore.QObject

# Gui
QColor = QtGui.QColor
QFont = QtGui.QFont
QPainter = QtGui.QPainter
QPainterPath = QtGui.QPainterPath
QCursor = QtGui.QCursor
QIcon = QtGui.QIcon
QBrush = QtGui.QBrush
QPen = QtGui.QPen
QLinearGradient = QtGui.QLinearGradient
QRadialGradient = QtGui.QRadialGradient
QAction = QtGui.QAction
QActionGroup = QtGui.QActionGroup

try:
    if QT_BINDING == "PyQt6":
        from PyQt6.QtSvg import QSvgRenderer
    else:
        from PySide6.QtSvg import QSvgRenderer
except ImportError:
    QSvgRenderer = None

# Widgets
QWidget = QtWidgets.QWidget
QApplication = QtWidgets.QApplication
QLineEdit = QtWidgets.QLineEdit
QPushButton = QtWidgets.QPushButton
QMenu = QtWidgets.QMenu
QInputDialog = QtWidgets.QInputDialog
QMessageBox = QtWidgets.QMessageBox
QSystemTrayIcon = QtWidgets.QSystemTrayIcon
QStyle = QtWidgets.QStyle

__all__ = [
    "QT_BINDING", "Signal", "Slot", "QtCore", "QtGui", "QtWidgets",
    "Qt", "QTimer", "QPoint", "QPointF", "QRect", "QRectF", "QSize", "QObject",
    "QColor", "QFont", "QPainter", "QPainterPath", "QCursor", "QIcon", "QBrush", "QPen",
    "QLinearGradient", "QRadialGradient", "QAction", "QActionGroup", "QSvgRenderer",
    "QWidget", "QApplication", "QLineEdit", "QPushButton", "QMenu",
    "QInputDialog", "QMessageBox", "QSystemTrayIcon", "QStyle"
]
