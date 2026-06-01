#!/usr/bin/env python3
"""
Video Converter Pro GUI
A highly polished, modern, and professional desktop graphical interface
for converting local videos using PyQt6 and FFmpeg.
"""

import os
import sys
import re
import json
import time
import shutil
import subprocess
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QTableWidget, QTableWidgetItem,
    QProgressBar, QComboBox, QLineEdit, QTextEdit, QTabWidget,
    QGroupBox, QFormLayout, QMessageBox, QHeaderView, QAbstractItemView,
    QFrame, QCheckBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QColor, QPalette, QBrush, QIcon

# Regex patterns to parse FFmpeg progress and metadata
DURATION_REGEX = re.compile(r"Duration:\s*(\d{2}):(\d{2}):(\d{2})\.(\d{2})")
TIME_REGEX = re.compile(r"time=\s*(\d{2}):(\d{2}):(\d{2})\.(\d{2})")
SPEED_REGEX = re.compile(r"speed=\s*([\d\.]+)x")
FPS_REGEX = re.compile(r"fps=\s*([\d\.]+)")

SUPPORTED_FORMATS = ('.ts', '.mkv', '.avi', '.mp4', '.flv', '.webm', '.mov', '.m4v')

def find_ffmpeg(custom_path=None):
    """
    Search for the FFmpeg executable in common locations.
    """
    if custom_path:
        if os.path.exists(custom_path) and os.path.isfile(custom_path):
            return custom_path
        exe_path = os.path.join(custom_path, "ffmpeg.exe")
        if os.path.exists(exe_path):
            return exe_path
        exe_path = os.path.join(custom_path, "bin", "ffmpeg.exe")
        if os.path.exists(exe_path):
            return exe_path

    # Check system PATH
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        return ffmpeg_path

    # Check local workspace/directory
    local_ffmpeg = os.path.join(os.getcwd(), "ffmpeg.exe")
    if os.path.exists(local_ffmpeg):
        return local_ffmpeg

    local_bin_ffmpeg = os.path.join(os.getcwd(), "bin", "ffmpeg.exe")
    if os.path.exists(local_bin_ffmpeg):
        return local_bin_ffmpeg

    # Check relative path from conerter location
    script_dir = os.path.dirname(os.path.abspath(__file__))
    sibling_ffmpeg = os.path.join(script_dir, "ffmpeg", "bin", "ffmpeg.exe")
    if os.path.exists(sibling_ffmpeg):
        return sibling_ffmpeg

    return None

def format_seconds(seconds):
    """
    Format seconds into a highly readable duration string (HH:MM:SS or MM:SS).
    """
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"

