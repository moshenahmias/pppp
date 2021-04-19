from __future__ import annotations
import enum
import abc
from dataclasses import fields, dataclass, field
from functools import wraps


class PlayfieldMode(enum.Enum):
    Asymmetric = enum.auto()
    Symmetric = enum.auto()
    Mirror = enum.auto()


class ColorSystem(enum.Enum):
    NTSC = enum.auto()
    PAL = enum.auto()
    SECAM = enum.auto()


class ToolboxTool(enum.Enum):
    Pen = enum.auto()
    Brush = enum.auto()
    Bucket = enum.auto()
    Eraser = enum.auto()
    Line = enum.auto()
    ColorPicker = enum.auto()
    Selection = enum.auto()


@dataclass
class Command(abc.ABC):
    @abc.abstractmethod
    def execute(self) -> typing.Optional[Command]:
        raise NotImplementedError


from .pixel import PixelModel
from .scanline import ScanlineModel
from .playfield import PlayfieldModel
from .palette import PaletteModel


def init_model(model_cls, **model_kwargs):
    def decorator(f):
        @wraps(f)
        def wrapper(self, *args, **kwargs):
            model_fields = set(map(lambda fld: fld.name, fields(model_cls)))
            widget_kwargs = {}

            for k, v in kwargs.items():
                if k in model_fields:
                    model_kwargs[k] = v
                else:
                    widget_kwargs[k] = v

            self.model = model_cls(**model_kwargs)
            f(self, *args, **widget_kwargs)

        return wrapper

    return decorator
