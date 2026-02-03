import sys
import numpy as np
from PyQt6.QtWidgets import QApplication, QMainWindow, QFileDialog
from PyQt6.QtCore import QUrl, uic
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtMultimedia import (QMediaPlayer, QAudioOutput, QAudioDecoder, 
                                 QAudioBuffer, QAudioFormat)

# Import our UI class
from ui_player import Ui_AudioPlayer

class AudioApp(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.ui = Ui_AudioPlayer()
        self.ui.setupUi(self)
        self.setWindowTitle("Audio Sorter")

        # 1. Initialize Multimedia Engine
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        
        # 2. Decoder for extraction
        self.decoder = QAudioDecoder()
        self.decoder.bufferReady.connect(self._process_buffer)
        self.decoder.finished.connect(self._on_decoder_finished)
        self.accumulated_data: list[np.ndarray] = []

        # 3. Connect Signals
        self.ui.btnMain.clicked.connect(self.handle_interaction)
        self.player.playbackStateChanged.connect(self._on_state_changed)
        self.player.mediaStatusChanged.connect(self._on_status_changed)

        self.file_ready = False

    def handle_interaction(self) -> None:
        if not self.file_ready:
            self.load_file()
        else:
            if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                self.player.stop()
            else:
                self.player.play()

    def load_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Audio", "", "Audio (*.wav *.mp3 *.flac *.m4a *.ogg)"
        )
        if path:
            self.file_ready = False
            self.accumulated_data = []
            self.ui.btnMain.setText("Decoding...")
            self.ui.btnMain.setEnabled(False)
            
            url = QUrl.fromLocalFile(path)
            self.decoder.setSource(url)
            self.player.setSource(url)
            self.decoder.start()

    def _process_buffer(self) -> None:
        buffer: QAudioBuffer = self.decoder.read()
        if not buffer.isValid():
            return

        # Linter-safe buffer extraction
        ptr = buffer.constData()
        raw_bytes = ptr.asstring(buffer.byteCount())
        fmt = buffer.format().sampleFormat()
        
        # Handle bit-depth conversion
        if fmt == QAudioFormat.SampleFormat.Int16:
            data = np.frombuffer(raw_bytes, dtype=np.int16)
        elif fmt == QAudioFormat.SampleFormat.Float:
            data = np.frombuffer(raw_bytes, dtype=np.float32)
        else:
            data = np.frombuffer(raw_bytes, dtype=np.int16)

        # Downmix to mono for visualization
        channels = buffer.format().channelCount()
        self.accumulated_data.append(data[::channels] if channels > 1 else data)

    def _on_decoder_finished(self) -> None:
        if self.accumulated_data:
            full_waveform = np.concatenate(self.accumulated_data)
            self.ui.waveform.set_samples(full_waveform)
        
        self.file_ready = True
        self.ui.btnMain.setEnabled(True)
        self.ui.btnMain.setText("Play")

    def _on_state_changed(self, state: QMediaPlayer.PlaybackState) -> None:
        # Toggle button text based on playback state
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.ui.btnMain.setText("Stop (Press Key to Interrupt)")
        else:
            self.ui.btnMain.setText("Play")

    def _on_status_changed(self, status: QMediaPlayer.MediaStatus) -> None:
        # If song ends naturally, stop the player to reset position
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.player.stop()

    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        # The One-Shot requirement: Any key press halts playback
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.stop()
        super().keyPressEvent(a0)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AudioApp()
    window.show()
    sys.exit(app.exec())