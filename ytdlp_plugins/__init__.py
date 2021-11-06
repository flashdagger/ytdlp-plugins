#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import importlib
import sys
import traceback
from contextlib import suppress, ExitStack, contextmanager
from importlib.abc import MetaPathFinder, Loader
from importlib.machinery import ModuleSpec
from importlib.util import module_from_spec, find_spec
from inspect import getmembers, isclass, stack, getmodule
from itertools import accumulate, cycle
from pathlib import Path
from pkgutil import iter_modules
from unittest.mock import patch
from zipfile import ZipFile
from zipimport import zipimporter

from yt_dlp import YoutubeDL, utils as ytdlp_utils, main as ytdlp_main

__version__ = "2021.11.05.post5"
PACKAGE_NAME = __name__
_INITIALIZED = False
_FOUND = {}
_OVERRIDDEN = []


# pylint: disable=abstract-method
class PluginLoader(Loader):
    """Dummy loader for virtual namespace packages"""

    # pylint: disable=unused-argument, no-self-use
    def exec_module(self, module):
        return None


class PluginFinder(MetaPathFinder):
    """
    This class provides one or multiple namespace packages
    it searches in sys.path for the existing subdirectories
    from which the modules can be imported
    """

    def __init__(self, *packages):
        self.packages = set()
        self._zip_content_cache = {}

        for name in packages:
            self.packages.update(self.partition(name))

    @staticmethod
    def partition(name):
        yield from accumulate(name.split("."), lambda a, b: ".".join((a, b)))

    def zip_has_dir(self, archive, path):
        if archive not in self._zip_content_cache:
            with ZipFile(archive) as fd:
                self._zip_content_cache[archive] = [
                    Path(name) for name in fd.namelist()
                ]
        return any(path in file.parents for file in self._zip_content_cache[archive])

    def search_locations(self, fullname):
        parts = fullname.split(".")
        locations = []
        for path in map(Path, dict.fromkeys(sys.path).keys()):
            candidate = path.joinpath(*parts)
            if candidate.is_dir():
                locations.append(str(candidate))
            elif path.is_file() and path.suffix in {".zip", ".egg", ".whl"}:
                with suppress(FileNotFoundError):
                    if self.zip_has_dir(path, Path(*parts)):
                        locations.append(str(candidate))
        return locations

    def find_spec(self, fullname, _path=None, _target=None):
        if fullname not in self.packages:
            return None

        search_locations = self.search_locations(fullname)
        if not search_locations:
            return None

        spec = ModuleSpec(fullname, PluginLoader(), is_package=True)
        spec.submodule_search_locations = search_locations
        return spec

    def invalidate_caches(self):
        self._zip_content_cache.clear()
        for package in self.packages:
            if package in sys.modules:
                del sys.modules[package]


# pylint: disable=global-statement, protected-access
def initialize():
    global _INITIALIZED

    if not _INITIALIZED:
        sys.meta_path.insert(
            0,
            PluginFinder(f"{PACKAGE_NAME}.extractor", f"{PACKAGE_NAME}.postprocessor"),
        )
        _INITIALIZED = True


def directories():
    spec = find_spec(PACKAGE_NAME)
    return spec.submodule_search_locations if spec else []


def iter_plugin_modules(subpackage):
    fullname = f"{PACKAGE_NAME}.{subpackage}"
    with suppress(ModuleNotFoundError):
        pkg = importlib.import_module(fullname)
        yield from iter_modules(path=pkg.__path__, prefix=f"{fullname}.")


def detected_collisions(from_dict, to_dict):
    collisions = set(from_dict.keys()) & set(to_dict.keys())
    return [to_dict[key] for key in collisions]


