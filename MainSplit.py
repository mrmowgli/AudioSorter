import sys
import numpy as np
from PyQt6.QtWidgets import QApplication, QMainWindow, QFileDialog
from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtMultimedia import (QMediaPlayer, QAudioOutput, QAudioDecoder, 
                                 QAudioBuffer, QAudioFormat)
from PyQt6 import uic

class AudioApp(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        # Load the UI file
        uic.loadUi("player.ui", self)

        # Access widgets defined in the UI file by their objectName
        # self.waveform and self.btnMain are automatically created attributes
        
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        
        self.decoder = QAudioDecoder()
        self.decoder.bufferReady.connect(self._process_buffer)
        self.decoder.finished.connect(self._on_decoder_finished)
        
        self.accumulated_data: list[np.ndarray] = []
        self.file_ready = False

        # Connect signals to logic
        self.btnMain.clicked.connect(self.handle_interaction)
        self.player.playbackStateChanged.connect(self._on_state_changed)
        self.player.mediaStatusChanged.connect(self._on_status_changed)

    def handle_interaction(self) -> None:
        if not self.file_ready:
            self.load_file()
        elif self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.stop()
        else:
            self.player.play()

    def load_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open Audio", "", "Audio (*.wav *.mp3 *.flac)")
        if path:
            self.file_ready = False
            self.accumulated_data = []
            self.btnMain.setText("Decoding...")
            self.btnMain.setEnabled(False)
            
            url = QUrl.fromLocalFile(path)
            self.decoder.setSource(url)
            self.player.setSource(url)
            self.decoder.start()

    def _process_buffer(self) -> None:
        buf: QAudioBuffer = self.decoder.read()
        if not buf.isValid(): return
        
        # ptr.asstring() for linter-safe buffer access
        ptr = buf.constData()
        raw = ptr.asstring(buf.byteCount())
        fmt = buf.format().sampleFormat()
        
        dtype = np.float32 if fmt == QAudioFormat.SampleFormat.Float else np.int16
        data = np.frombuffer(raw, dtype=dtype)
        
        ch = buf.format().channelCount()
        self.accumulated_data.append(data[::ch] if ch > 1 else data)

    def _on_decoder_finished(self) -> None:
        if self.accumulated_data:
            self.waveform.set_samples(np.concatenate(self.accumulated_data))
        self.file_ready = True
        self.btnMain.setEnabled(True)
        self.btnMain.setText("Play")

    def _on_state_changed(self, state: QMediaPlayer.PlaybackState) -> None:
        self.btnMain.setText("Stop (Key to Interrupt)" if state == QMediaPlayer.PlaybackState.PlayingState else "Play")

    def _on_status_changed(self, status: QMediaPlayer.MediaStatus) -> None:
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.player.stop()

    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.stop()
        super().keyPressEvent(a0)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AudioApp()
    window.show()
    sys.exit(app.exec())