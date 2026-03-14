import sys
import os
import shutil
import numpy as np

from PyQt6 import uic
from PyQt6.QtCore import QUrl, QDir, QModelIndex, QItemSelection, Qt, QTimer, QSettings
from PyQt6.QtGui import QFileSystemModel, QKeyEvent, QColor
from PyQt6.QtWidgets import (QApplication, QMainWindow, QFileDialog, QTableWidgetItem, 
                             QHeaderView, QDialog, QVBoxLayout, QLabel, QDialogButtonBox)
from PyQt6.QtMultimedia import (QMediaPlayer, QAudioOutput, QAudioDecoder, 
                                 QAudioBuffer, QAudioFormat)

from qt_material import apply_stylesheet
from level_meter import LevelMeter

# --- New Preferences Dialog Class ---
class PreferencesDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.setMinimumWidth(300)
        
        layout = QVBoxLayout(self)
        
        # You can add actual settings widgets here (checkboxes, combos, etc.)
        self.info_label = QLabel("Audio Sorter Settings\n\nCustomizations and UI tweaks can be added here.")
        layout.addWidget(self.info_label)
        
        # Standard OK/Cancel buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

class AudioApp(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        uic.loadUi("AudioSorter.ui", self)

        self.settings = QSettings("AndNinjas", "AudioSorter")
        self.apply_system_theme()

        # 1. Setup File System Explorer
        self.model = QFileSystemModel()
        self.model.setRootPath(QDir.homePath())
        self.supported_exts = {'.wav', '.ogg', '.aiff', '.mp3', '.mp4', '.m4a', '.flac'}
        self.max_folders = 5
        self.model.setNameFilters([f"*{ext}" for ext in self.supported_exts])
        self.model.setNameFilterDisables(False)

        self.treeView.setModel(self.model)
        self.treeView.setRootIndex(self.model.index(QDir.homePath()))
        self.treeView.setColumnWidth(0, 250)
        self.treeView.selectionModel().selectionChanged.connect(self.on_selection_changed)

        # 2. Setup Folder Mapping Table
        self.setup_folder_table()
        self.load_saved_configs() 

        # 3. Multimedia Engine
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.decoder = QAudioDecoder()
        self.decoder.bufferReady.connect(self._process_buffer)
        self.decoder.finished.connect(self._on_decoder_finished)
       
        # Needed to help calculate durations of samples.
        self.current_sample_rate = 44100  # Default fallback
        self.accumulated_data: list[np.ndarray] = []
        self.current_source_path = ""

        # 4. Connections & Menu Hooks
        self.btnMain.clicked.connect(self.toggle_playback)
        self.player.playbackStateChanged.connect(self._on_state_changed)
        self.player.mediaStatusChanged.connect(self._on_status_changed)

        # 5. Live Meter Timer
        self.meter_timer = QTimer()
        self.meter_timer.setInterval(20) # 50 times per second
        self.meter_timer.timeout.connect(self.update_live_meter)
        
        # Connect to player states
        self.player.playbackStateChanged.connect(self._handle_timer_state)
        
        # Connect Menu Actions from UI file
        self.action_Open_Folder.triggered.connect(self.menu_open_folder)
        self.action_Preferences.triggered.connect(self.menu_show_preferences)
        self.actionE_xit.triggered.connect(self.close)
        self.actionAbout_Sound_Organizer.triggered.connect(self.menu_show_about)

        self.treeView.installEventFilter(self)

    # --- Menu Implementation Methods ---

    def menu_open_folder(self):
        """Changes the root directory of the file explorer."""
        folder = QFileDialog.getExistingDirectory(self, "Select Audio Directory", QDir.homePath())
        if folder:
            self.treeView.setRootIndex(self.model.index(folder))
            self.statusbar.showMessage(f"Navigated to: {folder}", 3000)

    def menu_show_preferences(self):
        """Launches the preferences dialog."""
        dialog = PreferencesDialog(self)
        if dialog.exec():
            # Handle logic if user pressed "OK"
            self.statusbar.showMessage("Preferences updated.", 2000)

    def menu_show_about(self):
        """Simple info message."""
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.about(self, "About Audio Sorter", 
                          "Audio Sorter v1.0\nBuilt with PyQt6 and NumPy.\n\nA fast utility for organizing samples.")

    # --- Existing Methods ---

    def apply_system_theme(self):
        # Placeholder for theme logic
        pass

    def setup_folder_table(self):
        self.tableFolders.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tableFolders.setEditTriggers(self.tableFolders.EditTrigger.NoEditTriggers)
        for i in range(self.max_folders):
            self.tableFolders.setItem(i, 0, QTableWidgetItem(f"Key {i+1}"))
            self.tableFolders.setItem(i, 1, QTableWidgetItem("None - Double click to set folder"))
        self.tableFolders.cellDoubleClicked.connect(self.set_row_folder)

    def set_row_folder(self, row, column):
        if column == 1:
            folder = QFileDialog.getExistingDirectory(self, f"Select Folder for Key {row+1}")
            if folder:
                self.tableFolders.item(row, 1).setText(folder)
                self.settings.setValue(f"slot_{row}", folder)
                self.statusbar.showMessage(f"Saved Slot {row+1} configuration.", 2000)

    def on_selection_changed(self, selected: QItemSelection, deselected: QItemSelection) -> None:
        indexes = self.treeView.selectionModel().selectedIndexes()
        if not indexes: return
        path = self.model.filePath(indexes[0])
        if not os.path.isdir(path):
            _, ext = os.path.splitext(path.lower())
            if ext in self.supported_exts:
                self.current_source_path = path 
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

    # Needed to display periodic updates of our meter while a sample is playing
    def _handle_timer_state(self, state):
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.meter_timer.start()
        else:
            self.meter_timer.stop()
            self.levelMeter.set_level(0) # Reset meter on stop
 
    def update_live_meter(self):
        # QMediaPlayer doesn't expose raw samples easily during playback
        # but it does expose a 'volume' property. 
        # For true sample-based metering, we'd use a Probe, 
        # but for now, let's sync it to the player's peak output.
        
        # If your LevelMeter expects 0.0-1.0:
        # Note: Qt Multimedia 6.x metering requires a QAudioProbe 
        # or custom output. As a reliable shortcut for this app:
        level = self.audio_output.volume() 
        self.levelMeter.set_level(level)

    def _process_buffer(self) -> None:
        buf: QAudioBuffer = self.decoder.read()
        if not buf.isValid(): return

        # Capture the sample rate from the first valid buffer
        if not self.accumulated_data:
            self.current_sample_rate = buf.format().sampleRate()

        ptr = buf.constData()
        raw = ptr.asstring(buf.byteCount())
        data = np.frombuffer(raw, dtype=np.float32 if buf.format().sampleFormat() == QAudioFormat.SampleFormat.Float else np.int16)
        ch = buf.format().channelCount()
        self.accumulated_data.append(data[::ch] if ch > 1 else data)

    def _on_decoder_finished(self) -> None:
        if self.accumulated_data:
            full_waveform = np.concatenate(self.accumulated_data)
            self.waveform.set_samples(full_waveform)


            peak = np.max(np.abs(full_waveform))
            if full_waveform.dtype == np.int16:
                peak /= 32768.0
            

            self.levelMeter.set_level(peak)

            # Convert peak to Decibels (dBFS)
            # We use 1e-5 to avoid log10(0) errors
            db = 20 * np.log10(max(peak, 1e-5)) if peak > 0 else -100.0
            
            # --- 2. Metadata Extraction ---
            fmt = self.decoder.audioFormat()
            
            # --- 2. Accurate Time Calculation ---
            # Total seconds = total samples / samples per second
            # Use the rate we captured during processing
            sample_rate = self.current_sample_rate if self.current_sample_rate > 0 else 44100
            sample_count = len(full_waveform)
            total_seconds = sample_count / sample_rate if (sample_count and sample_rate) else 0
            
            minutes = int(total_seconds // 60)
            seconds = int(total_seconds % 60)
            # Calculate "centiseconds" (1/100th of a second) for the " format
            centiseconds = int((total_seconds % 1) * 100)
            
            length_str = f"{minutes}'{seconds:02d}\"{centiseconds:02d}"

            codec = os.path.splitext(self.current_source_path)[1][1:].upper()
            bit_depth = "32-bit Float" if fmt.sampleFormat() == QAudioFormat.SampleFormat.Float else "16-bit Int"

            # --- 3. Update the UI ---
            stats_text = (
                f"Samples: {sample_count} | "
                f"Samplerate: {self.current_sample_rate} | "
                f"Format: {bit_depth} | "
                f"Codec: {codec} | "
                f"Length: {length_str} | "
                f"Peak: {db:.1f} dB"
            )
            
            # Assuming you add a QLabel named 'lblStats' to your UI
            if hasattr(self, 'lblStats'):
                self.lblStats.setText(stats_text)
            else:
                # Fallback to status bar if the label isn't in the .ui yet
                # self.statusbar.showMessage(f"Loaded: {length_str} | {db:.1f} dB")
                self.statusbar.showMessage(f"{stats_text}")
        self.btnMain.setEnabled(True)
        self.player.play()

    def copy_to_slot(self, slot_index: int) -> None:
        if not self.current_source_path:
            indexes = self.treeView.selectionModel().selectedIndexes()
            if indexes:
                path = self.model.filePath(indexes[0])
                if not os.path.isdir(path):
                    self.current_source_path = path

        target_dir = self.tableFolders.item(slot_index, 1).text()
        if "None" in target_dir or not self.current_source_path:
            self.statusbar.showMessage("Error: Slot not configured!", 3000)
            return

        try:
            filename = os.path.basename(self.current_source_path)
            dest = os.path.join(target_dir, filename)
            if os.path.exists(dest):
                self.statusbar.showMessage(f"Exists: {filename}", 2000)
                self.flash_row(slot_index, QColor(255, 165, 0))
            else:
                shutil.copy2(self.current_source_path, dest)
                self.statusbar.showMessage(f"Copied to Slot {slot_index+1}: {filename}", 2000)
                self.flash_row(slot_index, QColor(0, 255, 100))
        except Exception as e:
            self.flash_row(slot_index, QColor(255, 50, 50))
            self.statusbar.showMessage(f"Error: {e}", 5000)

    def flash_row(self, row_index: int, color: QColor) -> None:
        for col in range(self.tableFolders.columnCount()):
            item = self.tableFolders.item(row_index, col)
            if item:
                item.setData(Qt.ItemDataRole.BackgroundRole, color)
        self.tableFolders.viewport().update()
        QTimer.singleShot(200, lambda: self.reset_row_color(row_index))

    def reset_row_color(self, row_index: int) -> None:
        for col in range(self.tableFolders.columnCount()):
            item = self.tableFolders.item(row_index, col)
            if item:
                item.setData(Qt.ItemDataRole.BackgroundRole, None)
        self.tableFolders.viewport().update()

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
        if Qt.Key.Key_1 <= key <= Qt.Key.Key_5:
            slot = key - Qt.Key.Key_1
            self.copy_to_slot(slot)
            return
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.stop()
        super().keyPressEvent(a0)

    def eventFilter(self, source, event):
        if event.type() == event.Type.KeyPress and source is self.treeView:
            key = event.key()
            if Qt.Key.Key_1 <= key <= Qt.Key.Key_5:
                slot = key - Qt.Key.Key_1
                self.copy_to_slot(slot)
                return True
        return super().eventFilter(source, event)

    def load_saved_configs(self):
        for i in range(self.max_folders):
            saved_path = self.settings.value(f"slot_{i}", "")
            if saved_path and os.path.exists(saved_path):
                self.tableFolders.item(i, 1).setText(saved_path)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AudioApp()
    apply_stylesheet(app, theme='dark_teal.xml')
    window.show()
    sys.exit(app.exec())
