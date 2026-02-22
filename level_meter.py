#level_meter.py
from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter, QColor, QLinearGradient
from PyQt6.QtCore import Qt

class LevelMeter(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(20)
        self.level = 0.0  # 0.0 to 1.0

    def set_level(self, level):
        self.level = max(0.0, min(1.0, level))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        rect = self.contentsRect()
        
        # Draw background (dimmer version of the theme)
        painter.fillRect(rect, QColor(30, 30, 30))
        
        # Calculate height based on level
        fill_height = int(rect.height() * self.level)
        fill_rect = rect.adjusted(2, rect.height() - fill_height, -2, -2)
        
        # Create a Teal-to-Yellow-to-Red gradient
        gradient = QLinearGradient(0, rect.height(), 0, 0)
        gradient.setColorAt(0.0, QColor("#00f0ff"))  # Teal
        gradient.setColorAt(0.7, QColor("#00f0ff")) 
        gradient.setColorAt(0.9, QColor("#ffff00"))  # Yellow (Warning)
        gradient.setColorAt(1.0, QColor("#ff0000"))  # Red (Clip)
        
        painter.fillRect(fill_rect, gradient)