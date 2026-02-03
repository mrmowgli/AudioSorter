import sys
import os
import numpy as np
# Correct PyQt6 Imports
from PyQt6.QtWidgets import QApplication, QMainWindow
from PyQt6.QtGui import QFileSystemModel, QKeyEvent 
from PyQt6.QtCore import QUrl, QDir, QModelIndex, QItemSelection
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
        
        # Supported extensions
        self.supported_exts = {'.wav', '.ogg', '.aiff', '.mp3', '.mp4', '.m4a', '.flac'}
        self.model.setNameFilters([f"*{ext}" for ext in self.supported_exts])
        self.model.setNameFilterDisables(False)

        # Setup TreeView
        self.treeView.setModel(self.model)
        self.treeView.setRootIndex(self.model.index(home_path))
        self.treeView.setColumnWidth(0, 250)
        
        # Fix: Connect to selection changes instead of double-click
        self.treeView.selectionModel().selectionChanged.connect(self.on_selection_changed)

        # 2. Multimedia Engine
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        
        self.decoder = QAudioDecoder()
        self.decoder.bufferReady.connect(self._process_buffer)
        self.decoder.finished.connect(self._on_decoder_finished)
        
        self.accumulated_data: list[np.ndarray] = []

        # 3. Connections
        self.btnMain.clicked.connect(self.toggle_playback)
        self.player.playbackStateChanged.connect(self._on_state_changed)
        self.player.mediaStatusChanged.connect(self._on_status_changed)

    def on_selection_changed(self, selected: QItemSelection, deselected: QItemSelection) -> None:
        # Get the indexes of the newly selected item
        indexes = selected.indexes()
        if not indexes:
            return
        
        # We only care about the first column (the filename/path)
        index = indexes[0]
        path = self.model.filePath(index)
        
        # Check if it's a file and has a supported extension
        if not os.path.isdir(path):
            _, ext = os.path.splitext(path.lower())
            if ext in self.supported_exts:
                self.load_and_play(path)

    def load_and_play(self, path: str) -> None:
        # Stop any current playback/decoding immediately
        self.player.stop()
        self.decoder.stop() 
        
        self.accumulated_data = []
        self.ui_loading_state()
        
        url = QUrl.fromLocalFile(path)
        self.decoder.setSource(url)
        self.player.setSource(url)
        self.decoder.start()

    def ui_loading_state(self) -> None:
        self.btnMain.setText("Decoding...")
        self.btnMain.setEnabled(False)

    def _process_buffer(self) -> None:
        buf: QAudioBuffer = self.decoder.read()
        if not buf.isValid(): return
        
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
        # One-shot Auto-play
        self.player.play()

    def toggle_playback(self) -> None:
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.stop()
        else:
            self.player.play()

    def _on_state_changed(self, state: QMediaPlayer.PlaybackState) -> None:
        self.btnMain.setText("Stop (Key to Interrupt)" if state == QMediaPlayer.PlaybackState.PlayingState else "Play Selection")

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