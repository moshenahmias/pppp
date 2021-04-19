import typing

from PyQt5 import uic
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QDialog, QLabel

from tools import resource_path


class AboutDialog(QDialog):
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
