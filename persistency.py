import json
import typing

from models import ScanlineModel, PlayfieldMode, ColorSystem
from widgets import WPlayfield


def serialize_playfield(pf: WPlayfield, version: str) -> typing.Mapping:
    scanlines = []

    for j in range(pf.model.scanline_count):
        line = pf[j]
        line_data = [
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            line.model.palette_code.value,
            line.model.bg_palette_code.value,
        ]

        for i in range(ScanlineModel.pixel_count):
            if line.model.pixels[i]:
                line_data[int(i / 8)] = line_data[int(i / 8)] | (0x80 >> int(i % 8))

        scanlines.append(line_data)

    return {
        "version": version,
        "name": pf.model.name,
        "mode": pf.model.mode.name,
        "color_system": pf.model.color_system.name,
        "scanlines": scanlines,
    }


def deserialize_playfield(data: typing.Mapping, *args, **kwargs) -> WPlayfield:
    scanlines_data = data["scanlines"]

    pf = WPlayfield(
        name=data["name"],
        mode=PlayfieldMode[data["mode"]],
        color_system=ColorSystem[data["color_system"]],
        scanline_count=len(scanlines_data),
        *args,
        **kwargs,
    )

    for j in range(pf.model.scanline_count):
        line = pf[j]
        line_data = scanlines_data[j]

        for i in range(ScanlineModel.pixel_count):
            line.model.pixels[i] = line_data[int(i / 8)] & (0x80 >> int(i % 8)) != 0

        line.model.palette_code.value = line_data[5]
        line.model.bg_palette_code.value = line_data[6]

    return pf


def save_playfield(pf: WPlayfield, to: str, version: str):
    data = serialize_playfield(pf=pf, version=version)
    with open(to, "w") as f:
        json.dump(obj=data, fp=f)


def load_playfield(from_: str, *args, **kwargs) -> WPlayfield:
    with open(from_) as file:
        data = json.load(file)
        return deserialize_playfield(data=data, *args, **kwargs)
