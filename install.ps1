# install.ps1 - simple installer for Windows (creates venv and installs requirements)
param()

$ErrorActionPreference = 'Stop'

Write-Host "Creating virtual environment .venv..."
python -m venv .venv
Write-Host "Activating virtual environment..."
.\.venv\Scripts\Activate.ps1
Write-Host "Upgrading pip..."
python -m pip install --upgrade pip
Write-Host "Installing requirements from requirements.txt (excluding torch)..."
# install requirements but skip torch because user must pick correct CUDA wheel
Get-Content requirements.txt | Where-Object { $_ -notmatch '^\s*#' -and $_ -ne 'torch' -and $_ -ne 'torchvision' } | ForEach-Object { pip install $_ }
Write-Host "Done. Please install the correct torch wheel for your GPU following https://pytorch.org and then run:\n    pip install <torch-wheel-url>\n"
Write-Host "You can now run: python .\live_captioning.py"
