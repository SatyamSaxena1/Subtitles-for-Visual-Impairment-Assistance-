# Live Captioning (VBCABLE + Whisper)

Lightweight local live-captioning for Windows. Capture system audio routed through VBCABLE and transcribe locally with a Whisper model (via faster_whisper). The app shows an always-on-top caption window suitable for deaf users.

This repo contains:

- `live_captioning.py`  main script. Configure VBCABLE as the system playback device, then run this.
- `requirements.txt`  minimal Python dependencies.

## Quick start

1. Install VBCABLE (VBAudio Virtual Cable)
   - Download and install VBCABLE from the VBAudio project (search for "VB-CABLE Virtual Audio Device").
   - After install, reboot if the installer asks.

2. Route system audio to VBCABLE
   - Open Windows Sound settings > Output device and choose the device named like `CABLE Input (VB-Audio Virtual Cable)` as your default output.
   - The script listens on the matching `CABLE Output (VB-Audio Virtual Cable)` device, which receives the forwarded audio.

3. Prepare Python environment
   - Create and activate a Python environment (recommended: 3.10+).
   - Install dependencies (see `requirements.txt`). Note: install `torch` separately to match your CUDA version  see https://pytorch.org for the correct wheel.

PowerShell example:

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
# Install torch with the correct CUDA for your GPU following the instructions at https://pytorch.org
```

4. Run the captioning app

```powershell
python .\live_captioning.py
```

The script will try to auto-detect the VBCABLE device name. If it cannot find it, it will print the available device list  copy the index and either change the code or open an issue requesting a CLI option.

## Notes & troubleshooting

- GPU vs CPU: The script attempts to load `faster_whisper` on CUDA (float16) and will fall back to CPU if GPU load fails. For best performance on an RTX GPU, ensure you installed a `torch` build with the correct CUDA (see PyTorch site).
- Device names vary by Windows and VBAudio version. If your device name differs, open `Settings > Sound` to find the exact name, or run the script to view the printed device list.
- If captions lag: the script uses a bounded queue and drops oldest audio when overloaded to keep captions near-real-time. If you need longer transcription windows (more accurate/full sentences), increase `MAX_QUEUE_SECONDS` in `live_captioning.py`.
- If `faster_whisper` import or model load fails, ensure you have the dependencies installed and compatible versions of CUDA drivers.

## Accessibility options

- The caption window is frameless and always-on-top. You can edit `live_captioning.py` to change font, size, background opacity, and position.

## Packaging and distribution

- For non-technical users, considering packaging the app with PyInstaller into a single `exe`. Note: bundling a GPU-enabled model and the correct `torch` build increases complexity; you may want to provide clear instructions instead of a full bundled GPU build. Any ideas of alternatives are welcome

## License & credits

- Suggested license: MIT  add `LICENSE` if you want to publish.
- VBAudio (VBCABLE) is a third-party project; include attribution in your repo README when publishing.

## Next improvements (ideas)

- Small device-selection GUI and persistent config file for non-technical users.
- Large-font / high-contrast themes and position presets for accessibility.
- One-click installer or packaged binaries for Windows.

If you want, I can add a `README` section with screenshots and a short troubleshooting GIF for the VBCABLE steps.

## Model weights (manual download option)

By default the app will attempt to download Whisper model weights automatically the first time it loads the model if internet is available. If you prefer to download them manually (or need to distribute the weights to an offline machine), download the model file and place it in `models/whisper/`.

- Suggested place to get Whisper models: https://huggingface.co/openai/whisper (choose the model size you want)

Place the downloaded files (or extracted folder) under `models/whisper/<model-name>/` and then set the `MODEL_PATH` environment variable to the path of the model directory, or edit `live_captioning.py` to point to the local path.

## Automated installer script (Windows PowerShell)

An `install.ps1` helper will create a venv and install Python packages from `requirements.txt`. It does not install `torch` automatically — follow the PyTorch site for the correct wheel for your GPU/CUDA.

Run in PowerShell (as user):

```powershell
.\install.ps1
```

## Environment checker

Run `check_env.py` to verify your Python, packages, and VB-CABLE installation. The script prints a checklist and detects several common errors (missing torch, incompatible CUDA, missing sounddevice backend). If an error is detected the script reports a helpful message and offers a link to open a GitHub issue.


