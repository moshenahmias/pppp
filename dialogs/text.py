import typing

from PyQt5 import uic
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QDialog, QLineEdit, QDialogButtonBox, QComboBox

from tools import resource_path


class InsertText(QDialog):
    def __init__(self, *args, fonts: typing.Iterable[str], **kwargs):
        flags = (
            Qt.WindowType.Window
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.CustomizeWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        super().__init__(*args, flags=flags, **kwargs)
        uic.loadUi(resource_path("ui/text.ui"), self)

        self.setFixedSize(self.size())

        self._line_edit_text = typing.cast(
            QLineEdit, self.findChild(QLineEdit, "lineEditText")
        )

        self._combo_box_font = typing.cast(
            QComboBox, self.findChild(QComboBox, "comboBoxFont")
        )

        self._button_box = typing.cast(
            QDialogButtonBox, self.findChild(QDialogButtonBox, "buttonBox")
        )

        def on_text_change():
            self._button_box.button(QDialogButtonBox.Ok).setEnabled(len(self.text) > 0)

        self._line_edit_text.textChanged.connect(on_text_change)

        on_text_change()

        for font in fonts:
            self._combo_box_font.addItem(font)

        self._line_edit_text.setFocus()

    @property
    def text(self) -> str:
        return self._line_edit_text.text()

    @property
    def font(self) -> str:
        return self._combo_box_font.currentText()
