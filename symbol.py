from __future__ import annotations

import json
import typing
from dataclasses import dataclass, field


@dataclass
class Symbol:
    width: int
    height: int
    pixels: typing.List[typing.Tuple[int, int]] = field(default_factory=lambda: [])

    def add(self, y: int, x: int) -> Symbol:
        self.pixels.append((x, y))
        return self

    @classmethod
    def deserialize(cls, data: typing.Mapping, *args, **kwargs) -> Symbol:
        sym = cls(width=data["width"], height=data["height"])

        for y, xs in data["pixels"].items():
            for x in xs:
                sym.add(y=int(y), x=x)

        return sym


def deserialize_font(data: typing.Mapping, *args, **kwargs) -> typing.Mapping[str, Symbol]:
    font = {}

    for char, pixel_data in data.items():
        font[char] = Symbol.deserialize(data=pixel_data, *args, **kwargs)

    return font


def load_font(filename: str, *args, **kwargs) -> typing.Mapping[str, Symbol]:
    with open(filename) as file:
        data = json.load(file)
        return deserialize_font(data=data, *args, **kwargs)
