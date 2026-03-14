import sys
import importlib.util
import os
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

def check_dependencies():
    """
    Verifies environment before UI initialization to prevent silent crashes.
    Add any new third-party requirements to the 'required' dict.
    """
    required = {
        "PyQt6": "UI Framework",
        "numpy": "Audio Processing",
        "qt_material": "Theme Engine"
    }
    
    missing = [f"• {pkg} ({purpose})" for pkg, purpose in required.items() 
               if importlib.util.find_spec(pkg) is None]
            
    if missing:
        error_msg = "Missing required dependencies:\n\n" + "\n".join(missing)
        print(f"CRITICAL ERROR:\n{error_msg}")
        
        # Fallback to GUI error if PyQt6 happened to be installed but others weren't
        try:
            from PyQt6.QtWidgets import QApplication, QMessageBox
            app = QApplication(sys.argv)
            QMessageBox.critical(None, "Startup Error", error_msg)
        except ImportError:
            pass
        sys.exit(1)

def resource_path(relative_path):
    """
    Handles file resolution for both raw python execution and PyInstaller bundles.
    PyInstaller unpacks data to a temporary folder stored in sys._MEIPASS.
    """
    base_path = getattr(sys, '_MEIPASS', os.path.abspath("."))
    return os.path.join(base_path, relative_path)