def format_size(bytes_size):
    """
    Convert file bytes into a human-readable size string.
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.1f} PB"

def get_matching_subtitle(video_path):
    """
    Check if a matching subtitle file (.srt or .vtt) exists in the same folder.
    """
    base_name = os.path.splitext(video_path)[0]
    for ext in ['.srt', '.vtt']:
        sub_path = base_name + ext
        if os.path.exists(sub_path) and os.path.isfile(sub_path):
            return sub_path
    return None

# ==============================================================================
# Dynamic QThread Worker for Conversions
# ==============================================================================
class ConversionWorker(QThread):
    progress_updated = pyqtSignal(int, int, str, str)  # current_sec, total_sec, speed, fps
    log_received = pyqtSignal(str)
    finished = pyqtSignal(int, bool, str)  # file_id, success, error_message
    
    def __init__(self, file_id, ffmpeg_path, input_path, output_path, video_encoder='libx264', copy_codec=False, preset='medium', embed_subtitles=True, subtitle_path=None):
        super().__init__()
        self.file_id = file_id
        self.ffmpeg_path = ffmpeg_path
        self.input_path = input_path
        self.output_path = output_path
        self.video_encoder = video_encoder
        self.copy_codec = copy_codec
        self.preset = preset
        self.embed_subtitles = embed_subtitles
        self.subtitle_path = subtitle_path
        self.is_running = True
        self.process = None

    def run(self):
        # 1. Prepare output folder if it doesn't exist
        out_dir = os.path.dirname(self.output_path)
        if out_dir and not os.path.exists(out_dir):
            os.makedirs(out_dir, exist_ok=True)

        # 2. Build FFmpeg command
        command = [self.ffmpeg_path, '-hide_banner']
        
        # Explicitly force FFmpeg to use all CPU cores/threads
        command.extend(['-threads', '0'])
        
        command.extend(['-i', self.input_path])
        
        # Determine video/audio encoding parameters
        video_args = []
        audio_args = []
        
        if self.copy_codec:
            video_args.extend(['-c:v', 'copy'])
            audio_args.extend(['-c:a', 'copy'])
        else:
            video_args.extend(['-c:v', self.video_encoder])
            if self.video_encoder in ['libx264', 'libx265']:
                video_args.extend(['-preset', self.preset, '-crf', '23'])
            elif 'nvenc' in self.video_encoder:
                video_args.extend(['-cq', '23'])
            elif 'qsv' in self.video_encoder:
                video_args.extend(['-global_quality', '23'])
                
            audio_args.extend(['-c:a', 'aac', '-b:a', '128k'])
        
        # Check subtitles
        subtitle_file = self.subtitle_path
        if not subtitle_file and self.embed_subtitles:
            subtitle_file = get_matching_subtitle(self.input_path)
        
        if subtitle_file:
            command.extend(['-i', subtitle_file])
            command.extend(['-map', '0:v', '-map', '0:a', '-map', '1:s'])
            
            command.extend(video_args)
            command.extend(audio_args)
            
            out_ext = os.path.splitext(self.output_path)[1].lower()
            if out_ext == '.mp4':
                command.extend(['-c:s', 'mov_text'])
            elif out_ext == '.mkv':
                command.extend(['-c:s', 'srt'])
            else:
                command.extend(['-c:s', 'mov_text'])
        else:
            if self.copy_codec:
                command.extend(['-c', 'copy'])
            else:
                command.extend(video_args)
                command.extend(audio_args)
                
        command.extend(['-y', self.output_path])

        self.log_received.emit(f"\n[Starting File ID {self.file_id}] Input: {os.path.basename(self.input_path)}")
        self.log_received.emit(f"[Command] {' '.join(command)}\n")

        try:
            self.process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                encoding='utf-8',
                errors='replace'
            )

            total_seconds = 0
            current_seconds = 0
            speed = "N/A"
            fps = "N/A"

            for line in self.process.stdout:
                if not self.is_running:
                    break
                    
                self.log_received.emit(line)

                # Parse Duration
                if total_seconds == 0:
                    duration_match = DURATION_REGEX.search(line)
                    if duration_match:
                        h, m, s, _ = map(int, duration_match.groups())
                        total_seconds = h * 3600 + m * 60 + s

                # Parse Progress Info
                time_match = TIME_REGEX.search(line)
                if time_match:
                    try:
                        h, m, s, _ = map(int, time_match.groups())
                        current_seconds = h * 3600 + m * 60 + s
                    except ValueError:
                        pass

                    # Parse Speed
                    speed_match = SPEED_REGEX.search(line)
                    if speed_match:
                        speed = speed_match.group(1) + "x"

                    # Parse FPS
                    fps_match = FPS_REGEX.search(line)
                    if fps_match:
                        fps = fps_match.group(1)

                    self.progress_updated.emit(current_seconds, total_seconds, speed, fps)

            if not self.is_running:
                # Graceful Interruption cleanup
                if self.process:
                    self.process.terminate()
                    self.process.wait()
                if os.path.exists(self.output_path):
                    try:
                        os.remove(self.output_path)
                    except OSError:
                        pass
                self.finished.emit(self.file_id, False, "Interrupted by user")
                return

            self.process.wait()
            
            if self.process.returncode == 0:
                self.finished.emit(self.file_id, True, "")
            else:
                self.finished.emit(self.file_id, False, f"FFmpeg failed with exit code {self.process.returncode}")

        except Exception as e:
            self.finished.emit(self.file_id, False, str(e))

    def stop(self):
        self.is_running = False
        if self.process:
            try:
                self.process.terminate()
            except OSError:
                pass


# ==============================================================================
# Dash-Border Drag and Drop Panel Subclass
# ==============================================================================
class DragDropFrame(QFrame):
    files_dropped = pyqtSignal(list)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setObjectName("DragDropFrame")
        self.setStyleSheet("""
            #DragDropFrame {
                border: 2px dashed #45475a;
                border-radius: 12px;
                background-color: #181825;
            }
            #DragDropFrame:hover {
                border: 2px dashed #89b4fa;
                background-color: #1e1e2e;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(12)
        
        self.label_icon = QLabel("🎬", self)
        self.label_icon.setStyleSheet("font-size: 54px; margin-bottom: 5px;")
        self.label_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.label_icon)
        
        self.label_text = QLabel("Drag & Drop Video Files or Folders Here\n(Or Click anywhere in this box to Browse)", self)
        self.label_text.setStyleSheet("color: #a6adc8; font-size: 15px; font-weight: bold; line-height: 1.4;")
        self.label_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.label_text)
        
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet("""
                #DragDropFrame {
                    border: 2px dashed #a6e3a1;
                    background-color: #1e2e2e;
                }
            """)
            
    def dragLeaveEvent(self, event):
        self.setStyleSheet("""
            #DragDropFrame {
                border: 2px dashed #45475a;
                background-color: #181825;
            }
            #DragDropFrame:hover {
                border: 2px dashed #89b4fa;
                background-color: #1e1e2e;
            }
        """)
        
    def dropEvent(self, event):
        self.setStyleSheet("""
            #DragDropFrame {
                border: 2px dashed #45475a;
                background-color: #181825;
            }
        """)
        if event.mimeData().hasUrls():
            paths = []
            for url in event.mimeData().urls():
                paths.append(url.toLocalFile())
            self.files_dropped.emit(paths)
            event.acceptProposedAction()
            
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.files_dropped.emit([])  # Emits empty list to trigger files explorer browse dialogue


