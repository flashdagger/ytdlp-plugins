#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import json
from contextlib import suppress
from importlib import import_module
from itertools import cycle


def estimate_filesize(formats, duration):
    if not (formats and duration):
        return

    for item in formats:
        if any(map(item.get, ("filesize", "filesize_approx", "fs_approx"))):
            continue
        tbr = item.get("tbr")
        if tbr:
            item["filesize_approx"] = 128 * tbr * duration


def unlazify(cls: type) -> type:
    """if extractor class is lazy type, return the actual class"""
    with suppress(AttributeError, ImportError):
        actual_module = getattr(cls, "_module")
        module = import_module(actual_module)
        cls = getattr(module, cls.__name__)
    return cls


def tabify(items, join_string=" ", alignment="<"):
    tabs = tuple(map(lambda x: max(len(str(s)) for s in x), zip(*items)))
    for item in items:
        aligning = cycle(alignment)
        yield join_string.join(
            f"{part!s:{align}{width}}"
            for part, width, align in zip(item, tabs, aligning)
        )


def write_json_file(obj, file):
    with open(file, "w", encoding="utf-8") as fd:
        json.dump(obj, fd, indent=4)
