#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import hashlib
import json
import re
from contextlib import suppress
from importlib import import_module
from itertools import cycle
from pathlib import Path
from typing import Dict, Optional, Union
from urllib.parse import parse_qsl, urlparse


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


def md5(data: Union[Path, str]) -> str:
    if isinstance(data, Path):
        return hashlib.md5(data.read_bytes()).hexdigest()
    return hashlib.md5(data.encode("utf-8")).hexdigest()


class ParsedURL:
    """
    This class provides a unified interface for urlparse(),
    parse_qsl() and regular expression groups
    """

    def __init__(self, url: str, *, regex: Optional[str] = None):
        self._parts = parts = urlparse(url)
        self._query: Dict[str, str] = dict(parse_qsl(parts.query))
        self._match = re.match(regex, url) if regex else None

    def __getattr__(self, item):
        """
        forward the attributes from urlparse.ParsedResult
        thus providing scheme, netloc, url, params, fragment

        note that .query is shadowed by a different method
        """
        return getattr(self._parts, item)

    def query(self, key=None, default=None):
        if key is None:
            return dict(self._query)

        return self._query.get(key, default)

    def match(self, key=None):
        if self._match is None:
            return None

        if key is None:
            return self._match.groupdict()

        return self._match.group(key)
