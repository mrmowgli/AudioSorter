import sys
import importlib.util
import os

def check_dependencies():
    """Checks for required packages before launching the main app logic."""
    required = {
        "PyQt6": "UI Framework",
        "numpy": "Audio Processing",
        "qt_material": "Theme Engine"
    }
    
    missing = []
    for pkg, purpose in required.items():
        if importlib.util.find_spec(pkg) is None:
            missing.append(f"• {pkg} ({purpose})")
            
    if missing:
        # We try to use a basic message box if PyQt6 is available, 
        # otherwise we fallback to terminal.
        error_msg = "Missing required dependencies:\n\n" + "\n".join(missing)
        print(f"CRITICAL ERROR:\n{error_msg}")
        
        try:
            from PyQt6.QtWidgets import QApplication, QMessageBox
            app = QApplication(sys.argv)
            QMessageBox.critical(None, "Startup Error", error_msg)
        except ImportError:
            pass
        sys.exit(1)

check_dependencies()

import shutil
import numpy as np

from PyQt6 import uic
from PyQt6.QtCore import QUrl, QDir, QModelIndex, QItemSelection, Qt, QTimer, QSettings
from PyQt6.QtGui import QFileSystemModel, QKeyEvent, QColor, QIcon
from PyQt6.QtWidgets import (QApplication, QMainWindow, QFileDialog, QTableWidgetItem, 
                             QHeaderView, QDialog, QVBoxLayout, QLabel, QDialogButtonBox, QPushButton)
from PyQt6.QtMultimedia import (QMediaPlayer, QAudioOutput, QAudioDecoder, 
                                 QAudioBuffer, QAudioFormat)

