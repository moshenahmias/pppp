import typing
from functools import partial

from PyQt5 import uic
from PyQt5.QtWidgets import QFrame, QLabel, QPushButton

from models import init_model, PaletteModel
from tools import resource_path


class WPalette(QFrame):
    @init_model(PaletteModel)
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        uic.loadUi(resource_path("ui/palette.ui"), self)

        self._label_code = typing.cast(QLabel, self.findChild(QLabel, "labelCode"))

        def on_code_change(value: int, _):
            self._label_code.setStyleSheet(f"color:#{self.model.selected}")
            self._label_code.setText(f"{value:02X}")

        def on_palette_change(_, __):
            for i in range(16):
                for j in range(0, 15, 2):
                    ij = f"{i:01X}{j:01X}"
                    code = int(ij, 16)
                    color = self.model.color(code)

                    btn: QPushButton = typing.cast(
                        QPushButton, self.findChild(QPushButton, f"pushButtonColor{ij}")
                    )

                    btn.setStyleSheet(
                        f"background-color:#{color}; border-style: none; border-radius: 10px;"
                    )

                    def set_code(value: int):
                        self.model.code.value = value

                    btn.clicked.connect(partial(set_code, code))

            on_code_change(self.model.code.value, None)

        self.model.color_mapping.observe(on_palette_change)
        self.model.code.observe(on_code_change)

        on_palette_change(None, None)