class PreferencesDialog(QDialog):
    """
    Modal for global app configuration. 
    New settings (e.g. sample rate prefs) should be added to this layout.
    """
    def __init__(self, current_root, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.setMinimumWidth(400)
        self.selected_path = current_root
        
        layout = QVBoxLayout(self)
        
        # File Browser Config
        layout.addWidget(QLabel("<b>File Browser Settings</b>"))
        self.path_display = QLabel(f"Current Start Folder:\n{current_root}")
        self.path_display.setWordWrap(True)
        self.path_display.setStyleSheet("color: #888; padding: 5px;")
        layout.addWidget(self.path_display)
        
        self.btn_browse = QPushButton("Change Default Start Folder")
        self.btn_browse.clicked.connect(self.pick_folder)
        layout.addWidget(self.btn_browse)

        layout.addSpacing(20)
        
        layout.addWidget(QLabel("<i>Note: Destination slots are saved automatically.</i>"))
        
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def pick_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Default Directory", self.selected_path)
        if folder:
            self.selected_path = folder
            self.path_display.setText(f"Current Start Folder:\n{folder}")

class AudioApp(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        # Load external .ui file created in Qt Designer
        uic.loadUi(resource_path("AudioSorter.ui"), self)

        # Persistent storage (Registry on Windows, .plist on macOS, .conf on Linux)
        self.settings = QSettings("AndNinjas", "AudioSorter")
        
        # --- Internal State ---
        self.supported_exts = {'.wav', '.ogg', '.aiff', '.mp3', '.mp4', '.m4a', '.flac'}
        self.max_folders = 5
        self.current_sample_rate = 44100 
        self.accumulated_data: list[np.ndarray] = []
        self.current_source_path = ""
        self.meter_smooth_value = 0.0

        self.setup_ui_components()
        self.setup_multimedia()
        self.load_saved_configs()

    def setup_ui_components(self):
        """Initializes complex widgets and event filters."""
        # File System Tree
        self.model = QFileSystemModel()
        self.model.setRootPath(QDir.homePath())
        self.model.setNameFilters([f"*{ext}" for ext in self.supported_exts])
        self.model.setNameFilterDisables(False)

        self.treeView.setModel(self.model)
        self.treeView.setColumnWidth(0, 250)
        self.treeView.selectionModel().selectionChanged.connect(self.on_selection_changed)
        
        # Folder Mapping Table
        self.tableFolders.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tableFolders.setEditTriggers(self.tableFolders.EditTrigger.NoEditTriggers)
        for i in range(self.max_folders):
            self.tableFolders.setItem(i, 0, QTableWidgetItem(f"Key {i+1}"))
            self.tableFolders.setItem(i, 1, QTableWidgetItem("None - Double click to set folder"))
        self.tableFolders.cellDoubleClicked.connect(self.set_row_folder)

        # Menu Action Connections
        self.action_Open_Folder.triggered.connect(self.menu_open_folder)
        self.action_Preferences.triggered.connect(self.menu_show_preferences)
        self.actionE_xit.triggered.connect(self.close)
        self.actionAbout_Sound_Organizer.triggered.connect(self.menu_show_about)

        # Required to capture key presses while the tree view has focus
        self.treeView.installEventFilter(self)

    def setup_multimedia(self):
        """Prepares playback and background decoding engines."""
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        
        # QAudioDecoder is used to generate the visual waveform and level data
        self.decoder = QAudioDecoder()
        self.decoder.bufferReady.connect(self._process_buffer)
        self.decoder.finished.connect(self._on_decoder_finished)

        self.btnMain.clicked.connect(self.toggle_playback)
        self.player.playbackStateChanged.connect(self._on_state_changed)
        self.player.mediaStatusChanged.connect(self._on_status_changed)

        # Timer for the VU meter (runs at ~50fps)
        self.meter_timer = QTimer()
        self.meter_timer.setInterval(20)
        self.meter_timer.timeout.connect(self.update_live_meter)
        self.player.playbackStateChanged.connect(self._handle_timer_state)

    # --- Core Logic ---

    def load_and_play(self, path: str) -> None:
        """
        Resets engines and starts decoding a new file. 
        Playback begins automatically via _on_decoder_finished.
        """
        self.player.stop()
        self.decoder.stop() 
        self.current_source_path = path
        self.accumulated_data = []
        self.btnMain.setText("Decoding...")
        self.btnMain.setEnabled(False)
        
        source = QUrl.fromLocalFile(path)
        self.decoder.setSource(source)
        self.player.setSource(source)
        self.decoder.start()

    def _process_buffer(self) -> None:
        """Reads raw PCM data from the decoder for analysis."""
        buf: QAudioBuffer = self.decoder.read()
        if not buf.isValid(): return

        if not self.accumulated_data:
            self.current_sample_rate = buf.format().sampleRate()

        ptr = buf.constData()
        raw = ptr.asstring(buf.byteCount())
        
        # Convert to float32 for normalized processing across different file formats
        fmt = buf.format().sampleFormat()
        dtype = np.float32 if fmt == QAudioFormat.SampleFormat.Float else np.int16
        data = np.frombuffer(raw, dtype=dtype)
        
        ch = buf.format().channelCount()
        self.accumulated_data.append(data[::ch] if ch > 1 else data)

    def _on_decoder_finished(self) -> None:
        """Post-processing: Normalization, peak detection, and UI stats update."""
        if not self.accumulated_data:
            self.btnMain.setEnabled(True)
            self.btnMain.setText("Play Selection")
            return

        full_waveform = np.concatenate(self.accumulated_data)
        if full_waveform.dtype == np.int16:
            full_waveform = full_waveform.astype(np.float32) / 32768.0

        # Create volume profile for the level meter (20ms frames)
        frame_size = int(self.current_sample_rate * 0.02) 
        self.volume_profile = [np.sqrt(np.mean(full_waveform[i:i+frame_size]**2)) 
                               for i in range(0, len(full_waveform), frame_size) 
                               if len(full_waveform[i:i+frame_size]) > 0]
        
        if hasattr(self, 'waveform'):
            self.waveform.set_samples(full_waveform)

        # File Stats Calculation
        peak = np.max(np.abs(full_waveform))
        db = 20 * np.log10(max(peak, 1e-5))
        total_seconds = len(full_waveform) / (self.current_sample_rate or 44100)
        
        length_str = f"{int(total_seconds//60)}'{int(total_seconds%60):02d}\"{int((total_seconds%1)*100):02d}"
        codec = os.path.splitext(self.current_source_path)[1][1:].upper()
        
        stats_text = (f"Samples: {len(full_waveform)} | Rate: {self.current_sample_rate} | "
                      f"Codec: {codec} | Length: {length_str} | Peak: {db:.1f} dB")
        
        if hasattr(self, 'lblStats'): self.lblStats.setText(stats_text)
        else: self.statusbar.showMessage(stats_text)

        self.btnMain.setEnabled(True)
        if self.player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
            self.player.play()

    def update_live_meter(self):
        """
        Maps RMS values to a logarithmic dBFS scale for the UI.
        Implements a 'decay' factor to make the meter feel responsive but smooth.
        """
        if not hasattr(self, 'volume_profile') or not self.volume_profile:
            return

        # Estimate current frame based on playback position
        frame_index = int(self.player.position() / 20)
        
        target_level = 0.0
        if frame_index < len(self.volume_profile):
            rms = self.volume_profile[frame_index]
            db = 20 * np.log10(rms + 1e-6) 
            target_level = max(0, (db + 60) / 60) # Map -60...0 to 0...1

        # Smooth gravity logic
        if target_level > self.meter_smooth_value:
            self.meter_smooth_value = target_level
        else:
            self.meter_smooth_value *= 0.92 # Decay

        self.levelMeter.set_level(self.meter_smooth_value)

    def copy_to_slot(self, slot_index: int) -> None:
        """Orchestrates file copy and provides visual feedback on success/failure."""
        if not self.current_source_path:
            return

        target_dir = self.tableFolders.item(slot_index, 1).text()
        if "None" in target_dir:
            self.statusbar.showMessage("Error: Slot not configured!", 3000)
            return

        try:
            filename = os.path.basename(self.current_source_path)
            dest = os.path.join(target_dir, filename)
            
            if os.path.exists(dest):
                self.statusbar.showMessage(f"Exists: {filename}", 2000)
                self.flash_row(slot_index, QColor(255, 165, 0)) # Orange
            else:
                shutil.copy2(self.current_source_path, dest)
                self.statusbar.showMessage(f"Copied to Slot {slot_index+1}", 2000)
                self.flash_row(slot_index, QColor(0, 255, 100)) # Green
        except Exception as e:
            self.flash_row(slot_index, QColor(255, 50, 50)) # Red
            self.statusbar.showMessage(f"Error: {e}", 5000)

    def flash_row(self, row_index: int, color: QColor):
        """Momentarily highlights a table row to confirm an action."""
        old_palette = self.tableFolders.palette()
        new_palette = self.tableFolders.palette()
        new_palette.setColor(new_palette.ColorGroup.All, new_palette.ColorRole.Highlight, color)
        
        self.tableFolders.setPalette(new_palette)
        self.tableFolders.selectRow(row_index)
        
        QTimer.singleShot(250, lambda: self.tableFolders.setPalette(old_palette))
        QTimer.singleShot(250, lambda: self.tableFolders.clearSelection())

    # --- UI Event Handlers ---

    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        """Global hotkeys for the main window (1-5 for sorting)."""
        if not a0: return
        key = a0.key()
        if Qt.Key.Key_1 <= key <= Qt.Key.Key_5:
            self.copy_to_slot(key - Qt.Key.Key_1)
            return
        super().keyPressEvent(a0)

    def eventFilter(self, source, event):
        """Captures hotkeys specifically when the treeView has focus."""
        if event.type() == event.Type.KeyPress and source is self.treeView:
            key = event.key()
            if Qt.Key.Key_1 <= key <= Qt.Key.Key_5:
                self.copy_to_slot(key - Qt.Key.Key_1)
                return True
        return super().eventFilter(source, event)

    def on_selection_changed(self, selected, deselected) -> None:
        indexes = self.treeView.selectionModel().selectedIndexes()
        if not indexes: return
        path = self.model.filePath(indexes[0])
        if not os.path.isdir(path):
            _, ext = os.path.splitext(path.lower())
            if ext in self.supported_exts:
                self.load_and_play(path)

    def set_row_folder(self, row, column):
        if column == 1:
            folder = QFileDialog.getExistingDirectory(self, f"Select Folder for Key {row+1}")
            if folder:
                self.tableFolders.item(row, 1).setText(folder)
                self.settings.setValue(f"slot_{row}", folder)
                self.settings.sync() 

    def load_saved_configs(self):
        default_root = self.settings.value("browser_root", QDir.homePath())
        if os.path.exists(default_root):
            self.treeView.setRootIndex(self.model.index(default_root))
        
        for i in range(self.max_folders):
            saved_path = self.settings.value(f"slot_{i}", "")
            item = self.tableFolders.item(i, 1)
            if item:
                if saved_path and os.path.exists(str(saved_path)):
                    item.setText(str(saved_path))
                else:
                    item.setText("None - Double click to set folder")

    def menu_open_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Audio Directory", QDir.homePath())
        if folder:
            self.treeView.setRootIndex(self.model.index(folder))

    def menu_show_preferences(self):
        current_root = self.settings.value("browser_root", QDir.homePath())
        dialog = PreferencesDialog(current_root, self)
        if dialog.exec():
            new_path = dialog.selected_path
            self.settings.setValue("browser_root", new_path)
            self.treeView.setRootIndex(self.model.index(new_path))

    def menu_show_about(self):
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.about(self, "About Audio Sorter", "Audio Sorter v1.0\nBuilt with PyQt6 and NumPy.")

    def toggle_playback(self) -> None:
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.stop()
        else: self.player.play()

    def _on_state_changed(self, state: QMediaPlayer.PlaybackState) -> None:
        self.btnMain.setText("Stop" if state == QMediaPlayer.PlaybackState.PlayingState else "Play Selection")

    def _on_status_changed(self, status: QMediaPlayer.MediaStatus) -> None:
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.player.stop()

    def _handle_timer_state(self, state):
        if state == QMediaPlayer.PlaybackState.PlayingState: self.meter_timer.start()
        else:
            self.meter_timer.stop()
            self.levelMeter.set_level(0)

if __name__ == "__main__":
    check_dependencies()
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon("audiosorter.png"))
    
    # Global Theme Application
    apply_stylesheet(app, theme=resource_path('dark_teal.xml'))
    
    window = AudioApp()
    window.show()
    sys.exit(app.exec())