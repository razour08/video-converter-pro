# 🎬 Video Converter Pro

A professional, high-performance desktop GUI and interactive CLI video conversion utility powered by **FFmpeg**. 

Designed with a premium dark theme inspired by the curated **Catppuccin Macchiato** palette, this application offers rapid GPU hardware-acceleration (NVIDIA, Intel, AMD), instant stream-copying container transitions, and advanced subtitle embedding.

---

## 🌟 Key Features

* **Sleek Catppuccin Dark Theme:** A premium, modern graphical user interface designed for visual excellence and smooth interactions.
* **GPU Hardware Acceleration:** Native configuration integration for:
  * **NVIDIA NVENC** (`h264_nvenc`, `hevc_nvenc`)
  * **Intel QuickSync - QSV** (`h264_qsv`, `hevc_qsv`)
  * **AMD AMF** (`h264_amf`, `hevc_amf`)
* **Multi-threaded CPU Conversion:** Automatically scales to exploit **all available cores and threads** (`-threads 0`) of your CPU.
* **Instant Stream Copying:** Remux containers (e.g., `.ts` to `.mp4`) in less than 2 seconds without re-encoding, ensuring 0% quality loss.
* **Advanced Subtitle Integrator:**
  * **Automatic Match:** Instantly detects matching `.srt` or `.vtt` files sharing the same base name.
  * **Manual Selector:** Browse and select custom subtitle files directly inside the interactive queue!
* **Dynamic Table Queue:** Set formats individually per file, see independent inline progress bars, file sizes, and status counters in real-time.
* **Real-time Live Console Logs:** View the active FFmpeg terminal outputs directly inside a dedicated tab in the app.
* **Full CLI Companion:** Run a colored, beautiful interactive console menu or automate actions using clean terminal commands.

---

## ⚙️ Prerequisites

1. **Python 3.8+** installed on your system.
2. **FFmpeg** installed and added to your system PATH, or placed locally in the application folder.
   * You can download highly optimized pre-built FFmpeg binaries directly from the official [BtbN FFmpeg Builds Releases](https://github.com/BtbN/FFmpeg-Builds/releases).
   * *If FFmpeg is not detected, the GUI will automatically prompt you with a file-browse dialog to locate `ffmpeg.exe` on your system and save it permanently.*

---

## 🚀 Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/razour08/video-converter-pro.git
   cd video-converter-pro
   ```

2. **Set up a Virtual Environment (Recommended):**
   ```bash
   python -m venv .venv
   ```

3. **Activate the Virtual Environment:**
   * **Windows (PowerShell):**
     ```powershell
     .venv\Scripts\Activate.ps1
     ```
   * **Windows (CMD):**
     ```cmd
     .venv\Scripts\activate.bat
     ```
   * **macOS / Linux:**
     ```bash
     source .venv/bin/activate
     ```

4. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

---

## 💻 Running the Application

### 🖥️ 1. Start the Graphical Desktop GUI:
To launch the stunning desktop dashboard, run:
```bash
python gui.py
```

### 📟 2. Start the Interactive CLI Menu:
To run the terminal-friendly menu in your command prompt:
```bash
python conerter.py
```

### 🤖 3. Direct CLI Command Line Automation:
You can also bypass menus and run automated conversions directly:
```bash
# Convert a single video file
python conerter.py -i input.ts -o output.mp4

# Batch convert all supported videos in current directory
python conerter.py --batch --format mkv

# Perform an ultra-fast stream-copy remux
python conerter.py -i input.ts -c
```

---

## 🛠️ Configuration & Persistence
The application automatically creates a local `config.json` in the root workspace folder to permanently persist your preferences, including:
* Custom `ffmpeg.exe` installation path.
* Preferred default video format.
* Hardware encoder preferences (GPU selection).
* Default destination output directory.

---

## 🤝 Contributing
Contributions, issues, and feature requests are welcome! Feel free to check the issues page or submit pull requests to enhance the utility.

## 📄 License
This project is open-source and licensed under the [MIT License](LICENSE).
