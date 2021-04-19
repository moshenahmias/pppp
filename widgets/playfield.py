import typing
from functools import partial

from PyQt5 import QtGui
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
)

from models import init_model, PlayfieldModel
from tools import combine
from . import WScanline, WPixel


class WPlayfield(QWidget):
    @init_model(PlayfieldModel)
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.setFixedSize(
            self.model.width,
            self.model.height,
        )

        for j in range(self.model.scanline_count):
            line = WScanline(
                zoom=self.model.zoom,
                color_mapping=self.model.color_mapping,
                parent=self,
            )

            line.on_pixel_mouse_press_event = combine(
                line.on_pixel_mouse_press_event,
                partial(self._on_scanline_mouse_press_event, line, j),
            )
            line.on_pixel_mouse_move_event = combine(
                line.on_pixel_mouse_move_event,
                partial(self._on_scanline_mouse_move_event, line, j),
            )
            line.on_pixel_wheel_event = combine(
                line.on_pixel_wheel_event,
                partial(self._on_scanline_wheel_event, line, j),
            )

            layout.addWidget(line)
            line.show()

        self.setLayout(layout)

        @self.model.zoom.observe
        def zoom(_, __):
            self.setFixedSize(
                self.model.width,
                self.model.height,
            )

    def __getitem__(self, y: int) -> WScanline:
        return typing.cast(WScanline, self.layout().itemAt(y).widget())

    @property
    def scanlines(self) -> typing.Generator[WScanline, None, None]:
        for j in range(self.model.scanline_count):
            yield self[j]

    def on_scanline_mouse_press_event(
        self, line: WScanline, y: int, x: int, pixel: WPixel, event: QtGui.QMouseEvent
    ):
        pass

    def on_scanline_mouse_move_event(
        self, line: WScanline, y: int, x: int, pixel: WPixel, event: QtGui.QMouseEvent
    ):
        pass

    def on_scanline_wheel_event(
        self, line: WScanline, y: int, x: int, pixel: WPixel, event: QtGui.QWheelEvent
    ):
        pass

    def _on_scanline_mouse_press_event(
        self, line: WScanline, y: int, x: int, pixel: WPixel, event: QtGui.QMouseEvent
    ):
        self.on_scanline_mouse_press_event(
            line=line, y=y, x=x, pixel=pixel, event=event
        )

    def _on_scanline_mouse_move_event(
        self, line: WScanline, y: int, x: int, pixel: WPixel, event: QtGui.QMouseEvent
    ):
        self.on_scanline_mouse_move_event(line=line, y=y, x=x, pixel=pixel, event=event)

    def _on_scanline_wheel_event(
        self, line: WScanline, y: int, x: int, pixel: WPixel, event: QtGui.QWheelEvent
    ):
        self.on_scanline_wheel_event(line=line, y=y, x=x, pixel=pixel, event=event)
