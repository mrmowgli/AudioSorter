import numpy as np
from PyQt6.QtWidgets import QWidget, QSizePolicy
from PyQt6.QtGui import QPainter, QPen, QColor, QPaintEvent

class WaveformWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.samples: np.ndarray = np.array([], dtype=np.float32)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_samples(self, samples: np.ndarray) -> None:
        if len(samples) > 5000:
            self.samples = samples[::len(samples) // 5000].astype(np.float32)
        else:
            self.samples = samples.astype(np.float32)
        self.update()

    def paintEvent(self, a0: QPaintEvent | None) -> None:
        if self.samples.size == 0: return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), self.palette().color(self.palette().ColorRole.Window))
        # painter.fillRect(self.rect(), QColor(25, 25, 30))
        
        w, h, mid_y = self.width(), self.height(), self.height() // 2
        painter.setPen(QPen(QColor(0, 255, 127), 1))

        peak = np.max(np.abs(self.samples)) or 1
        norm_samples = (self.samples / peak) * (h / 2.5)
        x_axis = np.linspace(0, w, len(norm_samples))

        for i in range(len(norm_samples) - 1):
            painter.drawLine(
                int(x_axis[i]), int(mid_y - norm_samples[i]),
                int(x_axis[i+1]), int(mid_y - norm_samples[i+1])
            )
        painter.end()