# ==============================================================================
# Main GUI Window Class
# ==============================================================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Load user configuration
        self.config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
        self.config = self.load_config()
        
        # Validate/Detect FFmpeg Path
        self.ffmpeg_path = find_ffmpeg(self.config.get("ffmpeg_path"))
        if self.ffmpeg_path:
            self.config["ffmpeg_path"] = self.ffmpeg_path
            self.save_config()
        
        self.queue = []  # List of conversion dicts
        self.active_worker = None
        self.is_converting = False
        self.current_queue_index = -1
        
        # Stats tracking
        self.stats = {
            "total": 0,
            "success": 0,
            "failed": 0
        }
        
        self.init_ui()
        
        # If FFmpeg is missing, pop browse prompt immediately
        if not self.ffmpeg_path:
            self.prompt_ffmpeg_missing()

    # ==============================================================================
    # Configuration Load/Save
    # ==============================================================================
    def load_config(self):
        default = {
            "ffmpeg_path": "",
            "default_format": "mp4",
            "video_encoder": "libx264",
            "copy_codec": False,
            "preset": "medium",
            "embed_subtitles": True,
            "output_dir": ""
        }
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    default.update(data)
            except Exception:
                pass
        return default

    def save_config(self):
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving config: {e}")

    # ==============================================================================
    # Stylesheets Design System (Catppuccin Macchiato Theme inspired)
    # ==============================================================================
    def apply_styling(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e2e;
            }
            QWidget {
                color: #cdd6f4;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 13px;
            }
            QTabWidget::pane {
                border: 1px solid #313244;
                background-color: #181825;
                border-radius: 8px;
            }
            QTabBar::tab {
                background-color: #11111b;
                color: #a6adc8;
                padding: 10px 20px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 4px;
                font-weight: bold;
            }
            QTabBar::tab:hover {
                background-color: #1e1e2e;
                color: #cdd6f4;
            }
            QTabBar::tab:selected {
                background-color: #181825;
                color: #89b4fa;
                border-bottom: 2px solid #89b4fa;
            }
            
            QPushButton {
                background-color: #313244;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45475a;
                border-color: #585b70;
            }
            QPushButton:pressed {
                background-color: #585b70;
            }
            
            /* Action Buttons styling */
            QPushButton#btnStart {
                background-color: #a6e3a1;
                color: #11111b;
                border: none;
            }
            QPushButton#btnStart:hover {
                background-color: #b4f8b0;
            }
            QPushButton#btnStop {
                background-color: #f38ba8;
                color: #11111b;
                border: none;
            }
            QPushButton#btnStop:hover {
                background-color: #f7a3b8;
            }
            
            QTableWidget {
                background-color: #181825;
                color: #cdd6f4;
                gridline-color: #313244;
                border: 1px solid #313244;
                border-radius: 8px;
                selection-background-color: #313244;
                selection-color: #cdd6f4;
            }
            QTableWidget::item {
                padding: 8px;
            }
            QHeaderView::section {
                background-color: #11111b;
                color: #a6adc8;
                padding: 6px;
                border: none;
                border-bottom: 2px solid #313244;
                font-weight: bold;
            }
            
            QComboBox, QLineEdit {
                background-color: #1e1e2e;
                border: 1px solid #313244;
                border-radius: 6px;
                padding: 6px 12px;
                color: #cdd6f4;
            }
            QComboBox:hover, QLineEdit:hover {
                border: 1px solid #45475a;
            }
            QComboBox:focus, QLineEdit:focus {
                border: 1px solid #89b4fa;
            }
            QComboBox::drop-down {
                border: none;
            }
            
            QProgressBar {
                background-color: #11111b;
                border: 1px solid #313244;
                border-radius: 8px;
                text-align: center;
                color: #cdd6f4;
                font-weight: bold;
                height: 18px;
            }
            QProgressBar::chunk {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #89b4fa, stop:1 #b4befe);
                border-radius: 7px;
            }
            
            QGroupBox {
                border: 1px solid #313244;
                border-radius: 8px;
                margin-top: 16px;
                font-weight: bold;
                color: #89b4fa;
                padding: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 10px;
                padding: 0 5px;
            }
            
            QTextEdit {
                background-color: #11111b;
                border: 1px solid #313244;
                border-radius: 8px;
                color: #a6e3a1;
                font-family: 'Consolas', 'Courier New', monospace;
                padding: 10px;
            }
            
            /* Styled Scrollbars */
            QScrollBar:vertical {
                border: none;
                background-color: #11111b;
                width: 10px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background-color: #313244;
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #45475a;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                border: none;
                background: none;
            }
        """)

    # ==============================================================================
    # User Interface Initialization
    # ==============================================================================
    def init_ui(self):
        self.setWindowTitle("Video Converter Pro - Desktop UI")
        self.setMinimumSize(920, 680)
        self.apply_styling()
        
        # Main central Widget
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        
        # Main Layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)
        
        # 1. Header Section (Title & Stats)
        header_layout = QHBoxLayout()
        
        title_label = QLabel("🎬 Video Converter Pro", self)
        title_label.setStyleSheet("font-size: 22px; font-weight: bold; color: #89b4fa;")
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        # Stats Badges
        self.lbl_stats_total = QLabel("Total: 0", self)
        self.lbl_stats_total.setStyleSheet("background-color: #313244; padding: 4px 10px; border-radius: 4px; font-weight: bold;")
        self.lbl_stats_success = QLabel("Completed: 0", self)
        self.lbl_stats_success.setStyleSheet("background-color: #2e3c30; color: #a6e3a1; padding: 4px 10px; border-radius: 4px; font-weight: bold;")
        self.lbl_stats_failed = QLabel("Failed: 0", self)
        self.lbl_stats_failed.setStyleSheet("background-color: #3c2e30; color: #f38ba8; padding: 4px 10px; border-radius: 4px; font-weight: bold;")
        
        header_layout.addWidget(self.lbl_stats_total)
        header_layout.addWidget(self.lbl_stats_success)
        header_layout.addWidget(self.lbl_stats_failed)
        
        main_layout.addLayout(header_layout)
        
        # 2. Main Tabbed Layout Container
        self.tabs = QTabWidget(self)
        main_layout.addWidget(self.tabs)
        
        self.init_converter_tab()
        self.init_settings_tab()
        self.init_logs_tab()
        
        # 3. Bottom Active Progress Dashboard (Invisible until conversion starts)
        self.init_dashboard_panel(main_layout)
        
        # Update placeholder status
        self.update_placeholder_visibility()

    # ==============================================================================
    # Tab 1: Video Converter Queue Manager
    # ==============================================================================
    def init_converter_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)
        
        # Control Buttons Row
        ctrl_layout = QHBoxLayout()
        
        self.btn_add_files = QPushButton("➕ Add Files", self)
        self.btn_add_files.clicked.connect(self.action_add_files)
        
        self.btn_add_folder = QPushButton("📁 Add Folder", self)
        self.btn_add_folder.clicked.connect(self.action_add_folder)
        
        self.btn_remove = QPushButton("❌ Remove Selected", self)
        self.btn_remove.clicked.connect(self.action_remove_selected)
        
        self.btn_clear = QPushButton("🗑️ Clear Queue", self)
        self.btn_clear.clicked.connect(self.action_clear_queue)
        
        ctrl_layout.addWidget(self.btn_add_files)
        ctrl_layout.addWidget(self.btn_add_folder)
        ctrl_layout.addWidget(self.btn_remove)
        ctrl_layout.addWidget(self.btn_clear)
        ctrl_layout.addStretch()
        
        # Start/Stop Buttons
        self.btn_start = QPushButton("▶️ Start Conversion", self)
        self.btn_start.setObjectName("btnStart")
        self.btn_start.clicked.connect(self.action_start_conversion)
        
        self.btn_stop = QPushButton("⏹️ Stop Queue", self)
        self.btn_stop.setObjectName("btnStop")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.action_stop_conversion)
        
        ctrl_layout.addWidget(self.btn_start)
        ctrl_layout.addWidget(self.btn_stop)
        
        layout.addLayout(ctrl_layout)
        
        # Container for files view
        self.view_container = QVBoxLayout()
        self.view_container.setSpacing(0)
        
        # Drag & Drop Frame
        self.drag_drop_widget = DragDropFrame(self)
        self.drag_drop_widget.files_dropped.connect(self.handle_files_dropped)
        self.view_container.addWidget(self.drag_drop_widget)
        
        # Queue Table Widget (Hidden initially)
        self.table = QTableWidget(self)
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["File Name", "Target Format", "Size", "Subtitles", "Status", "Progress"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        
        self.table.setColumnWidth(1, 110)
        self.table.hide()
        
        self.view_container.addWidget(self.table)
        layout.addLayout(self.view_container)
        
        self.tabs.addTab(tab, "🔄 Converter Queue")

    # ==============================================================================
    # Tab 2: Settings Panel
    # ==============================================================================
    def init_settings_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # FFmpeg settings box
        ffmpeg_box = QGroupBox("System Environment (FFmpeg)")
        ffmpeg_layout = QFormLayout(ffmpeg_box)
        ffmpeg_layout.setSpacing(10)
        
        self.txt_ffmpeg_path = QLineEdit(self)
        self.txt_ffmpeg_path.setText(self.config.get("ffmpeg_path", ""))
        self.txt_ffmpeg_path.setPlaceholderText("Path to ffmpeg.exe")
        
        btn_browse_ffmpeg = QPushButton("Browse...", self)
        btn_browse_ffmpeg.clicked.connect(self.browse_ffmpeg_path)
        
        ffmpeg_row = QHBoxLayout()
        ffmpeg_row.addWidget(self.txt_ffmpeg_path)
        ffmpeg_row.addWidget(btn_browse_ffmpeg)
        ffmpeg_layout.addRow("FFmpeg Executable:", ffmpeg_row)
        
        layout.addWidget(ffmpeg_box)
        
        # Encoding preferences
        codec_box = QGroupBox("Default Codecs & Formats")
        codec_layout = QFormLayout(codec_box)
        codec_layout.setSpacing(10)
        
        self.cb_default_format = QComboBox(self)
        self.cb_default_format.addItems(["mp4", "mkv", "avi", "mov", "webm"])
        self.cb_default_format.setCurrentText(self.config.get("default_format", "mp4"))
        codec_layout.addRow("Default Output Format:", self.cb_default_format)
        
        self.cb_video_encoder = QComboBox(self)
        self.cb_video_encoder.addItem("H.264 (CPU - Highly Compatible)", "libx264")
        self.cb_video_encoder.addItem("H.265 / HEVC (CPU - High Compression)", "libx265")
        self.cb_video_encoder.addItem("NVIDIA NVENC (GPU H.264 - Extreme Speed)", "h264_nvenc")
        self.cb_video_encoder.addItem("NVIDIA NVENC (GPU H.265 - Extreme Speed)", "hevc_nvenc")
        self.cb_video_encoder.addItem("Intel QSV (GPU H.264 - Very Fast)", "h264_qsv")
        self.cb_video_encoder.addItem("Intel QSV (GPU H.265 - Very Fast)", "hevc_qsv")
        self.cb_video_encoder.addItem("AMD AMF (GPU H.264 - Very Fast)", "h264_amf")
        self.cb_video_encoder.addItem("AMD AMF (GPU H.265 - Very Fast)", "hevc_amf")
        
        saved_encoder = self.config.get("video_encoder", "libx264")
        idx = self.cb_video_encoder.findData(saved_encoder)
        if idx != -1:
            self.cb_video_encoder.setCurrentIndex(idx)
        codec_layout.addRow("Video Encoder Mode:", self.cb_video_encoder)
        
        self.chk_copy_codec = QCheckBox("Ultra-fast Stream Copy (No re-encoding)", self)
        self.chk_copy_codec.setChecked(self.config.get("copy_codec", False))
        codec_layout.addRow("Copy Option:", self.chk_copy_codec)
        
        self.cb_preset = QComboBox(self)
        self.cb_preset.addItems(['ultrafast', 'superfast', 'veryfast', 'faster', 'fast', 'medium', 'slow', 'slower', 'veryslow'])
        self.cb_preset.setCurrentText(self.config.get("preset", "medium"))
        codec_layout.addRow("Compression Preset:", self.cb_preset)
        
        self.chk_embed_subs = QCheckBox("Automatically search and embed matching subtitle files (.srt/.vtt)", self)
        self.chk_embed_subs.setChecked(self.config.get("embed_subtitles", True))
        codec_layout.addRow("Subtitles Preference:", self.chk_embed_subs)
        
        layout.addWidget(codec_box)
        
        # Output directory box
        out_box = QGroupBox("Destination Directory")
        out_layout = QFormLayout(out_box)
        out_layout.setSpacing(10)
        
        self.txt_out_dir = QLineEdit(self)
        self.txt_out_dir.setText(self.config.get("output_dir", ""))
        self.txt_out_dir.setPlaceholderText("Default: Same folder as source video")
        
        btn_browse_out = QPushButton("Browse...", self)
        btn_browse_out.clicked.connect(self.browse_output_dir)
        
        out_row = QHBoxLayout()
        out_row.addWidget(self.txt_out_dir)
        out_row.addWidget(btn_browse_out)
        out_layout.addRow("Output Folder:", out_row)
        
        layout.addWidget(out_box)
        
        # Save Button at bottom
        btn_save = QPushButton("💾 Save Preferences", self)
        btn_save.setStyleSheet("background-color: #89b4fa; color: #11111b; font-size: 14px; padding: 10px;")
        btn_save.clicked.connect(self.action_save_settings)
        
        layout.addWidget(btn_save)
        layout.addStretch()
        
        self.tabs.addTab(tab, "⚙️ Advanced Settings")

    # ==============================================================================
    # Tab 3: Real-Time FFmpeg Console Logs
    # ==============================================================================
    def init_logs_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        
        header_row = QHBoxLayout()
        lbl = QLabel("Live FFmpeg Console Logging Stream", self)
        lbl.setStyleSheet("font-weight: bold; color: #a6e3a1;")
        
        btn_clear_logs = QPushButton("🗑️ Clear Log Terminal", self)
        btn_clear_logs.clicked.connect(self.action_clear_logs)
        
        header_row.addWidget(lbl)
        header_row.addStretch()
        header_row.addWidget(btn_clear_logs)
        
        layout.addLayout(header_row)
        
        self.txt_logs = QTextEdit(self)
        self.txt_logs.setReadOnly(True)
        self.txt_logs.setPlaceholderText("Conversion log outputs will stream here in real-time...")
        layout.addWidget(self.txt_logs)
        
        self.tabs.addTab(tab, "📜 Real-Time Logs")

    # ==============================================================================
    # Bottom active progress dashboard
    # ==============================================================================
    def init_dashboard_panel(self, parent_layout):
        self.dash_frame = QFrame(self)
        self.dash_frame.setStyleSheet("""
            QFrame {
                background-color: #11111b;
                border: 1px solid #313244;
                border-radius: 8px;
            }
            QLabel {
                border: none;
            }
        """)
        self.dash_frame.hide()
        
        dash_layout = QVBoxLayout(self.dash_frame)
        dash_layout.setContentsMargins(12, 12, 12, 12)
        dash_layout.setSpacing(10)
        
        # Grid layout for Stats indicators
        stats_layout = QHBoxLayout()
        
        self.lbl_dash_filename = QLabel("Current File: None", self)
        self.lbl_dash_filename.setStyleSheet("font-weight: bold; color: #89b4fa; font-size: 14px;")
        
        self.lbl_dash_speed = QLabel("Speed: 0.0x", self)
        self.lbl_dash_speed.setStyleSheet("background-color: #181825; padding: 4px 8px; border-radius: 4px;")
        
        self.lbl_dash_fps = QLabel("FPS: 0", self)
        self.lbl_dash_fps.setStyleSheet("background-color: #181825; padding: 4px 8px; border-radius: 4px;")
        
        self.lbl_dash_time = QLabel("Duration: 00:00 / 00:00", self)
        self.lbl_dash_time.setStyleSheet("background-color: #181825; padding: 4px 8px; border-radius: 4px;")
        
        stats_layout.addWidget(self.lbl_dash_filename)
        stats_layout.addStretch()
        stats_layout.addWidget(self.lbl_dash_speed)
        stats_layout.addWidget(self.lbl_dash_fps)
        stats_layout.addWidget(self.lbl_dash_time)
        
        dash_layout.addLayout(stats_layout)
        
        # Global active progress bar
        self.dash_pbar = QProgressBar(self)
        self.dash_pbar.setValue(0)
        dash_layout.addWidget(self.dash_pbar)
        
        parent_layout.addWidget(self.dash_frame)

    # ==============================================================================
    # View Helper Logic
    # ==============================================================================
    def update_placeholder_visibility(self):
        """
        Toggles files table visibility depending on whether items are present in queue.
        """
        if not self.queue:
            self.table.hide()
            self.drag_drop_widget.show()
        else:
            self.drag_drop_widget.hide()
            self.table.show()

    def update_stats_badges(self):
        """
        Updates colored status indicator labels in window header.
        """
        self.lbl_stats_total.setText(f"Total: {self.stats['total']}")
        self.lbl_stats_success.setText(f"Completed: {self.stats['success']}")
        self.lbl_stats_failed.setText(f"Failed: {self.stats['failed']}")

    # ==============================================================================
    # Drag and Drop Events Dispatcher
    # ==============================================================================
    def handle_files_dropped(self, paths):
        """
        Handles files dropped into frame or triggers explorer files browser if empty list.
        """
        if not paths:
            self.action_add_files()
            return
            
        video_files = []
        for path in paths:
            if os.path.isdir(path):
                # Search folder for video formats
                for root, _, files in os.walk(path):
                    for file in files:
                        if file.lower().endswith(SUPPORTED_FORMATS):
                            video_files.append(os.path.join(root, file))
                    break # non-recursive search
            elif os.path.isfile(path) and path.lower().endswith(SUPPORTED_FORMATS):
                video_files.append(path)
                
        if video_files:
            for file in video_files:
                self.add_file_to_queue(file)
            self.update_placeholder_visibility()
        else:
            QMessageBox.information(
                self, "Unsupported Files",
                "None of the dropped files match supported video container formats:\n" + ", ".join(SUPPORTED_FORMATS)
            )

    # ==============================================================================
    # Queue Modification Actions
    # ==============================================================================
    def add_file_to_queue(self, file_path):
        # Validate path
        if not os.path.exists(file_path):
            return
            
        # Avoid duplicate additions
        if any(item['input_path'] == file_path for item in self.queue):
            return
            
        file_id = len(self.queue)
        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        size_str = format_size(file_size)
        
        # Subtitles detection
        has_subs = get_matching_subtitle(file_path) is not None
        sub_text = "Yes (Auto)" if has_subs else "None"
        
        # Default output setup
        default_format = self.config.get("default_format", "mp4")
        
        item = {
            'id': file_id,
            'input_path': file_path,
            'format': default_format,
            'subtitles': has_subs,
            'status': 'Waiting',
            'progress': 0
        }
        self.queue.append(item)
        self.stats["total"] = len(self.queue)
        self.update_stats_badges()
        
        row = self.table.rowCount()
        self.table.insertRow(row)
        
        # Col 0: File name
        name_item = QTableWidgetItem(file_name)
        name_item.setToolTip(file_path)
        name_item.setData(Qt.ItemDataRole.UserRole, file_id)
        self.table.setItem(row, 0, name_item)
        
        # Col 1: Format selector combo
        format_cb = QComboBox(self)
        format_cb.addItems(["mp4", "mkv", "avi", "mov", "webm"])
        format_cb.setCurrentText(default_format)
        format_cb.currentTextChanged.connect(lambda text, fid=file_id: self.update_queue_item_format(fid, text))
        self.table.setCellWidget(row, 1, format_cb)
        
        # Col 2: Human-readable size
        size_item = QTableWidgetItem(size_str)
        size_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setItem(row, 2, size_item)
        
        # Col 3: Subtitles Selector (Interactive Widget)
        sub_widget = QWidget(self)
        sub_layout = QHBoxLayout(sub_widget)
        sub_layout.setContentsMargins(4, 2, 4, 2)
        sub_layout.setSpacing(6)
        
        lbl_sub = QLabel(sub_text, sub_widget)
        lbl_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_sub.setStyleSheet("border: none; font-size: 11px;")
        
        btn_sub = QPushButton("📂", sub_widget)
        btn_sub.setToolTip("Manually browse and select a subtitle file (.srt/.vtt)")
        btn_sub.setStyleSheet("""
            QPushButton {
                background-color: #313244;
                border: 1px solid #45475a;
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #45475a;
            }
        """)
        
        btn_sub.clicked.connect(lambda checked, fid=file_id, lbl=lbl_sub: self.action_browse_subtitle(fid, lbl))
        
        sub_layout.addWidget(lbl_sub, 1)
        sub_layout.addWidget(btn_sub)
        self.table.setCellWidget(row, 3, sub_widget)
        
        # Col 4: Color-coded waiting status
        status_item = QTableWidgetItem("Waiting")
        status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        status_item.setForeground(QBrush(QColor("#f9e2af"))) # Catppuccin Peach
        self.table.setItem(row, 4, status_item)
        
        # Col 5: Inner Row progress bar widget
        pbar = QProgressBar(self)
        pbar.setRange(0, 100)
        pbar.setValue(0)
        pbar.setStyleSheet("QProgressBar { height: 16px; margin: 4px; }")
        self.table.setCellWidget(row, 5, pbar)

    def update_queue_item_format(self, file_id, new_format):
        for item in self.queue:
            if item['id'] == file_id:
                item['format'] = new_format
                break

    def action_browse_subtitle(self, file_id, label_widget):
        filters = "Subtitles (*.srt *.vtt);;All Files (*)"
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Subtitle File", "", filters)
        if file_path:
            for item in self.queue:
                if item['id'] == file_id:
                    item['manual_subtitle_path'] = file_path
                    item['subtitles'] = True
                    # Update label with selected subtitle file name
                    filename = os.path.basename(file_path)
                    label_widget.setText(filename)
                    label_widget.setStyleSheet("color: #a6e3a1; font-weight: bold; border: none; font-size: 11px;")
                    label_widget.setToolTip(file_path)
                    break

    # ==============================================================================
    # GUI Interactive Action Commands
    # ==============================================================================
    def action_add_files(self):
        filters = "Videos (" + " ".join(["*" + ext for ext in SUPPORTED_FORMATS]) + ");;All Files (*)"
        files, _ = QFileDialog.getOpenFileNames(self, "Select Video Files", "", filters)
        if files:
            for file in files:
                self.add_file_to_queue(file)
            self.update_placeholder_visibility()

    def action_add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Video Folder")
        if folder:
            video_files = []
            for root, _, files in os.walk(folder):
                for file in files:
                    if file.lower().endswith(SUPPORTED_FORMATS):
                        video_files.append(os.path.join(root, file))
                break # top-level directory only
            
            if video_files:
                for file in video_files:
                    self.add_file_to_queue(file)
                self.update_placeholder_visibility()
            else:
                QMessageBox.information(self, "Empty Folder", "No compatible video formats found in the selected folder.")

    def action_remove_selected(self):
        if self.is_converting:
            QMessageBox.warning(self, "Queue Processing", "Cannot remove items while conversions are actively running.")
            return
            
        selected_ranges = self.table.selectedRanges()
        if not selected_ranges:
            return
            
        # Get all selected row indices
        rows_to_remove = set()
        for r_range in selected_ranges:
            for r in range(r_range.topRow(), r_range.bottomRow() + 1):
                rows_to_remove.add(r)
                
        # Sort in reverse to delete correctly from bottom up
        for row in sorted(rows_to_remove, reverse=True):
            file_name_item = self.table.item(row, 0)
            if file_name_item:
                file_id = file_name_item.data(Qt.ItemDataRole.UserRole)
                # Remove from self.queue list
                self.queue = [item for item in self.queue if item['id'] != file_id]
            self.table.removeRow(row)
            
        # Re-index remaining queue items
        for idx, item in enumerate(self.queue):
            item['id'] = idx
            
        self.stats["total"] = len(self.queue)
        self.update_stats_badges()
        self.update_placeholder_visibility()

    def action_clear_queue(self):
        if self.is_converting:
            QMessageBox.warning(self, "Queue Processing", "Please stop conversion queue before wiping it.")
            return
            
        self.queue.clear()
        self.table.setRowCount(0)
        self.stats = {"total": 0, "success": 0, "failed": 0}
        self.update_stats_badges()
        self.update_placeholder_visibility()

    # ==============================================================================
    # Queue Conversions Runner Engine
    # ==============================================================================
    def action_start_conversion(self):
        if not self.ffmpeg_path:
            self.prompt_ffmpeg_missing()
            return
            
        if self.is_converting:
            return
            
        if not self.queue:
            QMessageBox.information(self, "Empty Queue", "Please add files to the queue before starting.")
            return

        # Find the first 'Waiting' or 'Failed' file to process
        self.current_queue_index = -1
        for idx, item in enumerate(self.queue):
            if item['status'] in ['Waiting', 'Failed']:
                self.current_queue_index = idx
                break
                
        if self.current_queue_index == -1:
            QMessageBox.information(self, "Queue Complete", "All files in queue have already been successfully processed.")
            return

        # Update controls state
        self.is_converting = True
        self.btn_add_files.setEnabled(False)
        self.btn_add_folder.setEnabled(False)
        self.btn_remove.setEnabled(False)
        self.btn_clear.setEnabled(False)
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.dash_frame.show()
        
        # Launch next item in stack
        self.start_next_queue_item()

    def start_next_queue_item(self):
        if not self.is_converting or self.current_queue_index >= len(self.queue):
            self.action_stop_conversion(complete=True)
            return

        item = self.queue[self.current_queue_index]
        if item['status'] not in ['Waiting', 'Failed']:
            # Skip already handled rows
            self.current_queue_index += 1
            self.start_next_queue_item()
            return

        # Prepare parameters
        input_path = item['input_path']
        output_format = item['format']
        
        base_name = os.path.splitext(input_path)[0]
        
        # Decide output directory
        out_dir = self.config.get("output_dir", "")
        if out_dir:
            output_path = os.path.join(out_dir, os.path.basename(base_name) + f".{output_format}")
        else:
            output_path = base_name + f"_converted.{output_format}"
            
        # Avoid input overwrite
        if output_path.lower() == input_path.lower():
            output_path = base_name + f"_converted_1.{output_format}"

        # Update table status column
        row_idx = self.find_table_row_by_id(item['id'])
        if row_idx != -1:
            status_item = self.table.item(row_idx, 4)
            status_item.setText("Converting")
            status_item.setForeground(QBrush(QColor("#89b4fa"))) # Blue Color

        # Update stats bottom panel
        self.lbl_dash_filename.setText(f"Converting: {os.path.basename(input_path)}")
        self.lbl_dash_speed.setText("Speed: N/A")
        self.lbl_dash_fps.setText("FPS: N/A")
        self.lbl_dash_time.setText("Duration: 00:00 / 00:00")
        self.dash_pbar.setValue(0)
        
        # Instantiate and connect QThread Worker
        self.active_worker = ConversionWorker(
            file_id=item['id'],
            ffmpeg_path=self.ffmpeg_path,
            input_path=input_path,
            output_path=output_path,
            video_encoder=self.config.get("video_encoder", "libx264"),
            copy_codec=self.config.get("copy_codec", False),
            preset=self.config.get("preset", "medium"),
            embed_subtitles=self.config.get("embed_subtitles", True),
            subtitle_path=item.get('manual_subtitle_path')
        )
        self.active_worker.progress_updated.connect(self.handle_worker_progress)
        self.active_worker.log_received.connect(self.handle_worker_logs)
        self.active_worker.finished.connect(self.handle_worker_finished)
        
        item['status'] = 'Converting'
        self.active_worker.start()

    def action_stop_conversion(self, complete=False):
        self.is_converting = False
        self.btn_stop.setEnabled(False)
        
        if self.active_worker and self.active_worker.isRunning():
            self.active_worker.stop()
            self.active_worker.wait()
            self.active_worker = None

        # Reset Controls
        self.btn_add_files.setEnabled(True)
        self.btn_add_folder.setEnabled(True)
        self.btn_remove.setEnabled(True)
        self.btn_clear.setEnabled(True)
        self.btn_start.setEnabled(True)
        self.dash_frame.hide()
        
        # Reset current conversions status row to Waiting if interrupted
        for item in self.queue:
            if item['status'] == 'Converting':
                item['status'] = 'Waiting'
                row_idx = self.find_table_row_by_id(item['id'])
                if row_idx != -1:
                    status_item = self.table.item(row_idx, 4)
                    status_item.setText("Waiting")
                    status_item.setForeground(QBrush(QColor("#f9e2af")))
                    pbar = self.table.cellWidget(row_idx, 5)
                    if pbar:
                        pbar.setValue(0)

        if complete:
            QMessageBox.information(self, "Process Finished", "Batch video conversion queue completed.")

    # ==============================================================================
    # Worker Thread Signals Callbacks
    # ==============================================================================
    def handle_worker_progress(self, current, total, speed, fps):
        # Update dashboard
        self.lbl_dash_speed.setText(f"Speed: {speed}")
        self.lbl_dash_fps.setText(f"FPS: {fps}")
        self.lbl_dash_time.setText(f"Duration: {format_seconds(current)} / {format_seconds(total)}")
        
        percent = 0
        if total > 0:
            percent = min(int((current * 100) / total), 100)
            
        self.dash_pbar.setValue(percent)
        
        # Update Table Row progress
        item = self.queue[self.current_queue_index]
        item['progress'] = percent
        
        row_idx = self.find_table_row_by_id(item['id'])
        if row_idx != -1:
            pbar = self.table.cellWidget(row_idx, 5)
            if pbar:
                pbar.setValue(percent)

    def handle_worker_logs(self, text):
        self.txt_logs.append(text.rstrip())
        # Automatically scroll to bottom of logs
        self.txt_logs.verticalScrollBar().setValue(
            self.txt_logs.verticalScrollBar().maximum()
        )

    def handle_worker_finished(self, file_id, success, error_message):
        self.active_worker = None
        item = self.queue[self.current_queue_index]
        
        row_idx = self.find_table_row_by_id(file_id)
        if row_idx != -1:
            status_item = self.table.item(row_idx, 4)
            pbar = self.table.cellWidget(row_idx, 5)
            
            if success:
                item['status'] = 'Completed'
                status_item.setText("Completed")
                status_item.setForeground(QBrush(QColor("#a6e3a1"))) # Green color
                if pbar:
                    pbar.setValue(100)
                self.stats["success"] += 1
            else:
                item['status'] = 'Failed'
                status_item.setText("Failed")
                status_item.setForeground(QBrush(QColor("#f38ba8"))) # Red color
                status_item.setToolTip(error_message)
                if pbar:
                    pbar.setValue(0)
                self.stats["failed"] += 1

        self.update_stats_badges()
        
        # Fetch next item from the queue
        if self.is_converting:
            self.current_queue_index += 1
            self.start_next_queue_item()

    def find_table_row_by_id(self, file_id):
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.data(Qt.ItemDataRole.UserRole) == file_id:
                return row
        return -1

    # ==============================================================================
    # Tab 2: Settings Preferences handlers
    # ==============================================================================
    def browse_ffmpeg_path(self):
        path, _ = QFileDialog.getOpenFileName(self, "Locate FFmpeg Binary", "", "Executable (ffmpeg.exe);;All Files (*)")
        if path:
            self.txt_ffmpeg_path.setText(path)

    def browse_output_dir(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if folder:
            self.txt_out_dir.setText(folder)

    def action_save_settings(self):
        ffmpeg_val = self.txt_ffmpeg_path.text().strip()
        # Verify FFmpeg
        valid_ffmpeg = find_ffmpeg(ffmpeg_val)
        
        if not valid_ffmpeg:
            QMessageBox.critical(self, "Invalid Path", "The specified FFmpeg executable is invalid or does not exist.")
            return

        self.ffmpeg_path = valid_ffmpeg
        self.config["ffmpeg_path"] = self.ffmpeg_path
        self.config["default_format"] = self.cb_default_format.currentText()
        self.config["video_encoder"] = self.cb_video_encoder.currentData()
        self.config["copy_codec"] = self.chk_copy_codec.isChecked()
        self.config["preset"] = self.cb_preset.currentText()
        self.config["embed_subtitles"] = self.chk_embed_subs.isChecked()
        self.config["output_dir"] = self.txt_out_dir.text().strip()
        
        self.save_config()
        QMessageBox.information(self, "Settings Saved", "Your preferences have been successfully saved.")

    def prompt_ffmpeg_missing(self):
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setWindowTitle("FFmpeg Executable Required")
        msg.setText("FFmpeg is required for video conversion. It was not found in your system PATH or local folder.")
        msg.setInformativeText("Would you like to browse and locate 'ffmpeg.exe' now?")
        
        btn_browse = msg.addButton("Browse Locally", QMessageBox.ButtonRole.AcceptRole)
        btn_cancel = msg.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        
        msg.exec()
        
        if msg.clickedButton() == btn_browse:
            self.tabs.setCurrentIndex(1) # Switch to Settings Tab
            self.browse_ffmpeg_path()

    # ==============================================================================
    # Tab 3: Log Terminal Clean
    # ==============================================================================
    def action_clear_logs(self):
        self.txt_logs.clear()

    # ==============================================================================
    # Window Close handler
    # ==============================================================================
    def closeEvent(self, event):
        if self.is_converting:
            confirm = QMessageBox.question(
                self, "Exit Application",
                "Conversions are currently running. Are you sure you want to stop them and exit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if confirm == QMessageBox.StandardButton.Yes:
                self.action_stop_conversion()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()


# ==============================================================================
# Executable Entry Point
# ==============================================================================
def main():
    app = QApplication(sys.argv)
    
    # High DPI scaling is enabled by default in Qt6
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
