#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import os
import re
import sys
import warnings
from inspect import getfile
from pathlib import Path
from typing import Any, Dict
from unittest import TestCase

from yt_dlp.extractor.common import InfoExtractor
from yt_dlp.utils import preferredencoding, write_string
from yt_dlp.extractor import gen_extractor_classes
from ytdlp_plugins import initialize, add_plugins, FOUND
from .utils import md5, unlazify

DEFAULT_PARAMS = {
    "allsubtitles": False,
    "check_formats": False,
    "consoletitle": False,
    "continuedl": True,
    "fixup": "never",
    "force_write_download_archive": False,
    "forcedescription": False,
    "forcefilename": False,
    "forceformat": False,
    "forcethumbnail": False,
    "forcetitle": False,
    "forceurl": False,
    "format": "best",
    "ignoreerrors": False,
    "listformats": None,
    "listsubtitles": False,
    "logtostderr": False,
    "matchtitle": None,
    "max_downloads": None,
    "nocheckcertificate": True,
    "nopart": False,
    "noprogress": False,
    "outtmpl": "%(id)s.%(ext)s",
    "overwrites": None,
    "password": None,
    "playliststart": 1,
    "prefer_free_formats": False,
    "quiet": False,
    "ratelimit": None,
    "rejecttitle": None,
    "retries": 10,
    "simulate": False,
    "socket_timeout": 20,
    "subtitlesformat": "best",
    "subtitleslang": None,
    "test": True,
    "updatetime": True,
    "usenetrc": False,
    "username": None,
    "verbose": True,
    "writeannotations": False,
    "writedescription": False,
    "writedesktoplink": False,
    "writeinfojson": True,
    "writelink": False,
    "writesubtitles": False,
    "writeurllink": False,
    "writewebloclink": False,
}


def get_params(override=None):
    parameters = dict(DEFAULT_PARAMS)
    if override:
        parameters.update(override)
    return parameters


def report_warning(message):
    """
    Print the message to stderr, it will be prefixed with 'WARNING:'
    If stderr is a tty file the 'WARNING:' will be colored
    """
    if sys.stderr.isatty() and os.name != "nt":
        _msg_header = "\033[0;33mWARNING:\033[0m"
    else:
        _msg_header = "WARNING:"
    output = f"{_msg_header} {message}\n"
    if "b" in getattr(sys.stderr, "mode", "") or sys.version_info[0] < 3:
        output = output.encode(preferredencoding())
    sys.stderr.write(output)


def get_class_testcases(cls):
    cls = unlazify(cls)
    if not issubclass(cls, InfoExtractor):
        return

    for key in ("_TEST", "_TESTS"):
        if key in cls.__dict__:
            break
    else:
        return

    test_cases = cls.__dict__[key]
    if isinstance(test_cases, dict):
        test_cases = [test_cases]
    if not isinstance(test_cases, (list, tuple)):
        if test_cases is not None:
            warnings.warn(f"{cls}: _TEST is {type(test_cases)}", UserWarning)
        return
    for test_case in test_cases:
        test_case["name"] = cls.__name__[:-2]
        test_case["cls"] = cls
        yield test_case


def get_testcases():
    initialize()
    add_plugins()
    project_plugins = Path.cwd() / "ytdlp_plugins"
    if "--all" in sys.argv:
        test_classes = gen_extractor_classes()
        filter_local = False
    else:
        test_classes = FOUND.values()
        filter_local = True

    for cls in test_classes:
        module_file = Path(getfile(cls))
        if (
            filter_local
            and project_plugins.is_dir()
            and project_plugins != module_file.parents[1]
        ):
            continue
        yield from get_class_testcases(cls)


