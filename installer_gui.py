from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout,
                             QMessageBox, QCheckBox)
import sys
import subprocess
import webbrowser
import os

from check_env import CHECKS if False else None

# Lightweight installer GUI to run checks and guide users
class InstallerWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Live Captioning Installer')
        self.resize(600, 300)
        layout = QVBoxLayout()

        layout.addWidget(QLabel('Environment checklist'))
        self.check_area = QVBoxLayout()
        layout.addLayout(self.check_area)

        btn_layout = QHBoxLayout()
        self.run_checks_btn = QPushButton('Run checks')
        self.install_btn = QPushButton('Run install.ps1')
        self.torch_btn = QPushButton('Open PyTorch site')
        self.model_btn = QPushButton('Open Whisper model page')
        btn_layout.addWidget(self.run_checks_btn)
        btn_layout.addWidget(self.install_btn)
        btn_layout.addWidget(self.torch_btn)
        btn_layout.addWidget(self.model_btn)
        layout.addLayout(btn_layout)

        self.setLayout(layout)

        self.run_checks_btn.clicked.connect(self.run_checks)
        self.install_btn.clicked.connect(self.run_install)
        self.torch_btn.clicked.connect(lambda: webbrowser.open('https://pytorch.org'))
        self.model_btn.clicked.connect(lambda: webbrowser.open('https://huggingface.co/openai/whisper'))

    def run_checks(self):
        # spawn the check_env.py and capture output
        try:
            out = subprocess.check_output([sys.executable, 'check_env.py'], stderr=subprocess.STDOUT, text=True)
        except subprocess.CalledProcessError as e:
            out = e.output
        dlg = QMessageBox(self)
        dlg.setWindowTitle('Checks output')
        dlg.setText(out)
        dlg.exec_()

    def run_install(self):
        # run the installer powershell script
        try:
            subprocess.check_call(['powershell', '-ExecutionPolicy', 'Bypass', '.\\install.ps1'], shell=True)
            QMessageBox.information(self, 'Installer', 'install.ps1 completed successfully.')
        except Exception as e:
            QMessageBox.critical(self, 'Installer', f'install.ps1 failed: {e}')

if __name__ == '__main__':
    app = QApplication(sys.argv)
    w = InstallerWindow()
    w.show()
    sys.exit(app.exec_())
