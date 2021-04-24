from __future__ import annotations

import abc
import os
import sys
import typing
from functools import wraps

from PyQt5.QtWidgets import QMessageBox
from pymitter import EventEmitter

T = typing.TypeVar("T")


class Observable(abc.ABC):
    @abc.abstractmethod
    def observe(self, f):
        return NotImplementedError


class ObservableMatrix(typing.Generic[T], Observable):
    _value_changed_event = "value_changed_event"

    def __init__(self, rows: int, cols: int, init: T):
        self._event_emitter = EventEmitter()
        self._init = init
        self._cols = cols
        self._rows = rows
        self._data = None
        self.clear()

    def __getitem__(self, yx: typing.Tuple[int, int]) -> T:
        return self.get(*yx)

    def __setitem__(self, yx: typing.Tuple[int, int], value: T):
        self.set(*yx, value)

    def observe(self, f):
        self._event_emitter.on(self._value_changed_event, f)
        return f

    def clear(self):
        self._data = [
            [self._init for _ in range(self._cols)] for _ in range(self._rows)
        ]

    def get(self, y: int, x: int) -> T:
        return self._data[y][x]

    def set(self, y: int, x: int, value: T):
        if self._data[y][x] != value:
            self._data[y][x] = value
            self._event_emitter.emit(self._value_changed_event, y, x, value)


class ObservableProperty(typing.Generic[T]):
    _value_changed_event = "value_changed_event"

    def __init__(self, value: T, no_change_notify: bool = False):
        self._event_emitter = EventEmitter()
        self._value = value
        self.no_change_notify = no_change_notify

    def observe(self, f):
        self._event_emitter.on(self._value_changed_event, f)
        return f

    @property
    def copy(self) -> ObservableProperty[T]:
        return ObservableProperty(self.value)

    @property
    def value(self) -> T:
        return self._value

    @value.setter
    def value(self, value: T):
        prev = self._value
        self._value = value

        if self.no_change_notify or prev is not value:
            self._event_emitter.emit(self._value_changed_event, value, prev)

    def silent_set(self, value: T):
        self._value = value


class CappedStack(typing.Generic[T]):
    def __init__(self, maximum: int):
        self._stack = []
        self._maximum = maximum

    def __len__(self) -> int:
        return len(self._stack)

    def push(self, item: T):
        if len(self._stack) > self._maximum:
            self._stack = self._stack[1:]

        self._stack.append(item)

    def pop(self) -> T:
        return self._stack.pop()

    def empty(self) -> bool:
        return len(self._stack) == 0

    def full(self) -> bool:
        return len(self._stack) == self._maximum


def combine(f0, f1, *more):
    def wrapper(*args, **kwargs):
        f0(*args, **kwargs)
        f1(*args, **kwargs)
        for f in more:
            f(*args, **kwargs)

    return wrapper


def is_iterable(obj: typing.Any) -> bool:
    try:
        iter(obj)
    except TypeError:
        return False

    return True


def resource_path(relative_path):
    return os.path.join(
        sys._MEIPASS if hasattr(sys, "_MEIPASS") else os.path.abspath("."),
        relative_path,
    )


def run_x(x: int, f, *args, **kwargs):
    for _ in range(x):
        f(*args, **kwargs)


def error_box(errors, text=None, informative_text=None, title="Error", parent=None):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except errors as e:
                msg = QMessageBox(parent=parent)
                msg.setIcon(QMessageBox.Critical)
                msg.setText(text(e) if text else str(e))
                if informative_text:
                    msg.setInformativeText(informative_text(e))
                msg.setWindowTitle(title)
                msg.exec_()

        return wrapper

    return decorator
