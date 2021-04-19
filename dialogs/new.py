import typing
from functools import partial

from PyQt5 import uic
from PyQt5.QtWidgets import QDialog, QLineEdit, QSpinBox, QRadioButton, QDialogButtonBox
from PyQt5.QtCore import Qt
from models import ColorSystem, PlayfieldMode
from tools import resource_path


class NewDialog(QDialog):
    def __init__(self, *args, **kwargs):
        flags = (
            Qt.WindowType.Window
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.CustomizeWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        super().__init__(*args, flags=flags, **kwargs)
        uic.loadUi(resource_path("ui/new.ui"), self)

        self.setFixedSize(self.size())

        self._line_edit_name = typing.cast(
            QLineEdit, self.findChild(QLineEdit, "lineEditName")
        )
        self.radio_button_color_system_ntsc = typing.cast(
            QRadioButton, self.findChild(QRadioButton, "radioButtonColorSystemNtsc")
        )
        self.radio_button_color_system_pal = typing.cast(
            QRadioButton, self.findChild(QRadioButton, "radioButtonColorSystemPal")
        )
        self.radio_button_color_system_secam = typing.cast(
            QRadioButton, self.findChild(QRadioButton, "radioButtonColorSystemSecam")
        )
        self._spin_box_scanlines = typing.cast(
            QSpinBox, self.findChild(QSpinBox, "spinBoxScanlines")
        )

        self.radio_button_mode_asymmetric = typing.cast(
            QRadioButton, self.findChild(QRadioButton, "radioButtonModeAsymmetric")
        )
        self.radio_button_mode_symmetric = typing.cast(
            QRadioButton, self.findChild(QRadioButton, "radioButtonModeSymmetric")
        )
        self.radio_button_mode_system_mirror = typing.cast(
            QRadioButton, self.findChild(QRadioButton, "radioButtonModeMirror")
        )

        self._button_box = typing.cast(
            QDialogButtonBox, self.findChild(QDialogButtonBox, "buttonBox")
        )

        def on_name_change():
            self._button_box.button(QDialogButtonBox.Ok).setEnabled(len(self.name) > 0)

        self._line_edit_name.textChanged.connect(on_name_change)

        def on_color_system_change(system: ColorSystem):
            self._spin_box_scanlines.setValue(
                {
                    ColorSystem.NTSC: 192,
                    ColorSystem.PAL: 242,
                    ColorSystem.SECAM: 242,
                }.get(system)
            )

        self.radio_button_color_system_ntsc.clicked.connect(
            partial(on_color_system_change, ColorSystem.NTSC)
        )
        self.radio_button_color_system_pal.clicked.connect(
            partial(on_color_system_change, ColorSystem.PAL)
        )
        self.radio_button_color_system_secam.clicked.connect(
            partial(on_color_system_change, ColorSystem.SECAM)
        )

        self._line_edit_name.setFocus()

    @property
    def name(self) -> str:
        return self._line_edit_name.text()

    @property
    def scanlines(self) -> int:
        return self._spin_box_scanlines.value()

    @property
    def color_system(self) -> ColorSystem:
        if self.radio_button_color_system_ntsc.isChecked():
            return ColorSystem.NTSC

        if self.radio_button_color_system_pal.isChecked():
            return ColorSystem.PAL

        return ColorSystem.SECAM

    @property
    def mode(self) -> PlayfieldMode:
        if self.radio_button_mode_asymmetric.isChecked():
            return PlayfieldMode.Asymmetric

        if self.radio_button_mode_symmetric.isChecked():
            return PlayfieldMode.Symmetric

        return PlayfieldMode.Mirror