from qt_material import apply_stylesheet
from level_meter import LevelMeter

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

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
        uic.loadUi(resource_path("AudioSorter.ui"), self)

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

        self.meter_smooth_value = 0.0

    # --- Menu Implementation Methods ---

    def menu_open_folder(self):
        """Changes the root directory of the file explorer."""
        folder = QFileDialog.getExistingDirectory(self, "Select Audio Directory", QDir.homePath())
        if folder:
            self.treeView.setRootIndex(self.model.index(folder))
            self.statusbar.showMessage(f"Navigated to: {folder}", 3000)

    def menu_show_preferences(self):
        """Launches preferences and saves the new root path."""
        current_root = self.settings.value("browser_root", QDir.homePath())
        dialog = PreferencesDialog(current_root, self)
        
        if dialog.exec():
            new_path = dialog.selected_path
            self.settings.setValue("browser_root", new_path)
            
            # Apply immediately to the tree view
            self.treeView.setRootIndex(self.model.index(new_path))
            self.statusbar.showMessage("Default folder updated.", 2000)

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
        """Modified to ensure QSettings saves immediately when a slot changes."""
        if column == 1:
            folder = QFileDialog.getExistingDirectory(self, f"Select Folder for Key {row+1}")
            if folder:
                self.tableFolders.item(row, 1).setText(folder)
                self.settings.setValue(f"slot_{row}", folder)
                self.settings.sync() # Force write to disk
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
        """Syncs the LevelMeter with log scaling and gravity."""
        if not hasattr(self, 'volume_profile') or not self.volume_profile:
            return

        pos_ms = self.player.position()
        frame_index = int(pos_ms / 20)
        
        target_level = 0.0
        if frame_index < len(self.volume_profile):
            rms = self.volume_profile[frame_index]
            
            # 1. Convert RMS to dBFS (Decibels relative to Full Scale)
            # -60dB is basically silence, 0dB is clipping
            db = 20 * np.log10(rms + 1e-6) 
            
            # 2. Map -60dB...0dB to 0.0...1.0 for the UI
            # This makes "quiet" sounds actually show up on the bar
            target_level = max(0, (db + 60) / 60)

        # Apply "Gravity" (Smoothing)
        # If the new level is higher, jump to it. If lower, drift down slowly.
        if target_level > self.meter_smooth_value:
            self.meter_smooth_value = target_level
        else:
            self.meter_smooth_value *= 0.95 # Decay factor

        self.levelMeter.set_level(self.meter_smooth_value)

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
        """Handles post-decoding UI updates and starts playback."""
        if not self.accumulated_data:
            self.btnMain.setEnabled(True)
            self.btnMain.setText("Play Selection")
            return

        full_waveform = np.concatenate(self.accumulated_data)

        # Normalize the waveform if it's int16 so calculations are consistent
        if full_waveform.dtype == np.int16:
            full_waveform = full_waveform.astype(np.float32) / 32768.0

        # Calculate frames
        frame_size = int(self.current_sample_rate * 0.02) 
        self.volume_profile = []
        
        if frame_size > 0:
            for i in range(0, len(full_waveform), frame_size):
                chunk = full_waveform[i : i + frame_size]
                if len(chunk) == 0: continue
                # RMS calculation
                rms = np.sqrt(np.mean(chunk**2))
                self.volume_profile.append(rms)
        
        # Update Waveform widget
        if hasattr(self, 'waveform'):
            self.waveform.set_samples(full_waveform)

        # Calculate Peak
        peak = np.max(np.abs(full_waveform))
        if full_waveform.dtype == np.int16:
            peak /= 32768.0
        
        self.levelMeter.set_level(peak)
        db = 20 * np.log10(max(peak, 1e-5)) if peak > 0 else -100.0

        # Time Calculations
        sample_rate = self.current_sample_rate if self.current_sample_rate > 0 else 44100
        sample_count = len(full_waveform)
        total_seconds = sample_count / sample_rate
        
        minutes = int(total_seconds // 60)
        seconds = int(total_seconds % 60)
        centiseconds = int((total_seconds % 1) * 100)
        length_str = f"{minutes}'{seconds:02d}\"{centiseconds:02d}"

        codec = os.path.splitext(self.current_source_path)[1][1:].upper()
        
        # UI Update logic
        stats_text = (f"Samples: {sample_count} | Rate: {sample_rate} | "
                      f"Codec: {codec} | Length: {length_str} | Peak: {db:.1f} dB")
        
        if hasattr(self, 'lblStats'):
            self.lblStats.setText(stats_text)
        else:
            self.statusbar.showMessage(stats_text)

        self.btnMain.setEnabled(True)
        # Only auto-play if the player isn't already playing
        if self.player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
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

    def flash_row(self, row_index: int, color: QColor):
        # Save the current selection behavior
        old_palette = self.tableFolders.palette()
        
        # Create a palette with the flash color as the Highlight
        new_palette = self.tableFolders.palette()
        new_palette.setColor(self.tableFolders.palette().ColorGroup.All, 
                             self.tableFolders.palette().ColorRole.Highlight, color)
        
        self.tableFolders.setPalette(new_palette)
        self.tableFolders.selectRow(row_index)
        
        # Reset after 200ms
        QTimer.singleShot(200, lambda: self.tableFolders.setPalette(old_palette))
        QTimer.singleShot(200, lambda: self.tableFolders.clearSelection())

    def reset_row_color(self) -> None:
        # Clearing the stylesheet returns it to the 'qt-material' default
        self.tableFolders.setStyleSheet("")

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
        """Restores the browser root and the 5 destination slots."""
        # 1. Restore Browser Root
        default_root = self.settings.value("browser_root", QDir.homePath())
        if os.path.exists(default_root):
            self.treeView.setRootIndex(self.model.index(default_root))
        
        # 2. Restore Destination Slots
        for i in range(self.max_folders):
            saved_path = self.settings.value(f"slot_{i}", "")
            item = self.tableFolders.item(i, 1)
            # Ensure path exists and item is valid before setting
            if item and saved_path and os.path.exists(str(saved_path)):
                item.setText(str(saved_path))
            elif item:
                item.setText("None - Double click to set folder")


class PreferencesDialog(QDialog):
    def __init__(self, current_root, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.setMinimumWidth(400)
        
        layout = QVBoxLayout(self)
        
        # Section 1: Default Browser Path
        self.group_label = QLabel("<b>File Browser Settings</b>")
        layout.addWidget(self.group_label)
        
        self.path_display = QLabel(f"Current Start Folder:\n{current_root}")
        self.path_display.setWordWrap(True)
        self.path_display.setStyleSheet("color: #888; padding: 5px;")
        layout.addWidget(self.path_display)
        
        self.btn_browse = QPushButton("Change Default Start Folder")
        self.btn_browse.clicked.connect(self.pick_folder)
        layout.addWidget(self.btn_browse)

        layout.addSpacing(20) # Visual gap
        
        # Section 2: Instructions
        self.info_label = QLabel("<i>Note: Destination slots are saved automatically when changed in the main table.</i>")
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)
        
        # Buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)
        
        self.selected_path = current_root

    def pick_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Default Directory", self.selected_path)
        if folder:
            self.selected_path = folder
            self.path_display.setText(f"Current Start Folder:\n{folder}")



if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon("audiosorter.png"))
    window = AudioApp()
    apply_stylesheet(app, theme=resource_path('dark_teal.xml'))
    window.show()
    sys.exit(app.exec())
