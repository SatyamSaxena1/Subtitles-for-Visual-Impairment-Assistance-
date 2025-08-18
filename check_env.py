#!/usr/bin/env python
"""Simple environment checker for Live Captioning.

Checks Python version, key packages, CUDA availability for torch, and VB-CABLE device presence.
"""
import sys
import importlib
import sounddevice as sd
import os

CHECKS = []

# Python version
py_ok = sys.version_info >= (3, 10)
CHECKS.append(("Python 3.10+", py_ok, sys.version.splitlines()[0]))

# packages
def check_pkg(name):
    try:
        m = importlib.import_module(name)
        return True, getattr(m, '__version__', 'unknown')
    except Exception as e:
        return False, str(e)

for pkg in ['numpy', 'sounddevice', 'PyQt5', 'faster_whisper']:
    ok, ver = check_pkg(pkg)
    CHECKS.append((pkg, ok, ver))

# torch + cuda
try:
    import torch
    torch_ok = True
    cuda_ok = torch.cuda.is_available()
    torch_ver = torch.__version__
except Exception as e:
    torch_ok = False
    cuda_ok = False
    torch_ver = str(e)
CHECKS.append(('torch', torch_ok, torch_ver))
CHECKS.append(('torch.cuda_available', cuda_ok, ''))

# VB-Cable detection
vb_found = False
vb_list = []
try:
    devs = sd.query_devices()
    for i, d in enumerate(devs):
        name = d.get('name', '')
        vb_list.append((i, name))
        if 'cable' in name.lower():
            vb_found = True
except Exception as e:
    vb_list = str(e)

CHECKS.append(('VB-CABLE device detected', vb_found, vb_list if vb_found else 'not found'))

# Print results
print('\nEnvironment check results:\n')
for name, ok, info in CHECKS:
    status = 'OK' if ok else 'MISSING'
    print(f"{name:30} : {status} - {info}")

# If any missing, offer quick help
missing = [c for c in CHECKS if not c[1]]
if missing:
    print('\nSome checks failed. Common fixes:')
    for name, ok, info in missing:
        if name == 'torch':
            print('- torch missing or failed to import: install a matching wheel for your CUDA version from https://pytorch.org')
        if name == 'torch.cuda_available' and not info:
            print('- CUDA not available to torch: ensure drivers and CUDA runtime match the torch wheel')
        if name == 'faster_whisper':
            print('- faster_whisper missing: pip install faster_whisper')
        if name == 'VB-CABLE device detected':
            print('- VB-CABLE not detected: install VB-CABLE and set system output to CABLE Input')
    print('\nIf you want, open a GitHub issue with the log (press Y).')
    ans = input('Open issue? (Y/n): ').strip().lower()
    if ans in ('y', 'yes', ''):
        import webbrowser
        webbrowser.open('https://github.com/your/repo/issues/new')

print('\nDone.')
