import typing
from dataclasses import dataclass, field

from tools import ObservableProperty


@dataclass
class PixelModel:
    default_width: typing.ClassVar[int] = 12
    default_height: typing.ClassVar[int] = 2

    zoom: ObservableProperty[int]

    color: ObservableProperty[str] = field(
        default_factory=lambda: ObservableProperty("000000")
    )

    selected: ObservableProperty[bool] = field(
        default_factory=lambda: ObservableProperty(False)
    )

    @property
    def width(self):
        return self.default_width * self.zoom.value

    @property
    def height(self):
        return self.default_height * self.zoom.value
