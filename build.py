import subprocess
import sys
import os
import platform

def build_app():
    # 1. Configuration
    app_name = "AudioSorter"
    main_script = "main.py"
    icon_file = "icon.png"  # Ensure this exists
    
    # List your external files here: (source_path, destination_in_exe)
    assets = [
        ("AudioSorter.ui", "."),
        ("dark_teal.xml", ".")
    ]

    # 2. Handle OS-specific separators for --add-data
    # Windows uses ';', Linux/macOS uses ':'
    sep = ";" if platform.system() == "Windows" else ":"
    
    build_command = [
        "pyinstaller",
        "--noconfirm",
        "--onefile",
        "--windowed",
        f"--name={app_name}",
        f"--icon={icon_file}",
    ]

    # 3. Add the assets to the command
    for src, dest in assets:
        build_command.extend(["--add-data", f"{src}{sep}{dest}"])

    # 4. Explicitly collect QtMultimedia submodules to ensure audio drivers are bundled
    build_command.extend(["--collect-submodules", "PyQt6.QtMultimedia"])

    # 5. Add the main script
    build_command.append(main_script)

    # 6. Run the build
    print(f"--- Starting Build for {platform.system()} ---")
    try:
        subprocess.run(build_command, check=True)
        print("\n--- Build Successful! Check the 'dist' folder. ---")
    except subprocess.CalledProcessError as e:
        print(f"\n--- Build Failed! ---\n{e}")

if __name__ == "__main__":
    build_app()