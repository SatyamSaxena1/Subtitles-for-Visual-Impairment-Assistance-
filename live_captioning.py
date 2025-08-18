import sys
import os
import queue
import json
import numpy as np
import sounddevice as sd
# Note: defer importing WhisperModel until runtime to avoid heavy GPU work on import
from PyQt5.QtWidgets import (QApplication, QLabel, QVBoxLayout, QWidget, QHBoxLayout,
                             QPushButton, QComboBox, QDialog, QTextEdit, QScrollArea,
                             QSizePolicy, QRadioButton, QButtonGroup)
from PyQt5.QtCore import Qt, QTimer, QPoint
from PyQt5.QtGui import QFont, QTextCursor

# Configuration
DEVICE_NAME = "CABLE Output (VB-Audio Virtual Cable"
SAMPLE_RATE = 16000
CHANNELS = 1
BLOCKSIZE = 8000
DTYPE = 'int16'
UPDATE_INTERVAL_MS = 500  # 0.5s
MAX_QUEUE_SECONDS = 5
# approximate number of blocks we keep before dropping oldest
MAX_QUEUE_SIZE = max(1, int((MAX_QUEUE_SECONDS * SAMPLE_RATE) / max(1, BLOCKSIZE)))


# Config
CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.json')

# Global placeholders (set at runtime)
model = None
app = None
window = None

# Bounded queue size (blocks)
AUDIO_QUEUE_MAXSIZE = max(2, MAX_QUEUE_SIZE * 2)


# ===== Audio buffer queue =====
audio_q = queue.Queue(AUDIO_QUEUE_MAXSIZE)

def audio_callback(indata, frames, time, status):
    """Push incoming audio chunks into queue with a drop-oldest policy when full.

    This callback runs in a high-priority audio thread so keep it cheap.
    """
    if status:
        print(f"[AUDIO CALLBACK WARNING] {status}")
    # cheap check for silence; only log when there's a significant signal
    max_amp = float(np.max(np.abs(indata)))
    if max_amp > 0.01:
        # non-blocking: drop oldest if full to avoid blocking audio thread
        try:
            if audio_q.full():
                try:
                    audio_q.get_nowait()  # drop oldest
                except queue.Empty:
                    pass
            audio_q.put_nowait(indata.copy())
        except queue.Full:
            # last-resort: silently drop if we couldn't make room
            pass

class CaptionWindow(QWidget):
    """Main caption window with two modes:
    - live: large caption + history box (like TikTok)
    - comprehensive: fixed-size scrollable transcript box
    Both modes are draggable (frameless window).
    """
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)
        self.setStyleSheet("background-color: rgba(0, 0, 0, 200); color: white;")
        self.drag_position = None

        # UI elements
        self.mode = 'live'  # default; can be overridden by config

        # Live mode: big caption + history
        self.big_label = QLabel("Listening to system audio...", self)
        self.big_label.setWordWrap(True)
        big_font = QFont()
        big_font.setPointSize(28)
        big_font.setBold(True)
        self.big_label.setFont(big_font)

        self.history = QTextEdit(self)
        self.history.setReadOnly(True)
        self.history.setStyleSheet("background: rgba(0,0,0,0); color: white; border: none;")
        self.history.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Comprehensive mode: scrollable fixed box
        self.comprehensive_area = QScrollArea(self)
        self.comprehensive_area.setWidgetResizable(True)
        self.comprehensive_text = QTextEdit()
        self.comprehensive_text.setReadOnly(True)
        self.comprehensive_area.setWidget(self.comprehensive_text)
        self.comprehensive_area.setFixedSize(600, 300)

        # controls
        self.settings_btn = QPushButton("⚙")
        self.settings_btn.setFixedSize(28, 28)
        self.settings_btn.setStyleSheet("background: transparent; color: white; border: none;")
        self.settings_btn.clicked.connect(self.open_settings)

        # Mode buttons
        self.live_btn = QPushButton("Live")
        self.comp_btn = QPushButton("Comprehensive")
        self.live_btn.setCheckable(True)
        self.comp_btn.setCheckable(True)
        self.live_btn.clicked.connect(lambda: self.set_mode('live'))
        self.comp_btn.clicked.connect(lambda: self.set_mode('comprehensive'))

        btn_h = QHBoxLayout()
        btn_h.addWidget(self.live_btn)
        btn_h.addWidget(self.comp_btn)
        btn_h.addWidget(self.settings_btn)

        # Layout assembly
        main_layout = QVBoxLayout()
        main_layout.addLayout(btn_h)
        main_layout.addWidget(self.big_label)
        main_layout.addWidget(self.history)
        main_layout.addWidget(self.comprehensive_area)
        self.setLayout(main_layout)

        # initial sizes and visibility
        self.resize(900, 200)
        self.move(100, 100)
        self.set_mode(self.mode)

    def set_mode(self, mode_name: str):
        self.mode = mode_name
        if mode_name == 'live':
            self.big_label.show()
            self.history.show()
            self.comprehensive_area.hide()
            self.live_btn.setChecked(True)
            self.comp_btn.setChecked(False)
            # larger window for live
            self.resize(900, 300)
        else:
            self.big_label.hide()
            self.history.hide()
            self.comprehensive_area.show()
            self.live_btn.setChecked(False)
            self.comp_btn.setChecked(True)
            # set a compact size for comprehensive
            self.resize(640, 380)

    def append_transcript(self, text: str):
        """Append a transcribed segment to the appropriate UI depending on mode."""
        if self.mode == 'live':
            # show latest as big caption and append to history
            self.big_label.setText(text)
            # prepend to history so newest appears at the top
            try:
                cursor = self.history.textCursor()
                cursor.beginEditBlock()
                cursor.movePosition(QTextCursor.Start)
                cursor.insertText(text + "\n")
                cursor.endEditBlock()
                # ensure view is at the top so newest is visible
                self.history.moveCursor(QTextCursor.Start)
            except Exception:
                # fallback
                self.history.insertPlainText(text + "\n")
        else:
            # comprehensive: append to the scrollable transcript
            try:
                cursor = self.comprehensive_text.textCursor()
                cursor.beginEditBlock()
                cursor.movePosition(QTextCursor.Start)
                cursor.insertText(text + "\n")
                cursor.endEditBlock()
                self.comprehensive_text.moveCursor(QTextCursor.Start)
            except Exception:
                self.comprehensive_text.insertPlainText(text + "\n")

    def open_settings(self):
        dlg = SettingsWindow(parent=self)
        # preload selection for mode
        cfg = load_config() or {}
        pref = cfg.get('mode')
        if pref:
            dlg.mode_group.button(0).setChecked(pref == 'live')
        if dlg.exec_():
            # after saving, re-read config to apply mode
            cfg = load_config() or {}
            mode = cfg.get('mode', 'live')
            self.set_mode(mode)

    # make the window draggable since it's frameless
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self.drag_position and event.buttons() == Qt.LeftButton:
            self.move(event.globalPos() - self.drag_position)
            event.accept()


class SettingsWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Select audio device (VB-Cable):"))
        self.device_combo = QComboBox()
        try:
            devs = sd.query_devices()
            for i, d in enumerate(devs):
                name = d.get('name', '')
                self.device_combo.addItem(f"{i}: {name}", i)
        except Exception:
            self.device_combo.addItem("(no devices found)")

        # preload selection from config
        cfg = load_config()
        sel_name = cfg.get('device_name') if cfg else None
        if sel_name:
            for idx in range(self.device_combo.count()):
                if sel_name.lower() in self.device_combo.itemText(idx).lower():
                    self.device_combo.setCurrentIndex(idx)
                    break

        layout.addWidget(self.device_combo)
        # Mode selection
        layout.addWidget(QLabel("Display mode:"))
        self.mode_live = QRadioButton("Live (large captions + history)")
        self.mode_comp = QRadioButton("Comprehensive (scrollable transcript)")
        self.mode_group = QButtonGroup()
        self.mode_group.addButton(self.mode_live)
        self.mode_group.addButton(self.mode_comp)
        layout.addWidget(self.mode_live)
        layout.addWidget(self.mode_comp)
        # preload mode selection from config
        cfg_mode = load_config() or {}
        mode_sel = cfg_mode.get('mode', 'live')
        if mode_sel == 'live':
            self.mode_live.setChecked(True)
        else:
            self.mode_comp.setChecked(True)

        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Save")
        cancel_btn = QPushButton("Cancel")
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)
        self.setLayout(layout)

        save_btn.clicked.connect(self.save_and_close)
        cancel_btn.clicked.connect(self.reject)

    def save_and_close(self):
        text = self.device_combo.currentText()
        try:
            _, name = text.split(": ", 1)
        except Exception:
            name = text
        mode = 'live' if getattr(self, 'mode_live', None) and self.mode_live.isChecked() else 'comprehensive'
        cfg = {'device_name': name, 'mode': mode}
        save_config(cfg)
        from PyQt5.QtWidgets import QMessageBox
        QMessageBox.information(self, "Saved", "Device saved. Please restart the application to apply changes.")
        self.accept()

def process_audio():
    """Take queued audio chunks (up to a bounded window) and transcribe.

    Runs in the Qt main thread via QTimer.
    """
    global model, window
    if audio_q.empty():
        return

    chunks = []
    # collect up to MAX_QUEUE_SIZE chunks to limit duration
    for _ in range(MAX_QUEUE_SIZE):
        try:
            chunks.append(audio_q.get_nowait())
        except queue.Empty:
            break

    if not chunks:
        return

    audio = np.concatenate(chunks, axis=0).flatten()

    # normalize only if int16
    if audio.dtype == np.int16:
        audio = audio.astype(np.float32) / 32768.0
    else:
        audio = audio.astype(np.float32)

    peak = np.max(np.abs(audio)) if audio.size else 0
    if peak < 0.001:
        return

    if model is None:
        print("[ERROR] Model not loaded yet; skipping transcription.")
        return

    try:
        segments, _ = model.transcribe(audio, vad_filter=True, language="en")
        appended = False
        for segment in segments:
            appended = True
            # append streaming style: keep prior text and add new segment
            try:
                window.append_transcript(segment.text)
            except Exception:
                print(segment.text)
            print(f"[TRANSCRIPTION] {segment.text}")
        if not appended:
            # nothing detected
            pass
    except Exception as e:
        print(f"[ERROR] Transcription failed: {e}")