# noinspection PyBroadException
def load_plugins(name, suffix, namespace=None):
    classes = {}
    namespace = namespace or {}

    def gen_predicate(package_name):
        def check_predicate(obj):
            return (
                isclass(obj)
                and obj.__name__.endswith(suffix)
                and obj.__module__.startswith(package_name)
            )

        return check_predicate

    for finder, module_name, _is_pkg in iter_plugin_modules(name):
        try:
            if isinstance(finder, zipimporter):
                module = finder.load_module(module_name)
            else:
                spec = finder.find_spec(module_name)
                module = module_from_spec(spec)
                spec.loader.exec_module(module)
        except Exception:  # pylint: disable=broad-except
            print(f"Error while importing module '{module_name}'", file=sys.stderr)
            traceback.print_exc(limit=-1)
            continue

        sys.modules[module_name] = module
        module_classes = dict(getmembers(module, gen_predicate(module_name)))

        _OVERRIDDEN.extend(detected_collisions(module_classes, classes))
        classes.update(module_classes)

    _OVERRIDDEN.extend(detected_collisions(classes, namespace))
    namespace.update(classes)

    return classes


def add_plugins():
    # pylint: disable=import-outside-toplevel
    from yt_dlp import (
        extractor,
        postprocessor,
    )

    ie_plugins = load_plugins("extractor", "IE", extractor.__dict__)
    _FOUND.update(ie_plugins)
    getattr(extractor, "_ALL_CLASSES", [])[:0] = ie_plugins.values()

    pp_plugins = load_plugins("postprocessor", "PP", postprocessor.__dict__)
    _FOUND.update(pp_plugins)


def monkey_patch(orig):
    def decorator(func):
        def decorated(*args, **kwargs):
            return func(*args, **kwargs)

        decorated.__original__ = orig
        return decorated

    return decorator


def tabify(items, join_string=" ", alignment="<"):
    tabs = tuple(map(lambda x: max(len(str(s)) for s in x), zip(*items)))
    for item in items:
        aligning = cycle(alignment)
        yield join_string.join(
            f"{part!s:{align}{width}}"
            for part, width, align in zip(item, tabs, aligning)
        )


def calling_plugin_class():
    plugins = set(_FOUND.values())
    for frame_info in stack():
        try:
            cls = frame_info[0].f_locals["self"].__class__
        except (KeyError, AttributeError):
            cls = None
        if cls in plugins:
            return cls
    return None


@monkey_patch(YoutubeDL.print_debug_header)
def plugin_debug_header(self):
    plugin_list = []
    for name, cls in _FOUND.items():
        module = getmodule(cls)
        version = getattr(cls, "__version__", None) or getattr(
            module, "__version__", None
        )
        version = f"(v{version})" if version else ""
        module_info = f"from {module.__name__!r}" if module else ""
        alt_name = getattr(cls(), "IE_NAME", name)
        plugin_list.append((f"[{alt_name}]", module_info, version))

    if plugin_list:
        plural_s = "s" if len(plugin_list) > 1 else ""
        self.write_debug(
            f"Loaded {len(plugin_list)} plugin{plural_s} which are not part of yt-dlp. "
            f"Use at your own risk."
        )
        for line in tabify(sorted(plugin_list), join_string=" "):
            self.write_debug(" " + line)
    if _OVERRIDDEN:
        self.write_debug("Overridden classes due to name collisions:")
        items = [
            (f"{cls.__name__!r}", f"from {cls.__module__!r}") for cls in _OVERRIDDEN
        ]
        for line in tabify(items):
            self.write_debug(" " + line)

    return plugin_debug_header.__original__(self)


@monkey_patch(ytdlp_utils.bug_reports_message)
def bug_reports_message(*args, **kwargs):
    cls = calling_plugin_class()
    if cls is None:
        return bug_reports_message.__original__(*args, **kwargs)
    with suppress(AttributeError):
        return "; " + cls().BUG_REPORT
    return ""


_PATCHES = (
    patch("yt_dlp.YoutubeDL.print_debug_header", plugin_debug_header),
    patch("yt_dlp.utils.bug_reports_message", bug_reports_message),
)


def patch_decorator(func):
    for _patch in _PATCHES:
        func = _patch(func)
    return func


@contextmanager
def patch_context():
    _stack = ExitStack()
    try:
        yield [_stack.enter_context(ctx) for ctx in _PATCHES]
    finally:
        _stack.close()


@patch_decorator
def main(argv=None):
    initialize()
    add_plugins()
    ytdlp_main(argv=argv)
