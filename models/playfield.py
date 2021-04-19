import typing
from dataclasses import dataclass, field

import palettes
from tools import ObservableProperty, CappedStack, ObservableMatrix
from . import PlayfieldMode, ColorSystem, ScanlineModel, PixelModel, Command


@dataclass
class PlayfieldModel:

    min_zoom: typing.ClassVar[int] = 1
    max_zoom: typing.ClassVar[int] = 40
    max_undo_redo: typing.ClassVar[int] = 100

    name: str
    mode: PlayfieldMode
    color_system: ColorSystem
    scanline_count: int
    zoom: ObservableProperty[int]
    filename: str = None
    need_save: bool = False
    prev_drag_x: int = None
    prev_drag_y: int = None

    bg_palette_code: ObservableProperty[int] = field(
        default_factory=lambda: ObservableProperty(0x00)
    )

    palette_code: ObservableProperty[int] = field(
        default_factory=lambda: ObservableProperty(0x00)
    )

    undo_commands: CappedStack[Command] = field(
        default_factory=lambda: CappedStack(maximum=PlayfieldModel.max_undo_redo)
    )

    redo_commands: CappedStack[Command] = field(
        default_factory=lambda: CappedStack(maximum=PlayfieldModel.max_undo_redo)
    )

    def undo(self):
        if not self.undo_commands.empty():
            command = self.undo_commands.pop()
            invert = command.execute()
            if invert:
                self.redo_commands.push(invert)

    def redo(self):
        if not self.redo_commands.empty():
            command = self.redo_commands.pop()
            invert = command.execute()
            if invert:
                self.undo_commands.push(invert)

    def execute(self, command: Command, *more):
        invert = command.execute()
        if invert:
            self.undo_commands.push(invert)

        for command_ in more:
            invert = command_.execute()
            if invert:
                self.undo_commands.push(invert)

    def neighbor(self, x: int) -> typing.Optional[int]:
        if self.mode == PlayfieldMode.Asymmetric:
            return None

        return (
            ScanlineModel.pixel_count - x - 1
            if self.mode == PlayfieldMode.Mirror
            else (x + 20 if x < 20 else x - 20)
        )

    def zoom_in(self) -> int:
        if self.zoom.value < self.max_zoom:
            self.zoom.value += 1

        return self.zoom.value

    def zoom_out(self) -> int:
        if self.zoom.value > self.min_zoom:
            self.zoom.value -= 1

        return self.zoom.value

    @property
    def color_mapping(self) -> typing.Mapping[int, str]:
        return palettes.table[self.color_system]

    @property
    def width(self):
        return ScanlineModel.pixel_count * PixelModel.default_width * self.zoom.value

    @property
    def height(self):
        return self.scanline_count * PixelModel.default_height * self.zoom.value
