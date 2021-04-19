from __future__ import annotations

import typing
from collections import defaultdict
from dataclasses import dataclass, field

from models import ScanlineModel, Command
from widgets import WPlayfield


@dataclass
class CommandsGroup(Command):
    commands: typing.List[Command] = field(default_factory=lambda: [])

    def __len__(self):
        return len(self.commands)

    def append(self, command: Command) -> CommandsGroup:
        self.commands.append(command)
        return self

    def execute(self, *, force: bool = False, **kwargs) -> typing.Optional[Command]:
        if len(self) == 0:
            return None

        invert_group = CommandsGroup()

        for command in self.commands:
            invert = command.execute()
            if invert:
                invert_group.append(invert)

        return invert_group if len(invert_group) > 0 else None


@dataclass
class UpdateLinePaletteCode(Command):
    model: ScanlineModel
    code: int

    def execute(self) -> typing.Optional[Command]:
        if self.model.palette_code.value == self.code:
            return None

        invert = UpdateLinePaletteCode(
            model=self.model, code=self.model.palette_code.value
        )
        self.model.palette_code.value = self.code
        return invert


@dataclass
class UpdateLineBackgroundPaletteCode(Command):
    model: ScanlineModel
    code: int

    def execute(self) -> typing.Optional[Command]:
        if self.model.bg_palette_code.value == self.code:
            return None

        invert = UpdateLineBackgroundPaletteCode(
            model=self.model, code=self.model.bg_palette_code.value
        )
        self.model.bg_palette_code.value = self.code
        return invert


@dataclass
class UpdatePixels(Command):
    @dataclass
    class Update:
        x: int
        y: int
        status: bool
        code: int

    pf: WPlayfield
    updates: typing.List[Update]

    def execute(self) -> typing.Optional[Command]:
        invert_updates = []

        lines_to_update = typing.cast(
            typing.MutableMapping[int, typing.MutableMapping[str, int]],
            defaultdict(lambda: {"color": None, "bg_color": None}),
        )

        for update in self.updates:
            line = self.pf[update.y]
            current_status = line.model.pixels[update.x]
            if current_status != update.status:
                lines_to_update[update.y][
                    "color" if update.status else "bg_color"
                ] = update.code
                invert_updates.append(
                    UpdatePixels.Update(
                        x=update.x,
                        y=update.y,
                        status=current_status,
                        code=line.model.palette_code.value
                        if current_status
                        else line.model.bg_palette_code.value,
                    )
                )
                line.model.pixels[update.x] = update.status
            else:
                if update.status:
                    if line.model.palette_code.value != update.code:
                        lines_to_update[update.y]["color"] = update.code
                        invert_updates.append(
                            UpdatePixels.Update(
                                x=update.x,
                                y=update.y,
                                status=current_status,
                                code=line.model.palette_code.value,
                            )
                        )
                else:
                    if line.model.bg_palette_code.value != update.code:
                        lines_to_update[update.y]["bg_color"] = update.code
                        invert_updates.append(
                            UpdatePixels.Update(
                                x=update.x,
                                y=update.y,
                                status=current_status,
                                code=line.model.bg_palette_code.value,
                            )
                        )

        for j, codes in lines_to_update.items():
            self.pf[j].model.update(**codes)

        return (
            UpdatePixels(pf=self.pf, updates=invert_updates)
            if len(invert_updates) > 0
            else None
        )


@dataclass
class UpdatePixel(Command):
    pf: WPlayfield
    x: int
    y: int
    status: bool
    code: int

    def execute(self) -> typing.Optional[Command]:
        return UpdatePixels(
            pf=self.pf,
            updates=[
                UpdatePixels.Update(
                    x=self.x, y=self.y, status=self.status, code=self.code
                )
            ],
        ).execute()


@dataclass
class ClearPixels(Command):
    pf: WPlayfield
    code: int

    def execute(self) -> typing.Optional[Command]:

        updates = []

        for j, line in enumerate(self.pf.scanlines):
            for i, _ in enumerate(line.pixels):
                updates.append(
                    UpdatePixels.Update(x=i, y=j, status=False, code=self.code)
                )

        if len(updates) == 0:
            return None

        return UpdatePixels(pf=self.pf, updates=updates).execute()
