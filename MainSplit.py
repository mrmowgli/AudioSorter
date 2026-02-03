import sys
import os
import numpy as np
from PyQt6.QtWidgets import QApplication, QMainWindow
from PyQt6.QtGui import QFileSystemModel
from PyQt6.QtCore import QUrl, QDir, QModelIndex
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtMultimedia import (QMediaPlayer, QAudioOutput, QAudioDecoder, 
                                 QAudioBuffer, QAudioFormat)
from PyQt6 import uic

class AudioApp(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        uic.loadUi("player.ui", self)

        # 1. Setup File System Model
        self.model = QFileSystemModel()
        home_path = QDir.homePath()
        self.model.setRootPath(home_path)
        
        # Filter for audio files only
        self.model.setNameFilters(["*.wav", "*.mp3", "*.flac", "*.m4a", "*.ogg"])
        self.model.setNameFilterDisables(False) # Hide non-matching files

        # Setup TreeView
        self.treeView.setModel(self.model)
        self.treeView.setRootIndex(self.model.index(home_path))
        self.treeView.setColumnWidth(0, 250) # Make filename column wider
        self.treeView.doubleClicked.connect(self.on_file_selected)

        # 2. Multimedia Engine
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        
        self.decoder = QAudioDecoder()
        self.decoder.bufferReady.connect(self._process_buffer)
        self.decoder.finished.connect(self._on_decoder_finished)
        
        self.accumulated_data: list[np.ndarray] = []
        self.current_path = ""

        # 3. Connections
        self.btnMain.clicked.connect(self.toggle_playback)
        self.player.playbackStateChanged.connect(self._on_state_changed)
        self.player.mediaStatusChanged.connect(self._on_status_changed)

    def on_file_selected(self, index: QModelIndex) -> None:
        path = self.model.filePath(index)
        if not os.path.isdir(path):
            self.load_and_play(path)

    def load_and_play(self, path: str) -> None:
        # One-shot logic: Stop existing playback
        self.player.stop()
        self.current_path = path
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
        
        self.btnMain.setEnabled(True)
        self.player.play() # Auto-play once decoded

    def toggle_playback(self) -> None:
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.stop()
        else:
            self.player.play()

    def _on_state_changed(self, state: QMediaPlayer.PlaybackState) -> None:
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.btnMain.setText("Stop (Key to Interrupt)")
        else:
            self.btnMain.setText("Play Selection")

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
