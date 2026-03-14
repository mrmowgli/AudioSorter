# AudioSorter ⚡

![[AudioSorter_Screenshot.png]]

**AudioSorter** is a high-speed utility designed for sound designers, musicians, and foley artists who need to audition and organize large libraries of audio samples rapidly. Built with Python 3.14, PyQt6, and NumPy, it focuses on a "one-key" workflow to move files into categorized folders.

## ✨ Key Features

- **Rapid Auditioning**: Instant playback and waveform visualization upon selection.
    
- **Logarithmic Peak Metering**: Real-time bouncing VU meter with RMS-to-dB mapping and smooth gravity decay.
    
- **Keyboard-Driven Sorting**: Map 5 destination folders to keys `1`–`5` for instant, one-handed organization.
    
- **Smart Persistence**: Automatically remembers your last-used file browser directory and destination slots.
    
- **Modern UI**: Sleek "Dark Teal" material interface for low eye-strain during long sessions.
    


---

## 🎹 General Workflow

1. **Configure**: Double-click the path cells in the right-hand table to set your destination folders (e.g., "Kicks", "Snares", "Trash").
    
2. **Browse**: Use the file tree on the left to navigate your sample packs.
    
3. **Audition**: Click any audio file. It will play automatically and display its waveform, samplerate, and peak volume.
    
4. **Sort**: Press keys **1, 2, 3, 4, or 5** on your keyboard to instantly copy the current file to the corresponding folder. The row will flash **green** on success or **orange** if the file already exists.
    

---

## 🚀 Getting the App (Pre-built Binaries)

You don't need to install Python to use AudioSorter. We provide standalone executables for Windows and Linux.

1. Navigate to the **[Releases](https://www.google.com/search?q=https://github.com/your-username/AudioSorter/releases)** page.
    
2. Download the archive for your operating system:
    
    - **Windows**: `AudioSorter-Windows-latest.zip` (Run the `.exe`)
        
    - **Linux**: `AudioSorter-Ubuntu-latest.zip` (Run the binary; ensure it has execution permissions: `chmod +x AudioSorter`)
        

---

## 🛠️ Building from Source (Developers)

To ensure forward compatibility and a clean build, it is highly recommended to use a Virtual Environment (`venv`).

## 1. Clone the Repository

Bash

```
git clone https://github.com/your-username/AudioSorter.git
cd AudioSorter
```

## 2. Set Up a Virtual Environment

**Windows:**

PowerShell

```
python -m venv venv
.\venv\Scripts\activate
```

**macOS / Linux:**

Bash

```
python3 -m venv venv
source venv/bin/activate
```

## 3. Install Dependencies

Bash

```
pip install -r requirements.txt
```

## 4. Run the Application

Bash

```
python main.py
```

## 5. Create Your Own Executable

Run the automated build script to generate a bundled version in the `dist/` folder:

Bash

```
python build.py
```

---

## 📝 Requirements

- **Python**: 3.12+ (Tested up to 3.14)
    
- **Dependencies**: PyQt6, NumPy, qt-material, PyInstaller (for building)