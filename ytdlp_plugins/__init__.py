#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import importlib
import re
import sys
import traceback
from contextlib import suppress
from importlib.abc import Loader, MetaPathFinder
from importlib.machinery import ModuleSpec, PathFinder
from importlib.util import find_spec, module_from_spec
from inspect import getmembers, isclass
from itertools import accumulate
from pathlib import Path
from pkgutil import iter_modules
from typing import Dict
from zipfile import ZipFile
from zipimport import zipimporter

from yt_dlp.extractor.common import InfoExtractor

__version__ = "2022.12.17"
PACKAGE_NAME = __name__


class GLOBALS:
    _INITIALIZED = False
    FOUND: Dict[str, InfoExtractor] = {}
    OVERRIDDEN: Dict[str, InfoExtractor] = {}
    SUBPACKAGES = (f"{PACKAGE_NAME}.extractor", f"{PACKAGE_NAME}.postprocessor")

    @classmethod
    def initialize(cls):
        if not cls._INITIALIZED:
            sys.meta_path.insert(
                0,
                PluginFinder(*cls.SUBPACKAGES),
            )
            cls._INITIALIZED = True

    @classmethod
    def reset(cls):
        # update sys.path_importer_cache
        importlib.invalidate_caches()
        for package in cls.SUBPACKAGES:
            if package in sys.modules:
                del sys.modules[package]
            PathFinder.find_spec(package)


# pylint: disable=abstract-method
class PluginLoader(Loader):
    """Dummy loader for virtual namespace packages"""

    # pylint: disable=unused-argument
    def exec_module(self, module):
        return None


class PluginFinder(MetaPathFinder):
    """
    This class provides one or multiple namespace packages
    it searches in 'sys.path' for the existing subdirectories
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

    def zip_ns_dir(self, archive, parts):
        cache = self._zip_content_cache.setdefault(archive, set())
        path = Path(*parts)
        if not cache:
            with suppress(OSError):
                with ZipFile(archive) as fd:
                    for name in fd.namelist():
                        cache.update(set(Path(name).parents))
        return (Path(archive, path),) if path in cache else ()

    def search_locations(self, fullname):
        parts = fullname.split(".")
        locations = []
        for importer in sys.path_importer_cache.values():
            if isinstance(importer, zipimporter):
                locations.extend(
                    self.zip_ns_dir(Path(importer.archive).absolute(), parts)
                )
            elif hasattr(importer, "find_spec"):
                spec = importer.find_spec(fullname)
                path = Path(getattr(importer, "path", "."), *fullname.split("."))
                if spec is None and path.is_absolute() and path.is_dir():
                    locations.append(path)
                elif spec and spec.origin is None:
                    locations.extend(
                        Path(loc) for loc in spec.submodule_search_locations
                    )
        return [str(path) for path in dict.fromkeys(locations)]

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


def directories():
    spec = find_spec(PACKAGE_NAME)
    return spec.submodule_search_locations if spec else []


def iter_plugin_modules(fullname):
    with suppress(ModuleNotFoundError):
        pkg = importlib.import_module(fullname)
        yield from iter_modules(path=pkg.__path__, prefix=f"{fullname}.")


def detected_collisions(from_dict, to_dict):
    collisions = set(from_dict.keys()) & set(to_dict.keys())
    return {
        key: to_dict[key] for key in collisions if from_dict[key] is not to_dict[key]
    }


# noinspection PyBroadException
def load_plugins(fullname, suffix, namespace=None):
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

    for finder, module_name, _is_pkg in iter_plugin_modules(fullname):
        if re.match(r"^(\w+\.)*_", module_name):
            continue
        try:
            try:
                spec = finder.find_spec(module_name)
                module = module_from_spec(spec)
                spec.loader.exec_module(module)
            except AttributeError:
                # zipimporter instances have .find_spec() for python >= 3.10
                module = finder.load_module(module_name)
        except Exception:  # pylint: disable=broad-except
            print(f"Error while importing module '{module_name}'", file=sys.stderr)
            traceback.print_exc(limit=-1)
            continue

        sys.modules[module_name] = module
        if hasattr(module, "__all__"):
            module_classes = {
                name: obj
                for name, obj in getmembers(module, gen_predicate(module_name))
                if name in getattr(module, "__all__")
            }
        else:
            module_classes = {
                name: obj
                for name, obj in getmembers(module, gen_predicate(module_name))
                if not name.startswith("_")
            }
        GLOBALS.OVERRIDDEN.update(detected_collisions(module_classes, classes))
        classes.update(module_classes)

    GLOBALS.OVERRIDDEN.update(detected_collisions(classes, namespace))
    namespace.update(classes)

    return classes


def add_plugins():
    # pylint: disable=import-outside-toplevel
    from yt_dlp import extractor, postprocessor

    GLOBALS.initialize()
    all_classes = getattr(extractor, "_ALL_CLASSES", [])
    extractor_map = extractor.__dict__
    extractor_map.update(
        {cls.__name__: cls for cls in all_classes if cls.__name__ not in extractor_map}
    )
    for key in GLOBALS.FOUND:
        if key in GLOBALS.OVERRIDDEN:
            extractor_map[key] = GLOBALS.OVERRIDDEN[key]
        elif key in extractor_map:
            del extractor_map[key]
    GLOBALS.FOUND.clear()
    GLOBALS.OVERRIDDEN.clear()

    ie_plugins = load_plugins(f"{PACKAGE_NAME}.extractor", "IE", extractor_map)
    GLOBALS.FOUND.update(ie_plugins)
    extractors = getattr(extractor, "extractors", None)
    if extractors is not None:
        extractors.__dict__.update(ie_plugins)

    for cls in GLOBALS.OVERRIDDEN.values():
        with suppress(ValueError):
            all_classes.remove(cls)
    all_classes[:0] = ie_plugins.values()

    pp_plugins = load_plugins(
        f"{PACKAGE_NAME}.postprocessor", "PP", postprocessor.__dict__
    )
    GLOBALS.FOUND.update(pp_plugins)
