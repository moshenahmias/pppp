import typing
from functools import partial

from PyQt5 import QtGui
from PyQt5.QtWidgets import QWidget, QHBoxLayout

from models import ScanlineModel, init_model
from tools import combine
from . import WPixel


class WScanline(QWidget):
    @init_model(ScanlineModel)
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        for i in range(self.model.pixel_count):
            pixel = WPixel(zoom=self.model.zoom, parent=self)

            pixel.mousePressEvent = combine(
                pixel.mousePressEvent,
                partial(self._on_pixel_mouse_press_event, i, pixel),
            )

            pixel.mouseMoveEvent = combine(
                pixel.mouseMoveEvent, partial(self._on_pixel_mouse_move_event, i, pixel)
            )

            pixel.wheelEvent = combine(
                pixel.wheelEvent, partial(self._on_pixel_wheel_event, i, pixel)
            )

            layout.addWidget(pixel)
            pixel.show()

        self.setLayout(layout)

        @self.model.palette_code.observe
        @self.model.bg_palette_code.observe
        def on_palette_code_change(_, __):
            for i_, pixel_ in enumerate(self.pixels):
                pixel_.model.selected.value = self.model.selection[i_]

                if self.model.pixels[i_] or self.model.layer_1[i_]:
                    pixel_.model.color.value = self.model.color
                else:
                    pixel_.model.color.value = self.model.bg_color

    def __getitem__(self, x: int) -> WPixel:
        return typing.cast(WPixel, self.layout().itemAt(x).widget())

    @property
    def pixels(self) -> typing.Generator[WPixel, None, None]:
        for i in range(self.model.pixel_count):
            yield self[i]

    def on_pixel_mouse_press_event(
        self, x: int, pixel: WPixel, event: QtGui.QMouseEvent
    ):
        pass

    def on_pixel_mouse_move_event(
        self, x: int, pixel: WPixel, event: QtGui.QMouseEvent
    ):
        pass

    def on_pixel_wheel_event(self, x: int, pixel: WPixel, event: QtGui.QWheelEvent):
        pass

    def _on_pixel_mouse_press_event(
        self, x: int, pixel: WPixel, event: QtGui.QMouseEvent
    ):
        self.on_pixel_mouse_press_event(x=x, pixel=pixel, event=event)

    def _on_pixel_mouse_move_event(
        self, x: int, pixel: WPixel, event: QtGui.QMouseEvent
    ):
        self.on_pixel_mouse_move_event(x=x, pixel=pixel, event=event)

    def _on_pixel_wheel_event(self, x: int, pixel: WPixel, event: QtGui.QWheelEvent):
        self.on_pixel_wheel_event(x=x, pixel=pixel, event=event)
