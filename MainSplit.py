import sys
import os
import shutil
import numpy as np
from PyQt6.QtWidgets import QApplication, QMainWindow, QFileDialog, QTableWidgetItem, QHeaderView
from PyQt6.QtGui import QFileSystemModel, QKeyEvent 
from PyQt6.QtCore import QUrl, QDir, QModelIndex, QItemSelection, Qt
from PyQt6.QtMultimedia import (QMediaPlayer, QAudioOutput, QAudioDecoder, 
                                 QAudioBuffer, QAudioFormat)
from PyQt6 import uic

class AudioApp(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        uic.loadUi("player.ui", self)

        # 1. Setup File System Explorer
        self.model = QFileSystemModel()
        self.model.setRootPath(QDir.homePath())
        self.supported_exts = {'.wav', '.ogg', '.aiff', '.mp3', '.mp4', '.m4a', '.flac'}
        self.model.setNameFilters([f"*{ext}" for ext in self.supported_exts])
        self.model.setNameFilterDisables(False)

        self.treeView.setModel(self.model)
        self.treeView.setRootIndex(self.model.index(QDir.homePath()))
        self.treeView.setColumnWidth(0, 250)
        self.treeView.selectionModel().selectionChanged.connect(self.on_selection_changed)

        # 2. Setup Folder Mapping Table
        self.setup_folder_table()

        # 3. Multimedia Engine
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.decoder = QAudioDecoder()
        self.decoder.bufferReady.connect(self._process_buffer)
        self.decoder.finished.connect(self._on_decoder_finished)
        
        self.accumulated_data: list[np.ndarray] = []
        self.current_source_path = ""

        # 4. Connections
        self.btnMain.clicked.connect(self.toggle_playback)
        self.player.playbackStateChanged.connect(self._on_state_changed)
        self.player.mediaStatusChanged.connect(self._on_status_changed)

    def setup_folder_table(self):
        self.tableFolders.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tableFolders.setEditTriggers(self.tableFolders.EditTrigger.NoEditTriggers)
        
        for i in range(4):
            self.tableFolders.setItem(i, 0, QTableWidgetItem(f"Key {i+1}"))
            self.tableFolders.setItem(i, 1, QTableWidgetItem("None - Double click to set folder"))
        
        self.tableFolders.cellDoubleClicked.connect(self.set_row_folder)

    def set_row_folder(self, row, column):
        if column == 1:
            folder = QFileDialog.getExistingDirectory(self, f"Select Folder for Key {row+1}")
            if folder:
                self.tableFolders.item(row, 1).setText(folder)

    def on_selection_changed(self, selected: QItemSelection, deselected: QItemSelection) -> None:
        indexes = selected.indexes()
        if not indexes: return
        path = self.model.filePath(indexes[0])
        if not os.path.isdir(path):
            _, ext = os.path.splitext(path.lower())
            if ext in self.supported_exts:
                self.load_and_play(path)

    def load_and_play(self, path: str) -> None:
        self.player.stop()
        self.decoder.stop() 
        self.current_source_path = path
        self.accumulated_data = []
        self.btnMain.setText("Decoding...")
        self.btnMain.setEnabled(False)
        self.decoder.setSource(QUrl.fromLocalFile(path))
        self.player.setSource(QUrl.fromLocalFile(path))
        self.decoder.start()

    def _process_buffer(self) -> None:
        buf: QAudioBuffer = self.decoder.read()
        if not buf.isValid(): return
        ptr = buf.constData()
        raw = ptr.asstring(buf.byteCount())
        data = np.frombuffer(raw, dtype=np.float32 if buf.format().sampleFormat() == QAudioFormat.SampleFormat.Float else np.int16)
        ch = buf.format().channelCount()
        self.accumulated_data.append(data[::ch] if ch > 1 else data)

    def _on_decoder_finished(self) -> None:
        if self.accumulated_data:
            self.waveform.set_samples(np.concatenate(self.accumulated_data))
        self.btnMain.setEnabled(True)
        self.player.play()

    def copy_to_slot(self, slot_index: int) -> None:
        target_dir = self.tableFolders.item(slot_index, 1).text()
        if "None" in target_dir or not self.current_source_path:
            self.statusbar.showMessage("Error: Slot not configured!", 3000)
            return

        try:
            filename = os.path.basename(self.current_source_path)
            dest = os.path.join(target_dir, filename)
            if os.path.exists(dest):
                self.statusbar.showMessage(f"Exists: {filename}", 2000)
            else:
                shutil.copy2(self.current_source_path, dest)
                self.statusbar.showMessage(f"Copied to Slot {slot_index+1}: {filename}", 2000)
        except Exception as e:
            self.statusbar.showMessage(f"Error: {e}", 5000)

    def toggle_playback(self) -> None:
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.stop()
        else:
            self.player.play()

    def _on_state_changed(self, state: QMediaPlayer.PlaybackState) -> None:
        self.btnMain.setText("Stop" if state == QMediaPlayer.PlaybackState.PlayingState else "Play Selection")

    def _on_status_changed(self, status: QMediaPlayer.MediaStatus) -> None:
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.player.stop()

    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        if not a0: return
        key = a0.key()
        
        # Keys 1-4 for multi-slot sorting
        if Qt.Key.Key_1 <= key <= Qt.Key.Key_4:
            slot = key - Qt.Key.Key_1
            self.copy_to_slot(slot)
        elif self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.stop()
        super().keyPressEvent(a0)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AudioApp()
    window.show()
    sys.exit(app.exec())