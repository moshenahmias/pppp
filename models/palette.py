import typing
from dataclasses import dataclass, field

from tools import ObservableProperty


@dataclass
class PaletteModel:

    color_mapping: ObservableProperty[typing.Mapping[int, str]]
    code: ObservableProperty[int] = field(
        default_factory=lambda: ObservableProperty(0x00)
    )

    def color(self, code: int) -> str:
        return self.color_mapping.value[code]

    @property
    def selected(self) -> str:
        return self.color(self.code.value)
