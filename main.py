import os
import sys
import time
import typing
from collections import defaultdict, deque
from functools import partial, wraps

from PyQt5 import uic, QtGui, QtPrintSupport
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QPixmap, QKeyEvent
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QScrollArea,
    QMdiArea,
    QMdiSubWindow,
    QAction,
    QStatusBar,
    QFileDialog,
    QMessageBox,
    QWidget,
    QSplashScreen,
    QMenu,
)

import palettes
import symbol
from commands import (
    UpdateLinePaletteCode,
    CommandsGroup,
    UpdateLineBackgroundPaletteCode,
    ClearPixels,
    UpdatePixels,
)
from dialogs.about import AboutDialog
from dialogs.new import NewDialog
from dialogs.text import InsertText
from models import (
    ScanlineModel,
    ToolboxTool,
    Command,
    PixelModel,
    PlayfieldMode,
)
from persistency import save_playfield, load_playfield
from symbol import Symbol
from tools import ObservableProperty, combine, is_iterable, resource_path, run_x
from widgets import WPlayfield, WPixel, WPalette, WScanline

version = "202104.A"

font_ext = ".font"
fonts = {}


def error_box(errors, text=None, informative_text=None, title="Error"):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except errors as e:
                msg = QMessageBox()
                msg.setIcon(QMessageBox.Critical)
                msg.setText(text(e) if text else str(e))
                if informative_text:
                    msg.setInformativeText(informative_text(e))
                msg.setWindowTitle(title)
                msg.exec_()

        return wrapper

    return decorator


class MouseEventHandler:

    supported_keyboard_modifiers = [
        Qt.NoModifier,
        Qt.ControlModifier,
        Qt.ShiftModifier,
        Qt.AltModifier,
    ]

    def __init__(self):
        self._mapping = defaultdict(list)

    def register(
        self,
        *,
        tools: typing.Optional[
            typing.Union[typing.Iterable[ToolboxTool], ToolboxTool]
        ] = None,
        buttons: Qt.MouseButton = Qt.MouseButton.NoButton,
        keyboard_modifiers: typing.Optional[
            typing.Union[typing.Iterable[int], int]
        ] = None,
    ):
        def decorator(f):
            for tool in (
                (tools if is_iterable(tools) else (tools,))
                if tools is not None
                else ToolboxTool
            ):
                for modifier in (
                    (
                        keyboard_modifiers
                        if is_iterable(keyboard_modifiers)
                        else (keyboard_modifiers,)
                    )
                    if keyboard_modifiers is not None
                    else self.supported_keyboard_modifiers
                ):
                    if modifier not in self.supported_keyboard_modifiers:
                        raise ValueError(str(modifier))

                    self._mapping[(tool, buttons, modifier)].append(f)
            return f

        return decorator

    def __call__(
        self,
        *,
        tool: ToolboxTool,
        event: typing.Union[QtGui.QMouseEvent, QtGui.QWheelEvent],
        **kwargs,
    ):
        buttons = (
            event.buttons()
            if isinstance(event, QtGui.QMouseEvent)
            else Qt.MouseButton.NoButton
        )

        funcs = self._mapping.get((tool, buttons, event.modifiers().__int__()))
        if funcs:
            for f in funcs:
                f(tool=tool, event=event, **kwargs)


