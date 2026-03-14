# Contributing to AudioSorter ⚡

First off, thank you for considering contributing to AudioSorter! It’s people like you who make this tool better for the sound design community.

## 🛠️ Development Environment

We use **Python 3.14** and **PyQt6**. To maintain forward compatibility, we avoid deprecated NumPy calls and rely on the modern `QAudioSink` and `QAudioSource` API.

1. **Fork** the repository and clone it locally.
    
2. Set up a **Virtual Environment** as described in the [README.md](https://www.google.com/search?q=./README.md).
    
3. Ensure you have `qt-material` installed for consistent UI testing.
    

## 🤝 How Can You Help?

## 🐛 Bug Reports

- Use the GitHub Issue tracker.
    
- Include your Operating System (Windows/Linux/macOS).
    
- If the bug is audio-related, mention the file format (WAV, MP3, etc.) and your sample rate.
    

## ✨ Feature Requests

We aim to keep the UI minimal and fast. If you suggest a feature, think about how it can be controlled via **keyboard shortcuts** to maintain the "no-mouse" sorting workflow.

## 💻 Code Contributions

1. **Branching**: Create a branch for your feature (e.g., `feature/waveform-zoom` or `fix/peak-meter-flicker`).
    
2. **Style**: Follow PEP 8 guidelines.
    
3. **UI Changes**: If you modify `AudioSorter.ui`, please ensure it renders correctly at different window sizes (use Layouts!).
    
4. **Audio Threading**: Any heavy calculation (like RMS analysis) must stay off the Main GUI Thread to prevent UI freezing.
    

## 🚀 The Pull Request Process

1. Update the `README.md` if your change adds a new shortcut or setting.
    
2. Run `python build.py` to ensure your changes don't break the PyInstaller bundling process.
    
3. Submit your PR! A GitHub Action will automatically run to verify that your code builds on both Windows and Linux.
    

## 📜 Code of Conduct

Be kind and helpful. We are all here to build a great tool for creators.