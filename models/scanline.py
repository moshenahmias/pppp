import typing
from dataclasses import dataclass, field

from tools import ObservableProperty

default_pixel_count = 40


@dataclass
class ScanlineModel:
    pixel_count: typing.ClassVar[int] = default_pixel_count

    zoom: ObservableProperty[int]
    color_mapping: typing.Mapping

    bg_palette_code: ObservableProperty[int] = field(
        default_factory=lambda: ObservableProperty(value=0x00, no_change_notify=True)
    )

    palette_code: ObservableProperty[int] = field(
        default_factory=lambda: ObservableProperty(value=0x00, no_change_notify=True)
    )

    selection: typing.List[bool] = field(
        default_factory=lambda: [False for _ in range(default_pixel_count)]
    )

    layer_1: typing.List[bool] = field(
        default_factory=lambda: [False for _ in range(default_pixel_count)]
    )

    pixels: typing.List[bool] = field(
        default_factory=lambda: [False for _ in range(default_pixel_count)]
    )

    def clear_selection(self) -> typing.Set[int]:
        mods = set()
        for i in range(default_pixel_count):
            if self.selection[i]:
                self.selection[i] = False
                if self.layer_1[i]:
                    self.layer_1[i] = False
                    self.pixels[i] = True
                    mods.add(i)

        return mods

    def copy_selection(self):
        for i in range(default_pixel_count):
            if self.selection[i] and self.pixels[i]:
                self.layer_1[i] = self.pixels[i]

    def cut_selection(self) -> typing.Set[int]:
        mods = set()
        for i in range(default_pixel_count):
            if self.selection[i] and self.pixels[i]:
                self.layer_1[i] = self.pixels[i]
                self.pixels[i] = False
                mods.add(i)

        return mods

    def delete_selection(self) -> typing.Set[int]:
        mods = set()
        for i in range(default_pixel_count):
            if self.selection[i]:
                self.layer_1[i] = False
                self.pixels[i] = False
                mods.add(i)
            self.selection[i] = False

        return mods

    def rotate_right(self):
        self.selection = self.selection[-1:] + self.selection[:-1]
        self.layer_1 = self.layer_1[-1:] + self.layer_1[:-1]

    def rotate_left(self):
        self.selection = self.selection[1:] + self.selection[:1]
        self.layer_1 = self.layer_1[1:] + self.layer_1[:1]

    def update(self, color: int = None, bg_color: int = None):
        if color is not None and bg_color is not None:
            self.bg_palette_code.silent_set(bg_color)
            self.palette_code.value = color
        elif color is not None:
            self.palette_code.value = color
        elif bg_color is not None:
            self.bg_palette_code.value = bg_color

    @property
    def color(self) -> int:
        return self.color_mapping[self.palette_code.value]

    @property
    def bg_color(self) -> int:
        return self.color_mapping[self.bg_palette_code.value]

    @property
    def pf0(self) -> int:
        pf = 0x10 if self.pixels[0] else 0x00
        pf = pf | 0x20 if self.pixels[1] else pf
        pf = pf | 0x40 if self.pixels[2] else pf
        pf = pf | 0x80 if self.pixels[3] else pf

        return pf

    @property
    def pf1(self) -> int:
        pf = 0x80 if self.pixels[4] else 0x00
        pf = pf | 0x40 if self.pixels[5] else pf
        pf = pf | 0x20 if self.pixels[6] else pf
        pf = pf | 0x10 if self.pixels[7] else pf
        pf = pf | 0x08 if self.pixels[8] else pf
        pf = pf | 0x04 if self.pixels[9] else pf
        pf = pf | 0x02 if self.pixels[10] else pf
        pf = pf | 0x01 if self.pixels[11] else pf

        return pf

    @property
    def pf2(self) -> int:
        pf = 0x01 if self.pixels[12] else 0x00
        pf = pf | 0x02 if self.pixels[13] else pf
        pf = pf | 0x04 if self.pixels[14] else pf
        pf = pf | 0x08 if self.pixels[15] else pf
        pf = pf | 0x10 if self.pixels[16] else pf
        pf = pf | 0x20 if self.pixels[17] else pf
        pf = pf | 0x40 if self.pixels[18] else pf
        pf = pf | 0x80 if self.pixels[19] else pf

        return pf

    @property
    def pf0_neighbor(self) -> int:
        pf = 0x10 if self.pixels[20] else 0x00
        pf = pf | 0x20 if self.pixels[21] else pf
        pf = pf | 0x40 if self.pixels[22] else pf
        pf = pf | 0x80 if self.pixels[23] else pf

        return pf

    @property
    def pf1_neighbor(self) -> int:
        pf = 0x80 if self.pixels[24] else 0x00
        pf = pf | 0x40 if self.pixels[25] else pf
        pf = pf | 0x20 if self.pixels[26] else pf
        pf = pf | 0x10 if self.pixels[27] else pf
        pf = pf | 0x08 if self.pixels[28] else pf
        pf = pf | 0x04 if self.pixels[29] else pf
        pf = pf | 0x02 if self.pixels[30] else pf
        pf = pf | 0x01 if self.pixels[31] else pf

        return pf

    @property
    def pf2_neighbor(self) -> int:
        pf = 0x01 if self.pixels[32] else 0x00
        pf = pf | 0x02 if self.pixels[33] else pf
        pf = pf | 0x04 if self.pixels[34] else pf
        pf = pf | 0x08 if self.pixels[35] else pf
        pf = pf | 0x10 if self.pixels[36] else pf
        pf = pf | 0x20 if self.pixels[37] else pf
        pf = pf | 0x40 if self.pixels[38] else pf
        pf = pf | 0x80 if self.pixels[39] else pf

        return pf