class Main(QMainWindow):
    _window_title_prefix = f"Playfield Pixel Perfect Pro {version}"
    _pf_cursor_size = QSize(4, 4)
    _load_save_filter = "PPPP project (*.pppp);; All Files (*.*)"
    _export_png_filter = "PNG (*.png);; All Files (*.*)"
    _default_zoom = 2
    _asm_rows = {
        "PF0_PF1_PF2": lambda y, line: f"\t.byte ${line.model.pf0:02X}, ${line.model.pf1:02X}, ${line.model.pf2:02X}\t; {y}",
        "PF0_PF1_PF2_PF0_PF1_PF2": lambda y, line: f"\t.byte ${line.model.pf0:02X}, ${line.model.pf1:02X}, ${line.model.pf2:02X}, ${line.model.pf0_neighbor:02X}, ${line.model.pf1_neighbor:02X}, ${line.model.pf2_neighbor:02X}\t; {y}",
        "PF0_PF1_PF2_COLUPF_COLUBK": lambda y, line: f"\t.byte ${line.model.pf0:02X}, ${line.model.pf1:02X}, ${line.model.pf2:02X}, ${line.model.palette_code.value:02X}, ${line.model.bg_palette_code.value:02X}\t; {y}",
        "PF0_PF1_PF2_COLUPF": lambda y, line: f"\t.byte ${line.model.pf0:02X}, ${line.model.pf1:02X}, ${line.model.pf2:02X}, ${line.model.palette_code.value:02X}\t; {y}",
        "PF0_PF1_PF2_COLUBK": lambda y, line: f"\t.byte ${line.model.pf0:02X}, ${line.model.pf1:02X}, ${line.model.pf2:02X}, ${line.model.bg_palette_code.value:02X}\t; {y}",
        "PF0_PF1_PF2_PF0_PF1_PF2_COLUPF_COLUBK": lambda y, line: f"\t.byte ${line.model.pf0:02X}, ${line.model.pf1:02X}, ${line.model.pf2:02X}, ${line.model.pf0_neighbor:02X}, ${line.model.pf1_neighbor:02X}, ${line.model.pf2_neighbor:02X}, ${line.model.palette_code.value:02X}, ${line.model.bg_palette_code.value:02X}\t; {y}",
        "PF0_PF1_PF2_PF0_PF1_PF2_COLUPF": lambda y, line: f"\t.byte ${line.model.pf0:02X}, ${line.model.pf1:02X}, ${line.model.pf2:02X}, ${line.model.pf0_neighbor:02X}, ${line.model.pf1_neighbor:02X}, ${line.model.pf2_neighbor:02X}, ${line.model.palette_code.value:02X}\t; {y}",
        "PF0_PF1_PF2_PF0_PF1_PF2_COLUBK": lambda y, line: f"\t.byte ${line.model.pf0:02X}, ${line.model.pf1:02X}, ${line.model.pf2:02X}, ${line.model.pf0_neighbor:02X}, ${line.model.pf1_neighbor:02X}, ${line.model.pf2_neighbor:02X}, ${line.model.bg_palette_code.value:02X}\t; {y}",
        "PF0_COLUPF_PF1_PF2_PF0_COLUPF_PF1_PF2": lambda y, line: f"\t.byte ${(line.model.pf0 | ((line.model.palette_code.value & 0xF0) >> 4)):02X}, ${line.model.pf1:02X}, ${line.model.pf2:02X}, ${line.model.pf0_neighbor | (line.model.palette_code.value & 0x0F):02X}, ${line.model.pf1_neighbor:02X}, ${line.model.pf2_neighbor:02X}\t; {y}",
        "PF0_COLUBK_PF1_PF2_PF0_COLUBK_PF1_PF2": lambda y, line: f"\t.byte ${(line.model.pf0 | ((line.model.bg_palette_code.value & 0xF0) >> 4)):02X}, ${line.model.pf1:02X}, ${line.model.pf2:02X}, ${line.model.pf0_neighbor | (line.model.bg_palette_code.value & 0x0F):02X}, ${line.model.pf1_neighbor:02X}, ${line.model.pf2_neighbor:02X}\t; {y}",
        "PF0_COLUPF_PF1_PF2_PF0_COLUPF_PF1_PF2_COLUBK": lambda y, line: f"\t.byte ${(line.model.pf0 | ((line.model.palette_code.value & 0xF0)) >> 4):02X}, ${line.model.pf1:02X}, ${line.model.pf2:02X}, ${line.model.pf0_neighbor | (line.model.palette_code.value & 0x0F):02X}, ${line.model.pf1_neighbor:02X}, ${line.model.pf2_neighbor:02X}, ${line.model.bg_palette_code.value:02X}\t; {y}",
        "PF0_COLUBK_PF1_PF2_PF0_COLUBK_PF1_PF2_COLUPF": lambda y, line: f"\t.byte ${(line.model.pf0 | ((line.model.bg_palette_code.value & 0xF0) >> 4)):02X}, ${line.model.pf1:02X}, ${line.model.pf2:02X}, ${line.model.pf0_neighbor | (line.model.bg_palette_code.value & 0x0F):02X}, ${line.model.pf1_neighbor:02X}, ${line.model.pf2_neighbor:02X}, ${line.model.palette_code.value:02X}\t; {y}",
        "COLUPF_COLUBK_PF0_PF1_PF2": lambda y, line: f"\t.byte ${line.model.palette_code.value:02X}, ${line.model.bg_palette_code.value:02X}, ${line.model.pf0:02X}, ${line.model.pf1:02X}, ${line.model.pf2:02X}\t; {y}",
        "COLUPF_PF0_PF1_PF2": lambda y, line: f"\t.byte ${line.model.palette_code.value:02X}, ${line.model.pf0:02X}, ${line.model.pf1:02X}, ${line.model.pf2:02X}\t; {y}",
        "COLUBK_PF0_PF1_PF2": lambda y, line: f"\t.byte ${line.model.bg_palette_code.value:02X}, ${line.model.pf0:02X}, ${line.model.pf1:02X}, ${line.model.pf2:02X}\t; {y}",
        "COLUPF_COLUBK_PF0_PF1_PF2_PF0_PF1_PF2": lambda y, line: f"\t.byte ${line.model.palette_code.value:02X}, ${line.model.bg_palette_code.value:02X}, ${line.model.pf0:02X}, ${line.model.pf1:02X}, ${line.model.pf2:02X}, ${line.model.pf0_neighbor:02X}, ${line.model.pf1_neighbor:02X}, ${line.model.pf2_neighbor:02X}\t; {y}",
        "COLUPF_PF0_PF1_PF2_PF0_PF1_PF2": lambda y, line: f"\t.byte ${line.model.palette_code.value:02X}, ${line.model.pf0:02X}, ${line.model.pf1:02X}, ${line.model.pf2:02X}, ${line.model.pf0_neighbor:02X}, ${line.model.pf1_neighbor:02X}, ${line.model.pf2_neighbor:02X}\t; {y}",
        "COLUBK_PF0_PF1_PF2_PF0_PF1_PF2": lambda y, line: f"\t.byte ${line.model.bg_palette_code.value:02X}, ${line.model.pf0:02X}, ${line.model.pf1:02X}, ${line.model.pf2:02X}, ${line.model.pf0_neighbor:02X}, ${line.model.pf1_neighbor:02X}, ${line.model.pf2_neighbor:02X}\t; {y}",
    }

    def copy_asm_to_clipboard(self, data: typing.List[str]):
        data.insert(0, f"\t; auto-generated by Playfield Pixel Perfect Pro {version}")
        cb = QApplication.clipboard()
        cb.clear(mode=cb.Clipboard)
        cb.setText("\n".join(data), mode=cb.Clipboard)

        QMessageBox.information(
            self,
            "ASM",
            "Assembly data copied to clipboard",
            QMessageBox.Ok,
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        uic.loadUi(resource_path("ui/main.ui"), self)

        self._cursors = {
            ToolboxTool.Pen: QtGui.QCursor(
                QPixmap(resource_path("assets/cursors/18/pen.png")), 3, 15
            ),
            ToolboxTool.Brush: QtGui.QCursor(
                QPixmap(resource_path("assets/cursors/18/brush.png")), 8, 2
            ),
            ToolboxTool.Bucket: QtGui.QCursor(
                QPixmap(resource_path("assets/cursors/18/bucket.png")), 13, 11
            ),
            ToolboxTool.Line: QtGui.QCursor(
                QPixmap(resource_path("assets/cursors/18/line.png")), 8, 17
            ),
            ToolboxTool.ColorPicker: QtGui.QCursor(
                QPixmap(resource_path("assets/cursors/18/picker.png")), 4, 13
            ),
            ToolboxTool.Selection: QtGui.QCursor(
                QPixmap(resource_path("assets/cursors/18/selection.png")), 4, 4
            ),
            ToolboxTool.Eraser: QtGui.QCursor(
                QPixmap(resource_path("assets/cursors/18/eraser.png")), 3, 14
            ),
        }

        self._pf_icon = QtGui.QIcon(
            resource_path("assets/icons/24/common-file-empty.png")
        )

        self._mouse_press_handler = MouseEventHandler()
        self._mouse_move_handler = MouseEventHandler()
        self._wheel_handler = MouseEventHandler()

        self.register_mouse_actions()

        self.setWindowTitle(self._window_title_prefix)

        self._playfields = {}
        self._active_pf = None
        self._mdi_area = typing.cast(QMdiArea, self.findChild(QMdiArea, "mdiArea"))

        self._action_file_new = typing.cast(
            QAction, self.findChild(QAction, "actionFileNew")
        )

        self._action_file_save = typing.cast(
            QAction, self.findChild(QAction, "actionFileSave")
        )

        self._action_file_save_as = typing.cast(
            QAction, self.findChild(QAction, "actionFileSaveAs")
        )

        self._action_file_export_to_png = typing.cast(
            QAction, self.findChild(QAction, "actionFileExportToPng")
        )

        self._action_file_load = typing.cast(
            QAction, self.findChild(QAction, "actionFileLoad")
        )

        self._action_file_print = typing.cast(
            QAction, self.findChild(QAction, "actionFilePrint")
        )

        self._action_file_exit = typing.cast(
            QAction, self.findChild(QAction, "actionFileExit")
        )

        self._action_file_asm_registers = typing.cast(
            QAction, self.findChild(QAction, "actionFileAsmRegisters")
        )

        self._menu_file_asm = typing.cast(QMenu, self.findChild(QMenu, "menuFileAsm"))

        self._action_edit_clear = typing.cast(
            QAction, self.findChild(QAction, "actionEditClear")
        )

        self._action_edit_undo = typing.cast(
            QAction, self.findChild(QAction, "actionEditUndo")
        )

        self._action_edit_redo = typing.cast(
            QAction, self.findChild(QAction, "actionEditRedo")
        )

        self._action_edit_toolbox_pen = typing.cast(
            QAction, self.findChild(QAction, "actionEditToolboxPen")
        )

        self._action_edit_toolbox_brush = typing.cast(
            QAction, self.findChild(QAction, "actionEditToolboxBrush")
        )

        self._action_edit_toolbox_selection = typing.cast(
            QAction, self.findChild(QAction, "actionEditToolboxSelection")
        )

        self._action_edit_toolbox_bucket = typing.cast(
            QAction, self.findChild(QAction, "actionEditToolboxBucket")
        )

        self._action_edit_toolbox_eraser = typing.cast(
            QAction, self.findChild(QAction, "actionEditToolboxEraser")
        )

        self._action_edit_toolbox_eraser = typing.cast(
            QAction, self.findChild(QAction, "actionEditToolboxEraser")
        )

        self._action_edit_toolbox_color_picker = typing.cast(
            QAction, self.findChild(QAction, "actionEditToolboxColorPicker")
        )

        self._action_edit_toolbox_line = typing.cast(
            QAction, self.findChild(QAction, "actionEditToolboxLine")
        )

        self._toolbox_actions = [
            (self._action_edit_toolbox_pen, ToolboxTool.Pen),
            (self._action_edit_toolbox_brush, ToolboxTool.Brush),
            (self._action_edit_toolbox_selection, ToolboxTool.Selection),
            (self._action_edit_toolbox_bucket, ToolboxTool.Bucket),
            (self._action_edit_toolbox_eraser, ToolboxTool.Eraser),
            (self._action_edit_toolbox_color_picker, ToolboxTool.ColorPicker),
            (self._action_edit_toolbox_line, ToolboxTool.Line),
        ]

        self._action_edit_selection_move_up = typing.cast(
            QAction, self.findChild(QAction, "actionEditSelectionMoveUp")
        )

        self._action_edit_selection_move_down = typing.cast(
            QAction, self.findChild(QAction, "actionEditSelectionMoveDown")
        )

        self._action_edit_selection_move_left = typing.cast(
            QAction, self.findChild(QAction, "actionEditSelectionMoveLeft")
        )

        self._action_edit_selection_move_right = typing.cast(
            QAction, self.findChild(QAction, "actionEditSelectionMoveRight")
        )

        self._action_edit_selection_text = typing.cast(
            QAction, self.findChild(QAction, "actionEditSelectionText")
        )

        self._action_edit_selection_copy = typing.cast(
            QAction, self.findChild(QAction, "actionEditSelectionCopy")
        )

        self._action_edit_selection_cut = typing.cast(
            QAction, self.findChild(QAction, "actionEditSelectionCut")
        )

        self._action_edit_selection_delete = typing.cast(
            QAction, self.findChild(QAction, "actionEditSelectionDelete")
        )

        self._selection_actions = [
            self._action_edit_selection_move_up,
            self._action_edit_selection_move_down,
            self._action_edit_selection_move_left,
            self._action_edit_selection_move_right,
            self._action_edit_selection_text,
            self._action_edit_selection_copy,
            self._action_edit_selection_cut,
            self._action_edit_selection_delete,
        ]

        self._action_view_zoom_in = typing.cast(
            QAction, self.findChild(QAction, "actionViewZoomIn")
        )

        self._action_view_zoom_out = typing.cast(
            QAction, self.findChild(QAction, "actionViewZoomOut")
        )

        self._action_view_foreground_palette = typing.cast(
            QAction, self.findChild(QAction, "actionViewForegroundPalette")
        )

        self._action_view_background_palette = typing.cast(
            QAction, self.findChild(QAction, "actionViewBackgroundPalette")
        )

        self._action_help_about = typing.cast(
            QAction, self.findChild(QAction, "actionHelpAbout")
        )

        self._status_bar = typing.cast(
            QStatusBar, self.findChild(QStatusBar, "statusbar")
        )

        self.setCentralWidget(self._mdi_area)

        self.showMaximized()

        self._palette = self.add_palette(
            title="foreground", color_mapping=palettes.ntsc
        )
        self._bg_palette = self.add_palette(
            title="background", color_mapping=palettes.ntsc
        )

        def close_event(_):
            for pf in self._playfields.values():
                self.ask_save_dialog(pf=pf)

        self.closeEvent = combine(self.closeEvent, close_event)

        @self._palette.model.code.observe
        def on_color_change(code: int, _):
            for pf in self._playfields.values():
                pf.model.palette_code.value = code

        @self._bg_palette.model.code.observe
        def on_bg_color_change(code: int, _):
            for pf in self._playfields.values():
                pf.model.bg_palette_code.value = code

        def on_file_new_click():
            # def init(parent, *args, **kwargs) -> WPlayfield:
            #     return WPlayfield(
            #         name=f"asd",
            #         mode=PlayfieldMode.Asymmetric,
            #         color_system=ColorSystem.NTSC,
            #         scanline_count=192,
            #         zoom=ObservableProperty(2),
            #         parent=parent,
            #         *args,
            #         **kwargs,
            #     )
            #
            # self.add_playfield(init=init)
            # return

            dlg = NewDialog(self)
            if dlg.exec():

                def init(parent: QWidget, *args, **kwargs) -> WPlayfield:
                    return WPlayfield(
                        name=dlg.name,
                        mode=dlg.mode,
                        color_system=dlg.color_system,
                        scanline_count=dlg.scanlines,
                        zoom=ObservableProperty(self._default_zoom),
                        parent=parent,
                        *args,
                        **kwargs,
                    )

                self.add_playfield(init=init)

        self._action_file_new.triggered.connect(on_file_new_click)

        def on_file_save_click(as_: bool):
            if self.active_pf:
                self.file_save_dialog(pf=self.active_pf, as_=as_)

        self._action_file_save.triggered.connect(partial(on_file_save_click, False))
        self._action_file_save_as.triggered.connect(partial(on_file_save_click, True))

        self._asm_actions = []

        def on_file_asm_action_click(
            action: QAction, f: typing.Callable[[int, WScanline], str]
        ):
            if self.active_pf:
                data = [f"\t; {action.text()}", "Data:"]

                for y, line in enumerate(self.active_pf.scanlines):
                    data.append(f(y, line))

                self.copy_asm_to_clipboard(data=data)

        for k, v in self._asm_rows.items():
            action_ = typing.cast(
                QAction, self.findChild(QAction, f"actionFileAsmRows_{k}")
            )

            self._asm_actions.append(action_)

            action_.triggered.connect(partial(on_file_asm_action_click, action_, v))

        def on_file_asm_registers_click():
            if self.active_pf:
                bytes_in_row = 8

                pf0_raw = []
                pf1_raw = []
                pf2_raw = []
                colupf_raw = []
                colubk_raw = []

                for line in self.active_pf.scanlines:
                    pf0_raw.append(f"${line.model.pf0:02X}")
                    pf1_raw.append(f"${line.model.pf1:02X}")
                    pf2_raw.append(f"${line.model.pf2:02X}")

                    if self.active_pf.model.mode == PlayfieldMode.Asymmetric:
                        pf0_raw.append(f"${line.model.pf0_neighbor:02X}")
                        pf1_raw.append(f"${line.model.pf1_neighbor:02X}")
                        pf2_raw.append(f"${line.model.pf2_neighbor:02X}")

                    colupf_raw.append(f"${line.model.palette_code.value:02X}")
                    colubk_raw.append(f"${line.model.bg_palette_code.value:02X}")

                pf0_data = [
                    f"\t.byte {', '.join(pf0_raw[i : i + bytes_in_row])}"
                    for i in range(0, len(pf0_raw), bytes_in_row)
                ]
                pf1_data = [
                    f"\t.byte {', '.join(pf1_raw[i: i + bytes_in_row])}"
                    for i in range(0, len(pf1_raw), bytes_in_row)
                ]
                pf2_data = [
                    f"\t.byte {', '.join(pf2_raw[i: i + bytes_in_row])}"
                    for i in range(0, len(pf2_raw), bytes_in_row)
                ]
                colupf_data = [
                    f"\t.byte {', '.join(colupf_raw[i: i + bytes_in_row])}"
                    for i in range(0, len(colupf_raw), bytes_in_row)
                ]
                colubk_data = [
                    f"\t.byte {', '.join(colubk_raw[i: i + bytes_in_row])}"
                    for i in range(0, len(colubk_raw), bytes_in_row)
                ]

                data = ["DataPF0:"]
                data.extend(pf0_data)
                data.append("\nDataPF1:")
                data.extend(pf1_data)
                data.append("\nDataPF2:")
                data.extend(pf2_data)
                data.append("\nDataCOLUPF:")
                data.extend(colupf_data)
                data.append("\nDataCOLUBK:")
                data.extend(colubk_data)

                self.copy_asm_to_clipboard(data=data)

        self._action_file_asm_registers.triggered.connect(on_file_asm_registers_click)

        def on_file_export_to_png_click():
            if self.active_pf:
                self.png_export_dialog(self.active_pf)

        self._action_file_export_to_png.triggered.connect(on_file_export_to_png_click)

        def on_file_load_click():
            def init(from_: str, *args, **kwargs):
                return load_playfield(
                    from_, *args, zoom=ObservableProperty(self._default_zoom), **kwargs
                )

            files_to_load, _ = QFileDialog.getOpenFileNames(
                self,
                caption="Load project",
                directory="",
                filter=self._load_save_filter,
            )

            if files_to_load:
                for filename in files_to_load:
                    pf = self.add_playfield(partial(init, filename))
                    pf.model.filename = filename
                    self.update_playfield_window_title(pf=pf)

        self._action_file_load.triggered.connect(on_file_load_click)

        def on_file_print_click():
            if self.active_pf:
                self.clear_selection(pf=self.active_pf)
                self.send_to_printer(pf=self.active_pf)

        self._action_file_print.triggered.connect(on_file_print_click)

        def on_file_exit_click():
            self.close()

        self._action_file_exit.triggered.connect(on_file_exit_click)

        def on_view_zoom_click(in_: bool):
            if self.active_pf:
                self.zoom_in_out(pf=self.active_pf, in_=in_)

        self._action_view_zoom_in.triggered.connect(partial(on_view_zoom_click, True))
        self._action_view_zoom_out.triggered.connect(partial(on_view_zoom_click, False))

        def on_edit_clear_click():
            if self.active_pf:
                self.clear_selection(pf=self.active_pf)
                self.execute(
                    pf=self.active_pf,
                    command=ClearPixels(
                        pf=self.active_pf,
                        code=self.active_pf.model.bg_palette_code.value,
                    ),
                )

        self._action_edit_clear.triggered.connect(on_edit_clear_click)

        def on_edit_undo_click():
            if self.active_pf:
                self.clear_selection(pf=self.active_pf)
                self.undo(pf=self.active_pf)

        self._action_edit_undo.triggered.connect(on_edit_undo_click)

        def on_edit_redo_click():
            if self.active_pf:
                self.clear_selection(pf=self.active_pf)
                self.redo(pf=self.active_pf)

        self._action_edit_redo.triggered.connect(on_edit_redo_click)

        def on_view_foreground_palette_click():
            if self._action_view_foreground_palette.isChecked():
                self._palette.parent().show()
            else:
                self._palette.parent().hide()

        self._action_view_foreground_palette.triggered.connect(
            on_view_foreground_palette_click
        )

        def on_view_background_palette_click():
            if self._action_view_background_palette.isChecked():
                self._bg_palette.parent().show()
            else:
                self._bg_palette.parent().hide()

        self._action_view_background_palette.triggered.connect(
            on_view_background_palette_click
        )

        def on_toolbox_item_selection(action: QAction, tool: ToolboxTool):
            for toolbox_action, _ in self._toolbox_actions:
                toolbox_action.setChecked(toolbox_action is action)

            self._toolbox_tool = tool

            for action in self._selection_actions:
                action.setEnabled(tool == ToolboxTool.Selection)

            if tool != ToolboxTool.Selection and self.active_pf is not None:
                self.clear_selection(self.active_pf)

            for pf in self._playfields.values():
                pf.setCursor(self._cursors[tool])

        for toolbox_action_, toolbox_item in self._toolbox_actions:
            toolbox_action_.triggered.connect(
                partial(
                    on_toolbox_item_selection,
                    toolbox_action_,
                    toolbox_item,
                )
            )

        on_toolbox_item_selection(self._action_edit_toolbox_pen, ToolboxTool.Pen)

        self._action_edit_selection_move_up.triggered.connect(
            lambda: self.rotate_up(self.active_pf)
        )
        self._action_edit_selection_move_down.triggered.connect(
            lambda: self.rotate_down(self.active_pf)
        )
        self._action_edit_selection_move_left.triggered.connect(
            lambda: self.rotate_left(self.active_pf)
        )
        self._action_edit_selection_move_right.triggered.connect(
            lambda: self.rotate_right(self.active_pf)
        )
        self._action_edit_selection_copy.triggered.connect(
            lambda: self.copy_selection(self.active_pf)
        )
        self._action_edit_selection_cut.triggered.connect(
            lambda: self.cut_selection(self.active_pf)
        )
        self._action_edit_selection_delete.triggered.connect(
            lambda: self.delete_selection(self.active_pf)
        )

        @error_box(Exception, text=lambda err: str(err))
        @error_box(KeyError, text=lambda err: f"Font {str(err)} not found")
        def on_edit_selection_text_click(_):
            if self.active_pf:

                if len(fonts) == 0:
                    raise Exception("No fonts found")

                dlg = InsertText(self, fonts=fonts.keys())
                if dlg.exec():
                    font = fonts[dlg.font]
                    self.clear_selection(pf=self.active_pf)
                    self.draw_text(
                        y=1,
                        x=1,
                        font=font,
                        pf=self.active_pf,
                        text=dlg.text,
                    )

        self._action_edit_selection_text.triggered.connect(on_edit_selection_text_click)

        def on_help_about_click():
            AboutDialog(version=version).exec()

        self._action_help_about.triggered.connect(on_help_about_click)

        self.active_pf = typing.cast(WPlayfield, None)

    def undo(self, pf: WPlayfield):
        pf.model.undo()
        self._action_edit_undo.setEnabled(len(pf.model.undo_commands) > 0)
        self._action_edit_redo.setEnabled(len(pf.model.redo_commands) > 0)

    def redo(self, pf: WPlayfield):
        pf.model.redo()
        self._action_edit_undo.setEnabled(len(pf.model.undo_commands) > 0)
        self._action_edit_redo.setEnabled(len(pf.model.redo_commands) > 0)

    def set_window_title(self, text: str):
        self.setWindowTitle(
            f"{self._window_title_prefix} - {text}"
            if text
            else self._window_title_prefix
        )

    @property
    def active_pf(self) -> WPlayfield:
        return self._active_pf

    @active_pf.setter
    def active_pf(self, value: WPlayfield):
        if not value:
            self.set_window_title(text=typing.cast(str, None))
        elif self._active_pf is not value:
            self.set_window_title(text=value.model.name)
            self._active_pf = value
            self._palette.model.color_mapping.value = value.model.color_mapping
            self._bg_palette.model.color_mapping.value = value.model.color_mapping

        self._action_file_export_to_png.setEnabled(value is not None)
        self._action_file_save.setEnabled(value is not None)
        self._action_file_save_as.setEnabled(value is not None)
        self._action_file_print.setEnabled(value is not None)
        self._action_view_zoom_in.setEnabled(value is not None)
        self._action_view_zoom_out.setEnabled(value is not None)
        self._action_edit_clear.setEnabled(value is not None)
        self._action_edit_undo.setEnabled(
            value is not None and not value.model.undo_commands.empty()
        )
        self._action_edit_redo.setEnabled(
            value is not None and not value.model.redo_commands.empty()
        )

        self._menu_file_asm.setEnabled(value is not None)

        for action in self._asm_actions:
            action.setEnabled(value is not None)

        for action, _ in self._toolbox_actions:
            action.setEnabled(value is not None)

        for action in self._selection_actions:
            action.setEnabled(
                value is not None and self._toolbox_tool == ToolboxTool.Selection
            )

    def ask_save_dialog(self, pf: WPlayfield):
        if pf.model.need_save:
            answer = QMessageBox.question(
                self,
                "Save",
                f"Save changes to {pf.model.name}?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if answer == QMessageBox.Yes:
                self.file_save_dialog(pf=pf, as_=False)

    def file_save_dialog(self, pf: WPlayfield, as_: bool):
        if pf:
            if not as_ and pf.model.filename:
                file_to_save = pf.model.filename
            else:
                file_to_save, _ = QFileDialog.getSaveFileName(
                    self,
                    caption=f"Save {pf.model.name}",
                    directory=pf.model.filename if pf.model.filename else pf.model.name,
                    filter=self._load_save_filter,
                )

            if file_to_save:
                save_playfield(pf=pf, to=file_to_save, version=version)
                pf.model.need_save = False
                pf.model.filename = file_to_save
                self.update_playfield_window_title(pf=pf)
                self._status_bar.showMessage(
                    f"Saved {pf.model.name} to {file_to_save}", 3000
                )

    def png_export_dialog(self, pf: WPlayfield):
        if pf:
            filename, _ = QFileDialog.getSaveFileName(
                self,
                caption=f"Export {pf.model.name} to PNG",
                directory=pf.model.name,
                filter=self._export_png_filter,
            )

            pf.grab().save(filename, "png")

    def zoom_in_out(self, pf: WPlayfield, in_: bool):
        self._status_bar.showMessage(
            f"{(pf.model.zoom_in() if in_ else pf.model.zoom_out()) * 100}%",
            1000,
        )

    def add_palette(
        self, title: str, color_mapping: typing.Mapping[int, str]
    ) -> WPalette:
        sub = QMdiSubWindow()

        sub.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.CustomizeWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )

        palette = WPalette(color_mapping=ObservableProperty(color_mapping), parent=sub)
        palette.show()

        sub.setFixedSize(palette.size())
        sub.setWidget(palette)

        sub.setWindowTitle(title)
        self._mdi_area.addSubWindow(sub)
        sub.show()

        return palette

    @staticmethod
    def update_playfield_window_title(pf: WPlayfield):
        sub = pf.parent().parent()
        title = f"{pf.model.name} - {pf.model.mode.name} - {pf.model.color_system.name} - {pf.model.scanline_count}"
        if pf.model.filename:
            title += f" ({pf.model.filename})"
        sub.setWindowTitle(title)

    def add_playfield(
        self,
        init: typing.Callable[..., WPlayfield],
    ) -> WPlayfield:

        sub = QMdiSubWindow()

        scroll_area = QScrollArea(sub)
        scroll_area.setAlignment(Qt.AlignCenter)
        pf = init(parent=scroll_area)

        pf.setCursor(self._cursors[self._toolbox_tool])

        sub.resize(pf.size() * 1.1)

        sub.setWindowIcon(self._pf_icon)

        pf.show()

        pf.model.palette_code.value = self._palette.model.code.value
        pf.model.bg_palette_code.value = self._bg_palette.model.code.value

        scroll_area.setWidget(pf)

        sub.setWidget(scroll_area)

        self.update_playfield_window_title(pf)

        self._mdi_area.addSubWindow(sub)
        sub.show()

        def focus_in_event(*args, **kwargs):
            self.active_pf = pf

        scroll_area.mousePressEvent = combine(
            scroll_area.mousePressEvent, focus_in_event
        )
        sub.focusInEvent = combine(sub.focusInEvent, focus_in_event)

        pf_id = pf.__hash__()
        self._playfields[pf_id] = pf

        def close_event(_):
            self.ask_save_dialog(pf=pf)
            del self._playfields[pf_id]
            self.active_pf = typing.cast(WPlayfield, None)
            if len(self._playfields) != 0:
                self.active_pf = next(iter(self._playfields.values()))

        sub.closeEvent = combine(sub.closeEvent, close_event)

        # def key_press_event(event: QKeyEvent):
        #     #print(event.key())
        #     if event.key() == Qt.Key.Key_P:
        #
        #
        # sub.keyPressEvent = combine(sub.keyPressEvent, key_press_event)

        def scroll_area_wheel_event(
            f: typing.Callable[[QtGui.QWheelEvent], None], event: QtGui.QWheelEvent
        ):
            if QApplication.keyboardModifiers() == Qt.ControlModifier:
                event.ignore()
            else:
                f(event)

        scroll_area.wheelEvent = partial(
            scroll_area_wheel_event, scroll_area.wheelEvent
        )

        pf.on_scanline_mouse_press_event = combine(
            pf.on_scanline_mouse_press_event,
            partial(self.on_playfield_mouse_press_event, pf),
        )

        pf.on_scanline_mouse_move_event = combine(
            pf.on_scanline_mouse_move_event,
            partial(self.on_playfield_mouse_move_event, pf),
        )

        pf.on_scanline_wheel_event = combine(
            pf.on_scanline_wheel_event,
            partial(self.on_playfield_wheel_event, pf),
        )

        def brush(event: QtGui.QMouseEvent):
            if (
                self._toolbox_tool != ToolboxTool.Brush
                or event.buttons() not in (Qt.LeftButton, Qt.RightButton)
                or event.modifiers() != Qt.NoModifier
            ):
                return

            zoom = pf.model.zoom.value
            x = int(event.x() / (zoom * PixelModel.default_width))
            y = int(event.y() / (zoom * PixelModel.default_height))

            if (
                x < 0
                or y < 0
                or x > ScanlineModel.pixel_count - 1
                or y > pf.model.scanline_count - 1
            ):
                return

            tool = (
                ToolboxTool.Pen
                if event.buttons() == Qt.LeftButton
                else ToolboxTool.Eraser
            )
            event.buttons = lambda: Qt.NoButton
            event.modifiers = lambda: Qt.ShiftModifier

            line = pf[y]
            pixel = line[x]

            self._mouse_move_handler(
                tool=tool,
                pf=pf,
                line=line,
                y=y,
                x=x,
                pixel=pixel,
                event=event,
                neighbor=pf.model.neighbor(x),
            )

        def select(event: QtGui.QMouseEvent):
            if (
                self._toolbox_tool != ToolboxTool.Selection
                or event.buttons() != Qt.LeftButton
                or event.modifiers() != Qt.NoModifier
            ):
                return

            zoom = pf.model.zoom.value
            x = int(event.x() / (zoom * PixelModel.default_width))
            y = int(event.y() / (zoom * PixelModel.default_height))

            if (
                x < 0
                or y < 0
                or x > ScanlineModel.pixel_count - 1
                or y > pf.model.scanline_count - 1
            ):
                return

            line = pf[y]
            pixel = line[x]

            self._mouse_move_handler(
                tool=ToolboxTool.Selection,
                pf=pf,
                line=line,
                y=y,
                x=x,
                pixel=pixel,
                event=event,
                neighbor=pf.model.neighbor(x),
            )

        def drag(event: QtGui.QMouseEvent):
            if (
                self._toolbox_tool != ToolboxTool.Selection
                or event.buttons() != Qt.MiddleButton
                or event.modifiers() != Qt.NoModifier
            ):
                return

            zoom = pf.model.zoom.value
            x = int(event.x() / (zoom * PixelModel.default_width))
            y = int(event.y() / (zoom * PixelModel.default_height))

            if pf.model.prev_drag_x is not None:
                if x > pf.model.prev_drag_x:
                    run_x(1, self.rotate_right, pf)
                elif x < pf.model.prev_drag_x:
                    run_x(1, self.rotate_left, pf)

            pf.model.prev_drag_x = x

            if pf.model.prev_drag_y is not None:
                if y > pf.model.prev_drag_y:
                    run_x(4, self.rotate_down, pf)
                elif y < pf.model.prev_drag_y:
                    run_x(4, self.rotate_up, pf)

            pf.model.prev_drag_y = y

        pf.mouseMoveEvent = combine(pf.mouseMoveEvent, brush, select, drag)

        self.active_pf = pf

        return pf

    def on_playfield_mouse_press_event(
        self,
        pf: WPlayfield,
        line: WScanline,
        y: int,
        x: int,
        pixel: WPixel,
        event: QtGui.QMouseEvent,
    ):
        self._mouse_press_handler(
            tool=self._toolbox_tool,
            pf=pf,
            line=line,
            y=y,
            x=x,
            pixel=pixel,
            event=event,
            neighbor=pf.model.neighbor(x),
        )

    def on_playfield_mouse_move_event(
        self,
        pf: WPlayfield,
        line: WScanline,
        y: int,
        x: int,
        pixel: WPixel,
        event: QtGui.QMouseEvent,
    ):
        self._mouse_move_handler(
            tool=self._toolbox_tool,
            pf=pf,
            line=line,
            y=y,
            x=x,
            pixel=pixel,
            event=event,
            neighbor=pf.model.neighbor(x),
        )

    def on_playfield_wheel_event(
        self,
        pf: WPlayfield,
        line: WScanline,
        y: int,
        x: int,
        pixel: WPixel,
        event: QtGui.QWheelEvent,
    ):
        self._wheel_handler(
            tool=self._toolbox_tool,
            pf=pf,
            line=line,
            y=y,
            x=x,
            pixel=pixel,
            event=event,
            neighbor=pf.model.neighbor(x),
        )

    def execute(self, pf: WPlayfield, command: Command):
        pf.model.execute(command=command)
        self._action_edit_undo.setEnabled(not pf.model.undo_commands.empty())
        self._action_edit_redo.setEnabled(not pf.model.redo_commands.empty())

    @staticmethod
    def send_to_printer(pf: WPlayfield):
        printer = QtPrintSupport.QPrinter()
        painter = QtGui.QPainter()
        painter.begin(printer)
        screen = pf.grab()
        painter.drawPixmap(0, 0, screen)
        painter.end()

    @staticmethod
    def _position_symbol(
        y: int, x: int, sym: Symbol, pf: WPlayfield
    ) -> typing.Set[int]:
        lines_to_update = set()
        for i, j in sym.pixels:
            b = (y + j) % pf.model.scanline_count
            a = (x + i) % pf[b].model.pixel_count
            pf[b].model.layer_1[a] = True
            pf[b].model.selection[a] = True

            neighbor = pf.model.neighbor(a)
            if neighbor:
                pf[b].model.layer_1[neighbor] = True
                pf[b].model.selection[neighbor] = True

            lines_to_update.add(b)

        return lines_to_update

    def draw_symbol(self, y: int, x: int, sym: Symbol, pf: WPlayfield):
        lines_to_update = self._position_symbol(y=y, x=x, sym=sym, pf=pf)
        for j in lines_to_update:
            pf[j].model.bg_palette_code.silent_set(pf.model.bg_palette_code.value)
            pf[j].model.palette_code.value = pf.model.palette_code.value

    def draw_text(
        self,
        y: int,
        x: int,
        font: typing.Mapping[str, Symbol],
        pf: WPlayfield,
        text: str,
        spacing: int = 1,
    ):
        lines_to_update = set()
        i = x
        for c in text:
            sym = font.get(c, font.get(c.lower(), None))
            if not sym:
                continue
            lines_to_update.update(self._position_symbol(y=y, x=i, sym=sym, pf=pf))
            i += sym.width + spacing

        for j in lines_to_update:
            pf[j].model.bg_palette_code.silent_set(pf.model.bg_palette_code.value)
            pf[j].model.palette_code.value = pf.model.palette_code.value

    @staticmethod
    def copy_selection(pf: WPlayfield):
        for line in pf.scanlines:
            line.model.copy_selection()

    @staticmethod
    def cut_selection(pf: WPlayfield):
        updates = []
        for y, line in enumerate(pf.scanlines):
            mods = line.model.cut_selection()
            line.model.palette_code.value = line.model.palette_code.value

            if len(mods) > 0:
                updates.extend(
                    [
                        UpdatePixels.Update(
                            x=x, y=y, status=True, code=pf.model.palette_code.value
                        )
                        for x in mods
                    ]
                )

        if len(updates) > 0:
            pf.model.undo_commands.push(UpdatePixels(pf=pf, updates=updates))
            pf.model.need_save = True

    @staticmethod
    def delete_selection(pf: WPlayfield):
        updates = []
        for y, line in enumerate(pf.scanlines):
            mods = line.model.delete_selection()
            line.model.palette_code.value = line.model.palette_code.value

            if len(mods) > 0:
                updates.extend(
                    [
                        UpdatePixels.Update(
                            x=x, y=y, status=True, code=pf.model.palette_code.value
                        )
                        for x in mods
                    ]
                )

        if len(updates) > 0:
            pf.model.undo_commands.push(UpdatePixels(pf=pf, updates=updates))
            pf.model.need_save = True

    @staticmethod
    def clear_selection(pf: WPlayfield):
        pf.model.prev_drag_x = None
        pf.model.prev_drag_y = None
        updates = []
        for y, line in enumerate(pf.scanlines):
            mods = line.model.clear_selection()
            line.model.palette_code.value = line.model.palette_code.value

            if len(mods) > 0:
                updates.extend(
                    [
                        UpdatePixels.Update(
                            x=x, y=y, status=False, code=pf.model.bg_palette_code.value
                        )
                        for x in mods
                    ]
                )

        if len(updates) > 0:
            pf.model.undo_commands.push(UpdatePixels(pf=pf, updates=updates))
            pf.model.need_save = True

    @staticmethod
    def rotate_right(pf: WPlayfield):
        for line in pf.scanlines:
            line.model.rotate_right()
            line.model.palette_code.value = line.model.palette_code.value

    @staticmethod
    def rotate_left(pf: WPlayfield):
        for line in pf.scanlines:
            line.model.rotate_left()
            line.model.palette_code.value = line.model.palette_code.value

    @staticmethod
    def rotate_up(pf: WPlayfield):
        if pf.model.scanline_count < 2:
            return

        line_0_selection = pf[0].model.selection
        line_0_layer_1 = pf[0].model.layer_1

        for j in range(1, pf.model.scanline_count):
            y = (j - 1) % pf.model.scanline_count
            color = pf[j if True in pf[j].model.layer_1 else y].model.palette_code.value
            pf[y].model.selection = pf[j].model.selection
            pf[y].model.layer_1 = pf[j].model.layer_1
            pf[y].model.palette_code.value = color

        color = pf[
            0 if True in pf[0].model.layer_1 else pf.model.scanline_count - 1
        ].model.palette_code.value
        pf[pf.model.scanline_count - 1].model.selection = line_0_selection
        pf[pf.model.scanline_count - 1].model.layer_1 = line_0_layer_1
        pf[pf.model.scanline_count - 1].model.palette_code.value = color

    @staticmethod
    def rotate_down(pf: WPlayfield):
        if pf.model.scanline_count < 2:
            return

        line_last_selection = pf[pf.model.scanline_count - 1].model.selection
        line_last_layer_1 = pf[pf.model.scanline_count - 1].model.layer_1

        for j in range(pf.model.scanline_count - 2, -1, -1):
            y = (j + 1) % pf.model.scanline_count
            color = pf[j if True in pf[j].model.layer_1 else y].model.palette_code.value
            pf[y].model.selection = pf[j].model.selection
            pf[y].model.layer_1 = pf[j].model.layer_1
            pf[y].model.palette_code.value = color

        color = pf[
            pf.model.scanline_count - 1
            if True in pf[pf.model.scanline_count - 1].model.layer_1
            else 0
        ].model.palette_code.value
        pf[0].model.selection = line_last_selection
        pf[0].model.layer_1 = line_last_layer_1
        pf[0].model.palette_code.value = color

    def register_mouse_actions(self):
        @self._mouse_press_handler.register(
            tools=ToolboxTool.Selection,
            buttons=Qt.MouseButton.LeftButton,
            keyboard_modifiers=Qt.NoModifier,
        )
        @self._mouse_move_handler.register(
            tools=ToolboxTool.Selection,
            buttons=Qt.MouseButton.LeftButton,
            keyboard_modifiers=Qt.NoModifier,
        )
        def select(*, line: WScanline, x: int, neighbor: typing.Optional[int], **_):
            line.model.selection[x] = True
            if neighbor:
                line.model.selection[neighbor] = True
            line.model.palette_code.value = line.model.palette_code.value

        @self._mouse_press_handler.register(
            tools=ToolboxTool.Selection, buttons=Qt.MouseButton.RightButton
        )
        def clear_selection(*, pf: WPlayfield, **_):
            self.clear_selection(pf=pf)

        @self._wheel_handler.register(
            tools=ToolboxTool.Selection,
            buttons=Qt.MouseButton.NoButton,
            keyboard_modifiers=Qt.NoModifier,
        )
        def move_selection_up_down(*, pf: WPlayfield, event: QtGui.QWheelEvent, **_):
            if event.angleDelta().y() > 0:
                self.rotate_up(pf=pf)
            elif event.angleDelta().y() < 0:
                self.rotate_down(pf=pf)

        @self._wheel_handler.register(
            tools=ToolboxTool.Selection,
            buttons=Qt.MouseButton.NoButton,
            keyboard_modifiers=Qt.ShiftModifier,
        )
        def move_selection_left_right(*, pf: WPlayfield, event: QtGui.QWheelEvent, **_):
            if event.angleDelta().y() > 0:
                self.rotate_left(pf=pf)
            elif event.angleDelta().y() < 0:
                self.rotate_right(pf=pf)

        @self._mouse_press_handler.register(buttons=Qt.MouseButton.LeftButton)
        @self._mouse_press_handler.register(buttons=Qt.MouseButton.RightButton)
        def set_focus(*, pf: WPlayfield, **_):
            self.active_pf = pf

        @self._mouse_press_handler.register(
            tools=ToolboxTool.Pen,
            buttons=Qt.MouseButton.LeftButton,
            keyboard_modifiers=Qt.NoModifier,
        )
        @self._mouse_move_handler.register(
            tools=ToolboxTool.Pen,
            buttons=Qt.MouseButton.NoButton,
            keyboard_modifiers=Qt.ShiftModifier,
        )
        def draw(
            *,
            pf: WPlayfield,
            y: int,
            x: int,
            neighbor: typing.Optional[int],
            **_,
        ):
            updates = [
                UpdatePixels.Update(
                    x=x, y=y, status=True, code=pf.model.palette_code.value
                )
            ]

            if neighbor is not None:
                updates.append(
                    UpdatePixels.Update(
                        x=neighbor, y=y, status=True, code=pf.model.palette_code.value
                    )
                )

            self.execute(pf=pf, command=UpdatePixels(pf=pf, updates=updates))
            pf.model.need_save = True

        @self._mouse_press_handler.register(
            tools=ToolboxTool.Pen,
            buttons=Qt.MouseButton.RightButton,
            keyboard_modifiers=Qt.NoModifier,
        )
        @self._mouse_press_handler.register(
            tools=ToolboxTool.Eraser, buttons=Qt.MouseButton.LeftButton
        )
        @self._mouse_move_handler.register(
            tools=ToolboxTool.Eraser,
            buttons=Qt.MouseButton.NoButton,
            keyboard_modifiers=Qt.ShiftModifier,
        )
        def erase(
            *,
            pf: WPlayfield,
            y: int,
            x: int,
            neighbor: typing.Optional[int],
            **_,
        ):
            updates = [
                UpdatePixels.Update(
                    x=x, y=y, status=False, code=pf.model.bg_palette_code.value
                )
            ]

            if neighbor is not None:
                updates.append(
                    UpdatePixels.Update(
                        x=neighbor,
                        y=y,
                        status=False,
                        code=pf.model.bg_palette_code.value,
                    )
                )

            self.execute(pf=pf, command=UpdatePixels(pf=pf, updates=updates))
            pf.model.need_save = True

        @self._mouse_press_handler.register(
            tools=ToolboxTool.Bucket, buttons=Qt.MouseButton.RightButton
        )
        @self._mouse_press_handler.register(
            tools=ToolboxTool.Pen,
            buttons=Qt.MouseButton.RightButton,
            keyboard_modifiers=Qt.ControlModifier,
        )
        def fill_background(*, pf: WPlayfield, line: WScanline, y: int, x: int, **_):
            if not line.model.pixels[x]:
                commands = CommandsGroup()

                for j in range(y - 1, -1, -1):
                    if (
                        pf[j].model.bg_palette_code.value
                        != line.model.bg_palette_code.value
                    ):
                        break
                    commands.append(
                        UpdateLineBackgroundPaletteCode(
                            model=pf[j].model, code=pf.model.bg_palette_code.value
                        )
                    )

                for j in range(y + 1, pf.model.scanline_count):
                    if (
                        pf[j].model.bg_palette_code.value
                        != line.model.bg_palette_code.value
                    ):
                        break
                    commands.append(
                        UpdateLineBackgroundPaletteCode(
                            model=pf[j].model, code=pf.model.bg_palette_code.value
                        )
                    )

                commands.append(
                    UpdateLineBackgroundPaletteCode(
                        model=line.model, code=pf.model.bg_palette_code.value
                    )
                )
                self.execute(pf=pf, command=commands)

        @self._mouse_press_handler.register(
            tools=ToolboxTool.Bucket, buttons=Qt.MouseButton.LeftButton
        )
        @self._mouse_press_handler.register(
            tools=ToolboxTool.Pen,
            buttons=Qt.MouseButton.LeftButton,
            keyboard_modifiers=Qt.ControlModifier,
        )
        def fill_foreground(*, pf: WPlayfield, line: WScanline, y: int, x: int, **_):
            def calc_lines_to_update(
                j: int,
                i: int,
                visited: typing.List[typing.List[bool]],
                lines: typing.Set[int],
            ):
                s = deque()
                s.append((j, i))

                while len(s) > 0:
                    j, i = s.pop()

                    if visited[j][i]:
                        continue

                    visited[j][i] = True

                    pixel = pf[j][i]
                    pixel_above = pf[j - 1][i] if j > 0 else None
                    pixel_below = pf[j + 1][i] if j < pf.model.scanline_count - 1 else None
                    pixel_left = pf[j][i - 1] if i > 0 else None
                    pixel_right = (
                        pf[j][i + 1] if i < ScanlineModel.pixel_count - 1 else None
                    )

                    if (
                        pixel_above
                        and pf[j - 1].model.pixels[i]
                        and pixel_above.model.color.value == pixel.model.color.value
                    ):
                        lines.add(j - 1)
                        s.append((j-1, i))

                    if (
                        pixel_left
                        and pf[j].model.pixels[i - 1]
                        and pixel_left.model.color.value == pixel.model.color.value
                    ):
                        s.append((j, i - 1))

                    if (
                        pixel_right
                        and pf[j].model.pixels[i + 1]
                        and pixel_right.model.color.value == pixel.model.color.value
                    ):
                        s.append((j, i + 1))

                    if (
                        pixel_below
                        and pf[j + 1].model.pixels[i]
                        and pixel_below.model.color.value == pixel.model.color.value
                    ):
                        lines.add(j + 1)
                        s.append((j + 1, i))

            if line.model.pixels[x]:
                to_update_lines: typing.Set[int] = {y}
                calc_lines_to_update(
                    j=y,
                    i=x,
                    visited=[
                        [False for _ in range(ScanlineModel.pixel_count)]
                        for _ in range(pf.model.scanline_count)
                    ],
                    lines=to_update_lines,
                )

                commands = CommandsGroup()

                for j_ in to_update_lines:
                    commands.append(
                        UpdateLinePaletteCode(
                            model=pf[j_].model, code=pf.model.palette_code.value
                        )
                    )
                self.execute(pf=pf, command=commands)

        @self._mouse_press_handler.register(
            tools=ToolboxTool.Line,
            buttons=Qt.MouseButton.LeftButton,
            keyboard_modifiers=Qt.NoModifier,
        )
        @self._mouse_press_handler.register(
            tools=ToolboxTool.Pen,
            buttons=Qt.MouseButton.MiddleButton,
            keyboard_modifiers=Qt.NoModifier,
        )
        def draw_horizontal_line(*, pf: WPlayfield, line: WScanline, y: int, **_):
            updates = []

            for i in range(line.model.pixel_count):
                updates.append(
                    UpdatePixels.Update(
                        x=i, y=y, status=True, code=pf.model.palette_code.value
                    )
                )

            self.execute(pf=pf, command=UpdatePixels(pf=pf, updates=updates))
            pf.model.need_save = True

        @self._mouse_press_handler.register(
            tools=ToolboxTool.Line,
            buttons=Qt.MouseButton.LeftButton,
            keyboard_modifiers=Qt.ControlModifier,
        )
        @self._mouse_press_handler.register(
            tools=ToolboxTool.Pen,
            buttons=Qt.MouseButton.MiddleButton,
            keyboard_modifiers=Qt.ControlModifier,
        )
        def draw_vertical_line(
            *, pf: WPlayfield, x: int, neighbor: typing.Optional[int], **_
        ):
            updates = []

            for j in range(pf.model.scanline_count):
                updates.append(
                    UpdatePixels.Update(
                        x=x, y=j, status=True, code=pf.model.palette_code.value
                    )
                )
                if neighbor is not None:
                    updates.append(
                        UpdatePixels.Update(
                            x=neighbor,
                            y=j,
                            status=True,
                            code=pf.model.palette_code.value,
                        )
                    )

            self.execute(pf=pf, command=UpdatePixels(pf=pf, updates=updates))
            pf.model.need_save = True

        @self._mouse_press_handler.register(
            tools=ToolboxTool.ColorPicker, buttons=Qt.MouseButton.LeftButton
        )
        @self._mouse_press_handler.register(
            tools=ToolboxTool.Pen,
            buttons=Qt.MouseButton.LeftButton,
            keyboard_modifiers=Qt.AltModifier,
        )
        def pick_forground_color(*, pf: WPlayfield, line: WScanline, x: int, **_):
            if line.model.pixels[x]:
                self._palette.model.code.value = line.model.palette_code.value
                pf.model.palette_code.value = line.model.palette_code.value

        @self._mouse_press_handler.register(
            tools=ToolboxTool.ColorPicker, buttons=Qt.MouseButton.RightButton
        )
        @self._mouse_press_handler.register(
            tools=ToolboxTool.Pen,
            buttons=Qt.MouseButton.RightButton,
            keyboard_modifiers=Qt.AltModifier,
        )
        def pick_background_color(*, pf: WPlayfield, line: WScanline, **_):
            self._bg_palette.model.code.value = line.model.bg_palette_code.value
            pf.model.bg_palette_code.value = line.model.bg_palette_code.value

        @self._wheel_handler.register(
            buttons=Qt.MouseButton.NoButton, keyboard_modifiers=Qt.ControlModifier
        )
        def zoom_in_out(*, pf: WPlayfield, event: QtGui.QWheelEvent, **_):
            if event.angleDelta().y() > 0:
                self.zoom_in_out(in_=True, pf=pf)
            elif event.angleDelta().y() < 0:
                self.zoom_in_out(in_=False, pf=pf)

        @self._mouse_move_handler.register(buttons=Qt.MouseButton.NoButton)
        def update_status_bar(*, line: WScanline, y: int, x: int, **_):
            self._status_bar.showMessage(
                f"X={x}, Y={y}{f'  Color={line.model.palette_code.value:02X}' if line.model.pixels[x] else ''}",
                1000,
            )


def main():
    app = QApplication(sys.argv)

    splash_screen_length = int(os.getenv("SPLASH_SCREEN", 2))
    splash = None

    if splash_screen_length > 0:
        splash_pixmap = QPixmap(resource_path("assets/splash.png"))
        splash = QSplashScreen(pixmap=splash_pixmap, flags=Qt.WindowStaysOnTopHint)
        splash.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        splash.setEnabled(False)
        splash.showMessage(version, Qt.AlignBottom | Qt.AlignCenter, Qt.white)
        splash.show()
        app.processEvents()

    fonts_dir = os.getenv("FONTS_DIR", ".")

    for f in os.listdir(fonts_dir):
        full_path = os.path.join(fonts_dir, f)
        if os.path.isfile(full_path) and f.endswith(font_ext):
            fonts[f] = symbol.load_font(full_path)

    if splash_screen_length > 0:
        time.sleep(splash_screen_length)

    window = Main()

    if splash:
        splash.finish(window)

    sys.exit(app.exec_())


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        sys.stderr.write(str(e))
