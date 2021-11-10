#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import hashlib
import io
import json
import re
import sys
import types
from pathlib import Path
from typing import Union
from unittest import TestCase

from yt_dlp import YoutubeDL
from yt_dlp.compat import (
    compat_os_name,
    compat_str,
)
from yt_dlp.utils import (
    preferredencoding,
    write_string,
)

SELF_PATH = Path(__file__)
PARAMETERS_FILE = SELF_PATH.with_name("parameters.json")
LOCAL_PARAMETERS_FILE = SELF_PATH.with_name("local_parameters.json")


def get_params(override=None):
    with io.open(PARAMETERS_FILE, encoding="utf-8") as pf:
        parameters = json.load(pf)
    if LOCAL_PARAMETERS_FILE.exists():
        with io.open(LOCAL_PARAMETERS_FILE, encoding="utf-8") as pf:
            parameters.update(json.load(pf))
    if override:
        parameters.update(override)
    return parameters


def report_warning(message):
    """
    Print the message to stderr, it will be prefixed with 'WARNING:'
    If stderr is a tty file the 'WARNING:' will be colored
    """
    if sys.stderr.isatty() and compat_os_name != "nt":
        _msg_header = "\033[0;33mWARNING:\033[0m"
    else:
        _msg_header = "WARNING:"
    output = f"{_msg_header} {message}\n"
    if "b" in getattr(sys.stderr, "mode", "") or sys.version_info[0] < 3:
        output = output.encode(preferredencoding())
    sys.stderr.write(output)


class FakeYDL(YoutubeDL):
    def __init__(self, override=None):
        # Different instances of the downloader can't share the same dictionary
        # some test set the "sublang" parameter, which would break the md5 checks.
        params = get_params(override=override)
        super(FakeYDL, self).__init__(params, auto_init=False)
        self.result = []

    def to_screen(self, s, skip_eol=None):
        print(s)

    def trouble(self, message=None, tb=None):
        raise Exception(message)

    def download(self, x):
        self.result.append(x)

    def expect_warning(self, regex):
        # Silence an expected warning matching a regex
        old_report_warning = self.report_warning

        def report_warning(_self, message):
            if re.match(regex, message):
                return
            old_report_warning(message)

        self.report_warning = types.MethodType(report_warning, self)


def gettestcases():
    from inspect import getfile
    from . import initialize, add_plugins, _FOUND

    initialize()
    add_plugins()
    project_plugins = Path.cwd() / "ytdlp_plugins"

    for name, klass in _FOUND.items():
        if not name.endswith("IE"):
            continue
        module_file = Path(getfile(klass))
        if project_plugins.is_dir() and project_plugins != module_file.parents[1]:
            continue
        ie = klass()
        for tc in ie.get_testcases(include_onlymatching=True):
            tc["cls"] = klass
            yield tc


def md5(data: Union[Path, str]) -> str:
    if isinstance(data, Path):
        return hashlib.md5(data.read_bytes()).hexdigest()
    return hashlib.md5(data.encode("utf-8")).hexdigest()


class DownloadTestcase(TestCase):
    def expect_value(self, got, expected, field):
        if isinstance(expected, compat_str) and expected.startswith("re:"):
            match_str = expected[len("re:") :]
            match_rex = re.compile(match_str)

            self.assertTrue(
                isinstance(got, compat_str),
                f"Expected a {compat_str.__name__} object, "
                f"but got {type(got).__name__} for field {field}",
            )
            self.assertTrue(
                match_rex.match(got),
                f"field {field} (value: {got!r}) should match {match_str!r}",
            )
        elif isinstance(expected, compat_str) and expected.startswith("startswith:"):
            start_str = expected[len("startswith:") :]
            self.assertTrue(
                isinstance(got, compat_str),
                f"Expected a {compat_str.__name__} object, "
                f"but got {type(got).__name__} for field {field}",
            )
            self.assertTrue(
                got.startswith(start_str),
                f"field {field} (value: {got!r}) should start with {start_str!r}",
            )
        elif isinstance(expected, compat_str) and expected.startswith("contains:"):
            contains_str = expected[len("contains:") :]
            self.assertTrue(
                isinstance(got, compat_str),
                f"Expected a {compat_str.__name__} object, "
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
            if isinstance(expected, compat_str) and expected.startswith("md5:"):
                self.assertTrue(
                    isinstance(got, compat_str),
                    f"Expected field {field} to be a unicode object, "
                    f"but got value {got!r} of type {type(got)!r}",
                )
                got = "md5:" + md5(got)
            elif isinstance(expected, compat_str) and re.match(
                r"^(?:min|max)?count:\d+", expected
            ):
                self.assertTrue(
                    isinstance(got, (list, dict)),
                    f"Expected field {field} to be a list or a dict, "
                    f"but it is of type {type(got).__name__}",
                )
                op, _, expected_num = expected.partition(":")
                expected_num = int(expected_num)
                if op == "mincount":
                    assert_func = self.assertGreaterEqual
                    msg_tmpl = "Expected {} items in field {}, but only got {}"
                elif op == "maxcount":
                    assert_func = self.assertLessEqual
                    msg_tmpl = "Expected maximum {} items in field {}, but got {}"
                elif op == "count":
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
                if not isinstance(value, compat_str) or len(value) < 250
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
        if missing_keys:

            def _repr(v):
                if isinstance(v, compat_str):
                    return "{!r}".format(
                        v.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")
                    )
                else:
                    return repr(v)

            info_dict_str = ""
            if len(missing_keys) != len(expected_dict):
                info_dict_str += "".join(
                    "    {}: {},\n".format(_repr(k), _repr(v))
                    for k, v in test_info_dict.items()
                    if k not in missing_keys
                )

                if info_dict_str:
                    info_dict_str += "\n"
            info_dict_str += "".join(
                "    {}: {},\n".format(_repr(k), _repr(test_info_dict[k]))
                for k in missing_keys
            )
            write_string("\n'info_dict': {\n" + info_dict_str + "},\n", out=sys.stderr)
            self.assertFalse(
                missing_keys,
                "Missing keys in test definition: {}".format(
                    ", ".join(sorted(missing_keys))
                ),
            )

    def assertGreaterEqual(self, got, expected, msg=None):
        if not (got >= expected):
            if msg is None:
                msg = f"{got!r} not greater than or equal to {expected!r}"
            self.assertTrue(got >= expected, msg)

    def assertLessEqual(self, got, expected, msg=None):
        if not (got <= expected):
            if msg is None:
                msg = f"{got!r} not less than or equal to {expected!r}"
            self.assertTrue(got <= expected, msg)

    def assertEqual(self, got, expected, msg=None):
        if not (got == expected):
            if msg is None:
                msg = f"{got!r} not equal to {expected!r}"
            self.assertTrue(got == expected, msg)


def expect_warnings(ydl, warnings_re):
    real_warning = ydl.report_warning

    def _report_warning(w):
        if not any(re.search(w_re, w) for w_re in warnings_re):
            real_warning(w)

    ydl.report_warning = _report_warning
