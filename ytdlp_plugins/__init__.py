#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import importlib
import re
import sys
import traceback
from contextlib import suppress
from importlib.abc import MetaPathFinder, Loader
from importlib.machinery import ModuleSpec
from importlib.util import module_from_spec, find_spec
from inspect import getmembers, isclass
from itertools import accumulate
from pathlib import Path
from pkgutil import iter_modules
from typing import Dict
from zipfile import ZipFile
from zipimport import zipimporter

from yt_dlp.extractor.common import InfoExtractor

from .generic import GenericIE
from .utils import unlazify

__version__ = "2022.08.26"


_INITIALIZED = False
FOUND: Dict[str, InfoExtractor] = {}
OVERRIDDEN: Dict[str, InfoExtractor] = {}
PACKAGE_NAME = __name__


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
            with ZipFile(archive) as fd:
                for name in fd.namelist():
                    cache.update(set(Path(name).parents))
        return (str(Path(archive, path)),) if path in cache else ()

    def search_locations(self, fullname):
        parts = fullname.split(".")
        locations = []
        for name, importer in sys.path_importer_cache.items():
            if isinstance(importer, zipimporter):
                locations.extend(self.zip_ns_dir(importer.archive, parts))
            elif hasattr(importer, "find_spec"):
                spec = importer.find_spec(fullname)
                if spec and spec.origin is None:
                    locations.extend(spec.submodule_search_locations)
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


# pylint: disable=global-statement
def initialize():
    global _INITIALIZED

    if not _INITIALIZED:
        sys.meta_path.insert(
            0,
            PluginFinder(f"{PACKAGE_NAME}.extractor", f"{PACKAGE_NAME}.postprocessor"),
        )
        _INITIALIZED = True


def reset():
    importlib.invalidate_caches()  # reset the import caches


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
    return {
        key: to_dict[key] for key in collisions if from_dict[key] is not to_dict[key]
    }


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
        if re.match(r"^(\w+\.)*_", module_name):
            continue
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

        OVERRIDDEN.update(detected_collisions(module_classes, classes))
        classes.update(module_classes)

    OVERRIDDEN.update(detected_collisions(classes, namespace))
    namespace.update(classes)

    return classes


def add_plugins():
    # pylint: disable=import-outside-toplevel
    from yt_dlp import extractor, postprocessor

    all_classes = getattr(extractor, "_ALL_CLASSES", [])
    extractor_map = extractor.__dict__
    extractor_map.update(
        {cls.__name__: cls for cls in all_classes if cls.__name__ not in extractor_map}
    )
    for key in FOUND:
        if key in OVERRIDDEN:
            extractor_map[key] = OVERRIDDEN[key]
        elif key in extractor_map:
            del extractor_map[key]
    FOUND.clear()
    OVERRIDDEN.clear()

    ie_plugins = load_plugins("extractor", "IE", extractor_map)
    FOUND.update(ie_plugins)
    extractors = getattr(extractor, "extractors", None)
    if extractors is not None:
        extractors.__dict__.update(ie_plugins)

    for cls in OVERRIDDEN.values():
        with suppress(ValueError):
            all_classes.remove(cls)
    all_classes[:0] = ie_plugins.values()

    GenericIE.OTHER_EXTRACTORS.extend(FOUND.values())
    last_extractor = unlazify(all_classes[-1])
    if issubclass(GenericIE, last_extractor):
        setattr(extractor, last_extractor.__name__, GenericIE)
        all_classes[-1] = GenericIE
        if extractors:  # pylint: disable=using-constant-test
            extractors.GenericIE = GenericIE

    pp_plugins = load_plugins("postprocessor", "PP", postprocessor.__dict__)
    FOUND.update(pp_plugins)
