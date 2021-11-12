#!/usr/bin/env python
# -*- coding: UTF-8 -*-
from contextlib import suppress
from importlib import import_module


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
