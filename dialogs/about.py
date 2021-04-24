import typing
import webbrowser
from os import path

from PyQt5 import uic
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QDialog, QLabel, QPushButton

from tools import resource_path, error_box


class AboutDialog(QDialog):

    license_file_name = "LICENSE"

    def __init__(self, *, version: str, **kwargs):
        flags = (
            Qt.WindowType.Window
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.CustomizeWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        super().__init__(flags=flags, **kwargs)
        uic.loadUi(resource_path("ui/about.ui"), self)
        self.setFixedSize(self.size())
        label_version = typing.cast(QLabel, self.findChild(QLabel, "labelVersion"))
        label_version.setText(f"Version: {version}")

        license_button = typing.cast(
            QPushButton, self.findChild(QPushButton, "pushButtonLicense")
        )

        @error_box(Exception, text=lambda _: "Failed to open license file", parent=self)
        def on_license_button_click(_):
            if not path.exists(self.license_file_name):
                raise Exception(f"File {self.license_file_name} not found")

            webbrowser.open(self.license_file_name)
            self.close()

        license_button.clicked.connect(on_license_button_click)
