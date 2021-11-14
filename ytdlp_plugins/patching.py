#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import warnings
from contextlib import suppress, ContextDecorator, contextmanager, ExitStack
from inspect import stack, getmodule
from typing import Dict, Any, Callable, Optional, cast
from unittest.mock import patch

try:
    from typing import Protocol  # pylint: disable=ungrouped-imports
except ImportError:
    from typing_extensions import Protocol  # type: ignore

import yt_dlp

from . import FOUND, OVERRIDDEN
from .utils import tabify, write_json_file


# mypy typing stub
# pylint: disable=too-few-public-methods
class Function(Protocol):
    __globals__: Dict[str, Any]
    __call__: Callable


class InverseDecorated(Protocol):
    __original__: Callable
    __call__: Callable


def monkey_patch(orig):
    def decorator(func: Callable) -> InverseDecorated:
        def decorated(*args, **kwargs):
            return func(*args, **kwargs)

        setattr(decorated, "__original__", orig)
        return cast(InverseDecorated, decorated)

    return decorator


def calling_plugin_class():
    plugins = set(FOUND.values())
    for frame_info in stack():
        try:
            cls = frame_info[0].f_locals["self"].__class__
        except (KeyError, AttributeError):
            cls = None
        if cls in plugins:
            return cls
    return None


@monkey_patch(yt_dlp.YoutubeDL.print_debug_header)
def plugin_debug_header(self):
    plugin_list = []
    for name, cls in FOUND.items():
        module = getmodule(cls)
        version = getattr(cls, "__version__", None) or getattr(
            module, "__version__", None
        )
        version = f"(v{version})" if version else ""
        cls_path = f"{module.__name__}.{name}" if module else name
        alt_name = getattr(cls(), "IE_NAME", name)
        plugin_list.append((f"[{alt_name}]", f"via {cls_path!r}", version))

    if plugin_list:
        plural_s = "s" if len(plugin_list) > 1 else ""
        self.write_debug(
            f"Loaded {len(plugin_list)} plugin{plural_s} which are not part of yt-dlp. "
            f"Use at your own risk."
        )
        for line in tabify(sorted(plugin_list), join_string=" "):
            self.write_debug(" " + line)
    if OVERRIDDEN:
        self.write_debug("Overridden classes due to name collisions:")
        items = [
            (f"{cls.__name__!r}", f"from {cls.__module__!r}") for cls in OVERRIDDEN
        ]
        for line in tabify(items):
            self.write_debug(" " + line)

    return plugin_debug_header.__original__(self)


@monkey_patch(yt_dlp.utils.bug_reports_message)
def bug_reports_message(*args, **kwargs):
    cls = calling_plugin_class()
    if cls is None:
        return bug_reports_message.__original__(*args, **kwargs)
    with suppress(AttributeError):
        return "; " + cls().BUG_REPORT
    return ""


# pylint: disable=invalid-name
class patch_function_globals(ContextDecorator):
    """
    context manager which replaces an global capture object of given function
    """

    def __init__(
        self, func: Function, global_object: Any, *, global_name: Optional[str] = None
    ):
        self.obj = global_object
        self.globals = func.__globals__
        name = global_object.__name__ if global_name is None else global_name
        self.name = name if name in self.globals else None
        if self.name is None:
            warnings.warn(
                f"Unable to replace {name!r} in globals for {func}. "
                f"Context manager will have no effect.",
                RuntimeWarning,
                stacklevel=2,
            )

    def switch_object(self):
        if self.name is None:
            return
        self.globals[self.name], self.obj = self.obj, self.globals[self.name]

    def __enter__(self):
        self.switch_object()
        return self

    def __exit__(self, *exc):
        self.switch_object()
        return False


def windows_enable_vt_mode():
    """dummy stub to supress subprocess warnings"""


SKIP_VT_MODE = patch_function_globals(yt_dlp.YoutubeDL.__init__, windows_enable_vt_mode)
# pylint: disable=protected-access
_PATCHES = (
    patch("yt_dlp.utils.bug_reports_message", bug_reports_message),
    patch("yt_dlp.YoutubeDL.print_debug_header", plugin_debug_header),
    patch_function_globals(yt_dlp.YoutubeDL._write_info_json, write_json_file),
)


def patch_decorator(func):
    for _patch in reversed(_PATCHES):
        func = _patch(func)
    return func


@contextmanager
def patch_context():
    _stack = ExitStack()
    try:
        yield [_stack.enter_context(ctx) for ctx in _PATCHES]
    finally:
        _stack.close()
