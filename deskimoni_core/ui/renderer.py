#!/usr/bin/env python3
"""
Deskimoni v2 - Paint & Render Mixin
Zeichnet den 3D-Körper, alle Skins (Orbit, Sprout, Neo, Poko, Hopper, Soldier, Cat),
den ESP32-S3 Display-Screen mit allen Modi, Augen-Animationen, Partikel und Sprechblasen.
"""

import math
import time
from datetime import datetime

from deskimoni_core.qt import (
    Qt, QPointF, QRectF,
    QPainter, QColor, QPen, QBrush, QPainterPath, QLinearGradient, QRadialGradient, QFont
)


class DeskimonPaintMixin:
    """Mixin für alle Qt paintEvent- und Zeichen-Funktionen."""

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        painter.scale(self.scale_factor, self.scale_factor)

        # 0. Sprechblase oben über dem Kopf zeichnen (falls aktiv)
        if time.time() < self.bubble_until and self.bubble_text:
            self.draw_speech_bubble(painter)

        # Körper-Koordinatensystem
        painter.save()
        step_hop = abs(math.sin(self.walk_phase)) * -4.5 if self.is_stepping else 0.0
        breath_y = math.sin(self.breath_phase) * 2.2 + self.bounce_offset + step_hop

        if getattr(self, "is_dancing", False):
            if self.dance_style == "headbang":
                hb_t = self.dance_phase
                hb_y = (math.sin(hb_t) * 0.5 + 0.5) ** 1.6 * 14.0
                hb_tilt = math.sin(hb_t) * 12.5
                painter.translate(
                    self.body_offset_x + self.walk_offset_x,
                    self.body_offset_y + self.walk_offset_y + breath_y + hb_y,
                )
                painter.translate(120, 195)
                painter.rotate(hb_tilt)
                painter.translate(-120, -195)
            else:
                sway_x = math.sin(self.dance_phase) * 5.5
                sway_tilt = math.sin(self.dance_phase) * 5.0
                dance_hop = abs(math.sin(self.dance_phase * 2.0)) * -4.5
                painter.translate(
                    self.body_offset_x + self.walk_offset_x + sway_x,
                    self.body_offset_y + self.walk_offset_y + breath_y + dance_hop,
                )
                painter.translate(120, 185)
                painter.rotate(sway_tilt)
                painter.translate(-120, -185)
        else:
            painter.translate(
                self.body_offset_x + self.walk_offset_x,
                self.body_offset_y + self.walk_offset_y + breath_y,
            )
            if self.is_stepping:
                waddle_tilt = math.sin(self.walk_phase) * 3.5
                painter.translate(120, 145)
                painter.rotate(waddle_tilt)
                painter.translate(-120, -145)

        # 1. Schatten unter dem Deskimon
        shadow_grad = QRadialGradient(120, 252 - breath_y * 0.6, 70, 120, 252)
        shadow_grad.setColorAt(0.0, QColor(0, 0, 0, 110))
        shadow_grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(shadow_grad))
        painter.drawEllipse(QRectF(55, 240 - breath_y * 0.5, 130, 20))

        # 2. Charakter-spezifische Ohren/Antennen/Pflanze
        self.draw_skin_back_accessories(painter)

        # 3. 3D-gedrucktes Hauptgehäuse
        self.draw_3d_printed_body(painter)

        # 4. Eingelassenes ESP32-S3 IPS-Touch-Display
        self.draw_esp32_screen(painter)

        # 5. Vordergrund-Details
        self.draw_skin_front_accessories(painter)

        # 6. Schwebende Partikel
        self.draw_particles(painter)

        painter.restore()

    def draw_speech_bubble(self, painter: QPainter):
        bx_shift = self.body_offset_x - 15 + self.walk_offset_x
        by_shift = self.body_offset_y - 68 + self.walk_offset_y
        bubble_rect = QRectF(10 + bx_shift, 6 + by_shift, 250, 68)
        painter.setPen(QPen(QColor("#89b4fa"), 1.8))
        painter.setBrush(QColor(24, 25, 38, 238))
        painter.drawRoundedRect(bubble_rect, 14, 14)

        tail = QPainterPath()
        tail.moveTo(126 + bx_shift, 74 + by_shift)
        tail.lineTo(135 + bx_shift, 84 + by_shift)
        tail.lineTo(144 + bx_shift, 74 + by_shift)
        tail.closeSubpath()
        painter.drawPath(tail)

        painter.setPen(QColor("#cdd6f4"))
        painter.setFont(QFont("SansSerif", 9, QFont.Weight.Medium))
        text_rect = QRectF(18 + bx_shift, 10 + by_shift, 234, 60)
        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
            self.bubble_text,
        )

    def get_skin_palette(self):
        palettes = {
            "orbit": {
                "body_top": QColor("#f5f7fa"),
                "body_bot": QColor("#cfd8dc"),
                "accent": QColor("#ff6f00"),
                "bezel": QColor("#263238"),
                "eye": QColor("#00e5ff"),
            },
            "sprout": {
                "body_top": QColor("#e8f5e9"),
                "body_bot": QColor("#a5d6a7"),
                "accent": QColor("#43a047"),
                "bezel": QColor("#1b5e20"),
                "eye": QColor("#76ff03"),
            },
            "neo": {
                "body_top": QColor("#2b2d42"),
                "body_bot": QColor("#181926"),
                "accent": QColor("#f72585"),
                "bezel": QColor("#0f0f1a"),
                "eye": QColor("#b5179e"),
            },
            "poko": {
                "body_top": QColor("#ffffff"),
                "body_bot": QColor("#e0e0e0"),
                "accent": QColor("#212121"),
                "bezel": QColor("#1a1a1a"),
                "eye": QColor("#40c4ff"),
            },
            "hopper": {
                "body_top": QColor("#fce4ec"),
                "body_bot": QColor("#f48fb1"),
                "accent": QColor("#ec407a"),
                "bezel": QColor("#4a154b"),
                "eye": QColor("#ff80ab"),
            },
            "soldier": {
                "body_top": QColor("#5a6b32"),
                "body_bot": QColor("#3c4a22"),
                "accent": QColor("#7d5528"),
                "bezel": QColor("#1f2717"),
                "eye": QColor("#76ff03"),
            },
            "cat": {
                "body_top": QColor("#fff3e0"),
                "body_bot": QColor("#fedbb6"),
                "accent": QColor("#ff80ab"),
                "bezel": QColor("#2a1d22"),
                "eye": QColor("#00e5ff"),
            },
        }
        return palettes.get(self.skin, palettes["orbit"])

    def draw_skin_back_accessories(self, painter: QPainter):
        pal = self.get_skin_palette()
        painter.setPen(QPen(QColor(0, 0, 0, 50), 2))

        if self.skin == "orbit":
            painter.setPen(QPen(QColor("#90a4ae"), 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(120, 48, 120, 20)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(pal["accent"])
            painter.drawEllipse(QPointF(120, 17), 8, 8)
            painter.setBrush(QColor(255, 255, 255, 180))
            painter.drawEllipse(QPointF(117, 14), 3, 3)

        elif self.skin == "sprout":
            painter.setPen(QPen(QColor("#2e7d32"), 4.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(120, 48, 120, 22)

            leaf_left = QPainterPath()
            leaf_left.moveTo(120, 24)
            leaf_left.cubicTo(95, 10, 88, 32, 120, 28)
            painter.setPen(QPen(QColor("#1b5e20"), 1.5))
            painter.setBrush(QColor("#66bb6a"))
            painter.drawPath(leaf_left)

            leaf_right = QPainterPath()
            leaf_right.moveTo(120, 24)
            leaf_right.cubicTo(145, 8, 152, 30, 120, 28)
            painter.setBrush(QColor("#4caf50"))
            painter.drawPath(leaf_right)

        elif self.skin == "poko":
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#1f1f1f"))
            painter.drawEllipse(QPointF(62, 55), 22, 22)
            painter.drawEllipse(QPointF(178, 55), 22, 22)
            painter.setBrush(QColor("#424242"))
            painter.drawEllipse(QPointF(62, 55), 11, 11)
            painter.drawEllipse(QPointF(178, 55), 11, 11)

        elif self.skin == "hopper":
            ear_wobble = math.sin(self.breath_phase * 1.5) * 3.0
            painter.setPen(QPen(QColor(0, 0, 0, 35), 1.5))
            painter.setBrush(pal["body_top"])

            painter.save()
            painter.translate(82, 50)
            painter.rotate(-12 + ear_wobble)
            painter.drawRoundedRect(QRectF(-14, -42, 28, 52), 14, 14)
            painter.setBrush(pal["accent"])
            painter.drawRoundedRect(QRectF(-8, -34, 16, 36), 8, 8)
            painter.restore()

            painter.save()
            painter.translate(158, 50)
            painter.rotate(12 - ear_wobble)
            painter.setBrush(pal["body_top"])
            painter.drawRoundedRect(QRectF(-14, -42, 28, 52), 14, 14)
            painter.setBrush(pal["accent"])
            painter.drawRoundedRect(QRectF(-8, -34, 16, 36), 8, 8)
            painter.restore()

        elif self.skin == "soldier":
            painter.setPen(QPen(QColor("#2d3815"), 4.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(44, 45, 36, 6)
            painter.setPen(QPen(QColor("#1f2717"), 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(36, 6, 32, -14)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#76ff03"))
            painter.drawEllipse(QPointF(32, -15), 3.5, 3.5)

        elif self.skin == "cat":
            ear_twitch = math.sin(self.breath_phase * 1.8) * 3.0

            painter.save()
            painter.translate(72, 48)
            painter.rotate(-15 + ear_twitch)
            ear_left = QPainterPath()
            ear_left.moveTo(-16, 8)
            ear_left.lineTo(0, -32)
            ear_left.lineTo(16, 8)
            ear_left.closeSubpath()
            painter.setPen(QPen(QColor(0, 0, 0, 45), 1.5))
            painter.setBrush(pal["body_top"])
            painter.drawPath(ear_left)

            inner_left = QPainterPath()
            inner_left.moveTo(-10, 6)
            inner_left.lineTo(0, -22)
            inner_left.lineTo(10, 6)
            inner_left.closeSubpath()
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(pal["accent"])
            painter.drawPath(inner_left)
            painter.restore()

            painter.save()
            painter.translate(168, 48)
            painter.rotate(15 - ear_twitch)
            ear_right = QPainterPath()
            ear_right.moveTo(-16, 8)
            ear_right.lineTo(0, -32)
            ear_right.lineTo(16, 8)
            ear_right.closeSubpath()
            painter.setPen(QPen(QColor(0, 0, 0, 45), 1.5))
            painter.setBrush(pal["body_top"])
            painter.drawPath(ear_right)

            inner_right = QPainterPath()
            inner_right.moveTo(-10, 6)
            inner_right.lineTo(0, -22)
            inner_right.lineTo(10, 6)
            inner_right.closeSubpath()
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(pal["accent"])
            painter.drawPath(inner_right)
            painter.restore()

            tail_sway = math.sin(self.breath_phase * 1.2) * 6.0
            painter.save()
            painter.translate(202, 195)
            painter.rotate(tail_sway)
            painter.setPen(QPen(pal["body_bot"], 10, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            tail_path = QPainterPath()
            tail_path.moveTo(0, 0)
            tail_path.cubicTo(18, -5, 26, -25, 22, -38)
            painter.drawPath(tail_path)
            painter.setPen(QPen(QColor("#ffffff"), 9, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            tail_tip = QPainterPath()
            tail_tip.moveTo(25, -30)
            tail_tip.lineTo(22, -38)
            painter.drawPath(tail_tip)
            painter.restore()

    def draw_3d_printed_body(self, painter: QPainter):
        pal = self.get_skin_palette()

        foot_color = (
            pal["accent"] if self.skin in ("poko", "neo", "cat")
            else QColor("#1e2617") if self.skin == "soldier"
            else pal["body_bot"]
        )
        painter.setPen(QPen(QColor(0, 0, 0, 45), 1.5))
        painter.setBrush(foot_color)
        left_foot_y = 228 + (math.sin(self.walk_phase) * 6.0 if self.is_stepping else 0.0)
        right_foot_y = 228 + (-math.sin(self.walk_phase) * 6.0 if self.is_stepping else 0.0)
        painter.drawRoundedRect(QRectF(65, left_foot_y, 38, 22), 10, 10)
        painter.drawRoundedRect(QRectF(137, right_foot_y, 38, 22), 10, 10)

        arm_angle = math.sin(self.breath_phase) * 6.0
        if self.is_speaking:
            arm_angle = math.sin(self.tick_count * 0.28) * 12.0
        elif self.is_stepping:
            arm_angle = math.sin(self.walk_phase) * 16.0
        arm_color = pal["accent"] if self.skin == "poko" else pal["body_bot"]
        painter.setBrush(arm_color)

        painter.save()
        painter.translate(38, 145)
        painter.rotate(15 + arm_angle)
        painter.drawRoundedRect(QRectF(-12, -8, 24, 46), 11, 11)
        painter.restore()

        painter.save()
        painter.translate(202, 145)
        painter.rotate(-15 - arm_angle)
        painter.drawRoundedRect(QRectF(-12, -8, 24, 46), 11, 11)
        painter.restore()

        body_grad = QLinearGradient(120, 42, 120, 238)
        body_grad.setColorAt(0.0, pal["body_top"])
        body_grad.setColorAt(1.0, pal["body_bot"])

        painter.setPen(QPen(QColor(0, 0, 0, 65), 2.0))
        painter.setBrush(QBrush(body_grad))
        painter.drawRoundedRect(QRectF(36, 44, 168, 194), 42, 42)

        if self.skin == "soldier":
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#2d3815"))
            for bx, by, rx, ry in [(52, 85, 12, 7), (175, 95, 14, 8), (62, 180, 15, 9), (180, 175, 12, 8), (145, 215, 14, 7), (85, 220, 10, 6)]:
                painter.drawEllipse(QPointF(bx, by), rx, ry)
            painter.setBrush(QColor("#7d5528"))
            for bx, by, rx, ry in [(45, 125, 9, 6), (185, 135, 11, 7), (68, 205, 10, 6), (160, 195, 11, 7)]:
                painter.drawEllipse(QPointF(bx, by), rx, ry)
            painter.setBrush(QColor("#1a200f"))
            for bx, by, rx, ry in [(58, 105, 7, 5), (178, 115, 8, 5), (55, 195, 7, 5), (172, 185, 8, 5)]:
                painter.drawEllipse(QPointF(bx, by), rx, ry)

        highlight_pen = QPen(QColor(255, 255, 255, 110), 2.5)
        painter.setPen(highlight_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawArc(QRectF(42, 48, 156, 70), 30 * 16, 120 * 16)

    def draw_skin_front_accessories(self, painter: QPainter):
        pal = self.get_skin_palette()

        if self.skin == "neo":
            painter.setPen(QPen(QColor("#f72585"), 2.0))
            painter.setBrush(QColor("#11111b"))
            painter.drawRoundedRect(QRectF(22, 95, 18, 68), 8, 8)
            painter.drawRoundedRect(QRectF(200, 95, 18, 68), 8, 8)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#00f5d4"))
            painter.drawRoundedRect(QRectF(26, 110, 5, 38), 2, 2)
            painter.drawRoundedRect(QRectF(209, 110, 5, 38), 2, 2)

        elif self.skin == "cat":
            painter.setPen(QPen(QColor("#8d6e63"), 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(44, 125, 22, 118)
            painter.drawLine(44, 133, 18, 133)
            painter.drawLine(44, 141, 24, 148)
            painter.drawLine(196, 125, 218, 118)
            painter.drawLine(196, 133, 222, 133)
            painter.drawLine(196, 141, 216, 148)

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(pal["accent"])
            painter.drawEllipse(QPointF(84, 239), 5.5, 4.0)
            painter.drawEllipse(QPointF(74, 233), 2.2, 2.2)
            painter.drawEllipse(QPointF(84, 230), 2.2, 2.2)
            painter.drawEllipse(QPointF(94, 233), 2.2, 2.2)
            painter.drawEllipse(QPointF(156, 239), 5.5, 4.0)
            painter.drawEllipse(QPointF(146, 233), 2.2, 2.2)
            painter.drawEllipse(QPointF(156, 230), 2.2, 2.2)
            painter.drawEllipse(QPointF(166, 233), 2.2, 2.2)

        elif self.skin == "soldier":
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(0, 0, 0, 95))
            painter.drawRoundedRect(QRectF(38, 62, 164, 14), 7, 7)

            painter.setPen(QPen(QColor("#222818"), 3.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(42, 65, 48, 168)
            painter.drawLine(198, 65, 192, 168)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#111111"))
            painter.drawRoundedRect(QRectF(44, 120, 7, 10), 2, 2)
            painter.drawRoundedRect(QRectF(189, 120, 7, 10), 2, 2)

            helmet_path = QPainterPath()
            helmet_path.moveTo(28, 68)
            helmet_path.cubicTo(22, 46, 26, 20, 62, 10)
            helmet_path.cubicTo(90, 0, 150, 0, 178, 10)
            helmet_path.cubicTo(214, 20, 218, 46, 212, 68)
            helmet_path.cubicTo(168, 58, 72, 58, 28, 68)
            helmet_path.closeSubpath()

            helm_grad = QLinearGradient(60, 4, 180, 72)
            helm_grad.setColorAt(0.0, QColor("#667c3b"))
            helm_grad.setColorAt(0.4, QColor("#49592a"))
            helm_grad.setColorAt(1.0, QColor("#2a3518"))

            painter.save()
            painter.setPen(QPen(QColor(0, 0, 0, 95), 2.2))
            painter.setBrush(QBrush(helm_grad))
            painter.drawPath(helmet_path)

            painter.setClipPath(helmet_path)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#263214"))
            for fx, fy, rx, ry in [(55, 32, 16, 9), (145, 25, 18, 10), (105, 42, 14, 8), (185, 48, 13, 8), (38, 52, 12, 7)]:
                painter.drawEllipse(QPointF(fx, fy), rx, ry)
            painter.setBrush(QColor("#7d5528"))
            for fx, fy, rx, ry in [(82, 22, 13, 8), (170, 32, 15, 9), (125, 48, 12, 7), (60, 56, 11, 6), (150, 58, 13, 7)]:
                painter.drawEllipse(QPointF(fx, fy), rx, ry)
            painter.setBrush(QColor("#161a10"))
            for fx, fy, rx, ry in [(112, 20, 10, 6), (72, 44, 9, 6), (160, 42, 11, 6), (95, 58, 10, 5), (188, 38, 8, 5)]:
                painter.drawEllipse(QPointF(fx, fy), rx, ry)
            painter.setBrush(QColor("#6f8741"))
            for fx, fy, rx, ry in [(98, 32, 9, 5), (135, 16, 11, 6), (48, 42, 8, 5), (172, 54, 8, 5)]:
                painter.drawEllipse(QPointF(fx, fy), rx, ry)

            painter.restore()

            band_path = QPainterPath()
            band_path.moveTo(27, 54)
            band_path.cubicTo(70, 45, 170, 45, 213, 54)
            painter.setPen(QPen(QColor("#161814"), 4.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(band_path)

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#76ff03"))
            painter.drawRoundedRect(QRectF(85, 46, 7, 4), 1, 1)
            painter.drawRoundedRect(QRectF(148, 46, 7, 4), 1, 1)

            painter.setPen(QPen(QColor("#0d100b"), 1.5))
            painter.setBrush(QColor("#1f241a"))
            painter.drawRoundedRect(QRectF(111, 38, 18, 15), 3, 3)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#4b5636"))
            painter.drawRoundedRect(QRectF(115, 42, 10, 7), 1.5, 1.5)

            painter.setPen(QPen(QColor(0, 0, 0, 130), 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            rim_path = QPainterPath()
            rim_path.moveTo(28, 68)
            rim_path.cubicTo(72, 58, 168, 58, 212, 68)
            painter.drawPath(rim_path)

        btn_border = QColor("#ffffff") if getattr(self, "controls_visible", False) else QColor(0, 0, 0, 80)
        painter.setPen(QPen(btn_border, 1.5))
        painter.setBrush(pal["accent"])
        painter.drawRoundedRect(QRectF(96, 212, 48, 14), 7, 7)

        dot_alpha = 230 if getattr(self, "controls_visible", False) else 130
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, dot_alpha))
        for dx_dot in (110, 120, 130):
            painter.drawEllipse(QPointF(dx_dot, 219), 1.8, 1.8)

        led_color = QColor("#00e676") if self.cpu_percent < 75 else QColor("#ff1744")
        if self.mic_status == "recording":
            led_color = QColor("#ff1744")
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(led_color)
        painter.drawEllipse(QPointF(68, 219), 4, 4)

    def draw_esp32_screen(self, painter: QPainter):
        pal = self.get_skin_palette()

        painter.setPen(QPen(QColor(255, 255, 255, 35), 1.5))
        painter.setBrush(pal["bezel"])
        painter.drawRoundedRect(QRectF(48, 66, 144, 134), 26, 26)

        screen_rect = QRectF(54, 72, 132, 122)
        screen_grad = QLinearGradient(54, 72, 54, 194)
        screen_grad.setColorAt(0.0, QColor("#0b0e14"))
        screen_grad.setColorAt(1.0, QColor("#131722"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(screen_grad))
        painter.drawRoundedRect(screen_rect, 20, 20)

        painter.save()
        clip_path = QPainterPath()
        clip_path.addRoundedRect(screen_rect, 20, 20)
        painter.setClipPath(clip_path)

        if self.mode == "pet":
            self.draw_pet_face(painter, pal["eye"])
        elif self.mode == "clock":
            self.draw_clock_mode(painter, pal["eye"])
        elif self.mode == "weather":
            self.draw_weather_mode(painter, pal["eye"])
        elif self.mode == "news":
            self.draw_news_mode(painter, pal["eye"])
        elif self.mode == "radio":
            self.draw_radio_mode(painter, pal["eye"])
        elif self.mode == "music":
            self.draw_music_mode(painter, pal["eye"])
        elif self.mode == "linux":
            self.draw_linux_mode(painter, pal["eye"])
        elif self.mode == "pomodoro":
            self.draw_pomodoro_mode(painter, pal["eye"])
        elif self.mode == "sysmon":
            self.draw_sysmon_mode(painter, pal["eye"])

        glass_grad = QLinearGradient(54, 72, 54, 105)
        glass_grad.setColorAt(0.0, QColor(255, 255, 255, 22))
        glass_grad.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(glass_grad))
        painter.drawRoundedRect(QRectF(56, 73, 128, 32), 18, 18)

        painter.restore()

    def draw_pet_face(self, painter: QPainter, eye_color: QColor):
        cx = 120.0 + self.look_x
        cy = 126.0 + self.look_y

        left_eye_x = cx - 30.0
        right_eye_x = cx + 30.0
        emo = self.current_emotion

        glow = QRadialGradient(cx, cy, 55)
        glow_col = QColor(eye_color)
        glow_col.setAlpha(35)
        glow.setColorAt(0.0, glow_col)
        glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setBrush(QBrush(glow))
        painter.drawEllipse(QPointF(cx, cy), 55, 40)

        if emo in ("happy", "love", "excited") or self.is_speaking:
            painter.setBrush(QColor(255, 105, 180, 95))
            painter.drawEllipse(QPointF(left_eye_x - 10, cy + 20), 10, 5.5)
            painter.drawEllipse(QPointF(right_eye_x + 10, cy + 20), 10, 5.5)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(eye_color)

        if emo == "happy":
            pen = QPen(eye_color, 6.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawArc(QRectF(left_eye_x - 16, cy - 12, 32, 28), 20 * 16, 140 * 16)
            painter.drawArc(QRectF(right_eye_x - 16, cy - 12, 32, 28), 20 * 16, 140 * 16)

        elif emo == "love":
            self.draw_heart(painter, left_eye_x, cy, 17, QColor("#ff4081"))
            self.draw_heart(painter, right_eye_x, cy, 17, QColor("#ff4081"))

        elif emo == "sleepy":
            pen = QPen(eye_color, 5.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawLine(QPointF(left_eye_x - 14, cy + 2), QPointF(left_eye_x + 14, cy + 2))
            painter.drawLine(QPointF(right_eye_x - 14, cy + 2), QPointF(right_eye_x + 14, cy + 2))

        elif emo == "dizzy":
            pen = QPen(QColor("#ffeb3b"), 4.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawLine(QPointF(left_eye_x - 11, cy - 11), QPointF(left_eye_x + 11, cy + 11))
            painter.drawLine(QPointF(left_eye_x + 11, cy - 11), QPointF(left_eye_x - 11, cy + 11))
            painter.drawLine(QPointF(right_eye_x - 11, cy - 11), QPointF(right_eye_x + 11, cy + 11))
            painter.drawLine(QPointF(right_eye_x + 11, cy - 11), QPointF(right_eye_x - 11, cy + 11))

        elif emo == "angry":
            painter.setBrush(QColor("#ff5252"))
            path_l = QPainterPath()
            path_l.addRoundedRect(QRectF(left_eye_x - 15, cy - 14, 30, 28), 9, 9)
            painter.drawPath(path_l)
            path_r = QPainterPath()
            path_r.addRoundedRect(QRectF(right_eye_x - 15, cy - 14, 30, 28), 9, 9)
            painter.drawPath(path_r)
            painter.setBrush(QColor("#0f131c"))
            poly_l = QPainterPath()
            poly_l.moveTo(left_eye_x - 18, cy - 18)
            poly_l.lineTo(left_eye_x + 18, cy - 4)
            poly_l.lineTo(left_eye_x + 18, cy - 20)
            poly_l.closeSubpath()
            painter.drawPath(poly_l)

            poly_r = QPainterPath()
            poly_r.moveTo(right_eye_x + 18, cy - 18)
            poly_r.lineTo(right_eye_x - 18, cy - 4)
            poly_r.lineTo(right_eye_x - 18, cy - 20)
            poly_r.closeSubpath()
            painter.drawPath(poly_r)

        else:
            blink_factor = max(0.08, 1.0 - math.sin(min(1.0, self.blink_state) * math.pi))
            eye_h = 34.0 * blink_factor
            eye_w = 28.0

            for ex in (left_eye_x, right_eye_x):
                painter.setBrush(eye_color)
                painter.drawRoundedRect(
                    QRectF(ex - eye_w / 2, cy - eye_h / 2, eye_w, eye_h), 11, 11
                )
                if blink_factor > 0.4:
                    painter.setBrush(QColor(255, 255, 255, 220))
                    painter.drawEllipse(QPointF(ex - 5, cy - eye_h * 0.22), 4.5, 4.5)
                    painter.drawEllipse(QPointF(ex + 5, cy + eye_h * 0.15), 2.2, 2.2)

            if emo == "chill":
                painter.setBrush(QColor("#0b0e14"))
                painter.drawRect(QRectF(left_eye_x - 16, cy - 18, 32, 11))
                painter.drawRect(QRectF(right_eye_x - 16, cy - 18, 32, 11))

        # Mund
        if self.is_speaking:
            t = self.tick_count * 0.24
            syllable = 0.5 + 0.5 * math.sin(t)
            micro_mod = 0.25 * math.sin(t * 2.3)
            open_val = max(0.08, min(1.0, syllable + micro_mod))

            mouth_w = 12.0 + open_val * 11.0
            mouth_h = 3.5 + open_val * 10.0
            mouth_y = cy + 18.0

            painter.setPen(QPen(eye_color, 2.0))
            painter.setBrush(QColor("#d81b60"))
            mouth_rect = QRectF(cx - mouth_w / 2, mouth_y, mouth_w, mouth_h)
            painter.drawRoundedRect(mouth_rect, mouth_w * 0.45, mouth_h * 0.5)

            if mouth_h > 7.0:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor("#ff80ab"))
                painter.drawChord(
                    QRectF(cx - mouth_w * 0.35, mouth_y + mouth_h * 0.35, mouth_w * 0.7, mouth_h * 0.7),
                    0, 180 * 16
                )
        else:
            mouth_pen = QPen(eye_color, 3.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            painter.setPen(mouth_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)

            if emo in ("happy", "love", "excited"):
                painter.drawArc(QRectF(cx - 12, cy + 16, 24, 14), 190 * 16, 160 * 16)
            elif emo == "dizzy":
                painter.drawEllipse(QPointF(cx, cy + 24), 5, 6)
            elif emo == "sleepy":
                painter.drawEllipse(QPointF(cx, cy + 23), 3.5, 3.5)
            elif emo == "angry":
                painter.drawArc(QRectF(cx - 10, cy + 22, 20, 10), 20 * 16, 140 * 16)
            else:
                painter.drawArc(QRectF(cx - 9, cy + 18, 18, 9), 200 * 16, 140 * 16)

        painter.setFont(QFont("SansSerif", 8, QFont.Weight.Bold))
        if getattr(self, "is_dancing", False):
            if self.dance_style == "headbang":
                now_str = "🤘 HEADBANG ⚡"
                painter.setPen(QColor("#ff5252"))
            else:
                now_str = "🕺 GROOVE ♪"
                painter.setPen(QColor("#00e5ff"))
        elif self.alarm_active and self.alarm_time:
            rem_s = max(0, int(self.alarm_time - time.time()))
            now_str = f"⏰ {rem_s // 60:02d}:{rem_s % 60:02d}"
            painter.setPen(QColor("#f9e2af"))
        elif self.pomo_running:
            pm = self.pomo_remaining // 60
            ps = self.pomo_remaining % 60
            icon = "🍅" if self.pomo_phase == "work" else "☕"
            now_str = f"{icon} {pm:02d}:{ps:02d}"
            painter.setPen(QColor("#f38ba8") if self.pomo_phase == "work" else QColor("#a6e3a1"))
        else:
            now_str = datetime.now().strftime("%H:%M")
            painter.setPen(QColor(255, 255, 255, 90))
        painter.drawText(QRectF(54, 174, 132, 16), Qt.AlignmentFlag.AlignCenter, now_str)

    def draw_clock_mode(self, painter: QPainter, accent: QColor):
        now = datetime.now()
        time_str = now.strftime("%H:%M")
        sec_str = now.strftime(":%S")
        date_str = now.strftime("%a, %d. %b")

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(accent)
        painter.drawRoundedRect(QRectF(96, 82, 14, 10), 4, 4)
        painter.drawRoundedRect(QRectF(130, 82, 14, 10), 4, 4)

        painter.setPen(QColor("#ffffff"))
        painter.setFont(QFont("Monospace", 22, QFont.Weight.Bold))
        painter.drawText(QRectF(54, 102, 132, 38), Qt.AlignmentFlag.AlignCenter, time_str)

        painter.setPen(accent)
        painter.setFont(QFont("Monospace", 10, QFont.Weight.Bold))
        painter.drawText(QRectF(54, 138, 132, 20), Qt.AlignmentFlag.AlignCenter, sec_str)

        if self.alarm_active and self.alarm_time:
            rem_sec = max(0, int(self.alarm_time - time.time()))
            alarm_str = datetime.fromtimestamp(self.alarm_time).strftime("%H:%M")
            painter.setPen(QColor("#f9e2af"))
            painter.setFont(QFont("SansSerif", 8, QFont.Weight.Bold))
            painter.drawText(QRectF(54, 162, 132, 20), Qt.AlignmentFlag.AlignCenter, f"⏰ {alarm_str} ({rem_sec//60:02d}:{rem_sec%60:02d})")
        else:
            painter.setPen(QColor(255, 255, 255, 160))
            painter.setFont(QFont("SansSerif", 9))
            painter.drawText(QRectF(54, 162, 132, 20), Qt.AlignmentFlag.AlignCenter, date_str)

    def draw_weather_mode(self, painter: QPainter, accent: QColor):
        painter.setPen(accent)
        painter.setFont(QFont("SansSerif", 8, QFont.Weight.Bold))
        header = f"🌤️ WETTER {self.weather_city.upper()}" if self.weather_city else "🌤️ LIVE WETTER"
        painter.drawText(QRectF(54, 78, 132, 16), Qt.AlignmentFlag.AlignCenter, header)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#ffd54f"))
        painter.drawEllipse(QPointF(92, 118), 14, 14)
        painter.setBrush(QColor(225, 245, 254, 220))
        painter.drawRoundedRect(QRectF(88, 116, 36, 15), 7, 7)

        painter.setPen(QColor("#ffffff"))
        painter.setFont(QFont("Monospace", 17, QFont.Weight.Bold))
        painter.drawText(QRectF(112, 102, 72, 32), Qt.AlignmentFlag.AlignCenter, self.weather_temp)

        painter.setPen(QColor(255, 255, 255, 210))
        painter.setFont(QFont("SansSerif", 8, QFont.Weight.Medium))
        painter.drawText(QRectF(58, 142, 124, 24), Qt.AlignmentFlag.AlignCenter, self.weather_desc)

        painter.setPen(QColor(255, 255, 255, 100))
        painter.setFont(QFont("SansSerif", 7))
        painter.drawText(QRectF(54, 172, 132, 14), Qt.AlignmentFlag.AlignCenter, "(Klick = Neu laden)")

    def draw_news_mode(self, painter: QPainter, accent: QColor):
        painter.setPen(accent)
        painter.setFont(QFont("SansSerif", 8, QFont.Weight.Bold))
        painter.drawText(QRectF(54, 78, 132, 16), Qt.AlignmentFlag.AlignCenter, "📰 RSS NACHRICHTEN")

        if self.news_items:
            item = self.news_items[self.news_idx % len(self.news_items)]
            source = item.get("source", "News")
            title = item.get("title", "")
        else:
            source = "RSS Feed"
            title = "Lade Schlagzeilen..." if getattr(self, "news_fetching", False) else "Keine News (Klick für Abruf)"

        pill_rect = QRectF(70, 96, 100, 15)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, 28))
        painter.drawRoundedRect(pill_rect, 7, 7)
        painter.setPen(QColor("#89b4fa"))
        painter.setFont(QFont("SansSerif", 7, QFont.Weight.Bold))
        painter.drawText(pill_rect, Qt.AlignmentFlag.AlignCenter, source[:16])

        painter.setPen(QColor(255, 255, 255, 225))
        painter.setFont(QFont("SansSerif", 7, QFont.Weight.Medium))
        painter.drawText(
            QRectF(58, 114, 124, 52),
            Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
            title[:105] + ("..." if len(title) > 105 else ""),
        )

        painter.setPen(QColor(255, 255, 255, 120))
        painter.setFont(QFont("SansSerif", 7))
        painter.drawText(QRectF(54, 170, 132, 16), Qt.AlignmentFlag.AlignCenter, "◄ Vorlesen (Klick) ►")

    def draw_radio_mode(self, painter: QPainter, accent: QColor):
        painter.setPen(accent)
        painter.setFont(QFont("SansSerif", 8, QFont.Weight.Bold))
        if getattr(self, "is_dancing", False) and self.dance_style == "headbang":
            status_hdr = "⚡ ROCK ON AIR ⚡"
        elif self.radio_playing:
            status_hdr = "📻 RADIO: ON AIR"
        else:
            status_hdr = "📻 INTERNET-RADIO"
        painter.drawText(QRectF(54, 78, 132, 16), Qt.AlignmentFlag.AlignCenter, status_hdr)

        bar_w = 6
        spacing = 4
        start_x = int(120 - (7 * (bar_w + spacing)) / 2)
        mult = 22 if (getattr(self, "is_dancing", False) and self.dance_style == "headbang") else 14
        for i in range(7):
            bh = 4 + int(abs(math.sin(self.tick_count * 0.3 + i * 1.1)) * mult) if self.radio_playing else 3
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(accent if i % 2 == 0 else QColor("#00e5ff"))
            painter.drawRoundedRect(QRectF(start_x + i * (bar_w + spacing), 114 - bh, bar_w, bh), 2, 2)

        st_name = "Kein Sender"
        if self.radio_stations:
            st = self.radio_stations[self.active_radio_idx % len(self.radio_stations)]
            st_name = st.get("name", "Radio")

        painter.setPen(QColor("#ffffff"))
        painter.setFont(QFont("SansSerif", 8, QFont.Weight.Bold))
        painter.drawText(QRectF(58, 122, 124, 26), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, st_name)

        status_col = QColor("#a6e3a1") if self.radio_playing else QColor("#f38ba8")
        status_txt = "▶ LÄUFT" if self.radio_playing else "⏸ PAUSIERT"
        painter.setPen(status_col)
        painter.setFont(QFont("SansSerif", 7, QFont.Weight.Bold))
        painter.drawText(QRectF(58, 148, 124, 14), Qt.AlignmentFlag.AlignCenter, status_txt)

        painter.setPen(accent)
        painter.setFont(QFont("SansSerif", 10, QFont.Weight.Bold))
        play_sym = "⏸" if self.radio_playing else "▶"
        painter.drawText(QRectF(58, 166, 124, 22), Qt.AlignmentFlag.AlignCenter, f"⏮     {play_sym}     ⏭")

    def draw_music_mode(self, painter: QPainter, accent: QColor):
        painter.setPen(accent)
        painter.setFont(QFont("SansSerif", 8, QFont.Weight.Bold))
        if getattr(self, "is_dancing", False) and self.dance_style == "headbang":
            status_hdr = "🎸 ROCKSTAR MODE"
        elif self.music_playing:
            status_hdr = "🎵 NOW PLAYING"
        else:
            status_hdr = "🎵 MEDIA PLAYER"
        painter.drawText(QRectF(54, 78, 132, 16), Qt.AlignmentFlag.AlignCenter, status_hdr)

        bar_x = 80
        mult = 28 if (getattr(self, "is_dancing", False) and self.dance_style == "headbang") else 22
        for i in range(8):
            bh = 6 + abs(math.sin(self.tick_count * 0.3 + i * 0.9)) * mult if self.music_playing else 4
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(accent if i % 2 == 0 else QColor("#f72585"))
            painter.drawRoundedRect(QRectF(bar_x + i * 10, 124 - bh, 6, bh), 2, 2)

        painter.setPen(QColor("#ffffff"))
        painter.setFont(QFont("SansSerif", 8, QFont.Weight.Bold))
        painter.drawText(QRectF(58, 130, 124, 18), Qt.AlignmentFlag.AlignCenter, self.music_title)

        painter.setPen(QColor(255, 255, 255, 160))
        painter.setFont(QFont("SansSerif", 7))
        painter.drawText(QRectF(58, 146, 124, 16), Qt.AlignmentFlag.AlignCenter, self.music_artist)

        painter.setPen(accent)
        painter.setFont(QFont("SansSerif", 10, QFont.Weight.Bold))
        play_sym = "⏸" if self.music_playing else "▶"
        painter.drawText(QRectF(58, 166, 124, 22), Qt.AlignmentFlag.AlignCenter, f"⏮     {play_sym}     ⏭")

    def draw_linux_mode(self, painter: QPainter, accent: QColor):
        title, body = self.LINUX_TIPS[self.linux_tip_idx]
        painter.setPen(QColor("#a6e3a1"))
        painter.setFont(QFont("SansSerif", 8, QFont.Weight.Bold))
        painter.drawText(QRectF(54, 78, 132, 16), Qt.AlignmentFlag.AlignCenter, "🐧 LINUX HELFER")

        painter.setPen(accent)
        painter.setFont(QFont("SansSerif", 8, QFont.Weight.Bold))
        painter.drawText(QRectF(58, 96, 124, 18), Qt.AlignmentFlag.AlignCenter, title)

        painter.setPen(QColor(255, 255, 255, 215))
        painter.setFont(QFont("SansSerif", 7))
        painter.drawText(
            QRectF(58, 114, 124, 56),
            Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
            body[:90] + ("..." if len(body) > 90 else ""),
        )

        painter.setPen(QColor(255, 255, 255, 110))
        painter.setFont(QFont("SansSerif", 7))
        painter.drawText(QRectF(54, 172, 132, 14), Qt.AlignmentFlag.AlignCenter, "(Klick = Nächster Tipp)")

    def draw_pomodoro_mode(self, painter: QPainter, accent: QColor):
        mins = self.pomo_remaining // 60
        secs = self.pomo_remaining % 60
        timer_text = f"{mins:02d}:{secs:02d}"

        if self.pomo_phase == "short_break":
            status = "☕ PAUSE LÄUFT" if self.pomo_running else "☕ PAUSE (Klick)"
            phase_col = QColor("#a6e3a1")
        elif self.pomo_phase == "long_break":
            status = "🛋️ PAUSE LÄUFT" if self.pomo_running else "🛋️ PAUSE (Klick)"
            phase_col = QColor("#89b4fa")
        else:
            status = "🍅 FOKUS LÄUFT" if self.pomo_running else "🍅 FOKUS (Klick)"
            phase_col = accent

        painter.setPen(phase_col)
        painter.setFont(QFont("SansSerif", 9, QFont.Weight.Bold))
        painter.drawText(QRectF(54, 80, 132, 18), Qt.AlignmentFlag.AlignCenter, status)

        progress = self.pomo_remaining / max(1, self.pomo_duration)
        ring_rect = QRectF(83, 100, 74, 74)
        painter.setPen(QPen(QColor(255, 255, 255, 30), 6))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(ring_rect)

        painter.setPen(QPen(phase_col, 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawArc(ring_rect, 90 * 16, int(-360 * 16 * progress))

        painter.setPen(QColor("#ffffff"))
        painter.setFont(QFont("Monospace", 13, QFont.Weight.Bold))
        painter.drawText(ring_rect, Qt.AlignmentFlag.AlignCenter, timer_text)

    def draw_sysmon_mode(self, painter: QPainter, accent: QColor):
        painter.setPen(accent)
        painter.setFont(QFont("SansSerif", 9, QFont.Weight.Bold))
        painter.drawText(QRectF(54, 78, 132, 18), Qt.AlignmentFlag.AlignCenter, "⚡ PC VITALS")

        metrics = [
            ("CPU", self.cpu_percent, f"{self.cpu_percent:.0f}%", QColor("#00e5ff")),
            ("RAM", self.ram_percent, f"{self.ram_percent:.0f}%", QColor("#b388ff")),
            ("TMP", min(100.0, self.cpu_temp), f"{self.cpu_temp:.0f}°C", QColor("#ff8a65")),
        ]

        y = 104
        for label, val, txt, col in metrics:
            painter.setPen(QColor(255, 255, 255, 200))
            painter.setFont(QFont("Monospace", 8, QFont.Weight.Bold))
            painter.drawText(QRectF(62, y, 30, 16), Qt.AlignmentFlag.AlignLeft, label)
            painter.drawText(QRectF(144, y, 36, 16), Qt.AlignmentFlag.AlignRight, txt)

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(255, 255, 255, 35))
            painter.drawRoundedRect(QRectF(92, y + 3, 50, 8), 4, 4)

            painter.setBrush(col)
            fill_w = max(4.0, 50.0 * (min(100.0, max(0.0, val)) / 100.0))
            painter.drawRoundedRect(QRectF(92, y + 3, fill_w, 8), 4, 4)
            y += 28

    def draw_heart(self, painter: QPainter, cx: float, cy: float, size: float, color: QColor):
        path = QPainterPath()
        path.moveTo(cx, cy + size * 0.6)
        path.cubicTo(
            cx - size * 1.2,
            cy - size * 0.2,
            cx - size * 0.6,
            cy - size * 1.1,
            cx,
            cy - size * 0.35,
        )
        path.cubicTo(
            cx + size * 0.6,
            cy - size * 1.1,
            cx + size * 1.2,
            cy - size * 0.2,
            cx,
            cy + size * 0.6,
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawPath(path)

    def draw_particles(self, painter: QPainter):
        for p in self.particles:
            alpha = int(max(0.0, min(1.0, p["life"])) * 255)
            if p["type"] == "heart":
                col = QColor(255, 64, 129, alpha)
                self.draw_heart(painter, p["x"], p["y"], p["size"] * 0.55, col)
            elif p["type"] == "star":
                col = QColor(255, 215, 64, alpha)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(col)
                painter.drawEllipse(QPointF(p["x"], p["y"]), p["size"] * 0.3, p["size"] * 0.3)
            elif p["type"] == "zzz":
                painter.setPen(QColor(179, 229, 252, alpha))
                painter.setFont(QFont("SansSerif", int(p["size"] * 0.75), QFont.Weight.Bold))
                painter.drawText(QPointF(p["x"], p["y"]), "Zzz")
            elif p["type"] == "note":
                painter.setPen(QColor(247, 37, 133, alpha))
                painter.setFont(QFont("SansSerif", int(p["size"] * 0.85), QFont.Weight.Bold))
                painter.drawText(QPointF(p["x"], p["y"]), "♪")
            elif p["type"] == "water":
                col = QColor(0, 185, 255, alpha)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(col)
                painter.drawEllipse(QPointF(p["x"], p["y"]), p["size"] * 0.35, p["size"] * 0.45)