class DownloadTestcase(TestCase):
    def assert_field_is_valid(self, expr: bool, field: str, msg: str) -> None:
        if not expr:
            msg = self._formatMessage(msg, f"Mismatch in field {field!r}")
            raise self.failureException(msg)

    def assert_field_is_present(self, expr: Any, *fields: str) -> None:
        if isinstance(expr, dict):
            fields = tuple(field for field in fields if not bool(expr.get(field)))
            expr = not bool(fields)

        if not expr:
            fields_str = ", ".join((repr(field) for field in fields))
            msg = f"Missing field {fields_str}"
            raise self.failureException(msg)

    def expect_value(self, got, expected, field):
        if isinstance(expected, str):
            self.expect_string(got, expected, field)
        elif isinstance(expected, type):
            self.assert_field_is_valid(
                isinstance(got, expected),
                field,
                f"expected type {expected!r}, "
                f"but got value {got!r} of type {type(got)!r}",
            )
        elif isinstance(expected, dict) and isinstance(got, dict):
            self.expect_dict(got, expected)
        elif isinstance(expected, list) and isinstance(got, list):
            self.assert_field_is_valid(
                len(expected) == len(got),
                field,
                f"expected a list of length {len(expected):d}, "
                f"but got a list of length {len(got):d} for field {field}",
            )
            for index, (item_got, item_expected) in enumerate(zip(got, expected)):
                type_got = type(item_got)
                type_expected = type(item_expected)
                field_name = f"{field}[{index}]"
                self.assert_field_is_valid(
                    type_expected == type_got,
                    field_name,
                    f"expected type {type_expected!r}, got {type_got!r}",
                )
                self.expect_value(item_got, item_expected, field_name)
        else:
            self.expect_field(got, expected, field)

    def expect_field(self, got: Any, expected: Any, field: str):
        self.assert_field_is_valid(
            expected == got,
            field,
            f"expected {expected!r}, got {got!r}",
        )

    def expect_string(self, got: Any, expected: str, field: str):
        if expected.startswith("re:"):
            match_str = expected[len("re:") :]
            match_rex = re.compile(match_str)

            self.assert_field_is_valid(
                isinstance(got, str),
                field,
                f"expected a {str.__name__} object, " f"but got {type(got).__name__}",
            )
            self.assert_field_is_valid(
                bool(match_rex.match(got)),
                field,
                f"{got!r}) should match {match_str!r}",
            )
        elif expected.startswith("startswith:"):
            start_str = expected[len("startswith:") :]
            self.assert_field_is_valid(
                isinstance(got, str),
                field,
                f"expected a {str.__name__} object, " f"but got {type(got).__name__}",
            )
            self.assert_field_is_valid(
                got.startswith(start_str),
                field,
                f"{got!r} should start with {start_str!r}",
            )
        elif expected.startswith("contains:"):
            contains_str = expected[len("contains:") :]
            self.assert_field_is_valid(
                isinstance(got, str),
                field,
                f"expected a {str.__name__} object, " f"but got {type(got).__name__}",
            )
            self.assert_field_is_valid(
                contains_str in got,
                field,
                f"{got!r} should contain {contains_str!r}",
            )
        elif expected.startswith("md5:"):
            self.assert_field_is_valid(
                isinstance(got, str),
                field,
                f"expected a string object, "
                f"but got value {got!r} of type {type(got)!r}",
            )
            self.expect_field("md5:" + md5(got), expected, field)
        elif re.match(r"^(?:min|max)?count:\d+", expected):
            self.assert_field_is_valid(
                isinstance(got, (list, dict)),
                field,
                f"expected a list or a dict, "
                f"but value is of type {type(got).__name__}",
            )
            operation, expected_num = expected.split(":")
            expected_int = int(expected_num)
            if operation == "mincount":
                assert_func = lambda a, b: a >= b
                msg_tmpl = "expected at least {} items, but only got {}"
            elif operation == "maxcount":
                assert_func = lambda a, b: a <= b
                msg_tmpl = "expected not more than {} items, but got {}"
            elif operation == "count":
                assert_func = lambda a, b: a == b
                msg_tmpl = "expected exactly {} items, but got {}"
            else:
                raise Exception("Should not happen")
            self.assert_field_is_valid(
                assert_func(len(got), expected_int),
                field,
                msg_tmpl.format(expected_int, len(got)),
            )
        else:
            self.expect_field(got, expected, field)

    def expect_dict(self, got_dict, expected_dict: Dict[str, Any]):
        self.assertIsInstance(got_dict, dict)
        for info_field, expected in expected_dict.items():
            got = got_dict.get(info_field)
            self.expect_value(got, expected, info_field)

    def expect_info_dict(self, got_dict, expected_dict):
        self.expect_dict(got_dict, expected_dict)
        # Check for the presence of mandatory fields
        if got_dict.get("_type") not in ("playlist", "multi_video"):
            mandatory_fields = ["id", "title"]
            if expected_dict.get("ext"):
                mandatory_fields.extend(("url", "ext"))
            self.assert_field_is_present(got_dict, *mandatory_fields)
        # Check for mandatory fields that are automatically set by YoutubeDL
        self.assert_field_is_present(
            got_dict, *("webpage_url", "extractor", "extractor_key")
        )

        # Are checkable fields missing from the test case definition?
        test_info_dict = dict(
            (
                key,
                value
                if not isinstance(value, str) or len(value) < 250
                else "md5:" + md5(value),
            )
            for key, value in got_dict.items()
            if value
            and key
            in (
                "id",
                "title",
                "description",
                "uploader",
                "upload_date",
                "timestamp",
                "uploader_id",
                "location",
                "age_limit",
            )
        )
        missing_keys = set(test_info_dict.keys()) - set(expected_dict.keys())
        if not missing_keys:
            return
        info_dict_str = ""
        if len(missing_keys) != len(expected_dict):
            info_dict_str += "".join(
                f"    {k!r}: {v!r},\n"
                for k, v in test_info_dict.items()
                if k not in missing_keys
            )

            if info_dict_str:
                info_dict_str += "\n"
        info_dict_str += "".join(
            f"    {k!r}: {test_info_dict[k]!r},\n" for k in missing_keys
        )
        write_string("\n'info_dict': {\n" + info_dict_str + "},\n", out=sys.stderr)
        self.assert_field_is_present(not missing_keys, *missing_keys)


def expect_warnings(ydl, warnings_re):
    real_warning = ydl.report_warning

    def _report_warning(msg):
        if not any(re.search(w_re, msg) for w_re in warnings_re):
            real_warning(msg)

    ydl.report_warning = _report_warning