def find_device_by_name(name_substring: str):
    """Return the device index that contains name_substring, or None."""
    try:
        devs = sd.query_devices()
    except Exception:
        return None
    for idx, dev in enumerate(devs):
        try:
            if name_substring.lower() in dev['name'].lower():
                return idx
        except Exception:
            continue
    return None


def load_config():
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def save_config(cfg: dict):
    try:
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, indent=2)
    except Exception as e:
        print(f"[WARN] Failed to save config: {e}")


def main():
    global model, app, window
    # model load (deferred) with GPU preferred and CPU fallback
  # Ensure a QApplication exists before showing any dialogs
    try:
        from PyQt5.QtWidgets import QApplication as _QApp
        if _QApp.instance() is None:
            app = _QApp(sys.argv)
        else:
            app = _QApp.instance()
    except Exception:
        app = None
  
    # model path handling: prefer MODEL_PATH env var, then models/whisper/<model-dir> if present
    model_path = os.environ.get('MODEL_PATH')
    if not model_path:
        # try to find any folder under models/whisper
        base = os.path.join(os.path.dirname(__file__), 'models', 'whisper')
        if os.path.isdir(base):
            try:
                entries = [d for d in os.listdir(base) if os.path.isdir(os.path.join(base, d))]
                if entries:
                    # pick the first one
                    model_path = os.path.join(base, entries[0])
            except Exception:
                pass
    try:
        import faster_whisper
        from faster_whisper import WhisperModel
        print(f"[INIT] faster_whisper version: {faster_whisper.__version__}")
    except Exception as e:
        print(f"[ERROR] faster_whisper import failed: {e}")
        # continue; allow user to see device list even if model import fails
    try:
        print("[INIT] Loading Whisper model (prefer local path if set)...")
        if model_path:
            print(f"[INIT] Using local model path: {model_path}")
            model = WhisperModel(model_path, device="cuda", compute_type="float16")
            print("[INIT] Model loaded on CUDA successfully.")
        else:
            # Do NOT auto-download without user consent. Prompt via GUI.
            try:
                from PyQt5.QtWidgets import QMessageBox
                answer = QMessageBox.question(None, "Whisper model not found",
                    "No local Whisper model was found. Do you want the app to download the model now?\n(This requires internet and may download a large file)",
                    QMessageBox.Yes | QMessageBox.No)
            except Exception:
                # If GUI not available, default to not downloading
                answer = None

            if answer == QMessageBox.Yes:
                print("[INIT] User agreed to download model; loading model by name (may download weights)...")
                model = WhisperModel("tiny", device="cuda", compute_type="float16")
                print("[INIT] Model loaded on CUDA successfully.")
            else:
                print("[INIT] No local model and user declined auto-download. Please download a model and place it under models/whisper/<model-dir> or set MODEL_PATH.")
                model = None
    except Exception as e:
        print(f"[WARN] GPU model load failed: {e}. Falling back to CPU.")
        try:
            model = WhisperModel("tiny", device="cpu", compute_type="int8")
            print("[INIT] Model loaded on CPU successfully.")
        except Exception as e2:
            print(f"[ERROR] CPU model load failed: {e2}")
            model = None

    # create GUI and timer
    app = QApplication(sys.argv)
    window = CaptionWindow()
    window.show()

    timer = QTimer()
    timer.timeout.connect(process_audio)
    timer.start(UPDATE_INTERVAL_MS)

    # Start audio stream
    try:
        print("[INIT] Starting audio stream...")
        # try to auto-detect VB-Cable by name, prefer saved config
        cfg = load_config() or {}
        prefer_name = cfg.get('device_name') or DEVICE_NAME
        device_idx = None
        if prefer_name:
            device_idx = find_device_by_name(prefer_name)
            if device_idx is not None:
                print(f"[INIT] Using device index {device_idx} for device name match: '{prefer_name}'")
        if device_idx is None:
            # fall back to default heuristic
            device_idx = find_device_by_name(DEVICE_NAME)
            if device_idx is not None:
                print(f"[INIT] Using device index {device_idx} for default VB-Cable name heuristic")
            else:
                print("[INIT] VB-Cable device not auto-detected; using default input.\nAvailable devices:")
                try:
                    for i, d in enumerate(sd.query_devices()):
                        print(f"  {i}: {d['name']}")
                except Exception:
                    pass

        with sd.InputStream(callback=audio_callback,
                            channels=CHANNELS,
                            samplerate=SAMPLE_RATE,
                            blocksize=BLOCKSIZE,
                            device=device_idx,
                            dtype=DTYPE,
                            latency="low"):
            app.exec_()
    except Exception as e:
        print(f"[ERROR] Audio stream failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
