from PyQt5 import QtGui, QtCore
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget

from models import init_model, PixelModel


class WPixel(QWidget):
    @init_model(PixelModel)
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFixedSize(self.model.width, self.model.height)
        self.setMouseTracking(True)
        self.model.zoom.observe(
            lambda _, __: self.setFixedSize(self.model.width, self.model.height)
        )
        self.model.color.observe(lambda _, __: self.update())
        self.model.selected.observe(lambda _, __: self.update())

    def paintEvent(self, e):
        painter = QtGui.QPainter(self)
        brush = QtGui.QBrush()

        brush.setStyle(Qt.BrushStyle.SolidPattern)

        # if self.model.selected.value:
        #     brush.setColor(QtGui.QColor("white"))
        #     rect = QtCore.QRect(0, 0, self.model.width, self.model.height)
        #     painter.fillRect(rect, brush)
        #     brush.setColor(QtGui.QColor(f"#{self.model.color.value}"))
        #     rect = QtCore.QRect(2, 2, self.model.width-2, self.model.height-2)
        # else:
        #     brush.setColor(QtGui.QColor(f"#{self.model.color.value}"))
        #     rect = QtCore.QRect(0, 0, self.model.width, self.model.height)

        if self.model.selected.value:
            brush.setStyle(Qt.BrushStyle.Dense4Pattern)

        brush.setColor(QtGui.QColor(f"#{self.model.color.value}"))
        rect = QtCore.QRect(0, 0, self.model.width, self.model.height)

        painter.fillRect(rect, brush)
