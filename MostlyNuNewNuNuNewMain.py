import sys
import numpy as np
from PyQt6.QtWidgets import (QApplication, QMainWindow, QPushButton, 
                             QVBoxLayout, QWidget, QFileDialog)
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QPainter, QPen, QColor, QPaintEvent, QKeyEvent
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput, QAudioDecoder, QAudioBuffer, QAudioFormat

class WaveformWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.samples: np.ndarray = np.array([], dtype=np.float32)
        self.setMinimumHeight(160)
        self.setBackgroundRole(self.backgroundRole())

    def set_samples(self, samples: np.ndarray) -> None:
        # Keep the visualizer snappy by limiting data points
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
        painter.fillRect(self.rect(), QColor(25, 25, 30))
        
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
        painter.end()

class AudioPlayer(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("PyQt6 Linter-Safe Player")
        self.resize(800, 400)

        # 1. Media and Audio Output
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        
        # 2. Decoder logic
        self.decoder = QAudioDecoder()
        self.decoder.bufferReady.connect(self._process_buffer)
        self.decoder.finished.connect(self._on_decoder_finished)
        self.accumulated_data: list[np.ndarray] = []

        # 3. State handling
        self.player.playbackStateChanged.connect(self._on_state_changed)
        self.player.mediaStatusChanged.connect(self._on_status_changed)

        # UI Layout
        container = QWidget()
        self.setCentralWidget(container)
        layout = QVBoxLayout(container)

        self.waveform = WaveformWidget()
        layout.addWidget(self.waveform)

        self.btn_main = QPushButton("Load Audio File")
        self.btn_main.clicked.connect(self.handle_interaction)
        layout.addWidget(self.btn_main)

        self.file_ready = False

    def handle_interaction(self) -> None:
        if not self.file_ready:
            self.load_file()
        else:
            self.toggle_playback()

    def load_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select Audio", "", "Audio (*.wav *.mp3 *.flac *.m4a)")
        if path:
            self.file_ready = False
            self.accumulated_data = []
            self.btn_main.setText("Decoding...")
            self.btn_main.setEnabled(False)
            
            url = QUrl.fromLocalFile(path)
            self.decoder.setSource(url)
            self.player.setSource(url)
            self.decoder.start()

    def _process_buffer(self) -> None:
        buffer: QAudioBuffer = self.decoder.read()
        if not buffer.isValid():
            return

        # FIXED: ptr.asstring() returns a 'bytes' object which np.frombuffer accepts
        ptr = buffer.constData()
        raw_bytes = ptr.asstring(buffer.byteCount())
        
        fmt = buffer.format().sampleFormat()
        
        # Determine the correct numpy dtype based on Qt's format
        if fmt == QAudioFormat.SampleFormat.Int16:
            data = np.frombuffer(raw_bytes, dtype=np.int16)
        elif fmt == QAudioFormat.SampleFormat.Float:
            data = np.frombuffer(raw_bytes, dtype=np.float32)
        else:
            # Fallback for common 16-bit streams
            data = np.frombuffer(raw_bytes, dtype=np.int16)

        # Convert to mono if necessary
        channels = buffer.format().channelCount()
        if channels > 1:
            self.accumulated_data.append(data[::channels])
        else:
            self.accumulated_data.append(data)

    def _on_decoder_finished(self) -> None:
        if self.accumulated_data:
            full_waveform = np.concatenate(self.accumulated_data)
            self.waveform.set_samples(full_waveform)
        
        self.file_ready = True
        self.btn_main.setEnabled(True)
        self.btn_main.setText("Play")

    def toggle_playback(self) -> None:
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.stop() # 'Stop' resets the position for one-shot feel
        else:
            self.player.play()

    def _on_state_changed(self, state: QMediaPlayer.PlaybackState) -> None:
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.btn_main.setText("Stop (Any Key to Interrupt)")
        else:
            self.btn_main.setText("Play")

    def _on_status_changed(self, status: QMediaPlayer.MediaStatus) -> None:
        # If the file finishes playing naturally, reset the player
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.player.stop()

    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        # One-shot interrupt logic
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.stop()
        super().keyPressEvent(a0)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AudioPlayer()
    window.show()
    sys.exit(app.exec())

