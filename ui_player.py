import numpy as np
from PyQt6.QtWidgets import (QWidget, QPushButton, QVBoxLayout, QSizePolicy)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QPen, QColor, QPaintEvent

class WaveformWidget(QWidget):
    """Custom widget for drawing the audio waveform."""
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.samples: np.ndarray = np.array([], dtype=np.float32)
        self.setMinimumHeight(160)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_samples(self, samples: np.ndarray) -> None:
        # Downsample for UI snappiness
        if len(samples) > 5000:
            self.samples = samples[::len(samples) // 5000].astype(np.float32)
        else:
            self.samples = samples.astype(np.float32)
        self.update()

    def paintEvent(self, a0: QPaintEvent | None) -> None:
        if self.samples.size == 0:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(20, 20, 25))
        
        w, h = self.width(), self.height()
        mid_y = h // 2
        painter.setPen(QPen(QColor(0, 255, 127), 1))

        peak = np.max(np.abs(self.samples)) if self.samples.size > 0 else 1
        if peak == 0: peak = 1
        
        norm_samples = (self.samples / peak) * (h / 2.5)
        x_axis = np.linspace(0, w, len(norm_samples))

        for i in range(len(norm_samples) - 1):
            painter.drawLine(
                int(x_axis[i]), int(mid_y - norm_samples[i]),
                int(x_axis[i+1]), int(mid_y - norm_samples[i+1])
            )

class Ui_AudioPlayer:
    """The UI layout class, mimicking pyuic6 output."""
    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(800, 400)
        
        self.centralWidget = QWidget(MainWindow)
        self.layout = QVBoxLayout(self.centralWidget)
        
        self.waveform = WaveformWidget(self.centralWidget)
        self.layout.addWidget(self.waveform)
        
        self.btnMain = QPushButton(self.centralWidget)
        self.btnMain.setText("Load Audio File")
        self.btnMain.setMinimumHeight(40)
        self.layout.addWidget(self.btnMain)
        
        MainWindow.setCentralWidget(self.centralWidget)