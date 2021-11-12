#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import os
import re
import sys
from inspect import getfile
from pathlib import Path
from unittest import TestCase

from yt_dlp.utils import preferredencoding, write_string

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

    for key in ("_TEST", "_TESTS"):
        if key in cls.__dict__:
            break
    else:
        return

    test_cases = cls.__dict__[key]
    if isinstance(test_cases, dict):
        test_cases = [test_cases]
    for test_case in test_cases:
        test_case["name"] = cls.__name__[:-2]
        test_case["cls"] = cls
        yield test_case


def get_testcases():
    initialize()
    add_plugins()
    project_plugins = Path.cwd() / "ytdlp_plugins"

    for name, cls in FOUND.items():
        if not name.endswith("IE"):
            continue
        module_file = Path(getfile(cls))
        if project_plugins.is_dir() and project_plugins != module_file.parents[1]:
            continue
        yield from get_class_testcases(cls)


class DownloadTestcase(TestCase):
    def expect_value(self, got, expected, field):
        if isinstance(expected, str) and expected.startswith("re:"):
            match_str = expected[len("re:") :]
            match_rex = re.compile(match_str)

            self.assertTrue(
                isinstance(got, str),
                f"Expected a {str.__name__} object, "
                f"but got {type(got).__name__} for field {field}",
            )
            self.assertTrue(
                match_rex.match(got),
                f"field {field} (value: {got!r}) should match {match_str!r}",
            )
        elif isinstance(expected, str) and expected.startswith("startswith:"):
            start_str = expected[len("startswith:") :]
            self.assertTrue(
                isinstance(got, str),
                f"Expected a {str.__name__} object, "
                f"but got {type(got).__name__} for field {field}",
            )
            self.assertTrue(
                got.startswith(start_str),
                f"field {field} (value: {got!r}) should start with {start_str!r}",
            )
        elif isinstance(expected, str) and expected.startswith("contains:"):
            contains_str = expected[len("contains:") :]
            self.assertTrue(
                isinstance(got, str),
                f"Expected a {str.__name__} object, "
                f"but got {type(got).__name__} for field {field}",
            )
            self.assertTrue(
                contains_str in got,
                f"field {field} (value: {got!r}) should contain {contains_str!r}",
            )
        elif isinstance(expected, type):
            self.assertTrue(
                isinstance(got, expected),
                f"Expected type {expected!r} for field {field}, "
                f"but got value {got!r} of type {type(got)!r}",
            )
        elif isinstance(expected, dict) and isinstance(got, dict):
            self.expect_dict(got, expected)
        elif isinstance(expected, list) and isinstance(got, list):
            self.assertEqual(
                len(expected),
                len(got),
                f"Expect a list of length {len(expected):d}, "
                f"but got a list of length {len(got):d} for field {field}",
            )
            for index, (item_got, item_expected) in enumerate(zip(got, expected)):
                type_got = type(item_got)
                type_expected = type(item_expected)
                self.assertEqual(
                    type_expected,
                    type_got,
                    f"Type mismatch for list item at index {index:d} for field {field}, "
                    f"expected {type_expected!r}, got {type_got!r}",
                )
                self.expect_value(item_got, item_expected, field)
        else:
            if isinstance(expected, str) and expected.startswith("md5:"):
                self.assertTrue(
                    isinstance(got, str),
                    f"Expected field {field} to be a unicode object, "
                    f"but got value {got!r} of type {type(got)!r}",
                )
                got = "md5:" + md5(got)
            elif isinstance(expected, str) and re.match(
                r"^(?:min|max)?count:\d+", expected
            ):
                self.assertTrue(
                    isinstance(got, (list, dict)),
                    f"Expected field {field} to be a list or a dict, "
                    f"but it is of type {type(got).__name__}",
                )
                operation, _, expected_num = expected.partition(":")
                expected_num = int(expected_num)
                if operation == "mincount":
                    assert_func = self.assertGreaterEqual
                    msg_tmpl = "Expected {} items in field {}, but only got {}"
                elif operation == "maxcount":
                    assert_func = self.assertLessEqual
                    msg_tmpl = "Expected maximum {} items in field {}, but got {}"
                elif operation == "count":
                    assert_func = self.assertEqual
                    msg_tmpl = "Expected exactly {} items in field {}, but got {}"
                else:
                    assert False
                assert_func(
                    len(got),
                    expected_num,
                    msg_tmpl.format(expected_num, field, len(got)),
                )
                return
            self.assertEqual(
                expected,
                got,
                f"Invalid value for field {field}, expected {expected!r}, got {got!r}",
            )

    def expect_dict(self, got_dict, expected_dict):
        self.assertTrue(isinstance(got_dict, dict))
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
            for key in mandatory_fields:
                self.assertTrue(got_dict.get(key), f"Missing mandatory field {key}")
        # Check for mandatory fields that are automatically set by YoutubeDL
        for key in ["webpage_url", "extractor", "extractor_key"]:
            self.assertTrue(got_dict.get(key), f"Missing field: {key}")

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
        self.assertFalse(
            missing_keys,
            f"Missing keys in test definition: {', '.join(sorted(missing_keys))}",
        )

    def assertGreaterEqual(self, a, b, msg=None):
        if not a >= b:
            if msg is None:
                msg = f"{a!r} not greater than or equal to {b!r}"
            self.assertTrue(a >= b, msg)

    def assertLessEqual(self, a, b, msg=None):
        if not a <= b:
            if msg is None:
                msg = f"{a!r} not less than or equal to {b!r}"
            self.assertTrue(a <= b, msg)

    def assertEqual(self, first, second, msg=None):
        if not first == second:
            if msg is None:
                msg = f"{first!r} not equal to {second!r}"
            self.assertTrue(first == second, msg)


def expect_warnings(ydl, warnings_re):
    real_warning = ydl.report_warning

    def _report_warning(msg):
        if not any(re.search(w_re, msg) for w_re in warnings_re):
            real_warning(msg)

    ydl.report_warning = _report_warning
